"""Tests for obabot.voyager.extractor — FSM model extraction from handlers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List, Optional
from unittest.mock import MagicMock

import pytest

from obabot.voyager.extractor import (
    DEFAULT_STATE,
    _analyze_handler_body,
    _classify_filters,
    _collect_handlers,
    _build_model_dict,
    _analyze_handler,
    _HandlerInfo,
    _Button,
    extract_fsm_model,
)


# ---------------------------------------------------------------------------
# Fake filter objects (mimic aiogram at runtime)
# ---------------------------------------------------------------------------

class FakeState:
    """Mimic aiogram State descriptor."""

    def __init__(self, state_str: str):
        self.state = state_str
        self.group = None


class FakeStateFilter:
    """Mimic aiogram StateFilter that wraps one or more State objects."""

    def __init__(self, *states: FakeState):
        self.states = states


class FakeCommand:
    """Mimic aiogram Command filter."""

    def __init__(self, *commands: str):
        self.commands = frozenset(commands)


class FakeCommandStart:
    """Mimic aiogram CommandStart filter."""
    pass


class FakeMagicFilter:
    """Mimic aiogram MagicFilter (F.data == 'xxx')."""

    def __init__(self, operations: list):
        self._operations = operations


class FakeGetAttribute:
    """Mimic MagicFilter GetAttribute operation."""

    def __init__(self, name: str):
        self.name = name


class FakeComparator:
    """Mimic MagicFilter Comparator operation."""

    def __init__(self, right: Any):
        self.right = right


# ---------------------------------------------------------------------------
# Test filter classification
# ---------------------------------------------------------------------------

class TestClassifyFilters:
    def test_command_start(self):
        filters = (FakeCommandStart(),)
        state, action = _classify_filters(filters, "message")
        assert state is None
        assert action == "command:/start"

    def test_command(self):
        filters = (FakeCommand("help"),)
        state, action = _classify_filters(filters, "message")
        assert state is None
        assert action == "command:/help"

    def test_state_filter(self):
        filters = (FakeState("Form:waiting_name"),)
        state, action = _classify_filters(filters, "message")
        assert state == "Form:waiting_name"
        assert action == "text:*"

    def test_state_filter_wrapper(self):
        inner = FakeState("Form:waiting_email")
        filters = (FakeStateFilter(inner),)
        state, action = _classify_filters(filters, "message")
        assert state == "Form:waiting_email"

    def test_magic_filter_callback_data(self):
        ops = [FakeGetAttribute("data"), FakeComparator("register")]
        filters = (FakeMagicFilter(ops),)
        state, action = _classify_filters(filters, "callback_query")
        assert state is None
        assert action == "callback:register"

    def test_magic_filter_text(self):
        ops = [FakeGetAttribute("text")]
        filters = (FakeMagicFilter(ops),)
        state, action = _classify_filters(filters, "message")
        assert state is None
        assert action == "text:*"

    def test_state_plus_no_action(self):
        """Message handler with only State filter → action should be text:*."""
        filters = (FakeState("Form:waiting_name"),)
        state, action = _classify_filters(filters, "message")
        assert state == "Form:waiting_name"
        assert action == "text:*"

    def test_callback_query_no_filter(self):
        state, action = _classify_filters((), "callback_query")
        assert action == "callback:*"

    def test_empty_message_filters(self):
        state, action = _classify_filters((), "message")
        assert state is None
        assert action is None


# ---------------------------------------------------------------------------
# Test AST analysis
# ---------------------------------------------------------------------------

class TestAnalyzeHandlerBody:

    def test_set_state(self):
        async def handler(message, state):
            await state.set_state(MyForm.waiting_name)
            await message.answer("Enter name:")

        targets, clears, buttons, text = _analyze_handler_body(handler)
        assert targets == ["MyForm:waiting_name"]
        assert not clears
        assert text == "Enter name:"

    def test_state_clear(self):
        async def handler(message, state):
            await state.clear()
            await message.answer("Done!")

        targets, clears, buttons, text = _analyze_handler_body(handler)
        assert targets == []
        assert clears is True
        assert text == "Done!"

    def test_inline_keyboard(self):
        async def handler(message):
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="Option A", callback_data="opt_a"),
                    InlineKeyboardButton(text="Option B", callback_data="opt_b"),
                ],
                [
                    InlineKeyboardButton(text="Help", callback_data="help"),
                ],
            ])
            await message.answer("Choose:", reply_markup=keyboard)

        targets, clears, buttons, text = _analyze_handler_body(handler)
        assert len(buttons) == 2
        assert len(buttons[0]) == 2
        assert len(buttons[1]) == 1
        assert buttons[0][0].text == "Option A"
        assert buttons[0][0].data == "opt_a"
        assert buttons[1][0].data == "help"
        assert text == "Choose:"

    def test_fstring_text(self):
        async def handler(message):
            name = "World"
            await message.answer(f"Hello, {name}!")

        targets, clears, buttons, text = _analyze_handler_body(handler)
        assert text is not None
        assert "Hello, " in text

    def test_callback_message_answer(self):
        async def handler(callback, state):
            await state.set_state(Form.waiting)
            await callback.message.answer("Please enter data:")
            await callback.answer()

        targets, clears, buttons, text = _analyze_handler_body(handler)
        assert targets == ["Form:waiting"]
        assert text == "Please enter data:"

    def test_multiple_set_states(self):
        async def handler(message, state):
            if condition:
                await state.set_state(Form.step_a)
                await message.answer("Path A")
            else:
                await state.set_state(Form.step_b)
                await message.answer("Path B")

        targets, clears, buttons, text = _analyze_handler_body(handler)
        assert "Form:step_a" in targets
        assert "Form:step_b" in targets

    def test_no_fsm_handler(self):
        async def handler(message):
            await message.answer("Echo")

        targets, clears, buttons, text = _analyze_handler_body(handler)
        assert targets == []
        assert not clears
        assert text == "Echo"


# ---------------------------------------------------------------------------
# Test model building
# ---------------------------------------------------------------------------

class TestBuildModelDict:

    def _make_info(self, **kwargs) -> _HandlerInfo:
        defaults = dict(
            name="test_handler",
            handler_type="message",
            from_state=None,
            action=None,
            target_states=[],
            clears_state=False,
            buttons=[],
            message_text=None,
        )
        defaults.update(kwargs)
        return _HandlerInfo(**defaults)

    def test_simple_command_handler(self):
        handlers = [
            self._make_info(
                name="cmd_start",
                action="command:/start",
                message_text="Welcome!",
                buttons=[[_Button("Go", "go")]],
            ),
        ]
        model = _build_model_dict(handlers, "Bot", DEFAULT_STATE)

        assert model["bot_name"] == "Bot"
        assert model["initial_state"] == DEFAULT_STATE
        assert DEFAULT_STATE in model["states"]
        assert len(model["transitions"]) == 1

        tr = model["transitions"][0]
        assert tr["from"] == DEFAULT_STATE
        assert tr["to"] == DEFAULT_STATE
        assert tr["action"] == "command:/start"

    def test_callback_cross_reference(self):
        """Callback handler should resolve from_state via button origin."""
        handlers = [
            self._make_info(
                name="cmd_start",
                action="command:/start",
                message_text="Welcome!",
                buttons=[[_Button("Register", "register")]],
            ),
            self._make_info(
                name="on_register",
                handler_type="callback_query",
                action="callback:register",
                target_states=["Form:waiting_name"],
                message_text="Enter name:",
            ),
        ]
        model = _build_model_dict(handlers, "Bot", DEFAULT_STATE)

        register_tr = [
            t for t in model["transitions"] if t["action"] == "callback:register"
        ]
        assert len(register_tr) == 1
        assert register_tr[0]["from"] == DEFAULT_STATE
        assert register_tr[0]["to"] == "Form:waiting_name"

    def test_state_filtered_handler(self):
        handlers = [
            self._make_info(
                name="process_name",
                from_state="Form:waiting_name",
                action="text:*",
                target_states=["Form:waiting_email"],
                message_text="Enter email:",
            ),
        ]
        model = _build_model_dict(handlers, "Bot", DEFAULT_STATE)

        assert len(model["transitions"]) == 1
        tr = model["transitions"][0]
        assert tr["from"] == "Form:waiting_name"
        assert tr["to"] == "Form:waiting_email"
        assert tr["action"] == "text:*"

    def test_clear_state_goes_to_initial(self):
        handlers = [
            self._make_info(
                name="process_phone",
                from_state="Form:waiting_phone",
                action="text:*",
                clears_state=True,
                message_text="Registration complete!",
            ),
        ]
        model = _build_model_dict(handlers, "Bot", DEFAULT_STATE)

        tr = model["transitions"][0]
        assert tr["to"] == DEFAULT_STATE

    def test_all_states_created(self):
        handlers = [
            self._make_info(
                name="cmd_start",
                action="command:/start",
                message_text="Welcome!",
            ),
            self._make_info(
                name="process_name",
                from_state="Form:waiting_name",
                action="text:*",
                target_states=["Form:waiting_email"],
            ),
        ]
        model = _build_model_dict(handlers, "Bot", DEFAULT_STATE)

        state_ids = set(model["states"].keys())
        assert DEFAULT_STATE in state_ids
        assert "Form:waiting_name" in state_ids
        assert "Form:waiting_email" in state_ids

    def test_deduplicates_transitions(self):
        handlers = [
            self._make_info(name="h1", action="command:/start"),
            self._make_info(name="h2", action="command:/start"),
        ]
        model = _build_model_dict(handlers, "Bot", DEFAULT_STATE)
        assert len(model["transitions"]) == 1

    def test_button_label_on_transition(self):
        handlers = [
            self._make_info(
                name="cmd_start",
                action="command:/start",
                buttons=[[_Button("Help", "help_btn")]],
            ),
            self._make_info(
                name="on_help",
                handler_type="callback_query",
                action="callback:help_btn",
                message_text="Help text",
            ),
        ]
        model = _build_model_dict(handlers, "Bot", DEFAULT_STATE)

        help_tr = [
            t for t in model["transitions"] if t["action"] == "callback:help_btn"
        ]
        assert len(help_tr) == 1
        assert help_tr[0].get("label") == "Help"

    def test_state_text_and_buttons_preserved(self):
        handlers = [
            self._make_info(
                name="cmd_start",
                action="command:/start",
                message_text="Welcome!",
                buttons=[
                    [_Button("A", "a"), _Button("B", "b")],
                    [_Button("C", "c")],
                ],
            ),
        ]
        model = _build_model_dict(handlers, "Bot", DEFAULT_STATE)

        state = model["states"][DEFAULT_STATE]
        assert state["text"] == "Welcome!"
        assert len(state["buttons"]) == 2
        assert len(state["buttons"][0]) == 2
        assert state["buttons"][0][0]["text"] == "A"
        assert state["buttons"][1][0]["data"] == "c"


# ---------------------------------------------------------------------------
# Test end-to-end extract_fsm_model with a fake ProxyRouter
# ---------------------------------------------------------------------------

class FakeProxyRouter:
    """Minimal mock of ProxyRouter with _pending_handlers."""

    def __init__(self):
        self._pending_handlers = []

    def add(self, handler_type: str, filters: tuple, handler):
        self._pending_handlers.append((handler_type, filters, {}, handler))


class TestExtractFSMModel:

    def _build_router_with_example_handlers(self) -> FakeProxyRouter:
        router = FakeProxyRouter()

        # @router.message(Command("start"))
        async def cmd_start(message):
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="Register", callback_data="register"),
                    InlineKeyboardButton(text="Info", callback_data="info"),
                ],
            ])
            await message.answer("Welcome!", reply_markup=keyboard)

        router.add("message", (FakeCommand("start"),), cmd_start)

        # @router.callback_query(F.data == "register")
        async def on_register(callback, state):
            await state.set_state(RegistrationForm.waiting_name)
            await callback.message.answer("Enter your name:")
            await callback.answer()

        router.add(
            "callback_query",
            (FakeMagicFilter([FakeGetAttribute("data"), FakeComparator("register")]),),
            on_register,
        )

        # @router.callback_query(F.data == "info")
        async def on_info(callback):
            await callback.message.answer("Info page")
            await callback.answer()

        router.add(
            "callback_query",
            (FakeMagicFilter([FakeGetAttribute("data"), FakeComparator("info")]),),
            on_info,
        )

        # @router.message(RegistrationForm.waiting_name)
        async def process_name(message, state):
            await state.set_state(RegistrationForm.waiting_email)
            await message.answer("Now enter email:")

        router.add("message", (FakeState("RegistrationForm:waiting_name"),), process_name)

        # @router.message(RegistrationForm.waiting_email)
        async def process_email(message, state):
            await state.clear()
            await message.answer("Done! Registration complete.")

        router.add("message", (FakeState("RegistrationForm:waiting_email"),), process_email)

        return router

    def test_extracts_all_states(self):
        router = self._build_router_with_example_handlers()
        model = extract_fsm_model(router, bot_name="TestBot")

        state_ids = set(model["states"].keys())
        assert DEFAULT_STATE in state_ids
        assert "RegistrationForm:waiting_name" in state_ids
        assert "RegistrationForm:waiting_email" in state_ids

    def test_extracts_transitions(self):
        router = self._build_router_with_example_handlers()
        model = extract_fsm_model(router, bot_name="TestBot")

        actions = {t["action"] for t in model["transitions"]}
        assert "command:/start" in actions
        assert "callback:register" in actions
        assert "callback:info" in actions
        assert "text:*" in actions

    def test_callback_from_state_resolved(self):
        router = self._build_router_with_example_handlers()
        model = extract_fsm_model(router, bot_name="TestBot")

        register_tr = [
            t for t in model["transitions"] if t["action"] == "callback:register"
        ]
        assert len(register_tr) == 1
        assert register_tr[0]["from"] == DEFAULT_STATE
        assert register_tr[0]["to"] == "RegistrationForm:waiting_name"

    def test_clear_returns_to_initial(self):
        router = self._build_router_with_example_handlers()
        model = extract_fsm_model(router, bot_name="TestBot")

        email_tr = [
            t
            for t in model["transitions"]
            if t["from"] == "RegistrationForm:waiting_email"
        ]
        assert len(email_tr) >= 1
        assert any(t["to"] == DEFAULT_STATE for t in email_tr)

    def test_save_to_file(self, tmp_path):
        router = self._build_router_with_example_handlers()
        out = tmp_path / "model.json"

        model = extract_fsm_model(router, bot_name="TestBot", save_to=str(out))

        assert out.exists()
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["bot_name"] == "TestBot"
        assert loaded == model

    def test_bot_name_custom(self):
        router = self._build_router_with_example_handlers()
        model = extract_fsm_model(router, bot_name="MyAwesomeBot")
        assert model["bot_name"] == "MyAwesomeBot"

    def test_custom_initial_state(self):
        router = self._build_router_with_example_handlers()
        model = extract_fsm_model(router, bot_name="Bot", initial_state="start")
        assert model["initial_state"] == "start"
        assert "start" in model["states"]

    def test_buttons_in_default_state(self):
        router = self._build_router_with_example_handlers()
        model = extract_fsm_model(router, bot_name="TestBot")

        default = model["states"][DEFAULT_STATE]
        assert len(default["buttons"]) >= 1
        all_data = [
            btn["data"]
            for row in default["buttons"]
            for btn in row
        ]
        assert "register" in all_data
        assert "info" in all_data

    def test_transition_labels(self):
        router = self._build_router_with_example_handlers()
        model = extract_fsm_model(router, bot_name="TestBot")

        register_tr = [
            t for t in model["transitions"] if t["action"] == "callback:register"
        ]
        assert register_tr[0].get("label") == "Register"

    def test_model_json_schema_compatible(self):
        """Verify the output matches FSM-Voyager's expected schema structure."""
        router = self._build_router_with_example_handlers()
        model = extract_fsm_model(router, bot_name="TestBot")

        assert isinstance(model["bot_name"], str)
        assert isinstance(model["initial_state"], str)
        assert isinstance(model["states"], dict)
        assert isinstance(model["transitions"], list)

        for sid, state in model["states"].items():
            assert "text" in state
            assert "buttons" in state
            assert isinstance(state["buttons"], list)
            for row in state["buttons"]:
                assert isinstance(row, list)
                for btn in row:
                    assert "text" in btn
                    assert "data" in btn

        for tr in model["transitions"]:
            assert "from" in tr
            assert "to" in tr
            assert "action" in tr
            assert ":" in tr["action"]


# ---------------------------------------------------------------------------
# Test with ProxyDispatcher-like wrapper
# ---------------------------------------------------------------------------

class FakeDispatcher:
    """Mimic ProxyDispatcher that wraps a ProxyRouter."""

    def __init__(self, router: FakeProxyRouter):
        self._router = router


class TestExtractFromDispatcher:

    def test_extracts_via_dispatcher(self):
        router = FakeProxyRouter()

        async def handler(message):
            await message.answer("Hello")

        router.add("message", (FakeCommand("start"),), handler)

        dp = FakeDispatcher(router)
        model = extract_fsm_model(dp, bot_name="Bot")

        assert len(model["transitions"]) == 1
        assert model["transitions"][0]["action"] == "command:/start"
