"""Pytest configuration and fixtures."""

import pytest
import os
from pathlib import Path
from typing import Optional

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not installed, use system env vars

from obabot import create_bot
from aiogram import Bot, Dispatcher, Router


@pytest.fixture
def tg_token() -> Optional[str]:
    """Get Telegram test token from environment."""
    return os.getenv("TG_TOKEN") or os.getenv("TG_TEST_TOKEN")


@pytest.fixture
def max_token() -> Optional[str]:
    """Get Max test token from environment."""
    return os.getenv("MAX_TOKEN") or os.getenv("MAX_TEST_TOKEN")


@pytest.fixture
def skip_if_no_tg_token(tg_token):
    """Skip test if Telegram token is not available."""
    if not tg_token:
        pytest.skip("Telegram token not available")


@pytest.fixture
def skip_if_no_max_token(max_token):
    """Skip test if Max token is not available."""
    if not max_token:
        pytest.skip("Max token not available")


@pytest.fixture
async def obabot_telegram_bot(tg_token, skip_if_no_tg_token):
    """Create obabot instance for Telegram."""
    bot, dp, router = create_bot(tg_token=tg_token)
    yield bot, dp, router
    await bot.close()


@pytest.fixture
async def obabot_max_bot(max_token, skip_if_no_max_token):
    """Create obabot instance for Max."""
    bot, dp, router = create_bot(max_token=max_token)
    yield bot, dp, router
    await bot.close()


@pytest.fixture
async def obabot_dual_bot(tg_token, max_token):
    """Create obabot instance for both platforms."""
    if not tg_token or not max_token:
        pytest.skip("Both tokens required for dual platform test")
    bot, dp, router = create_bot(tg_token=tg_token, max_token=max_token)
    yield bot, dp, router
    await bot.close()


@pytest.fixture
async def aiogram_bot(tg_token, skip_if_no_tg_token):
    """Create original aiogram bot for comparison."""
    bot = Bot(token=tg_token)
    dp = Dispatcher()
    router = Router()
    dp.include_router(router)
    yield bot, dp, router
    await bot.session.close()

