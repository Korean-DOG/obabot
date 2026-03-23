"""
Example: Triple-platform bot using obabot.

This example shows how to create a bot that works on Telegram,
Max, AND Yandex Messenger simultaneously with the SAME code!

To run:
    1. Set TG_TOKEN, MAX_TOKEN, YANDEX_TOKEN environment variables
    2. Run: python triple_platform.py

The bot will start polling on all three platforms in parallel.
"""

import asyncio
import os
import logging

from obabot import create_bot
from obabot.filters import Command, F
from obabot.fsm import State, StatesGroup, FSMContext, MemoryStorage
from obabot.types import InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(level=logging.INFO)

TG_TOKEN = os.getenv("TG_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
MAX_TOKEN = os.getenv("MAX_TOKEN", "YOUR_MAX_BOT_TOKEN")
YANDEX_TOKEN = os.getenv("YANDEX_TOKEN", "YOUR_YANDEX_BOT_TOKEN")

bot, dp, router = create_bot(
    tg_token=TG_TOKEN,
    max_token=MAX_TOKEN,
    yandex_token=YANDEX_TOKEN,
    fsm_storage=MemoryStorage(),
)


class Form(StatesGroup):
    waiting_name = State()


@router.message(Command("start"))
async def cmd_start(message):
    """Works identically on Telegram, Max, and Yandex Messenger."""
    platform = getattr(message, "platform", "unknown")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Регистрация", callback_data="register"),
            InlineKeyboardButton(text="О боте", callback_data="about"),
        ]
    ])
    await message.answer(
        f"Привет, {message.from_user.first_name}!\n"
        f"Ты пишешь из: {platform.upper()}\n\n"
        "Этот бот работает на Telegram, Max и Яндекс Мессенджере!",
        reply_markup=keyboard,
    )


@router.callback_query(F.data == "register")
async def on_register(callback, state: FSMContext):
    await state.set_state(Form.waiting_name)
    await callback.message.answer("Как тебя зовут?")
    await callback.answer()


@router.callback_query(F.data == "about")
async def on_about(callback):
    platform = getattr(callback.message, "platform", "unknown")
    await callback.message.answer(
        "obabot — универсальная библиотека для ботов.\n"
        f"Сейчас ты общаешься через: {platform.upper()}"
    )
    await callback.answer()


@router.message(Form.waiting_name)
async def process_name(message, state: FSMContext):
    await state.clear()
    platform = getattr(message, "platform", "unknown")
    await message.answer(
        f"Приятно познакомиться, {message.text}!\n"
        f"Платформа: {platform}"
    )


@router.message()
async def echo(message):
    platform = getattr(message, "platform", "unknown")
    await message.answer(f"[{platform.upper()}] Эхо: {message.text}")


async def main():
    logging.info("Starting triple-platform bot (Telegram + Max + Yandex)...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
