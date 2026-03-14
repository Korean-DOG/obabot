"""
Example: The SAME bot migrated from aiogram to obabot

This is the EXACT same bot as aiogram_original.py,
but migrated to obabot. Notice how LITTLE changed!

CHANGES MADE:
1. Changed imports (from aiogram to obabot)
2. Changed initialization (from Bot/Dispatcher/Router to create_bot)
3. Everything else is IDENTICAL!
"""

import asyncio
import os
import logging

# === obabot IMPORTS (changed from aiogram) ===
from obabot import create_bot
from obabot.filters import Command, F
from obabot.fsm import State, StatesGroup, FSMContext
from obabot.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# === INITIALIZATION (ONLY THIS CHANGED!) ===
TG_TOKEN = os.getenv("TG_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

# BEFORE (aiogram):
# bot = Bot(token=TG_TOKEN)
# dp = Dispatcher()
# router = Router()
# dp.include_router(router)

# AFTER (obabot):
bot, dp, router = create_bot(tg_token=TG_TOKEN)
# That's it! One line instead of four!


# === FSM STATES (IDENTICAL - no changes) ===
class RegistrationForm(StatesGroup):
    waiting_name = State()
    waiting_email = State()
    waiting_phone = State()


# === HANDLERS (100% IDENTICAL - no changes at all!) ===

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Handle /start command."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Регистрация", callback_data="register"),
            InlineKeyboardButton(text="ℹ️ Информация", callback_data="info"),
        ],
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="stats"),
        ]
    ])
    
    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "Добро пожаловать в бота!\n\n"
        "Выберите действие:",
        reply_markup=keyboard
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command."""
    await message.answer(
        "📚 Доступные команды:\n\n"
        "/start - Начать работу с ботом\n"
        "/help - Показать эту справку\n"
        "/cancel - Отменить текущее действие\n"
        "/reset - Сбросить все данные"
    )


@router.callback_query(F.data == "register")
async def on_register(callback: CallbackQuery, state: FSMContext):
    """Handle registration button click."""
    await state.set_state(RegistrationForm.waiting_name)
    await callback.message.answer("Как тебя зовут?")
    await callback.answer()


@router.callback_query(F.data == "info")
async def on_info(callback: CallbackQuery):
    """Handle info button click."""
    await callback.message.answer(
        "ℹ️ Информация о боте:\n\n"
        "Этот бот написан на obabot\n"
        "Использует FSM для управления состояниями\n"
        "Поддерживает inline-клавиатуры\n\n"
        "Теперь можно легко переключиться на Max!"
    )
    await callback.answer()


@router.callback_query(F.data == "stats")
async def on_stats(callback: CallbackQuery):
    """Handle stats button click."""
    await callback.message.answer(
        "📊 Статистика:\n\n"
        "Пользователей: 0\n"
        "Сообщений: 0\n"
        "Регистраций: 0"
    )
    await callback.answer()


@router.message(RegistrationForm.waiting_name)
async def process_name(message: Message, state: FSMContext):
    """Process user's name."""
    if len(message.text) < 2:
        await message.answer("Имя слишком короткое. Введите имя еще раз:")
        return
    
    await state.update_data(name=message.text)
    await state.set_state(RegistrationForm.waiting_email)
    await message.answer(f"Отлично, {message.text}! Теперь введите email:")


@router.message(RegistrationForm.waiting_email)
async def process_email(message: Message, state: FSMContext):
    """Process user's email."""
    if "@" not in message.text:
        await message.answer("Некорректный email. Введите email еще раз:")
        return
    
    await state.update_data(email=message.text)
    await state.set_state(RegistrationForm.waiting_phone)
    await message.answer("Теперь введите номер телефона:")


@router.message(RegistrationForm.waiting_phone)
async def process_phone(message: Message, state: FSMContext):
    """Process user's phone."""
    if not message.text.replace("+", "").replace("-", "").replace(" ", "").isdigit():
        await message.answer("Некорректный номер телефона. Введите номер еще раз:")
        return
    
    data = await state.get_data()
    name = data.get("name", "не указано")
    email = data.get("email", "не указано")
    
    await state.clear()
    await message.answer(
        f"✅ Регистрация завершена!\n\n"
        f"📝 Ваши данные:\n"
        f"Имя: {name}\n"
        f"Email: {email}\n"
        f"Телефон: {message.text}\n\n"
        f"Спасибо за регистрацию!"
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Cancel current state."""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нет активных действий для отмены.")
        return
    
    await state.clear()
    await message.answer("Действие отменено.")


@router.message(Command("reset"))
async def cmd_reset(message: Message, state: FSMContext):
    """Reset all data."""
    await state.clear()
    await message.answer("Все данные сброшены.")


@router.message(F.text)
async def echo_text(message: Message):
    """Echo text messages."""
    await message.answer(f"Вы написали: {message.text}")


@router.message(F.photo)
async def echo_photo(message: Message):
    """Handle photo messages."""
    await message.answer("Вы отправили фото!")


# === MAIN (IDENTICAL - no changes) ===

async def main():
    """Start the bot."""
    logger.info("Starting obabot bot (migrated from aiogram)...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


# ============================================================================
# MIGRATION SUMMARY
# ============================================================================
#
# WHAT CHANGED:
# ------------
# 1. Imports:
#    - from aiogram import ... → from obabot import ...
#    - from aiogram.filters import ... → from obabot.filters import ...
#    - from aiogram.fsm import ... → from obabot.fsm import ...
#
# 2. Initialization:
#    BEFORE:
#        bot = Bot(token=TG_TOKEN)
#        dp = Dispatcher()
#        router = Router()
#        dp.include_router(router)
#    
#    AFTER:
#        bot, dp, router = create_bot(tg_token=TG_TOKEN)
#
# WHAT DIDN'T CHANGE:
# ------------------
# - All handlers (100% identical)
# - All decorators (@router.message, @router.callback_query)
# - All filters (Command, F, State)
# - All FSM logic (StatesGroup, FSMContext)
# - All message methods (answer, reply, etc.)
# - All keyboard creation
# - All business logic
#
# TO SWITCH TO MAX:
# ----------------
# Just change one line:
#    bot, dp, router = create_bot(max_token=MAX_TOKEN)
#
# TO RUN ON BOTH PLATFORMS:
# ------------------------
# Just change one line:
#    bot, dp, router = create_bot(tg_token=TG_TOKEN, max_token=MAX_TOKEN)
#
# ============================================================================

