"""
Example: Dual-platform bot using obabot.

This example shows how to create a bot that works on BOTH
Telegram and Max simultaneously with the SAME code!

The only difference from single-platform examples is that
we pass BOTH tokens to create_bot().

To run:
    1. Set TG_TOKEN and MAX_TOKEN environment variables
    2. Run: python dual_platform.py
    
The bot will start polling on both platforms in parallel.
"""

import asyncio
import os
import logging

# === obabot IMPORTS (same as other examples) ===
from obabot import create_bot
from obabot.filters import Command, F
from obabot.fsm import State, StatesGroup, FSMContext, MemoryStorage
from obabot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Configure logging
logging.basicConfig(level=logging.INFO)


# === INITIALIZATION (both tokens = dual-platform mode) ===
TG_TOKEN = os.getenv("TG_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
MAX_TOKEN = os.getenv("MAX_TOKEN", "YOUR_MAX_BOT_TOKEN")

# Create bot with shared FSM storage for both platforms
# You can also use RedisStorage for persistence:
#   from obabot.fsm import RedisStorage
#   fsm_storage = RedisStorage(redis=redis_client)
bot, dp, router = create_bot(
    tg_token=TG_TOKEN,
    max_token=MAX_TOKEN,
    fsm_storage=MemoryStorage()  # Shared storage for both platforms
)


# === FSM STATES (same as other examples) ===
class Form(StatesGroup):
    waiting_name = State()
    waiting_age = State()


# === HANDLERS (100% identical - works on BOTH platforms!) ===

@router.message(Command("start"))
async def cmd_start(message):
    """
    Handle /start command.
    
    This handler works on BOTH Telegram and Max!
    Use message.platform to detect which platform the message came from.
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Регистрация", callback_data="register"),
            InlineKeyboardButton(text="ℹ️ О боте", callback_data="about"),
        ]
    ])
    
    # message.platform tells you which platform this message is from
    platform_emoji = "📱" if message.platform == "telegram" else "💬"
    
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        f"{platform_emoji} Ты пишешь из: {message.platform.upper()}\n\n"
        "Этот бот работает одновременно на Telegram и Max!\n"
        "Выбери действие:",
        reply_markup=keyboard
    )


@router.message(Command("help"))
async def cmd_help(message):
    """Handle /help command."""
    await message.answer(
        "📚 Доступные команды:\n\n"
        "/start - Начать работу\n"
        "/help - Показать справку\n"
        "/platform - Показать текущую платформу\n"
        "/cancel - Отменить текущее действие"
    )


@router.message(Command("platform"))
async def cmd_platform(message):
    """Show current platform info."""
    await message.answer(
        f"🔍 Информация о платформе:\n\n"
        f"Платформа: {message.platform}\n"
        f"Chat ID: {message.chat.id}\n"
        f"User ID: {message.from_user.id}"
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
        "obabot позволяет писать код ОДИН раз и запускать\n"
        "его на Telegram и Max ОДНОВРЕМЕННО!\n\n"
        f"Сейчас ты пишешь из: {callback.message.platform.upper()}"
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
        f"Возраст: {age}\n"
        f"Платформа: {message.platform}"
    )


@router.message(Command("cancel"))
async def cmd_cancel(message, state: FSMContext):
    """Cancel current state."""
    await state.clear()
    await message.answer("Действие отменено.")


@router.message()
async def echo(message):
    """Echo all other messages with platform info."""
    await message.answer(
        f"[{message.platform.upper()}] Эхо: {message.text}"
    )


# === MAIN ===

async def main():
    """
    Start the bot on both platforms.
    
    dp.start_polling() automatically starts polling for
    ALL configured platforms in parallel!
    """
    logging.info("Starting dual-platform bot (Telegram + Max)...")
    logging.info("Bot will respond to messages from both platforms!")
    
    # This single call starts BOTH platforms
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

