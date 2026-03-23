"""Minimal example: Telegram + Max + Web PWA on one dispatcher.

Run:
    pip install obabot[web]
    python examples/web_demo.py

Then open http://localhost:8000/ in a browser — you'll see a simple chat UI
that is also installable as a PWA on mobile devices.
"""

import asyncio
import os

import uvicorn

from obabot import create_bot
from obabot.fsm import MemoryStorage, State, StatesGroup
from obabot.web import create_web, create_mobile

# ---------------------------------------------------------------------------
# FSM states
# ---------------------------------------------------------------------------

class Form(StatesGroup):
    waiting_name = State()
    waiting_age = State()


# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------

TG_TOKEN = os.getenv("TG_TOKEN", "")
MAX_TOKEN = os.getenv("MAX_TOKEN", "")

storage = MemoryStorage()

# In a real project you'd pass real tokens.  For this demo we allow empty
# tokens so the web layer can be tested standalone.
if TG_TOKEN or MAX_TOKEN:
    bot, dp, router = create_bot(
        tg_token=TG_TOKEN or None,
        max_token=MAX_TOKEN or None,
        fsm_storage=storage,
    )
else:
    # Test mode — no tokens, no Telegram/Max network calls
    bot, dp, router = create_bot(test_mode=True, fsm_storage=storage)


# ---------------------------------------------------------------------------
# Handlers (work on Telegram, Max, AND web without changes)
# ---------------------------------------------------------------------------

from aiogram.filters import Command, CommandStart


@router.message(CommandStart())
async def cmd_start(message):
    await message.answer(
        "Привет! Я бот-пример.\n"
        "Напиши /form чтобы начать форму, или любой текст — я его верну.",
    )


@router.message(Command("form"))
async def cmd_form(message, state=None):
    if state:
        await state.set_state(Form.waiting_name)
    else:
        await message.set_state(Form.waiting_name)
    await message.answer("Как тебя зовут?")


@router.message(Form.waiting_name)
async def process_name(message, state=None):
    name = message.text
    if state:
        await state.update_data(name=name)
        await state.set_state(Form.waiting_age)
    else:
        await message.update_data(name=name)
        await message.set_state(Form.waiting_age)
    await message.answer(f"Приятно познакомиться, {name}! Сколько тебе лет?")


@router.message(Form.waiting_age)
async def process_age(message, state=None):
    data = await (state.get_data() if state else message.get_data())
    name = data.get("name", "?")
    age = message.text
    if state:
        await state.clear()
    else:
        await message.reset_state()
    await message.answer(f"Записано: {name}, {age} лет. Спасибо!")


@router.message()
async def echo(message):
    await message.answer(f"Эхо: {message.text}")


# ---------------------------------------------------------------------------
# Web + PWA
# ---------------------------------------------------------------------------

web_app = create_web(dp, base_path="/api")
mobile_app = create_mobile(
    web_app,
    name="Бот-пример obabot",
    short_name="ObaBot",
    icons="/static/icons/",
    theme_color="#4a76a8",
    offline_enabled=True,
)


# ---------------------------------------------------------------------------
# Run everything together
# ---------------------------------------------------------------------------

async def main():
    # Start polling only if real tokens were provided
    if TG_TOKEN or MAX_TOKEN:
        bot_task = asyncio.create_task(dp.start_polling(bot))
    else:
        bot_task = None

    config = uvicorn.Config(mobile_app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

    if bot_task:
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
