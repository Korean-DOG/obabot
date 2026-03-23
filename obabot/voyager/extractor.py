"""FSM model extractor — builds model.json from registered obabot handlers.

Uses runtime introspection of handler registrations (filter objects)
combined with AST analysis of handler bodies to extract states,
transitions, buttons, and message texts.

Usage:
    from obabot.voyager.extractor import extract_fsm_model

    bot, dp, router = create_bot(...)
    # ... register all handlers ...

    model = extract_fsm_model(router, bot_name="MyBot", save_to="model.json")
"""

from __future__ import annotations

import ast
import inspect
import json
import logging
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)

DEFAULT_STATE = "__default__"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class _Button:
    text: str
    data: str


@dataclass
class _HandlerInfo:
    name: str
    handler_type: str  # "message", "callback_query"
    from_state: Optional[str]  # None = no state filter
    action: Optional[str]  # "command:/start", "callback:xxx", "text:*"
    target_states: List[str] = field(default_factory=list)
    clears_state: bool = False
    buttons: List[List[_Button]] = field(default_factory=list)
    message_text: Optional[str] = None


# ---------------------------------------------------------------------------
# Handler collection
# ---------------------------------------------------------------------------

HandlerRecord = Tuple[str, tuple, dict, Callable]


def _collect_handlers(source: Any) -> List[HandlerRecord]:
    """Get handler records from ProxyRouter, ProxyDispatcher, or aiogram Router.

    Each record is ``(handler_type, filters, kwargs, callback)``.
    """
    # ProxyRouter directly
    pending = getattr(source, "_pending_handlers", None)
    if pending:
        return list(pending)

    # ProxyDispatcher → ProxyRouter
    router = getattr(source, "_router", None)
    if router:
        pending = getattr(router, "_pending_handlers", None)
        if pending:
            return list(pending)

    # aiogram Router/Dispatcher
    records: List[HandlerRecord] = []
    routers: list = []
    sub = getattr(source, "sub_routers", None)
    if sub:
        routers.extend(sub)
    routers.append(source)

    for r in routers:
        _extract_aiogram_handlers(r, records)

    return records


def _unwrap_aiogram_filter(fo: Any) -> Any:
    """Extract the real filter from an aiogram ``FilterObject`` wrapper.

    Aiogram wraps filters differently depending on type:
    - MagicFilter  → stored in ``fo.magic``
    - Other (Command, StateFilter, etc.) → stored in ``fo.callback``
    """
    # MagicFilter has a dedicated .magic attribute on FilterObject
    magic = getattr(fo, "magic", None)
    if magic is not None:
        return magic

    # For bound-method callbacks, the __self__ might be the filter object
    cb = getattr(fo, "callback", None)
    if cb is not None:
        self_obj = getattr(cb, "__self__", None)
        if self_obj is not None and hasattr(self_obj, "_operations"):
            return self_obj
        return cb

    return fo


def _extract_aiogram_handlers(router: Any, out: List[HandlerRecord]) -> None:
    for event_name, handler_type in (
        ("message", "message"),
        ("callback_query", "callback_query"),
        ("edited_message", "edited_message"),
    ):
        observer = getattr(router, event_name, None)
        if observer is None:
            continue
        handler_objects = getattr(observer, "handlers", [])
        for ho in handler_objects:
            callback = getattr(ho, "callback", None)
            if callback is None:
                continue
            raw_filters = tuple(
                _unwrap_aiogram_filter(fo)
                for fo in (getattr(ho, "filters", None) or [])
            )
            out.append((handler_type, raw_filters, {}, callback))


# ---------------------------------------------------------------------------
# Filter introspection (runtime)
# ---------------------------------------------------------------------------

def _is_magic_filter(obj: Any) -> bool:
    """True if *obj* is a MagicFilter (intercepts all attribute access)."""
    return type(obj).__name__ == "MagicFilter" or (
        hasattr(type(obj), "_operations") and hasattr(obj, "_resolve_operation_")
    )


def _extract_state_from_filter(flt: Any) -> Optional[str]:
    """Extract FSM state string from a filter object."""
    # MagicFilter intercepts hasattr/getattr — skip it early
    if _is_magic_filter(flt):
        return None

    # StateFilter wraps one or more State objects (duck-type: has .states list)
    states_list = getattr(flt, "states", None)
    if states_list is not None and isinstance(states_list, (list, tuple)):
        for s in states_list:
            state_str = getattr(s, "state", None)
            if isinstance(state_str, str):
                return state_str
        return None

    # Raw State descriptor from StatesGroup (has both .state and .group)
    state_val = getattr(flt, "state", None)
    if isinstance(state_val, str) and hasattr(flt, "group"):
        return state_val

    # Other State-like objects
    flt_name = type(flt).__name__
    if "State" in flt_name and isinstance(state_val, str):
        return state_val

    return None


def _extract_action_from_magic_filter(flt: Any, handler_type: str) -> Optional[str]:
    """Parse MagicFilter operation chain to extract the trigger action."""
    ops = getattr(flt, "_operations", ())
    if not ops:
        return None

    attr_name: Optional[str] = None
    comparator_value: Any = None

    for op in ops:
        op_name = type(op).__name__
        if "GetAttribute" in op_name:
            attr_name = getattr(op, "name", None)
        elif "Comparator" in op_name:
            comparator_value = getattr(op, "right", None)

    if attr_name == "data":
        if comparator_value is not None:
            return f"callback:{comparator_value}"
        return "callback:*"

    if attr_name == "text":
        if comparator_value is not None:
            return f"text:{comparator_value}"
        return "text:*"

    return None


def _extract_action_from_filter(flt: Any, handler_type: str) -> Optional[str]:
    """Extract action string from a single filter object."""
    flt_name = type(flt).__name__

    # MagicFilter — check early (it intercepts getattr for everything)
    if _is_magic_filter(flt):
        return _extract_action_from_magic_filter(flt, handler_type)

    # CommandStart (duck-type: name contains "CommandStart")
    if "CommandStart" in flt_name:
        return "command:/start"

    # Command (duck-type: has .commands attribute with iterable of strings)
    commands = getattr(flt, "commands", None)
    if commands is not None and isinstance(commands, (list, tuple, set, frozenset)):
        if commands:
            cmd = next(iter(commands))
            return f"command:/{cmd}"
        return None

    # Fallback: anything with _operations (MagicFilter-like without __getattr__)
    ops = getattr(flt, "_operations", None)
    if ops is not None and isinstance(ops, (list, tuple)):
        return _extract_action_from_magic_filter(flt, handler_type)

    return None


def _classify_filters(
    filters: tuple,
    handler_type: str,
) -> Tuple[Optional[str], Optional[str]]:
    """Return ``(from_state, action)`` extracted from a handler's filter tuple."""
    from_state: Optional[str] = None
    action: Optional[str] = None

    for flt in filters:
        s = _extract_state_from_filter(flt)
        if s is not None:
            from_state = s
            continue

        a = _extract_action_from_filter(flt, handler_type)
        if a is not None and action is None:
            action = a

    # Default action when no explicit trigger filter was found
    if action is None:
        if handler_type == "callback_query":
            action = "callback:*"
        elif from_state is not None:
            # State-filtered message handler with no command/text filter → text input
            action = "text:*"

    return from_state, action


# ---------------------------------------------------------------------------
# AST analysis of handler bodies
# ---------------------------------------------------------------------------

def _get_handler_source(handler: Callable) -> Optional[str]:
    try:
        source = inspect.getsource(handler)
        return textwrap.dedent(source)
    except (OSError, TypeError):
        return None


def _find_state_param_name(handler: Callable) -> Optional[str]:
    """Detect parameter that receives FSMContext."""
    try:
        sig = inspect.signature(handler)
    except (ValueError, TypeError):
        return None
    for name, param in sig.parameters.items():
        ann = param.annotation
        ann_name = getattr(ann, "__name__", "")
        if "FSMContext" in ann_name or name == "state":
            return name
    return None


def _resolve_state_ref(node: ast.AST) -> Optional[str]:
    """Map ``ClassName.attr`` AST node to ``'ClassName:attr'`` state string."""
    # ClassName.attr
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return f"{node.value.id}:{node.attr}"
    # module.ClassName.attr → ClassName:attr
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute):
        return f"{node.value.attr}:{node.attr}"
    return None


class _HandlerBodyVisitor(ast.NodeVisitor):
    """Extract FSM-relevant information from handler function body."""

    def __init__(self, state_param: Optional[str], event_param: str = "message"):
        self.state_param = state_param
        self.event_param = event_param
        self.target_states: List[str] = []
        self.clears_state = False
        self.keyboard_rows: List[List[_Button]] = []
        self.message_texts: List[str] = []

    # -- visitors ----------------------------------------------------------

    def visit_Call(self, node: ast.Call) -> None:
        self._check_set_state(node)
        self._check_clear(node)
        self._check_keyboard_markup(node)
        self._check_answer(node)
        self.generic_visit(node)

    # -- set_state / clear -------------------------------------------------

    def _check_set_state(self, node: ast.Call) -> None:
        if not self._is_method_call_on(node, "set_state"):
            return
        if node.args:
            ref = _resolve_state_ref(node.args[0])
            if ref:
                self.target_states.append(ref)

    def _check_clear(self, node: ast.Call) -> None:
        if self._is_method_call_on(node, "clear"):
            self.clears_state = True
        if self._is_method_call_on(node, "reset_state"):
            self.clears_state = True

    def _is_method_call_on(self, node: ast.Call, method: str) -> bool:
        """True if ``node`` is ``state_param.method(...)`` or ``event_param.method(...)``."""
        if not isinstance(node.func, ast.Attribute) or node.func.attr != method:
            return False
        val = node.func.value
        if isinstance(val, ast.Name):
            return val.id in (self.state_param, self.event_param)
        return False

    # -- InlineKeyboardMarkup / InlineKeyboardButton -----------------------

    def _check_keyboard_markup(self, node: ast.Call) -> None:
        func_name = self._call_name(node)
        if func_name != "InlineKeyboardMarkup":
            return
        for kw in node.keywords:
            if kw.arg == "inline_keyboard" and isinstance(kw.value, ast.List):
                rows = self._parse_keyboard_rows(kw.value)
                if rows:
                    self.keyboard_rows = rows

    def _parse_keyboard_rows(self, list_node: ast.List) -> List[List[_Button]]:
        rows: List[List[_Button]] = []
        for row_node in list_node.elts:
            if not isinstance(row_node, ast.List):
                continue
            row: List[_Button] = []
            for btn_node in row_node.elts:
                if isinstance(btn_node, ast.Call):
                    btn = self._parse_button(btn_node)
                    if btn:
                        row.append(btn)
            if row:
                rows.append(row)
        return rows

    def _parse_button(self, node: ast.Call) -> Optional[_Button]:
        func_name = self._call_name(node)
        if func_name != "InlineKeyboardButton":
            return None
        text = self._kwarg_str(node, "text")
        data = self._kwarg_str(node, "callback_data")
        if text and data:
            return _Button(text=text, data=data)
        return None

    # -- message.answer / callback.message.answer --------------------------

    def _check_answer(self, node: ast.Call) -> None:
        if not isinstance(node.func, ast.Attribute):
            return
        if node.func.attr not in ("answer", "edit_text"):
            return
        # message.answer(...) or callback.message.answer(...)
        val = node.func.value
        is_answer = False
        if isinstance(val, ast.Name) and val.id in (self.event_param, "message"):
            is_answer = True
        elif isinstance(val, ast.Attribute) and val.attr == "message":
            is_answer = True
        if is_answer and node.args:
            text = self._extract_text(node.args[0])
            if text:
                self.message_texts.append(text)

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _call_name(node: ast.Call) -> Optional[str]:
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None

    @staticmethod
    def _kwarg_str(node: ast.Call, name: str) -> Optional[str]:
        for kw in node.keywords:
            if kw.arg == name and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                return kw.value.value
        return None

    @staticmethod
    def _extract_text(node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            parts: list = []
            for v in node.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    parts.append(v.value)
                else:
                    parts.append("{...}")
            return "".join(parts)
        return None


def _analyze_handler_body(
    handler: Callable,
) -> Tuple[List[str], bool, List[List[_Button]], Optional[str]]:
    """Return ``(target_states, clears_state, keyboard_rows, first_message_text)``."""
    source = _get_handler_source(handler)
    if source is None:
        return [], False, [], None

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [], False, [], None

    state_param = _find_state_param_name(handler)

    event_param = "message"
    try:
        sig = inspect.signature(handler)
        params = list(sig.parameters.keys())
        if params:
            event_param = params[0]
    except (ValueError, TypeError):
        pass

    visitor = _HandlerBodyVisitor(state_param, event_param)
    visitor.visit(tree)

    text = visitor.message_texts[0] if visitor.message_texts else None
    return visitor.target_states, visitor.clears_state, visitor.keyboard_rows, text


# ---------------------------------------------------------------------------
# Handler analysis (filters + AST combined)
# ---------------------------------------------------------------------------

def _analyze_handler(
    handler_type: str,
    filters: tuple,
    callback: Callable,
    initial_state: str,
) -> Optional[_HandlerInfo]:
    name = getattr(callback, "__name__", None) or str(callback)
    from_state, action = _classify_filters(filters, handler_type)
    targets, clears, buttons, text = _analyze_handler_body(callback)

    return _HandlerInfo(
        name=name,
        handler_type=handler_type,
        from_state=from_state,
        action=action,
        target_states=targets,
        clears_state=clears,
        buttons=buttons,
        message_text=text,
    )


# ---------------------------------------------------------------------------
# Model building (two-pass)
# ---------------------------------------------------------------------------

def _find_button_label(
    callback_data: str, all_handlers: List[_HandlerInfo]
) -> Optional[str]:
    """Find the button text that matches a given callback_data."""
    for h in all_handlers:
        for row in h.buttons:
            for btn in row:
                if btn.data == callback_data:
                    return btn.text
    return None


def _build_model_dict(
    handlers: List[_HandlerInfo],
    bot_name: str,
    initial_state: str,
) -> dict:
    """Assemble all handler analyses into a model.json-compatible dict."""

    # --- pass 1: build callback_data → source_state map -------------------
    # "If handler H shows button with data=X, and H's effective target state
    #  is S, then button X lives in state S."
    callback_data_home: Dict[str, str] = {}

    for h in handlers:
        if not h.buttons:
            continue
        # Determine which state the user is in AFTER this handler runs
        if h.target_states:
            dest = h.target_states[-1]
        elif h.clears_state:
            dest = initial_state
        else:
            dest = h.from_state or initial_state
        for row in h.buttons:
            for btn in row:
                callback_data_home[btn.data] = dest

    # --- pass 2: build transitions and collect state metadata -------------
    transitions: List[dict] = []
    # state_id → (text, buttons) — first writer wins
    state_meta: Dict[str, Tuple[Optional[str], List[List[_Button]]]] = {}
    seen_transitions: Set[Tuple[str, str, str]] = set()

    for h in handlers:
        effective_from = h.from_state or initial_state

        # For callback handlers without state filter, resolve via button location
        if (
            h.handler_type == "callback_query"
            and h.from_state is None
            and h.action
        ):
            action_value = h.action.split(":", 1)[1] if ":" in h.action else None
            if action_value and action_value != "*":
                resolved = callback_data_home.get(action_value)
                if resolved:
                    effective_from = resolved

        # Determine target(s)
        targets: List[str] = []
        if h.target_states:
            targets = list(h.target_states)
        elif h.clears_state:
            targets = [initial_state]
        else:
            targets = [effective_from]

        # Build transition(s)
        if h.action:
            for target in targets:
                key = (effective_from, target, h.action)
                if key in seen_transitions:
                    continue
                seen_transitions.add(key)

                label: Optional[str] = None
                action_type, _, action_value = h.action.partition(":")
                if action_type == "command":
                    label = action_value
                elif action_type == "callback" and action_value != "*":
                    label = _find_button_label(action_value, handlers)

                tr: dict = {
                    "from": effective_from,
                    "to": target,
                    "action": h.action,
                }
                if label:
                    tr["label"] = label
                transitions.append(tr)

        # Collect state appearance from the handler's output.
        # The text/buttons sent by a handler describe the TARGET state.
        dest = targets[-1] if targets else effective_from
        if dest not in state_meta:
            if h.message_text or h.buttons:
                state_meta[dest] = (h.message_text, h.buttons)

    # --- assemble states dict ---------------------------------------------
    all_state_ids: Set[str] = {initial_state}
    for t in transitions:
        all_state_ids.add(t["from"])
        all_state_ids.add(t["to"])

    states: Dict[str, dict] = {}
    for sid in sorted(all_state_ids):
        text, buttons = state_meta.get(sid, (None, []))
        state_dict: dict = {"text": text or f"[{sid}]"}
        if buttons:
            state_dict["buttons"] = [
                [{"text": b.text, "data": b.data} for b in row]
                for row in buttons
            ]
        else:
            state_dict["buttons"] = []
        states[sid] = state_dict

    return {
        "bot_name": bot_name,
        "initial_state": initial_state,
        "states": states,
        "transitions": transitions,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_fsm_model(
    router_or_dp: Any,
    *,
    bot_name: str = "Bot",
    initial_state: str = DEFAULT_STATE,
    save_to: Optional[Union[str, Path]] = None,
) -> dict:
    """Extract FSM model from registered obabot handlers.

    Introspects handler registrations at runtime and combines that with
    AST analysis of each handler's body to produce a ``model.json``
    compatible with FSM-Voyager.

    Args:
        router_or_dp: ``ProxyRouter``, ``ProxyDispatcher``, or aiogram
            ``Router`` / ``Dispatcher`` that has handlers registered on it.
        bot_name: Name to store in the model's ``bot_name`` field.
        initial_state: Identifier for the implicit "no FSM state" node.
        save_to: If given, the model dict is also written to this path as
            pretty-printed JSON.

    Returns:
        A dict that matches the FSM-Voyager ``FSMModel`` JSON schema.

    Example::

        bot, dp, router = create_bot(tg_token="...")
        # ... all @router.message / @router.callback_query decorators ...

        model = extract_fsm_model(router, bot_name="MyBot")

        # or save in one step:
        extract_fsm_model(router, bot_name="MyBot", save_to="model.json")
    """
    skip_types = frozenset((
        "error", "channel_post", "inline_query",
        "chosen_inline_result", "shipping_query",
        "pre_checkout_query", "edited_channel_post",
    ))

    records = _collect_handlers(router_or_dp)
    logger.info("Collected %d handler records", len(records))

    analyses: List[_HandlerInfo] = []
    for handler_type, filters, _kwargs, callback in records:
        if handler_type in skip_types:
            continue
        info = _analyze_handler(handler_type, filters, callback, initial_state)
        if info:
            analyses.append(info)

    logger.info("Analyzed %d relevant handlers", len(analyses))

    model_dict = _build_model_dict(analyses, bot_name, initial_state)

    if save_to is not None:
        path = Path(save_to)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(model_dict, f, ensure_ascii=False, indent=2)
        logger.info("Model saved to %s", path)

    return model_dict
