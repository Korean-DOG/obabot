"""
Example: Yandex Messenger bot using obabot.

Shows how to create a bot that works on Yandex Messenger
with the same handler API as Telegram and Max.

To run:
    1. Create a bot in Yandex 360 admin panel:
       https://admin.yandex.ru/bot-platform
    2. Set YANDEX_TOKEN environment variable
    3. Run: python yandex_only.py

The bot will start long-polling for updates from Yandex Messenger.
"""

import asyncio
import os
import logging

from obabot import create_bot
from obabot.filters import Command, F
from obabot.types import InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(level=logging.INFO)

YANDEX_TOKEN = os.getenv("YANDEX_TOKEN", "YOUR_YANDEX_BOT_TOKEN")

bot, dp, router = create_bot(yandex_token=YANDEX_TOKEN)


@router.message(Command("start"))
async def cmd_start(message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="О боте", callback_data="about"),
            InlineKeyboardButton(text="Помощь", callback_data="help"),
        ]
    ])
    await message.answer(
        f"Привет, {message.from_user.first_name}!\n"
        "Я бот для Яндекс Мессенджера, созданный с помощью obabot.",
        reply_markup=keyboard,
    )


@router.message(Command("help"))
async def cmd_help(message):
    await message.answer(
        "Доступные команды:\n"
        "/start - Начать работу\n"
        "/help - Показать справку"
    )


@router.callback_query(F.data == "about")
async def on_about(callback):
    await callback.message.answer(
        "obabot — универсальная библиотека для создания ботов.\n"
        "Поддерживает Telegram, Max и Яндекс Мессенджер."
    )
    await callback.answer()


@router.callback_query(F.data == "help")
async def on_help(callback):
    await callback.message.answer("Отправьте /help для справки.")
    await callback.answer()


@router.message()
async def echo(message):
    await message.answer(f"[Яндекс] Эхо: {message.text}")


async def main():
    logging.info("Starting Yandex Messenger bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
