import json
import time

import pytest

from obabot import create_bot
from obabot.filters import CommandStart


@pytest.mark.e2e
@pytest.mark.telegram
@pytest.mark.asyncio
async def test_webhook_start_command_via_proxy_dp(tg_token, skip_if_no_tg_token):
    """
    Ensure that ProxyDispatcher.feed_webhook correctly routes a Telegram /start
    update to a handler registered via ProxyRouter.message(CommandStart()).
    """
    bot, dp, router = create_bot(tg_token=tg_token)

    called = False
    received_text = None

    @router.message(CommandStart())
    async def handle_start(message):
        nonlocal called, received_text
        called = True
        received_text = message.text

    # Minimal realistic Telegram update dict for /start
    update = {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "date": int(time.time()),
            "chat": {"id": 123456, "type": "private"},
            "from": {"id": 123456, "is_bot": False, "first_name": "Test"},
            "text": "/start",
            "entities": [
                {"type": "bot_command", "offset": 0, "length": 6},
            ],
        },
    }

    # Simulate webhook call: body is already parsed JSON dict
    result = await dp.feed_webhook(body=update, event=None, bot=bot)

    # aiogram returns sentinel.UNHANDLED when no handler matched.
    # Here we only assert that our handler was invoked.
    assert called is True
    assert received_text == "/start"

    await bot.close()

