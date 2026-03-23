"""Tests for Yandex Messenger platform: adapters, keyboard, bot, router, factory."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from obabot import create_bot
from obabot.types import BPlatform


# ---------------------------------------------------------------------------
# YandexUserAdapter / YandexChatAdapter
# ---------------------------------------------------------------------------

class TestYandexUserAdapter:
    def test_properties(self):
        from obabot.adapters.yandex_user import YandexUserAdapter

        raw = {"id": "uid123", "login": "alice@corp.ru", "display_name": "Alice", "robot": False}
        user = YandexUserAdapter(raw)

        assert user.id == "uid123"
        assert user.username == "alice@corp.ru"
        assert user.first_name == "Alice"
        assert user.last_name is None
        assert user.is_bot is False
        assert user.language_code is None
        assert user.full_name == "Alice"
        assert "Alice" in repr(user)

    def test_bot_flag(self):
        from obabot.adapters.yandex_user import YandexUserAdapter

        raw = {"id": "bot1", "login": "bot@org.ru", "display_name": "Bot", "robot": True}
        assert YandexUserAdapter(raw).is_bot is True

    def test_missing_fields(self):
        from obabot.adapters.yandex_user import YandexUserAdapter

        user = YandexUserAdapter({})
        assert user.id == ""
        assert user.username is None
        assert user.first_name == ""


class TestYandexChatAdapter:
    def test_properties(self):
        from obabot.adapters.yandex_user import YandexChatAdapter

        raw = {"id": "chat_abc", "type": "group"}
        chat = YandexChatAdapter(raw)

        assert chat.id == "chat_abc"
        assert chat.type == "group"
        assert chat.title is None
        assert chat.username is None
        assert chat.first_name is None
        assert "chat_abc" in repr(chat)

    def test_defaults(self):
        from obabot.adapters.yandex_user import YandexChatAdapter

        chat = YandexChatAdapter({})
        assert chat.id == ""
        assert chat.type == "private"


# ---------------------------------------------------------------------------
# YandexMessageAdapter
# ---------------------------------------------------------------------------

class TestYandexMessageAdapter:
    def _make_raw(self, **overrides):
        raw = {
            "from": {"id": "u1", "login": "alice@corp.ru", "display_name": "Alice"},
            "chat": {"id": "c1", "type": "private"},
            "text": "hello",
            "message_id": 42,
            "timestamp": 1700000000,
        }
        raw.update(overrides)
        return raw

    def test_text_and_id(self):
        from obabot.adapters.yandex_message import YandexMessageAdapter

        msg = YandexMessageAdapter(self._make_raw())
        assert msg.text == "hello"
        assert msg.message_id == 42
        assert msg.id == 42

    def test_platform(self):
        from obabot.adapters.yandex_message import YandexMessageAdapter

        msg = YandexMessageAdapter(self._make_raw())
        assert msg.platform == "yandex"
        assert msg.get_platform() == "yandex"
        assert msg.is_yandex() is True
        assert msg.is_telegram() is False
        assert msg.is_max() is False

    def test_from_user_and_chat(self):
        from obabot.adapters.yandex_message import YandexMessageAdapter

        msg = YandexMessageAdapter(self._make_raw())
        assert msg.from_user is not None
        assert msg.from_user.id == "u1"
        assert msg.from_user.username == "alice@corp.ru"
        assert msg.sender is not None
        assert msg.chat is not None
        assert msg.chat.id == "c1"

    def test_attachment_stubs(self):
        from obabot.adapters.yandex_message import YandexMessageAdapter

        msg = YandexMessageAdapter(self._make_raw())
        assert msg.photo == []
        assert msg.document is None
        assert msg.audio is None
        assert msg.video is None
        assert msg.voice is None
        assert msg.video_note is None
        assert msg.sticker is None
        assert msg.animation is None
        assert msg.contact is None
        assert msg.location is None
        assert msg.successful_payment is None
        assert msg.content_type == "text"

    def test_content_type_unknown(self):
        from obabot.adapters.yandex_message import YandexMessageAdapter

        msg = YandexMessageAdapter({"message_id": 1})
        assert msg.content_type == "unknown"

    def test_date_and_update_id(self):
        from obabot.adapters.yandex_message import YandexMessageAdapter

        msg = YandexMessageAdapter(self._make_raw(update_id=99))
        assert msg.date == 1700000000
        assert msg.update_id == 99

    def test_from_user_none(self):
        from obabot.adapters.yandex_message import YandexMessageAdapter

        msg = YandexMessageAdapter({"text": "hi"})
        assert msg.from_user is None
        assert msg.chat is None

    async def test_answer(self):
        from obabot.adapters.yandex_message import YandexMessageAdapter

        bot = AsyncMock()
        bot.send_message = AsyncMock(return_value={"ok": True})
        msg = YandexMessageAdapter(self._make_raw(), bot=bot)

        await msg.answer("reply text")
        bot.send_message.assert_called_once()
        call_kwargs = bot.send_message.call_args
        assert "reply text" in str(call_kwargs)

    async def test_answer_no_bot_raises(self):
        from obabot.adapters.yandex_message import YandexMessageAdapter

        msg = YandexMessageAdapter(self._make_raw())
        with pytest.raises(NotImplementedError):
            await msg.answer("hi")

    async def test_reply_delegates_to_answer(self):
        from obabot.adapters.yandex_message import YandexMessageAdapter

        bot = AsyncMock()
        bot.send_message = AsyncMock(return_value={"ok": True})
        msg = YandexMessageAdapter(self._make_raw(), bot=bot)

        await msg.reply("reply")
        bot.send_message.assert_called_once()

    async def test_edit_text(self):
        from obabot.adapters.yandex_message import YandexMessageAdapter

        bot = AsyncMock()
        bot.edit_message_text = AsyncMock(return_value={"ok": True})
        msg = YandexMessageAdapter(self._make_raw(), bot=bot)

        await msg.edit_text("new text")
        bot.edit_message_text.assert_called_once()

    async def test_delete_returns_none(self):
        from obabot.adapters.yandex_message import YandexMessageAdapter

        msg = YandexMessageAdapter(self._make_raw())
        result = await msg.delete()
        assert result is None

    def test_getattr_fallback(self):
        from obabot.adapters.yandex_message import YandexMessageAdapter

        msg = YandexMessageAdapter({"custom_field": "value"})
        assert msg.custom_field == "value"

        with pytest.raises(AttributeError):
            _ = msg.nonexistent_field

    async def test_fsm_stubs(self):
        from obabot.adapters.yandex_message import YandexMessageAdapter

        msg = YandexMessageAdapter(self._make_raw())
        await msg.set_state("some")
        assert await msg.get_state() is None
        await msg.reset_state()
        await msg.update_data(key="val")
        assert await msg.get_data() == {}


# ---------------------------------------------------------------------------
# YandexCallbackQuery
# ---------------------------------------------------------------------------

class TestYandexCallbackQuery:
    def _make_raw(self, **overrides):
        raw = {
            "from": {"id": "u1", "login": "alice@corp.ru", "display_name": "Alice"},
            "chat": {"id": "c1", "type": "private"},
            "callback_data": "btn_ok",
            "message_id": 10,
            "update_id": 50,
        }
        raw.update(overrides)
        return raw

    def test_data_and_id(self):
        from obabot.adapters.yandex_callback import YandexCallbackQuery

        cb = YandexCallbackQuery(self._make_raw())
        assert cb.data == "btn_ok"
        assert cb.id == 50
        assert cb.message_id == 10

    def test_platform(self):
        from obabot.adapters.yandex_callback import YandexCallbackQuery

        cb = YandexCallbackQuery(self._make_raw())
        assert cb.platform == "yandex"

    def test_from_user(self):
        from obabot.adapters.yandex_callback import YandexCallbackQuery

        cb = YandexCallbackQuery(self._make_raw())
        assert cb.from_user is not None
        assert cb.from_user.username == "alice@corp.ru"

    def test_message_property(self):
        from obabot.adapters.yandex_callback import YandexCallbackQuery

        cb = YandexCallbackQuery(self._make_raw())
        msg = cb.message
        assert msg is not None
        assert msg.platform == "yandex"

    def test_callback_data_dict(self):
        from obabot.adapters.yandex_callback import _extract_callback_data

        assert _extract_callback_data("simple") == "simple"
        assert _extract_callback_data({"data": "inner"}) == "inner"
        assert _extract_callback_data(None) is None
        assert _extract_callback_data(42) == "42"

    def test_callback_data_dict_json(self):
        import json
        from obabot.adapters.yandex_callback import _extract_callback_data

        result = _extract_callback_data({"key": "value"})
        parsed = json.loads(result)
        assert parsed == {"key": "value"}

    async def test_answer(self):
        from obabot.adapters.yandex_callback import YandexCallbackQuery

        bot = AsyncMock()
        bot.answer_callback_query = AsyncMock(return_value={"ok": True})
        cb = YandexCallbackQuery(self._make_raw(), bot=bot)

        await cb.answer("ack")
        bot.answer_callback_query.assert_called_once()

    async def test_answer_no_bot(self):
        from obabot.adapters.yandex_callback import YandexCallbackQuery

        cb = YandexCallbackQuery(self._make_raw())
        result = await cb.answer("ack")
        assert result is None

    async def test_edit_message_text(self):
        from obabot.adapters.yandex_callback import YandexCallbackQuery

        bot = AsyncMock()
        bot.edit_message_text = AsyncMock(return_value={"ok": True})
        cb = YandexCallbackQuery(self._make_raw(), bot=bot)

        await cb.edit_message_text("updated")
        bot.edit_message_text.assert_called_once()

    async def test_delete_message_returns_none(self):
        from obabot.adapters.yandex_callback import YandexCallbackQuery

        cb = YandexCallbackQuery(self._make_raw())
        result = await cb.delete_message()
        assert result is None

    def test_repr(self):
        from obabot.adapters.yandex_callback import YandexCallbackQuery

        cb = YandexCallbackQuery(self._make_raw())
        r = repr(cb)
        assert "btn_ok" in r


# ---------------------------------------------------------------------------
# Keyboard conversion: convert_keyboard_to_yandex
# ---------------------------------------------------------------------------

class TestYandexKeyboard:
    def test_none_returns_none(self):
        from obabot.adapters.keyboard import convert_keyboard_to_yandex

        assert convert_keyboard_to_yandex(None) is None

    def test_inline_keyboard(self):
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from obabot.adapters.keyboard import convert_keyboard_to_yandex

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Yes", callback_data="yes"),
                InlineKeyboardButton(text="No", callback_data="no"),
            ],
            [
                InlineKeyboardButton(text="Link", url="https://example.com"),
            ],
        ])
        result = convert_keyboard_to_yandex(kb)

        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0]["text"] == "Yes"
        assert result[0]["callback_data"] == "yes"
        assert result[2]["url"] == "https://example.com"

    def test_unsupported_type_returns_none(self):
        from obabot.adapters.keyboard import convert_keyboard_to_yandex
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Hi")]])
        assert convert_keyboard_to_yandex(kb) is None

    def test_empty_keyboard_returns_none(self):
        from aiogram.types import InlineKeyboardMarkup
        from obabot.adapters.keyboard import convert_keyboard_to_yandex

        kb = InlineKeyboardMarkup(inline_keyboard=[])
        assert convert_keyboard_to_yandex(kb) is None


# ---------------------------------------------------------------------------
# YandexRouter
# ---------------------------------------------------------------------------

class TestYandexRouter:
    def test_register_message_handler(self):
        from obabot.platforms.yandex import YandexRouter

        router = YandexRouter()

        @router.message()
        async def handler(msg):
            pass

        assert len(router.message_handlers) == 1
        assert router.message_handlers[0][0] is handler

    def test_register_callback_handler(self):
        from obabot.platforms.yandex import YandexRouter

        router = YandexRouter()

        @router.callback_query()
        async def handler(cb):
            pass

        assert len(router.callback_handlers) == 1

    def test_callback_alias(self):
        from obabot.platforms.yandex import YandexRouter

        router = YandexRouter()

        @router.callback()
        async def handler(cb):
            pass

        assert len(router.callback_handlers) == 1

    def test_edited_message_delegates(self):
        from obabot.platforms.yandex import YandexRouter

        router = YandexRouter()

        @router.edited_message()
        async def handler(msg):
            pass

        assert len(router.message_handlers) == 1


# ---------------------------------------------------------------------------
# YandexBot (unit, no network)
# ---------------------------------------------------------------------------

class TestYandexBot:
    def test_token(self):
        from obabot.platforms.yandex import YandexBot

        bot = YandexBot("test-token")
        assert bot.token == "test-token"

    def test_session_returns_self(self):
        from obabot.platforms.yandex import YandexBot

        bot = YandexBot("t")
        assert bot.session is bot

    async def test_close_no_error(self):
        from obabot.platforms.yandex import YandexBot

        bot = YandexBot("t")
        await bot.close()


# ---------------------------------------------------------------------------
# YandexPlatform
# ---------------------------------------------------------------------------

class TestYandexPlatform:
    def test_platform_property(self):
        from obabot.platforms.yandex import YandexPlatform

        p = YandexPlatform("test-token")
        assert p.platform == BPlatform.yandex

    def test_bot_and_router(self):
        from obabot.platforms.yandex import YandexPlatform, YandexBot, YandexRouter

        p = YandexPlatform("test-token")
        assert isinstance(p.bot, YandexBot)
        assert isinstance(p.router, YandexRouter)
        assert p.dispatcher is p

    def test_add_middleware(self):
        from obabot.platforms.yandex import YandexPlatform

        p = YandexPlatform("t")
        mw = MagicMock()
        p.add_middleware("message", mw, outer=False)

        assert len(p.get_middlewares("message")) == 1
        assert p.get_middlewares("message")[0] == (mw, False)

    def test_convert_filters_command_start(self):
        from aiogram.filters import CommandStart
        from obabot.platforms.yandex import YandexPlatform

        p = YandexPlatform("t")
        converted = p.convert_filters_for_platform((CommandStart(),), "message")

        assert len(converted) == 1
        flt = converted[0]
        msg_ok = MagicMock(text="/start")
        msg_no = MagicMock(text="hello")
        assert flt(msg_ok) is True
        assert flt(msg_no) is False

    def test_convert_filters_command(self):
        from aiogram.filters import Command
        from obabot.platforms.yandex import YandexPlatform

        p = YandexPlatform("t")
        converted = p.convert_filters_for_platform((Command("help"),), "message")

        flt = converted[0]
        assert flt(MagicMock(text="/help")) is True
        assert flt(MagicMock(text="/help extra args")) is True
        assert flt(MagicMock(text="/start")) is False

    async def test_filter_check_none(self):
        from obabot.platforms.yandex import YandexPlatform

        p = YandexPlatform("t")
        assert await p._filter_check(None, MagicMock()) is True

    async def test_filter_check_callable(self):
        from obabot.platforms.yandex import YandexPlatform

        p = YandexPlatform("t")
        assert await p._filter_check(lambda m: True, MagicMock()) is True
        assert await p._filter_check(lambda m: False, MagicMock()) is False

    async def test_filter_check_command_start(self):
        from aiogram.filters import CommandStart
        from obabot.platforms.yandex import YandexPlatform

        p = YandexPlatform("t")
        msg_start = MagicMock(text="/start")
        msg_other = MagicMock(text="hello")

        assert await p._filter_check(CommandStart(), msg_start) is True
        assert await p._filter_check(CommandStart(), msg_other) is False

    async def test_dispatch_message(self):
        from obabot.platforms.yandex import YandexPlatform

        p = YandexPlatform("t")
        called = {}

        @p.router.message()
        async def handler(msg):
            called["text"] = msg.text

        update = {
            "from": {"id": "u1", "login": "a@b.ru", "display_name": "A"},
            "chat": {"id": "c1", "type": "private"},
            "text": "hello",
            "message_id": 1,
            "timestamp": 1,
        }
        await p.feed_update(update)
        assert called.get("text") == "hello"

    async def test_dispatch_callback(self):
        from obabot.platforms.yandex import YandexPlatform

        p = YandexPlatform("t")
        called = {}

        @p.router.callback_query()
        async def handler(cb):
            called["data"] = cb.data

        update = {
            "from": {"id": "u1", "login": "a@b.ru", "display_name": "A"},
            "callback_data": "btn_ok",
            "message_id": 5,
        }
        await p.feed_update(update)
        assert called.get("data") == "btn_ok"

    async def test_feed_raw_update_with_updates_array(self):
        from obabot.platforms.yandex import YandexPlatform

        p = YandexPlatform("t")
        texts = []

        @p.router.message()
        async def handler(msg):
            texts.append(msg.text)

        raw = {
            "updates": [
                {
                    "from": {"id": "u1", "login": "a@b.ru", "display_name": "A"},
                    "text": "first",
                    "message_id": 1,
                    "timestamp": 1,
                },
                {
                    "from": {"id": "u1", "login": "a@b.ru", "display_name": "A"},
                    "text": "second",
                    "message_id": 2,
                    "timestamp": 2,
                },
            ]
        }
        await p.feed_raw_update(raw)
        assert texts == ["first", "second"]

    async def test_stop_polling_no_error(self):
        from obabot.platforms.yandex import YandexPlatform

        p = YandexPlatform("t")
        await p.stop_polling()


# ---------------------------------------------------------------------------
# Factory: create_bot with yandex_token
# ---------------------------------------------------------------------------

class TestFactoryYandex:
    def test_create_bot_yandex_only(self):
        bot, dp, router = create_bot(yandex_token="ya-test-token")

        assert bot is not None
        assert dp is not None
        assert router is not None

    def test_create_bot_triple_platform(self):
        bot, dp, router = create_bot(
            tg_token="tg-test",
            max_token="max-test",
            yandex_token="ya-test",
        )
        platforms = [str(p.platform) for p in bot._platforms]
        assert "telegram" in platforms
        assert "max" in platforms
        assert "yandex" in platforms

    def test_create_bot_test_mode_ignores_yandex(self):
        bot, dp, router = create_bot(test_mode=True)
        assert bot is not None


# ---------------------------------------------------------------------------
# LazyPlatform with yandex
# ---------------------------------------------------------------------------

class TestLazyPlatformYandex:
    def test_platform_type(self):
        from obabot.platforms.lazy import LazyPlatform

        lp = LazyPlatform("yandex", "ya-token")
        assert lp.platform == BPlatform.yandex

    def test_invalid_platform_raises(self):
        from obabot.platforms.lazy import LazyPlatform

        with pytest.raises(ValueError):
            LazyPlatform("vk", "token")

    def test_lazy_init_yandex(self):
        from obabot.platforms.lazy import LazyPlatform
        from obabot.platforms.yandex import YandexPlatform

        lp = LazyPlatform("yandex", "ya-token")
        assert lp._real is None

        bot = lp.bot
        assert lp._real is not None
        assert isinstance(lp._real, YandexPlatform)

    async def test_lazy_feed_update(self):
        from obabot.platforms.lazy import LazyPlatform

        lp = LazyPlatform("yandex", "ya-token")
        called = {}

        lp._ensure_inited()
        @lp.router.message()
        async def handler(msg):
            called["text"] = msg.text

        update = {
            "from": {"id": "u1", "login": "a@b.ru", "display_name": "A"},
            "text": "lazy hello",
            "message_id": 1,
            "timestamp": 1,
        }
        await lp.feed_update(update)
        assert called.get("text") == "lazy hello"
