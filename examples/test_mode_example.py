"""
Example: using test mode for testing without real tokens or network.

The same app code works in production (with token) and in tests (test_mode=True).
In test mode create_bot() returns (StubBot, aiogram.Dispatcher, aiogram.Router).
The router is an instance and is already included in the dispatcher, so you do
not need to call dp.include_router(router) in tests. When feeding updates in
tests, pass MockBot (e.g. from aiogram-test-framework), not the stub_bot from
create_bot(), so handlers do not hit Telegram and you avoid TelegramUnauthorizedError.

Run without token (test mode):
    set TESTING=1
    python test_mode_example.py

Run with token (normal mode):
    set TG_TOKEN=your_token
    python test_mode_example.py

From repo root (so obabot is current): pip install -e .  then run as above.
"""

import asyncio
import os

from obabot import create_bot
from obabot.filters import Command

# Test mode: TESTING=1 or no token (for local run without token)
TESTING = os.environ.get("TESTING") == "1"
TG_TOKEN = os.environ.get("TG_TOKEN", "")

if TESTING or not TG_TOKEN:
    bot, dp, router = create_bot(test_mode=True)
else:
    bot, dp, router = create_bot(tg_token=TG_TOKEN)


@router.message(Command("start"))
async def cmd_start(message):
    await message.answer("Привет! Это тестовый режим — без реального бота.")


@router.message(Command("help"))
async def cmd_help(message):
    await message.answer("Доступные команды: /start, /help")


async def main():
    if getattr(bot, "id", None) is None and hasattr(bot, "token") and bot.token.startswith("test:"):
        # Test mode: no polling, just show that everything is ready
        print("Test mode: bot, dp, router created (no token, no network).")
        print("Router is already in dp; when feeding updates use MockBot to avoid TelegramUnauthorizedError.")
        return
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


# ---------------------------------------------------------------------------
# How to use in your tests (e.g. with pytest, optionally aiogram-test-framework)
# ---------------------------------------------------------------------------
#
# 1) In your app (main): same as above — create_bot(..., test_mode=os.getenv("TESTING")=="1")
#    and register all handlers on router.
#
# 2) In tests use the dispatcher from create_bot; router is already included:
#
#    bot, dp, router = create_bot(test_mode=True)
#    # dp.include_router(router) не нужен — роутер уже в dp (экземпляр, не класс).
#    # При прогоне апдейтов передавайте MockBot (из aiogram-test-framework),
#    # а не bot из create_bot, чтобы хендлеры не ходили в Telegram и не было
#    # TelegramUnauthorizedError:
#    # await dp.feed_update(mock_bot, update)
#
# 3) Минимальная проверка в pytest:
#
#    def test_dp_ready():
#        bot, dp, router = create_bot(test_mode=True)
#        assert router.parent_router is not None  # уже в dp
