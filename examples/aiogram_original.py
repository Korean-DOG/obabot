"""
Example: Original bot written with aiogram 3.x

This is how a typical aiogram bot looks like.
We'll migrate this to obabot in the next example.
"""

import asyncio
import os
import logging

# === AIOGRAM IMPORTS ===
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# === INITIALIZATION ===
TG_TOKEN = os.getenv("TG_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")

bot = Bot(token=TG_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)


# === FSM STATES ===
class RegistrationForm(StatesGroup):
    waiting_name = State()
    waiting_email = State()
    waiting_phone = State()


# === HANDLERS ===

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
        "Этот бот написан на aiogram 3.x\n"
        "Использует FSM для управления состояниями\n"
        "Поддерживает inline-клавиатуры"
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


# === MAIN ===

async def main():
    """Start the bot."""
    logger.info("Starting aiogram bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

