"""
Example: Telegram-only bot using obabot.

This example shows how to create a bot that works only on Telegram.
The code is almost identical to aiogram, with only the imports
and initialization being different.

To run:
    1. Set your Telegram bot token as TG_TOKEN environment variable
    2. Run: python telegram_only.py
"""

import asyncio
import os
import logging

# === obabot IMPORTS (instead of aiogram) ===
from obabot import create_bot
from obabot.filters import Command, F
from obabot.fsm import State, StatesGroup, FSMContext
from obabot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Configure logging
logging.basicConfig(level=logging.INFO)


# === INITIALIZATION (the only difference from aiogram) ===
TG_TOKEN = os.getenv("TG_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
bot, dp, router = create_bot(tg_token=TG_TOKEN)


# === FSM STATES (identical to aiogram) ===
class Form(StatesGroup):
    waiting_name = State()
    waiting_age = State()


# === HANDLERS (100% identical to aiogram) ===
# You can use either router.message() or dp.message() - both work!

@router.message(Command("start"))
# OR: @dp.message(Command("start"))  # Both work identically!
async def cmd_start(message):
    """Handle /start command."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Регистрация", callback_data="register"),
            InlineKeyboardButton(text="ℹ️ О боте", callback_data="about"),
        ]
    ])
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        f"Я работаю на платформе: {message.platform}\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )


@router.message(Command("help"))
async def cmd_help(message):
    """Handle /help command."""
    await message.answer(
        "📚 Доступные команды:\n\n"
        "/start - Начать работу\n"
        "/help - Показать справку\n"
        "/cancel - Отменить текущее действие"
    )


@router.callback_query(F.data == "register")
async def on_register(callback, state: FSMContext):
    """Handle registration button click."""
    await state.set_state(Form.waiting_name)
    await callback.message.answer("Как тебя зовут?")
    await callback.answer()


@router.callback_query(F.data == "about")
async def on_about(callback):
    """Handle about button click."""
    await callback.message.answer(
        "🤖 Этот бот создан с помощью библиотеки obabot.\n\n"
        "obabot позволяет писать код один раз и запускать\n"
        "его на Telegram и Max без изменений!"
    )
    await callback.answer()


@router.message(Form.waiting_name)
async def process_name(message, state: FSMContext):
    """Process user's name."""
    await state.update_data(name=message.text)
    await state.set_state(Form.waiting_age)
    await message.answer(f"Отлично, {message.text}! Сколько тебе лет?")


@router.message(Form.waiting_age)
async def process_age(message, state: FSMContext):
    """Process user's age."""
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите число.")
        return
    
    data = await state.get_data()
    name = data.get("name", "друг")
    age = int(message.text)
    
    await state.clear()
    await message.answer(
        f"✅ Регистрация завершена!\n\n"
        f"Имя: {name}\n"
        f"Возраст: {age}"
    )


@router.message(Command("cancel"))
async def cmd_cancel(message, state: FSMContext):
    """Cancel current state."""
    await state.clear()
    await message.answer("Действие отменено.")


@router.message()
async def echo(message):
    """Echo all other messages."""
    await message.answer(f"Эхо: {message.text}")


# === MAIN (identical to aiogram) ===

async def main():
    """Start the bot."""
    logging.info("Starting Telegram bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

