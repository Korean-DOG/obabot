"""Regression tests for MAX delete_message compatibility."""

from unittest.mock import AsyncMock, Mock

import pytest


@pytest.mark.asyncio
async def test_delete_max_message_prefers_header_request():
    """Use bot._request() so MAX auth goes through Authorization header."""
    from obabot.utils.max_api import delete_max_message

    bot = Mock()
    bot._request = AsyncMock(return_value={"ok": True})
    bot.delete_message = AsyncMock(side_effect=AssertionError("native delete_message should not be used"))

    result = await delete_max_message(bot, 123)

    assert result == {"ok": True}
    bot._request.assert_awaited_once_with(
        "DELETE",
        "/messages",
        params={"message_id": "123"},
    )
    bot.delete_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_max_message_adapter_delete_uses_request_workaround():
    """message.delete() should bypass broken umaxbot delete_message()."""
    from obabot.adapters.message import MaxMessageAdapter

    msg = Mock()
    msg.id = "msg_123"
    msg.chat = Mock(id=100)

    bot = Mock()
    bot._request = AsyncMock(return_value={"deleted": True})
    bot.delete_message = AsyncMock(side_effect=AssertionError("native delete_message should not be used"))

    adapter = MaxMessageAdapter(msg, bot)
    result = await adapter.delete()

    assert result == {"deleted": True}
    bot._request.assert_awaited_once_with(
        "DELETE",
        "/messages",
        params={"message_id": "msg_123"},
    )
    bot.delete_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_proxy_bot_delete_message_on_max_uses_request_workaround():
    """ProxyBot.delete_message(platform='max') should not pass chat_id to umaxbot."""
    from obabot.proxy.bot import ProxyBot
    from obabot.types import BPlatform

    platform = Mock()
    platform.platform = BPlatform.max

    bot = Mock()
    bot._request = AsyncMock(return_value={"deleted": True})
    bot.delete_message = AsyncMock(side_effect=AssertionError("native delete_message should not be used"))
    platform.bot = bot

    proxy_bot = ProxyBot([platform])
    result = await proxy_bot.delete_message(chat_id=42, message_id=777, platform="max")

    assert result is True
    bot._request.assert_awaited_once_with(
        "DELETE",
        "/messages",
        params={"message_id": "777"},
    )
    bot.delete_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_max_callback_delete_message_uses_request_workaround():
    """callback.delete_message() should use the same MAX workaround."""
    from maxbot.types import Callback, Chat, Message, User
    from obabot.adapters.max_callback import MaxCallbackQuery

    user = User(user_id=1, name="Test")
    chat = Chat(id=2, type="dialog")
    message = Message(id="msg_cb_1", text="hello", chat=chat, sender=user)
    callback = Callback(callback_id="cb_1", payload="x", user=user, message=message)

    bot = Mock()
    bot._request = AsyncMock(return_value={"deleted": True})
    bot.delete_message = AsyncMock(side_effect=AssertionError("native delete_message should not be used"))

    extended = MaxCallbackQuery.from_callback(callback, bot)
    result = await extended.delete_message()

    assert result is True
    bot._request.assert_awaited_once_with(
        "DELETE",
        "/messages",
        params={"message_id": "msg_cb_1"},
    )
    bot.delete_message.assert_not_awaited()
