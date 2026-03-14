"""
Integration tests using real tokens from .env file.

These tests verify that the library works correctly with real Telegram/Max API,
but do NOT send actual messages - they only test initialization and handler registration.

Run with: pytest tests/test_integration_real.py -v
Skip with: pytest tests/ --ignore=tests/test_integration_real.py
"""

import os
import pytest
from pathlib import Path
from typing import List

# Load .env from project root (optional, for local development)
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)
except ImportError:
    pass  # In CI, tokens are set via environment variables directly

# Get real tokens
REAL_TG_TOKEN = os.getenv("TG_TOKEN")
REAL_MAX_TOKEN = os.getenv("MAX_TOKEN")

# Skip all tests if tokens not available
pytestmark = pytest.mark.skipif(
    not REAL_TG_TOKEN or not REAL_MAX_TOKEN,
    reason="Real tokens not found in .env file"
)


class HandlerTracker:
    """Track handler calls."""
    
    def __init__(self):
        self.calls: List[str] = []
    
    def record(self, name: str):
        self.calls.append(name)
    
    def count(self, name: str) -> int:
        return self.calls.count(name)
    
    def clear(self):
        self.calls = []


@pytest.fixture
def tracker():
    return HandlerTracker()


# Sample payloads (same as in test_e2e_migration.py)
TELEGRAM_START = {
    "update_id": 999888777,
    "message": {
        "message_id": 1,
        "from": {"id": 123, "is_bot": False, "first_name": "Test"},
        "chat": {"id": 123, "type": "private"},
        "date": 1640000000,
        "text": "/start"
    }
}

TELEGRAM_HELP = {
    "update_id": 999888778,
    "message": {
        "message_id": 2,
        "from": {"id": 123, "is_bot": False, "first_name": "Test"},
        "chat": {"id": 123, "type": "private"},
        "date": 1640000001,
        "text": "/help"
    }
}

TELEGRAM_TEXT = {
    "update_id": 999888779,
    "message": {
        "message_id": 3,
        "from": {"id": 123, "is_bot": False, "first_name": "Test"},
        "chat": {"id": 123, "type": "private"},
        "date": 1640000002,
        "text": "Hello world"
    }
}

MAX_START = {
    "update_type": "message_created",
    "timestamp": 1640000000000,
    "message": {
        "body": {"mid": "test_msg_1", "seq": 1, "text": "/start"},
        "sender": {"user_id": 456, "name": "TestUser"},
        "recipient": {"chat_id": 456, "chat_type": "dialog"},
        "timestamp": 1640000000000
    }
}

MAX_HELP = {
    "update_type": "message_created",
    "timestamp": 1640000001000,
    "message": {
        "body": {"mid": "test_msg_2", "seq": 2, "text": "/help"},
        "sender": {"user_id": 456, "name": "TestUser"},
        "recipient": {"chat_id": 456, "chat_type": "dialog"},
        "timestamp": 1640000001000
    }
}

MAX_TEXT = {
    "update_type": "message_created",
    "timestamp": 1640000002000,
    "message": {
        "body": {"mid": "test_msg_3", "seq": 3, "text": "Hello world"},
        "sender": {"user_id": 456, "name": "TestUser"},
        "recipient": {"chat_id": 456, "chat_type": "dialog"},
        "timestamp": 1640000002000
    }
}


@pytest.mark.integration
class TestRealTokenInitialization:
    """Test that library initializes correctly with real tokens."""
    
    @pytest.mark.asyncio
    async def test_telegram_platform_initializes(self):
        """TelegramPlatform should initialize with real token."""
        from obabot import create_bot
        
        bot, dp, router = create_bot(tg_token=REAL_TG_TOKEN)
        
        assert bot is not None
        assert dp is not None
        assert router is not None
        
        await bot.close()
    
    @pytest.mark.asyncio
    async def test_max_platform_initializes(self):
        """MaxPlatform should initialize with real token."""
        from obabot import create_bot
        
        bot, dp, router = create_bot(max_token=REAL_MAX_TOKEN)
        
        assert bot is not None
        assert dp is not None
        assert router is not None
        
        await bot.close()
    
    @pytest.mark.asyncio
    async def test_dual_platform_initializes(self):
        """Both platforms should initialize together."""
        from obabot import create_bot
        
        bot, dp, router = create_bot(
            tg_token=REAL_TG_TOKEN,
            max_token=REAL_MAX_TOKEN
        )
        
        assert bot is not None
        assert len(dp._platforms) == 2
        
        await bot.close()


@pytest.mark.integration
class TestRealTokenHandlerExecution:
    """Test handler execution with real tokens (no actual API calls)."""
    
    @pytest.mark.asyncio
    async def test_telegram_handler_executes_once(self, tracker):
        """CRITICAL: Handler should execute exactly once with real token."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(tg_token=REAL_TG_TOKEN)
        
        @router.message(CommandStart())
        async def start_handler(message):
            tracker.record("start")
        
        await dp.feed_raw_update(update=TELEGRAM_START, platform="telegram")
        
        assert tracker.count("start") == 1, \
            f"Handler called {tracker.count('start')} times, expected 1"
        
        await bot.close()
    
    @pytest.mark.asyncio
    async def test_max_handler_executes_once(self, tracker):
        """CRITICAL: Max handler should execute exactly once with real token."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(max_token=REAL_MAX_TOKEN)
        
        @router.message(CommandStart())
        async def start_handler(message):
            tracker.record("start")
        
        await dp.feed_raw_update(update=MAX_START, platform="max")
        
        assert tracker.count("start") == 1, \
            f"Handler called {tracker.count('start')} times, expected 1"
        
        await bot.close()
    
    @pytest.mark.asyncio
    async def test_dual_platform_handlers_execute_correctly(self, tracker):
        """CRITICAL: Same handler should work on both platforms."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(
            tg_token=REAL_TG_TOKEN,
            max_token=REAL_MAX_TOKEN
        )
        
        @router.message(CommandStart())
        async def start_handler(message):
            platform = getattr(message, 'platform', 'unknown')
            tracker.record(f"start_{platform}")
        
        # Telegram
        await dp.feed_raw_update(update=TELEGRAM_START, platform="telegram")
        
        # Max
        await dp.feed_raw_update(update=MAX_START, platform="max")
        
        assert tracker.count("start_telegram") == 1, "Telegram handler should be called once"
        assert tracker.count("start_max") == 1, "Max handler should be called once"
        
        await bot.close()


@pytest.mark.integration
class TestRealTokenFilterBehavior:
    """Test that filters work correctly with real tokens."""
    
    @pytest.mark.asyncio
    async def test_telegram_filter_rejects_non_matching(self, tracker):
        """CommandStart should reject /help on Telegram."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(tg_token=REAL_TG_TOKEN)
        
        @router.message(CommandStart())
        async def start_handler(message):
            tracker.record("start")
        
        # Send /help - should NOT trigger start_handler
        await dp.feed_raw_update(update=TELEGRAM_HELP, platform="telegram")
        
        assert tracker.count("start") == 0, \
            "CommandStart should NOT match /help"
        
        await bot.close()
    
    @pytest.mark.asyncio
    async def test_max_filter_rejects_non_matching(self, tracker):
        """CommandStart should reject /help on Max."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(max_token=REAL_MAX_TOKEN)
        
        @router.message(CommandStart())
        async def start_handler(message):
            tracker.record("start")
        
        # Send /help - should NOT trigger start_handler
        await dp.feed_raw_update(update=MAX_HELP, platform="max")
        
        assert tracker.count("start") == 0, \
            "CommandStart should NOT match /help"
        
        await bot.close()
    
    @pytest.mark.asyncio
    async def test_max_filter_rejects_plain_text(self, tracker):
        """CommandStart should reject plain text on Max."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(max_token=REAL_MAX_TOKEN)
        
        @router.message(CommandStart())
        async def start_handler(message):
            tracker.record("start")
        
        # Send plain text - should NOT trigger start_handler
        await dp.feed_raw_update(update=MAX_TEXT, platform="max")
        
        assert tracker.count("start") == 0, \
            "CommandStart should NOT match plain text"
        
        await bot.close()


@pytest.mark.integration
class TestRealTokenFirstMatchOnly:
    """Test that only first matching handler is called."""
    
    @pytest.mark.asyncio
    async def test_max_first_match_only(self, tracker):
        """CRITICAL: Only first matching handler should be called on Max."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(max_token=REAL_MAX_TOKEN)
        
        @router.message(CommandStart())
        async def start_handler_1(message):
            tracker.record("start_1")
        
        @router.message(CommandStart())
        async def start_handler_2(message):
            tracker.record("start_2")
        
        @router.message()
        async def catch_all(message):
            tracker.record("catch_all")
        
        await dp.feed_raw_update(update=MAX_START, platform="max")
        
        assert tracker.count("start_1") == 1, "First handler should be called"
        assert tracker.count("start_2") == 0, "Second handler should NOT be called"
        assert tracker.count("catch_all") == 0, "Catch-all should NOT be called"
        
        await bot.close()
    
    @pytest.mark.asyncio
    async def test_repeated_updates_stable_handler_count(self, tracker):
        """CRITICAL: Multiple updates should not cause handler duplication."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(max_token=REAL_MAX_TOKEN)
        
        @router.message(CommandStart())
        async def start_handler(message):
            tracker.record("start")
        
        # Send 5 /start updates
        for i in range(5):
            update = dict(MAX_START)
            update["message"] = dict(update["message"])
            update["message"]["body"] = dict(update["message"]["body"])
            update["message"]["body"]["mid"] = f"msg_{i}"
            await dp.feed_raw_update(update=update, platform="max")
        
        # Should be exactly 5 calls, not 5+10+15+... (handler duplication bug)
        assert tracker.count("start") == 5, \
            f"Expected 5 calls, got {tracker.count('start')} (handler duplication bug!)"
        
        await bot.close()


@pytest.mark.integration
class TestRealTokenMessageParsing:
    """Test that message text is correctly parsed with real tokens."""
    
    @pytest.mark.asyncio
    async def test_max_message_text_extracted(self, tracker):
        """CRITICAL: Message text should be correctly extracted for Max."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(max_token=REAL_MAX_TOKEN)
        
        received_text = []
        
        @router.message(CommandStart())
        async def start_handler(message):
            received_text.append(message.text)
            tracker.record("start")
        
        await dp.feed_raw_update(update=MAX_START, platform="max")
        
        assert tracker.count("start") == 1, "Handler should be called"
        assert len(received_text) == 1, "Should receive one message"
        assert received_text[0] == "/start", \
            f"Message text should be '/start', got {received_text[0]!r}"
        
        await bot.close()
    
    @pytest.mark.asyncio
    async def test_telegram_message_text_extracted(self):
        """Message text should be correctly extracted for Telegram."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(tg_token=REAL_TG_TOKEN)
        
        received_text = []
        
        @router.message(CommandStart())
        async def start_handler(message):
            received_text.append(message.text)
        
        await dp.feed_raw_update(update=TELEGRAM_START, platform="telegram")
        
        assert len(received_text) == 1, "Should receive one message"
        assert received_text[0] == "/start", \
            f"Message text should be '/start', got {received_text[0]!r}"
        
        await bot.close()
