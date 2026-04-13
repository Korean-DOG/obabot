"""Mirror test_webhook_telegram: feed_webhook with real Max token."""

import time

import pytest

from obabot import create_bot
from obabot.filters import CommandStart


@pytest.mark.e2e
@pytest.mark.max
@pytest.mark.asyncio
async def test_webhook_start_command_via_proxy_dp_max(max_token, skip_if_no_max_token):
    """
    ProxyDispatcher.feed_webhook routes a Max /start update to a handler
    registered via ProxyRouter.message(CommandStart()).
    """
    bot, dp, router = create_bot(max_token=max_token)

    called = False
    received_text = None

    @router.message(CommandStart())
    async def handle_start(message):
        nonlocal called, received_text
        called = True
        received_text = message.text

    update = {
        "update_type": "message_created",
        "timestamp": int(time.time()) * 1000,
        "message": {
            "body": {
                "mid": "msg_webhook_test",
                "seq": 1,
                "text": "/start",
            },
            "sender": {
                "user_id": 123456,
                "name": "WebhookTest",
            },
            "recipient": {
                "chat_id": 123456,
                "chat_type": "dialog",
            },
            "timestamp": int(time.time()) * 1000,
        },
    }

    await dp.feed_webhook(body=update, event=None, bot=bot)

    assert called is True
    assert received_text == "/start"

    await bot.close()
