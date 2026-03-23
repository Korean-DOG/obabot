"""Tests for obabot.web module — emulators, dispatch, create_web, create_mobile."""

import pytest
from unittest.mock import AsyncMock

from obabot import create_bot
from obabot.fsm import MemoryStorage, State, StatesGroup


# ---------------------------------------------------------------------------
# FSM states used in tests
# ---------------------------------------------------------------------------

class TestStates(StatesGroup):
    waiting = State()
    confirmed = State()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def storage():
    return MemoryStorage()


@pytest.fixture
def bot_dp_router(storage):
    """Create obabot in test mode with MemoryStorage."""
    bot, dp, router = create_bot(test_mode=True, fsm_storage=storage)
    return bot, dp, router


# ---------------------------------------------------------------------------
# Emulator unit tests
# ---------------------------------------------------------------------------

class TestWebBot:
    async def test_send_message(self):
        from obabot.web.emulators import WebBot

        bot = WebBot()
        result = await bot.send_message(chat_id=123, text="hello")

        assert len(bot.outgoing) == 1
        assert bot.outgoing[0]["method"] == "send_message"
        assert bot.outgoing[0]["text"] == "hello"
        assert bot.outgoing[0]["chat_id"] == 123
        assert "message_id" in result

    async def test_edit_message_text(self):
        from obabot.web.emulators import WebBot

        bot = WebBot()
        await bot.edit_message_text("edited", chat_id=1, message_id=42)

        assert bot.outgoing[0]["method"] == "edit_message_text"
        assert bot.outgoing[0]["text"] == "edited"
        assert bot.outgoing[0]["message_id"] == 42

    async def test_answer_callback_query(self):
        from obabot.web.emulators import WebBot

        bot = WebBot()
        await bot.answer_callback_query("cb_1", text="ok")

        assert bot.outgoing[0]["method"] == "answer_callback_query"
        assert bot.outgoing[0]["text"] == "ok"

    async def test_delete_message(self):
        from obabot.web.emulators import WebBot

        bot = WebBot()
        await bot.delete_message(chat_id=1, message_id=5)

        assert bot.outgoing[0]["method"] == "delete_message"

    async def test_send_photo(self):
        from obabot.web.emulators import WebBot

        bot = WebBot()
        await bot.send_photo(chat_id=1, photo="http://example.com/img.png", caption="pic")

        assert bot.outgoing[0]["method"] == "send_photo"
        assert bot.outgoing[0]["caption"] == "pic"

    async def test_send_document(self):
        from obabot.web.emulators import WebBot

        bot = WebBot()
        await bot.send_document(chat_id=1, document="file.pdf", caption="doc")

        assert bot.outgoing[0]["method"] == "send_document"


class TestWebMessage:
    async def test_properties(self):
        from obabot.web.emulators import WebBot, WebMessage

        bot = WebBot()
        msg = WebMessage(bot, user_id=42, text="/start", chat_id=100)

        assert msg.text == "/start"
        assert msg.from_user.id == 42
        assert msg.chat.id == 100
        assert msg.platform == "web"
        assert msg.content_type == "text"
        assert msg.photo == []
        assert msg.document is None

    async def test_answer(self):
        from obabot.web.emulators import WebBot, WebMessage

        bot = WebBot()
        msg = WebMessage(bot, user_id=1, text="hi", chat_id=1)
        await msg.answer("hello back")

        assert len(bot.outgoing) == 1
        assert bot.outgoing[0]["text"] == "hello back"

    async def test_reply(self):
        from obabot.web.emulators import WebBot, WebMessage

        bot = WebBot()
        msg = WebMessage(bot, user_id=1, text="hi", chat_id=1)
        await msg.reply("reply text")

        assert bot.outgoing[0]["text"] == "reply text"

    async def test_edit_text(self):
        from obabot.web.emulators import WebBot, WebMessage

        bot = WebBot()
        msg = WebMessage(bot, user_id=1, text="old", chat_id=1, message_id=10)
        await msg.edit_text("new")

        assert bot.outgoing[0]["method"] == "edit_message_text"
        assert bot.outgoing[0]["text"] == "new"
        assert bot.outgoing[0]["message_id"] == 10


class TestWebCallbackQuery:
    async def test_properties(self):
        from obabot.web.emulators import WebBot, WebCallbackQuery

        bot = WebBot()
        cb = WebCallbackQuery(bot, user_id=7, callback_data="btn_1", chat_id=7)

        assert cb.data == "btn_1"
        assert cb.payload == "btn_1"
        assert cb.from_user.id == 7
        assert cb.platform == "web"
        assert cb.message is not None
        assert cb.message.chat.id == 7

    async def test_answer(self):
        from obabot.web.emulators import WebBot, WebCallbackQuery

        bot = WebBot()
        cb = WebCallbackQuery(bot, user_id=1, callback_data="x")
        await cb.answer("ack")

        assert bot.outgoing[0]["method"] == "answer_callback_query"

    async def test_edit_message_text(self):
        from obabot.web.emulators import WebBot, WebCallbackQuery

        bot = WebBot()
        cb = WebCallbackQuery(bot, user_id=1, callback_data="x", message_id=20)
        await cb.edit_message_text("updated")

        assert bot.outgoing[0]["method"] == "edit_message_text"
        assert bot.outgoing[0]["text"] == "updated"
        assert bot.outgoing[0]["message_id"] == 20

    async def test_delete_message(self):
        from obabot.web.emulators import WebBot, WebCallbackQuery

        bot = WebBot()
        cb = WebCallbackQuery(bot, user_id=1, callback_data="x", message_id=5, chat_id=1)
        await cb.delete_message()

        assert bot.outgoing[0]["method"] == "delete_message"
        assert bot.outgoing[0]["message_id"] == 5


class TestSerializeMarkup:
    def test_inline_keyboard(self):
        from obabot.web.emulators import _serialize_markup
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="A", callback_data="a"),
             InlineKeyboardButton(text="B", url="https://example.com")],
        ])
        result = _serialize_markup(kb)

        assert result["type"] == "inline_keyboard"
        assert len(result["inline_keyboard"]) == 1
        assert result["inline_keyboard"][0][0]["text"] == "A"
        assert result["inline_keyboard"][0][0]["callback_data"] == "a"
        assert result["inline_keyboard"][0][1]["url"] == "https://example.com"

    def test_none(self):
        from obabot.web.emulators import _serialize_markup

        assert _serialize_markup(None) is None


# ---------------------------------------------------------------------------
# Dispatch tests
# ---------------------------------------------------------------------------

class TestDispatch:
    async def test_message_dispatch_simple(self):
        """A plain message handler should be found and called."""
        from obabot.web.emulators import WebBot, WebMessage
        from obabot.web.dispatch import dispatch_message

        bot, dp, router = create_bot(test_mode=True)

        called = {}

        @router.message()
        async def echo(message):
            called["text"] = message.text
            await message.answer(f"echo: {message.text}")

        web_bot = WebBot()
        msg = WebMessage(web_bot, user_id=1, text="hello")
        await dispatch_message(dp, web_bot, msg)

        assert called.get("text") == "hello"
        assert len(web_bot.outgoing) == 1
        assert web_bot.outgoing[0]["text"] == "echo: hello"

    async def test_command_filter(self):
        """CommandStart filter should match /start."""
        from obabot.web.emulators import WebBot, WebMessage
        from obabot.web.dispatch import dispatch_message
        from aiogram.filters import CommandStart

        bot, dp, router = create_bot(test_mode=True)

        called = {}

        @router.message(CommandStart())
        async def start(message):
            called["ok"] = True
            await message.answer("Welcome!")

        @router.message()
        async def fallback(message):
            called["fallback"] = True

        web_bot = WebBot()
        msg = WebMessage(web_bot, user_id=1, text="/start")
        await dispatch_message(dp, web_bot, msg)

        assert called.get("ok") is True
        assert "fallback" not in called

    async def test_callback_dispatch(self):
        """Callback handler should be matched by F.data filter."""
        from obabot.web.emulators import WebBot, WebCallbackQuery
        from obabot.web.dispatch import dispatch_callback

        bot, dp, router = create_bot(test_mode=True)

        called = {}

        @router.callback_query()
        async def on_cb(callback):
            called["data"] = callback.data
            await callback.answer("got it")

        web_bot = WebBot()
        cb = WebCallbackQuery(web_bot, user_id=1, callback_data="test_btn")
        await dispatch_callback(dp, web_bot, cb)

        assert called.get("data") == "test_btn"
        assert len(web_bot.outgoing) == 1

    async def test_fsm_dispatch(self, storage):
        """FSM state filter should work in the web dispatch."""
        from obabot.web.emulators import WebBot, WebMessage
        from obabot.web.dispatch import dispatch_message, WebFSMContext

        bot, dp, router = create_bot(test_mode=True, fsm_storage=storage)

        results = []

        @router.message(TestStates.waiting)
        async def on_waiting(message, state=None):
            results.append("waiting_handler")
            if state:
                await state.set_state(None)
            await message.answer("got it")

        @router.message()
        async def fallback(message):
            results.append("fallback")

        # First: no state set — fallback should handle
        web_bot = WebBot()
        msg1 = WebMessage(web_bot, user_id=55, text="hi")
        await dispatch_message(dp, web_bot, msg1)
        assert results == ["fallback"]

        # Set state to TestStates.waiting
        ctx = WebFSMContext(storage, user_id=55, chat_id=55, bot_id=0)
        await ctx.set_state(TestStates.waiting)

        results.clear()
        web_bot2 = WebBot()
        msg2 = WebMessage(web_bot2, user_id=55, text="anything")
        await dispatch_message(dp, web_bot2, msg2)
        assert results == ["waiting_handler"]


class TestWebFSMContext:
    async def test_state_lifecycle(self, storage):
        from obabot.web.dispatch import WebFSMContext

        ctx = WebFSMContext(storage, user_id=1, chat_id=1, bot_id=0)

        assert await ctx.get_state() is None
        await ctx.set_state(TestStates.waiting)
        assert await ctx.get_state() == TestStates.waiting.state

        await ctx.update_data(name="test")
        data = await ctx.get_data()
        assert data["name"] == "test"

        await ctx.clear()
        assert await ctx.get_state() is None
        assert await ctx.get_data() == {}


# ---------------------------------------------------------------------------
# FastAPI integration tests (create_web / create_mobile)
# ---------------------------------------------------------------------------

class TestCreateWeb:
    async def test_webhook_endpoint(self):
        """POST /api/webhook should return bot responses."""
        from obabot.web import create_web

        bot, dp, router = create_bot(test_mode=True)

        @router.message()
        async def echo(message):
            await message.answer(f"echo: {message.text}")

        app = create_web(dp)

        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/webhook", json={
                "user_id": 1, "text": "ping",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["responses"]) == 1
        assert data["responses"][0]["text"] == "echo: ping"

    async def test_callback_endpoint(self):
        """POST /api/callback should trigger callback handler."""
        from obabot.web import create_web

        bot, dp, router = create_bot(test_mode=True)

        @router.callback_query()
        async def on_cb(callback):
            await callback.edit_message_text(f"Pressed: {callback.data}")

        app = create_web(dp)

        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/callback", json={
                "user_id": 1, "callback_data": "btn_ok",
            })

        assert resp.status_code == 200
        data = resp.json()
        assert any("Pressed: btn_ok" in r.get("text", "") for r in data["responses"])

    async def test_state_endpoint(self, storage):
        """GET /api/state/{user_id} should return FSM state."""
        from obabot.web import create_web
        from obabot.web.dispatch import WebFSMContext

        bot, dp, router = create_bot(test_mode=True, fsm_storage=storage)
        app = create_web(dp)

        ctx = WebFSMContext(storage, user_id=99, chat_id=99, bot_id=0)
        await ctx.set_state(TestStates.confirmed)
        await ctx.update_data(name="Alice")

        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/state/99")

        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == TestStates.confirmed.state
        assert data["data"]["name"] == "Alice"

    async def test_reset_endpoint(self, storage):
        """POST /api/reset/{user_id} should clear FSM."""
        from obabot.web import create_web
        from obabot.web.dispatch import WebFSMContext

        bot, dp, router = create_bot(test_mode=True, fsm_storage=storage)
        app = create_web(dp)

        ctx = WebFSMContext(storage, user_id=88, chat_id=88, bot_id=0)
        await ctx.set_state(TestStates.waiting)

        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/reset/88")

        assert resp.status_code == 200
        assert (await ctx.get_state()) is None

    async def test_custom_base_path(self):
        """create_web(base_path='/v2') should mount endpoints under /v2."""
        from obabot.web import create_web

        bot, dp, router = create_bot(test_mode=True)

        @router.message()
        async def echo(message):
            await message.answer("ok")

        app = create_web(dp, base_path="/v2")

        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/v2/webhook", json={"user_id": 1, "text": "x"})

        assert resp.status_code == 200


class TestCreateMobile:
    async def test_manifest_served(self):
        """manifest.json should be served at /static/manifest.json."""
        from obabot.web import create_web, create_mobile

        bot, dp, router = create_bot(test_mode=True)
        app = create_web(dp)
        create_mobile(app, name="Test", short_name="T",
                       icons="/static/icons/", theme_color="#ff0000")

        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/static/manifest.json")

        assert resp.status_code == 200
        manifest = resp.json()
        assert manifest["name"] == "Test"
        assert manifest["theme_color"] == "#ff0000"

    async def test_service_worker_served(self):
        """service-worker.js should be served at /service-worker.js."""
        from obabot.web import create_web, create_mobile

        bot, dp, router = create_bot(test_mode=True)
        app = create_web(dp)
        create_mobile(app, name="Test", short_name="T",
                       icons="/static/icons/", theme_color="#000000")

        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/service-worker.js")

        assert resp.status_code == 200
        assert "CACHE_NAME" in resp.text

    async def test_index_html_served(self):
        """GET / should return the PWA index page."""
        from obabot.web import create_web, create_mobile

        bot, dp, router = create_bot(test_mode=True)
        app = create_web(dp)
        create_mobile(app, name="Chat Bot", short_name="CB",
                       icons="/static/icons/", theme_color="#123456")

        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/")

        assert resp.status_code == 200
        assert "Chat Bot" in resp.text
        assert "manifest" in resp.text

    async def test_offline_disabled(self):
        """When offline_enabled=False, no service worker route should exist."""
        from obabot.web import create_web, create_mobile

        bot, dp, router = create_bot(test_mode=True)
        app = create_web(dp)
        create_mobile(app, name="T", short_name="T",
                       icons="/icons/", theme_color="#000",
                       offline_enabled=False)

        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/service-worker.js")

        assert resp.status_code in (404, 405)

    async def test_returns_same_app(self):
        """create_mobile should return the same FastAPI instance."""
        from obabot.web import create_web, create_mobile

        bot, dp, router = create_bot(test_mode=True)
        app = create_web(dp)
        result = create_mobile(app, name="T", short_name="T",
                                icons="/icons/", theme_color="#000")

        assert result is app


# ---------------------------------------------------------------------------
# Filter checking unit tests
# ---------------------------------------------------------------------------

class TestFilterCheck:
    async def test_command_start_filter(self):
        from obabot.web.dispatch import _check_filter
        from obabot.web.emulators import WebBot, WebMessage
        from aiogram.filters import CommandStart

        flt = CommandStart()
        bot = WebBot()

        msg_ok = WebMessage(bot, user_id=1, text="/start")
        assert await _check_filter(flt, msg_ok) is True

        msg_no = WebMessage(bot, user_id=1, text="hello")
        assert await _check_filter(flt, msg_no) is False

    async def test_command_filter(self):
        from obabot.web.dispatch import _check_filter
        from obabot.web.emulators import WebBot, WebMessage
        from aiogram.filters import Command

        flt = Command("help")
        bot = WebBot()

        assert await _check_filter(flt, WebMessage(bot, 1, "/help")) is True
        assert await _check_filter(flt, WebMessage(bot, 1, "/start")) is False

    async def test_callable_filter(self):
        from obabot.web.dispatch import _check_filter
        from obabot.web.emulators import WebBot, WebMessage

        def only_long(msg):
            return len(msg.text) > 5

        bot = WebBot()
        assert await _check_filter(only_long, WebMessage(bot, 1, "hi")) is False
        assert await _check_filter(only_long, WebMessage(bot, 1, "hello world")) is True

    async def test_none_filter(self):
        from obabot.web.dispatch import _check_filter

        assert await _check_filter(None, object()) is True

    async def test_state_filter(self, storage):
        from obabot.web.dispatch import _check_filter, WebFSMContext

        ctx = WebFSMContext(storage, user_id=1, chat_id=1, bot_id=0)
        await ctx.set_state(TestStates.waiting)

        assert await _check_filter(TestStates.waiting, object(), ctx) is True
        assert await _check_filter(TestStates.confirmed, object(), ctx) is False
