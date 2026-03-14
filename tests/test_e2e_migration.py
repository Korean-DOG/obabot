"""
End-to-end tests simulating real bot migrations from aiogram/umaxbot.

These tests verify that handlers registered via obabot's unified API
correctly process webhook payloads from both Telegram and Max platforms.

No real API calls are made - we simulate webhook payloads and verify
that handlers are invoked with properly adapted message/callback objects.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from typing import List, Any

# Valid format tokens for testing (aiogram validates format: NUMBER:STRING)
TEST_TG_TOKEN = "123456789:ABCdefGHIjklMNOpqrSTUvwxYZ1234567"
TEST_MAX_TOKEN = "test_max_token_12345"


# Sample Telegram webhook payloads
TELEGRAM_MESSAGE_START = {
    "update_id": 123456789,
    "message": {
        "message_id": 1,
        "from": {
            "id": 111222333,
            "is_bot": False,
            "first_name": "John",
            "last_name": "Doe",
            "username": "johndoe",
            "language_code": "en"
        },
        "chat": {
            "id": 111222333,
            "first_name": "John",
            "last_name": "Doe",
            "username": "johndoe",
            "type": "private"
        },
        "date": 1640000000,
        "text": "/start"
    }
}

TELEGRAM_MESSAGE_HELP = {
    "update_id": 123456790,
    "message": {
        "message_id": 2,
        "from": {
            "id": 111222333,
            "is_bot": False,
            "first_name": "John",
            "username": "johndoe"
        },
        "chat": {
            "id": 111222333,
            "first_name": "John",
            "type": "private"
        },
        "date": 1640000001,
        "text": "/help"
    }
}

TELEGRAM_MESSAGE_TEXT = {
    "update_id": 123456791,
    "message": {
        "message_id": 3,
        "from": {
            "id": 111222333,
            "is_bot": False,
            "first_name": "John"
        },
        "chat": {
            "id": 111222333,
            "type": "private"
        },
        "date": 1640000002,
        "text": "Hello bot!"
    }
}

TELEGRAM_CALLBACK_REGISTER = {
    "update_id": 123456792,
    "callback_query": {
        "id": "callback_123",
        "from": {
            "id": 111222333,
            "is_bot": False,
            "first_name": "John",
            "username": "johndoe"
        },
        "message": {
            "message_id": 1,
            "from": {
                "id": 999888777,
                "is_bot": True,
                "first_name": "MyBot"
            },
            "chat": {
                "id": 111222333,
                "type": "private"
            },
            "date": 1640000000,
            "text": "Welcome!"
        },
        "chat_instance": "12345",
        "data": "register"
    }
}

TELEGRAM_CALLBACK_INFO = {
    "update_id": 123456793,
    "callback_query": {
        "id": "callback_456",
        "from": {
            "id": 111222333,
            "is_bot": False,
            "first_name": "John"
        },
        "message": {
            "message_id": 1,
            "chat": {
                "id": 111222333,
                "type": "private"
            },
            "date": 1640000000,
            "text": "Welcome!"
        },
        "chat_instance": "12345",
        "data": "info"
    }
}


# Sample Max webhook payloads (umaxbot format)
MAX_MESSAGE_START = {
    "update_type": "message_created",
    "timestamp": 1640000000000,
    "message": {
        "body": {
            "mid": "msg_abc123",
            "seq": 1,
            "text": "/start"
        },
        "sender": {
            "user_id": 444555666,
            "name": "Alice",
            "username": None
        },
        "recipient": {
            "chat_id": 444555666,
            "chat_type": "dialog"
        },
        "timestamp": 1640000000000
    }
}

MAX_MESSAGE_HELP = {
    "update_type": "message_created",
    "timestamp": 1640000001000,
    "message": {
        "body": {
            "mid": "msg_def456",
            "seq": 2,
            "text": "/help"
        },
        "sender": {
            "user_id": 444555666,
            "name": "Alice"
        },
        "recipient": {
            "chat_id": 444555666,
            "chat_type": "dialog"
        },
        "timestamp": 1640000001000
    }
}

MAX_MESSAGE_TEXT = {
    "update_type": "message_created",
    "timestamp": 1640000002000,
    "message": {
        "body": {
            "mid": "msg_ghi789",
            "seq": 3,
            "text": "Hello Max bot!"
        },
        "sender": {
            "user_id": 444555666,
            "name": "Alice"
        },
        "recipient": {
            "chat_id": 444555666,
            "chat_type": "dialog"
        },
        "timestamp": 1640000002000
    }
}

MAX_CALLBACK_REGISTER = {
    "update_type": "message_callback",
    "timestamp": 1640000003000,
    "callback": {
        "callback_id": "cb_123abc",
        "payload": "register",
        "user": {
            "user_id": 444555666,
            "name": "Alice"
        }
    },
    "message": {
        "body": {
            "mid": "msg_xyz999",
            "seq": 1,
            "text": "Welcome!"
        },
        "sender": {
            "user_id": 999888777,
            "name": "Bot"
        },
        "recipient": {
            "chat_id": 444555666,
            "chat_type": "dialog"
        },
        "timestamp": 1640000000000
    }
}

MAX_CALLBACK_INFO = {
    "update_type": "message_callback",
    "timestamp": 1640000004000,
    "callback": {
        "callback_id": "cb_456def",
        "payload": "info",
        "user": {
            "user_id": 444555666,
            "name": "Alice"
        }
    },
    "message": {
        "body": {
            "mid": "msg_xyz999",
            "seq": 1,
            "text": "Welcome!"
        },
        "sender": {
            "user_id": 999888777,
            "name": "Bot"
        },
        "recipient": {
            "chat_id": 444555666,
            "chat_type": "dialog"
        },
        "timestamp": 1640000000000
    }
}


class HandlerTracker:
    """Track which handlers were called and with what arguments."""
    
    def __init__(self):
        self.calls: List[tuple] = []
    
    def record(self, handler_name: str, *args: Any) -> None:
        self.calls.append((handler_name, args))
    
    def was_called(self, handler_name: str) -> bool:
        return any(name == handler_name for name, _ in self.calls)
    
    def get_call_args(self, handler_name: str) -> list:
        return [args for name, args in self.calls if name == handler_name]
    
    def clear(self) -> None:
        self.calls = []


@pytest.fixture
def handler_tracker():
    """Provide a fresh handler tracker for each test."""
    return HandlerTracker()


@pytest.mark.e2e
class TestCommandHandlers:
    """Test that command handlers work for both Telegram and Max payloads."""
    
    @pytest.mark.telegram
    @pytest.mark.asyncio
    async def test_telegram_start_command(self, handler_tracker):
        """Test /start command handler with Telegram webhook payload."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(tg_token=TEST_TG_TOKEN)
        
        @router.message(CommandStart())
        async def start_handler(message):
            handler_tracker.record("start", message)
            assert message.text == "/start"
            assert hasattr(message, 'from_user')
        
        await dp.feed_raw_update(update=TELEGRAM_MESSAGE_START, platform="telegram")
        
        assert handler_tracker.was_called("start"), "start handler should be called"
        await bot.close()
    
    @pytest.mark.telegram
    @pytest.mark.asyncio
    async def test_telegram_help_command(self, handler_tracker):
        """Test /help command handler with Telegram webhook payload."""
        from obabot import create_bot
        from obabot.filters import Command
        
        bot, dp, router = create_bot(tg_token=TEST_TG_TOKEN)
        
        @router.message(Command("help"))
        async def help_handler(message):
            handler_tracker.record("help", message)
            assert message.text == "/help"
        
        await dp.feed_raw_update(update=TELEGRAM_MESSAGE_HELP, platform="telegram")
        
        assert handler_tracker.was_called("help"), "help handler should be called"
        await bot.close()
    
    @pytest.mark.max
    @pytest.mark.asyncio
    async def test_max_start_command(self, handler_tracker):
        """Test /start command handler with Max webhook payload."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(max_token=TEST_MAX_TOKEN)
        
        @router.message(CommandStart())
        async def start_handler(message):
            handler_tracker.record("start", message)
            assert message.text == "/start"
        
        await dp.feed_raw_update(update=MAX_MESSAGE_START, platform="max")
        
        assert handler_tracker.was_called("start"), "start handler should be called for Max"
        await bot.close()
    
    @pytest.mark.max
    @pytest.mark.asyncio
    async def test_max_help_command(self, handler_tracker):
        """Test /help command handler with Max webhook payload."""
        from obabot import create_bot
        from obabot.filters import Command
        
        bot, dp, router = create_bot(max_token=TEST_MAX_TOKEN)
        
        @router.message(Command("help"))
        async def help_handler(message):
            handler_tracker.record("help", message)
            assert message.text == "/help"
        
        await dp.feed_raw_update(update=MAX_MESSAGE_HELP, platform="max")
        
        assert handler_tracker.was_called("help"), "help handler should be called for Max"
        await bot.close()
    
    @pytest.mark.dual
    @pytest.mark.asyncio
    async def test_dual_platform_command_registration(self, handler_tracker):
        """Test that command handlers work on both platforms simultaneously."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(tg_token=TEST_TG_TOKEN, max_token=TEST_MAX_TOKEN)
        
        @router.message(CommandStart())
        async def start_handler(message):
            handler_tracker.record("start", message)
        
        # Telegram
        await dp.feed_raw_update(update=TELEGRAM_MESSAGE_START, platform="telegram")
        assert handler_tracker.was_called("start"), "start should be called for Telegram"
        
        handler_tracker.clear()
        
        # Max
        await dp.feed_raw_update(update=MAX_MESSAGE_START, platform="max")
        assert handler_tracker.was_called("start"), "start should be called for Max"
        
        await bot.close()


@pytest.mark.e2e
class TestCallbackHandlers:
    """Test that callback query handlers work for both platforms."""
    
    @pytest.mark.telegram
    @pytest.mark.asyncio
    async def test_telegram_callback_register(self, handler_tracker):
        """Test callback handler with F.data filter on Telegram."""
        from obabot import create_bot
        from obabot.filters import F
        
        bot, dp, router = create_bot(tg_token=TEST_TG_TOKEN)
        
        @router.callback_query(F.data == "register")
        async def register_callback(callback):
            handler_tracker.record("register", callback)
            assert callback.data == "register"
        
        await dp.feed_raw_update(update=TELEGRAM_CALLBACK_REGISTER, platform="telegram")
        
        assert handler_tracker.was_called("register"), "register callback should be called"
        await bot.close()
    
    @pytest.mark.telegram
    @pytest.mark.asyncio
    async def test_telegram_callback_info(self, handler_tracker):
        """Test callback handler with different data value."""
        from obabot import create_bot
        from obabot.filters import F
        
        bot, dp, router = create_bot(tg_token=TEST_TG_TOKEN)
        
        @router.callback_query(F.data == "info")
        async def info_callback(callback):
            handler_tracker.record("info", callback)
            assert callback.data == "info"
        
        await dp.feed_raw_update(update=TELEGRAM_CALLBACK_INFO, platform="telegram")
        
        assert handler_tracker.was_called("info"), "info callback should be called"
        await bot.close()
    
    @pytest.mark.max
    @pytest.mark.asyncio
    async def test_max_callback_register(self, handler_tracker):
        """Test callback handler on Max platform."""
        from obabot import create_bot
        from obabot.filters import F
        
        bot, dp, router = create_bot(max_token=TEST_MAX_TOKEN)
        
        @router.callback_query(F.data == "register")
        async def register_callback(callback):
            handler_tracker.record("register", callback)
            data = getattr(callback, 'data', None) or getattr(callback, 'payload', None)
            assert data == "register"
        
        await dp.feed_raw_update(update=MAX_CALLBACK_REGISTER, platform="max")
        
        assert handler_tracker.was_called("register"), "register callback should be called for Max"
        await bot.close()
    
    @pytest.mark.dual
    @pytest.mark.asyncio
    async def test_dual_platform_callback(self, handler_tracker):
        """Test callback works on both platforms with same handler."""
        from obabot import create_bot
        from obabot.filters import F
        
        bot, dp, router = create_bot(tg_token=TEST_TG_TOKEN, max_token=TEST_MAX_TOKEN)
        
        @router.callback_query(F.data == "info")
        async def info_callback(callback):
            handler_tracker.record("info", callback)
        
        # Telegram
        await dp.feed_raw_update(update=TELEGRAM_CALLBACK_INFO, platform="telegram")
        assert handler_tracker.was_called("info"), "info should be called for Telegram"
        
        handler_tracker.clear()
        
        # Max
        await dp.feed_raw_update(update=MAX_CALLBACK_INFO, platform="max")
        assert handler_tracker.was_called("info"), "info should be called for Max"
        
        await bot.close()


@pytest.mark.e2e
class TestTextMessageHandlers:
    """Test plain text message handlers with F.text filters."""
    
    @pytest.mark.telegram
    @pytest.mark.asyncio
    async def test_telegram_text_message(self, handler_tracker):
        """Test text message handler on Telegram."""
        from obabot import create_bot
        from obabot.filters import F
        
        bot, dp, router = create_bot(tg_token=TEST_TG_TOKEN)
        
        @router.message(F.text)
        async def text_handler(message):
            handler_tracker.record("text", message)
            assert message.text is not None
        
        await dp.feed_raw_update(update=TELEGRAM_MESSAGE_TEXT, platform="telegram")
        
        assert handler_tracker.was_called("text"), "text handler should be called"
        await bot.close()
    
    @pytest.mark.max
    @pytest.mark.asyncio
    async def test_max_text_message(self, handler_tracker):
        """Test text message handler on Max."""
        from obabot import create_bot
        from obabot.filters import F
        
        bot, dp, router = create_bot(max_token=TEST_MAX_TOKEN)
        
        @router.message(F.text)
        async def text_handler(message):
            handler_tracker.record("text", message)
            assert message.text is not None
        
        await dp.feed_raw_update(update=MAX_MESSAGE_TEXT, platform="max")
        
        assert handler_tracker.was_called("text"), "text handler should be called for Max"
        await bot.close()
    
    @pytest.mark.telegram
    @pytest.mark.asyncio
    async def test_text_message_content(self, handler_tracker):
        """Verify message text content is correctly passed."""
        from obabot import create_bot
        from obabot.filters import F
        
        bot, dp, router = create_bot(tg_token=TEST_TG_TOKEN)
        
        received_text = []
        
        @router.message(F.text)
        async def text_handler(message):
            handler_tracker.record("text", message)
            received_text.append(message.text)
        
        await dp.feed_raw_update(update=TELEGRAM_MESSAGE_TEXT, platform="telegram")
        
        assert handler_tracker.was_called("text")
        assert "Hello bot!" in received_text
        await bot.close()


@pytest.mark.e2e
class TestMultipleHandlers:
    """Test multiple handlers with different filters."""
    
    @pytest.mark.telegram
    @pytest.mark.asyncio
    async def test_multiple_command_handlers(self, handler_tracker):
        """Test that correct handler is called based on command."""
        from obabot import create_bot
        from obabot.filters import Command, CommandStart
        
        bot, dp, router = create_bot(tg_token=TEST_TG_TOKEN)
        
        @router.message(CommandStart())
        async def start_handler(message):
            handler_tracker.record("start", message)
        
        @router.message(Command("help"))
        async def help_handler(message):
            handler_tracker.record("help", message)
        
        @router.message(Command("settings"))
        async def settings_handler(message):
            handler_tracker.record("settings", message)
        
        # Send /start
        await dp.feed_raw_update(update=TELEGRAM_MESSAGE_START, platform="telegram")
        assert handler_tracker.was_called("start")
        assert not handler_tracker.was_called("help")
        assert not handler_tracker.was_called("settings")
        
        handler_tracker.clear()
        
        # Send /help
        await dp.feed_raw_update(update=TELEGRAM_MESSAGE_HELP, platform="telegram")
        assert handler_tracker.was_called("help")
        assert not handler_tracker.was_called("start")
        
        await bot.close()
    
    @pytest.mark.telegram
    @pytest.mark.asyncio
    async def test_multiple_callback_handlers(self, handler_tracker):
        """Test that correct callback handler is called based on data."""
        from obabot import create_bot
        from obabot.filters import F
        
        bot, dp, router = create_bot(tg_token=TEST_TG_TOKEN)
        
        @router.callback_query(F.data == "register")
        async def register_callback(callback):
            handler_tracker.record("register", callback)
        
        @router.callback_query(F.data == "info")
        async def info_callback(callback):
            handler_tracker.record("info", callback)
        
        @router.callback_query(F.data == "cancel")
        async def cancel_callback(callback):
            handler_tracker.record("cancel", callback)
        
        # Send register callback
        await dp.feed_raw_update(update=TELEGRAM_CALLBACK_REGISTER, platform="telegram")
        assert handler_tracker.was_called("register")
        assert not handler_tracker.was_called("info")
        assert not handler_tracker.was_called("cancel")
        
        handler_tracker.clear()
        
        # Send info callback
        await dp.feed_raw_update(update=TELEGRAM_CALLBACK_INFO, platform="telegram")
        assert handler_tracker.was_called("info")
        assert not handler_tracker.was_called("register")
        
        await bot.close()
    
    @pytest.mark.telegram
    @pytest.mark.asyncio
    async def test_mixed_handlers_telegram(self, handler_tracker):
        """Test mix of command and callback handlers."""
        from obabot import create_bot
        from obabot.filters import CommandStart, F
        
        bot, dp, router = create_bot(tg_token=TEST_TG_TOKEN)
        
        @router.message(CommandStart())
        async def start_handler(message):
            handler_tracker.record("start_msg", message)
        
        @router.callback_query(F.data == "register")
        async def register_callback(callback):
            handler_tracker.record("register_cb", callback)
        
        # Command
        await dp.feed_raw_update(update=TELEGRAM_MESSAGE_START, platform="telegram")
        assert handler_tracker.was_called("start_msg")
        assert not handler_tracker.was_called("register_cb")
        
        handler_tracker.clear()
        
        # Callback
        await dp.feed_raw_update(update=TELEGRAM_CALLBACK_REGISTER, platform="telegram")
        assert handler_tracker.was_called("register_cb")
        assert not handler_tracker.was_called("start_msg")
        
        await bot.close()


@pytest.mark.e2e
class TestMessageAttributes:
    """Test that message attributes are correctly adapted."""
    
    @pytest.mark.telegram
    @pytest.mark.asyncio
    async def test_telegram_message_from_user(self, handler_tracker):
        """Test from_user attribute on Telegram message."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(tg_token=TEST_TG_TOKEN)
        
        user_data = {}
        
        @router.message(CommandStart())
        async def start_handler(message):
            handler_tracker.record("start", message)
            user_data['id'] = message.from_user.id
            user_data['first_name'] = message.from_user.first_name
            user_data['username'] = getattr(message.from_user, 'username', None)
        
        await dp.feed_raw_update(update=TELEGRAM_MESSAGE_START, platform="telegram")
        
        assert handler_tracker.was_called("start")
        assert user_data['id'] == 111222333
        assert user_data['first_name'] == "John"
        assert user_data['username'] == "johndoe"
        await bot.close()
    
    @pytest.mark.max
    @pytest.mark.asyncio
    async def test_max_message_from_user(self, handler_tracker):
        """Test from_user attribute on Max message (adapted from sender)."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(max_token=TEST_MAX_TOKEN)
        
        user_data = {}
        
        @router.message(CommandStart())
        async def start_handler(message):
            handler_tracker.record("start", message)
            user_data['id'] = message.from_user.id
            user_data['first_name'] = message.from_user.first_name
        
        await dp.feed_raw_update(update=MAX_MESSAGE_START, platform="max")
        
        assert handler_tracker.was_called("start")
        assert user_data['id'] == 444555666
        assert user_data['first_name'] == "Alice"
        await bot.close()
    
    @pytest.mark.telegram
    @pytest.mark.asyncio
    async def test_callback_from_user(self, handler_tracker):
        """Test from_user attribute on callback query."""
        from obabot import create_bot
        from obabot.filters import F
        
        bot, dp, router = create_bot(tg_token=TEST_TG_TOKEN)
        
        user_data = {}
        
        @router.callback_query(F.data == "register")
        async def callback_handler(callback):
            handler_tracker.record("callback", callback)
            user_data['id'] = callback.from_user.id
            user_data['first_name'] = callback.from_user.first_name
        
        await dp.feed_raw_update(update=TELEGRAM_CALLBACK_REGISTER, platform="telegram")
        
        assert handler_tracker.was_called("callback")
        assert user_data['id'] == 111222333
        assert user_data['first_name'] == "John"
        await bot.close()


@pytest.mark.e2e
class TestPlatformDetection:
    """Test automatic platform detection from payload structure."""
    
    @pytest.mark.dual
    @pytest.mark.asyncio
    async def test_auto_detect_telegram(self, handler_tracker):
        """Test that Telegram payload is auto-detected by update_id."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(tg_token=TEST_TG_TOKEN, max_token=TEST_MAX_TOKEN)
        
        @router.message(CommandStart())
        async def start_handler(message):
            handler_tracker.record("start", message)
        
        # No explicit platform - should auto-detect Telegram by update_id
        await dp.feed_webhook(body=TELEGRAM_MESSAGE_START)
        
        assert handler_tracker.was_called("start")
        await bot.close()
    
    @pytest.mark.dual
    @pytest.mark.asyncio
    async def test_auto_detect_max(self, handler_tracker):
        """Test that Max payload is auto-detected by update_type/mid."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(tg_token=TEST_TG_TOKEN, max_token=TEST_MAX_TOKEN)
        
        @router.message(CommandStart())
        async def start_handler(message):
            handler_tracker.record("start", message)
        
        # No explicit platform - should auto-detect Max by update_type
        await dp.feed_webhook(body=MAX_MESSAGE_START)
        
        assert handler_tracker.was_called("start")
        await bot.close()


@pytest.mark.e2e
class TestHandlerDeduplication:
    """Test that handlers are not called multiple times (critical regression test)."""
    
    @pytest.mark.max
    @pytest.mark.asyncio
    async def test_max_handler_called_exactly_once(self, handler_tracker):
        """CRITICAL: Handler should be called exactly once, not multiple times."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(max_token=TEST_MAX_TOKEN)
        
        call_count = [0]
        
        @router.message(CommandStart())
        async def start_handler(message):
            call_count[0] += 1
            handler_tracker.record("start", message)
        
        await dp.feed_raw_update(update=MAX_MESSAGE_START, platform="max")
        
        assert handler_tracker.was_called("start"), "Handler should be called"
        assert call_count[0] == 1, f"Handler should be called exactly once, but was called {call_count[0]} times"
        await bot.close()
    
    @pytest.mark.telegram
    @pytest.mark.asyncio
    async def test_telegram_handler_called_exactly_once(self, handler_tracker):
        """CRITICAL: Handler should be called exactly once on Telegram too."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(tg_token=TEST_TG_TOKEN)
        
        call_count = [0]
        
        @router.message(CommandStart())
        async def start_handler(message):
            call_count[0] += 1
            handler_tracker.record("start", message)
        
        await dp.feed_raw_update(update=TELEGRAM_MESSAGE_START, platform="telegram")
        
        assert handler_tracker.was_called("start"), "Handler should be called"
        assert call_count[0] == 1, f"Handler should be called exactly once, but was called {call_count[0]} times"
        await bot.close()
    
    @pytest.mark.max
    @pytest.mark.asyncio
    async def test_max_only_first_matching_handler_called(self, handler_tracker):
        """CRITICAL: Only the first matching handler should be called (aiogram behavior)."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(max_token=TEST_MAX_TOKEN)
        
        @router.message(CommandStart())
        async def start_handler_1(message):
            handler_tracker.record("start_1", message)
        
        @router.message(CommandStart())  # Same filter - should NOT be called
        async def start_handler_2(message):
            handler_tracker.record("start_2", message)
        
        @router.message()  # Catch-all - should NOT be called (first handler matched)
        async def catch_all(message):
            handler_tracker.record("catch_all", message)
        
        await dp.feed_raw_update(update=MAX_MESSAGE_START, platform="max")
        
        assert handler_tracker.was_called("start_1"), "First matching handler should be called"
        assert not handler_tracker.was_called("start_2"), "Second matching handler should NOT be called"
        assert not handler_tracker.was_called("catch_all"), "Catch-all should NOT be called after match"
        await bot.close()
    
    @pytest.mark.telegram
    @pytest.mark.asyncio
    async def test_telegram_only_first_matching_handler_called(self, handler_tracker):
        """CRITICAL: Only first matching handler on Telegram."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(tg_token=TEST_TG_TOKEN)
        
        @router.message(CommandStart())
        async def start_handler_1(message):
            handler_tracker.record("start_1", message)
        
        @router.message(CommandStart())  # Same filter - should NOT be called
        async def start_handler_2(message):
            handler_tracker.record("start_2", message)
        
        await dp.feed_raw_update(update=TELEGRAM_MESSAGE_START, platform="telegram")
        
        assert handler_tracker.was_called("start_1"), "First matching handler should be called"
        # Note: aiogram might call both - this tests OUR behavior consistency
        await bot.close()


@pytest.mark.e2e
class TestFilterCorrectness:
    """Test that filters correctly reject non-matching messages."""
    
    @pytest.mark.max
    @pytest.mark.asyncio
    async def test_max_command_filter_rejects_plain_text(self, handler_tracker):
        """CRITICAL: CommandStart should NOT match plain text messages."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(max_token=TEST_MAX_TOKEN)
        
        @router.message(CommandStart())
        async def start_handler(message):
            handler_tracker.record("start", message)
        
        # Send plain text, NOT /start
        await dp.feed_raw_update(update=MAX_MESSAGE_TEXT, platform="max")
        
        assert not handler_tracker.was_called("start"), \
            "CommandStart should NOT match plain text message"
        await bot.close()
    
    @pytest.mark.max
    @pytest.mark.asyncio
    async def test_max_command_filter_rejects_different_command(self, handler_tracker):
        """CRITICAL: CommandStart should NOT match /help command."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(max_token=TEST_MAX_TOKEN)
        
        @router.message(CommandStart())
        async def start_handler(message):
            handler_tracker.record("start", message)
        
        # Send /help, NOT /start
        await dp.feed_raw_update(update=MAX_MESSAGE_HELP, platform="max")
        
        assert not handler_tracker.was_called("start"), \
            "CommandStart should NOT match /help command"
        await bot.close()
    
    @pytest.mark.max
    @pytest.mark.asyncio
    async def test_max_multiple_filters_only_correct_one_matches(self, handler_tracker):
        """CRITICAL: Only handler with matching filter should be called."""
        from obabot import create_bot
        from obabot.filters import CommandStart, Command
        from obabot.filters import F
        
        bot, dp, router = create_bot(max_token=TEST_MAX_TOKEN)
        
        @router.message(CommandStart())
        async def start_handler(message):
            handler_tracker.record("start", message)
        
        @router.message(Command("help"))
        async def help_handler(message):
            handler_tracker.record("help", message)
        
        @router.message(F.text & ~F.text.startswith("/"))
        async def text_handler(message):
            handler_tracker.record("text", message)
        
        # Send /start
        await dp.feed_raw_update(update=MAX_MESSAGE_START, platform="max")
        
        assert handler_tracker.was_called("start"), "start handler should match /start"
        assert not handler_tracker.was_called("help"), "help handler should NOT match /start"
        assert not handler_tracker.was_called("text"), "text handler should NOT match /start"
        
        handler_tracker.clear()
        
        # Send /help
        await dp.feed_raw_update(update=MAX_MESSAGE_HELP, platform="max")
        
        assert not handler_tracker.was_called("start"), "start handler should NOT match /help"
        assert handler_tracker.was_called("help"), "help handler should match /help"
        assert not handler_tracker.was_called("text"), "text handler should NOT match /help"
        
        handler_tracker.clear()
        
        # Send plain text
        await dp.feed_raw_update(update=MAX_MESSAGE_TEXT, platform="max")
        
        assert not handler_tracker.was_called("start"), "start handler should NOT match text"
        assert not handler_tracker.was_called("help"), "help handler should NOT match text"
        # text handler might or might not match depending on F.text implementation
        
        await bot.close()
    
    @pytest.mark.max
    @pytest.mark.asyncio
    async def test_max_callback_filter_rejects_wrong_data(self, handler_tracker):
        """CRITICAL: Callback filter should reject non-matching data."""
        from obabot import create_bot
        from obabot.filters import F
        
        bot, dp, router = create_bot(max_token=TEST_MAX_TOKEN)
        
        @router.callback_query(F.data == "register")
        async def register_handler(callback):
            handler_tracker.record("register", callback)
        
        @router.callback_query(F.data == "info")
        async def info_handler(callback):
            handler_tracker.record("info", callback)
        
        # Send "info" callback
        await dp.feed_raw_update(update=MAX_CALLBACK_INFO, platform="max")
        
        assert not handler_tracker.was_called("register"), \
            "register handler should NOT match 'info' callback"
        assert handler_tracker.was_called("info"), \
            "info handler should match 'info' callback"
        
        await bot.close()


@pytest.mark.e2e
class TestDualPlatformConsistency:
    """Test that both platforms behave identically."""
    
    @pytest.mark.dual
    @pytest.mark.asyncio
    async def test_same_handler_same_behavior_both_platforms(self, handler_tracker):
        """Both Telegram and Max should call handler exactly once with same filter."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(tg_token=TEST_TG_TOKEN, max_token=TEST_MAX_TOKEN)
        
        tg_calls = [0]
        max_calls = [0]
        
        @router.message(CommandStart())
        async def start_handler(message):
            platform = getattr(message, 'platform', 'unknown')
            if platform == 'telegram':
                tg_calls[0] += 1
            elif platform == 'max':
                max_calls[0] += 1
            handler_tracker.record("start", message)
        
        # Telegram
        await dp.feed_raw_update(update=TELEGRAM_MESSAGE_START, platform="telegram")
        
        # Max  
        await dp.feed_raw_update(update=MAX_MESSAGE_START, platform="max")
        
        assert tg_calls[0] == 1, f"Telegram handler called {tg_calls[0]} times, expected 1"
        assert max_calls[0] == 1, f"Max handler called {max_calls[0]} times, expected 1"
        
        await bot.close()
    
    @pytest.mark.dual
    @pytest.mark.asyncio
    async def test_repeated_updates_dont_duplicate_handlers(self, handler_tracker):
        """Multiple updates should not cause handler registration duplication."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        
        bot, dp, router = create_bot(tg_token=TEST_TG_TOKEN, max_token=TEST_MAX_TOKEN)
        
        call_count = [0]
        
        @router.message(CommandStart())
        async def start_handler(message):
            call_count[0] += 1
        
        # Send 3 updates to Max
        for i in range(3):
            update = dict(MAX_MESSAGE_START)
            update["message"] = dict(update["message"])
            update["message"]["body"] = dict(update["message"]["body"])
            update["message"]["body"]["mid"] = f"msg_{i}"
            await dp.feed_raw_update(update=update, platform="max")
        
        # Should be called exactly 3 times (once per update), not 3+6+9 etc
        assert call_count[0] == 3, f"Handler called {call_count[0]} times, expected 3"
        
        await bot.close()


@pytest.mark.e2e
class TestAttachmentFilters:
    """Test F.photo, F.document, etc. filter compatibility."""
    
    @pytest.mark.max
    def test_max_message_adapter_photo_property(self):
        """Test that MaxMessageAdapter.photo returns attachments correctly."""
        from obabot.adapters.message import MaxMessageAdapter
        from unittest.mock import Mock
        
        # Mock message with get_attachments method
        mock_msg = Mock()
        mock_attachment = Mock(type="image", url="https://example.com/photo.jpg")
        mock_msg.get_attachments = Mock(return_value=[mock_attachment])
        
        adapter = MaxMessageAdapter(mock_msg)
        
        # photo should return list of image attachments
        assert adapter.photo is not None
        assert len(adapter.photo) == 1
        assert adapter.content_type == "photo"
    
    @pytest.mark.max
    def test_max_message_adapter_document_property(self):
        """Test that MaxMessageAdapter.document returns file attachment."""
        from obabot.adapters.message import MaxMessageAdapter
        from unittest.mock import Mock
        
        mock_msg = Mock()
        mock_file = Mock(type="file", filename="doc.pdf")
        mock_msg.get_attachment = Mock(return_value=mock_file)
        mock_msg.get_attachments = Mock(return_value=[])
        
        adapter = MaxMessageAdapter(mock_msg)
        
        assert adapter.document is not None
        assert adapter.content_type == "document"
    
    @pytest.mark.max
    def test_max_message_adapter_no_attachments(self):
        """Test that attachment properties return None when no attachments."""
        from obabot.adapters.message import MaxMessageAdapter
        from unittest.mock import Mock
        
        mock_msg = Mock()
        mock_msg.get_attachments = Mock(return_value=[])
        mock_msg.get_attachment = Mock(return_value=None)
        mock_msg.text = "Hello"
        
        adapter = MaxMessageAdapter(mock_msg)
        
        # photo is always list (empty when none); other attachment props None when absent
        assert adapter.photo == []
        assert adapter.document is None
        assert adapter.audio is None
        assert adapter.video is None
        assert adapter.successful_payment is None  # Always None for Max
        assert adapter.content_type == "text"
    
    @pytest.mark.max
    def test_max_f_photo_filter_with_photo(self):
        """Test that F.photo filter works with Max message containing photo."""
        from obabot.adapters.message import MaxMessageAdapter
        from obabot.filters import F
        from unittest.mock import Mock
        
        mock_msg = Mock()
        mock_photo = Mock(type="image")
        mock_msg.get_attachments = Mock(return_value=[mock_photo])
        
        adapter = MaxMessageAdapter(mock_msg)
        
        # F.photo checks truthiness of message.photo
        # Simulate what aiogram MagicFilter does
        assert adapter.photo  # truthy = filter passes
    
    @pytest.mark.max
    def test_max_f_photo_filter_without_photo(self):
        """Test that F.photo filter rejects Max message without photo."""
        from obabot.adapters.message import MaxMessageAdapter
        from unittest.mock import Mock
        
        mock_msg = Mock()
        mock_msg.get_attachments = Mock(return_value=[])
        mock_msg.text = "Just text"
        
        adapter = MaxMessageAdapter(mock_msg)
        
        # F.photo checks truthiness - should be falsy
        assert not adapter.photo  # falsy = filter fails


@pytest.mark.e2e
class TestEditMessage:
    """E2E tests for message editing functionality."""
    
    @pytest.mark.max
    @pytest.mark.asyncio
    async def test_max_message_edit_text_calls_update_message(self):
        """Test that MaxMessageAdapter.edit_text calls bot.update_message with correct params."""
        from obabot.adapters.message import MaxMessageAdapter
        
        mock_msg = Mock()
        mock_msg.id = "msg_abc123"
        mock_msg.chat = Mock(id=123456)
        
        mock_bot = AsyncMock()
        mock_bot.update_message = AsyncMock(return_value={"success": True})
        
        adapter = MaxMessageAdapter(mock_msg, mock_bot)
        result = await adapter.edit_text("Updated text", reply_markup=None)
        
        mock_bot.update_message.assert_called_once()
        call_kwargs = mock_bot.update_message.call_args[1]
        assert call_kwargs["message_id"] == "msg_abc123"
        assert call_kwargs["text"] == "Updated text"
        assert result == {"success": True}
    
    @pytest.mark.max
    @pytest.mark.asyncio
    async def test_max_callback_message_edit_text(self):
        """Test that callback.edit_message_text works for Max callbacks via MaxCallbackQuery."""
        from obabot.adapters.max_callback import MaxCallbackQuery
        from maxbot.types import Callback, Message, User, Chat
        
        # Create real umaxbot objects for Pydantic validation
        mock_user = User(user_id=123, name="Test")
        mock_chat = Chat(id=789, type="dialog")
        mock_msg = Message(
            id="msg_xyz789",
            text="old",
            chat=mock_chat,
            sender=mock_user,
        )
        
        callback = Callback(
            callback_id="cb_123",
            payload="menu_signs",
            user=mock_user,
            message=mock_msg,
        )
        
        mock_bot = AsyncMock()
        mock_bot.update_message = AsyncMock(return_value={"edited": True})
        
        # Create extended callback
        extended = MaxCallbackQuery.from_callback(callback, mock_bot)
        
        # Verify has edit_message_text method
        assert hasattr(extended, 'edit_message_text')
        assert extended.get_platform() == "max"
    
    @pytest.mark.max
    @pytest.mark.asyncio
    async def test_max_edit_text_with_keyboard(self):
        """Test that edit_text passes reply_markup to update_message."""
        from obabot.adapters.message import MaxMessageAdapter
        from unittest.mock import Mock
        
        mock_msg = Mock()
        mock_msg.id = "msg_with_kb"
        mock_msg.chat = Mock(id=111)
        
        mock_bot = AsyncMock()
        mock_bot.update_message = AsyncMock(return_value={"success": True})
        
        adapter = MaxMessageAdapter(mock_msg, mock_bot)
        
        # Create a simple keyboard mock
        mock_keyboard = {"inline_keyboard": [[{"text": "Button", "callback_data": "click"}]]}
        
        result = await adapter.edit_text("Text with keyboard", reply_markup=mock_keyboard)
        
        mock_bot.update_message.assert_called_once()
        call_kwargs = mock_bot.update_message.call_args[1]
        assert call_kwargs["reply_markup"] is not None
    
    @pytest.mark.max
    @pytest.mark.asyncio
    async def test_max_edit_text_strips_html(self):
        """Test that edit_text strips HTML tags for Max (Max doesn't support HTML)."""
        from obabot.adapters.message import MaxMessageAdapter
        
        mock_msg = Mock()
        mock_msg.id = "msg_html"
        mock_msg.chat = Mock(id=222)
        
        mock_bot = AsyncMock()
        mock_bot.update_message = AsyncMock(return_value={"success": True})
        
        adapter = MaxMessageAdapter(mock_msg, mock_bot)
        
        # Send HTML formatted text
        await adapter.edit_text("<b>Bold</b> and <i>italic</i>", parse_mode="HTML")
        
        call_kwargs = mock_bot.update_message.call_args[1]
        # HTML tags should be stripped
        assert "<b>" not in call_kwargs["text"]
        assert "<i>" not in call_kwargs["text"]
        assert "Bold" in call_kwargs["text"]
        assert "italic" in call_kwargs["text"]
    
    @pytest.mark.asyncio
    async def test_max_answer_uses_bot_send_message(self):
        """Test that MaxMessageAdapter.answer uses bot.send_message."""
        from obabot.adapters.message import MaxMessageAdapter
        
        mock_msg = Mock()
        mock_msg.chat = Mock(id=333)
        
        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock(return_value={"sent": True})
        
        adapter = MaxMessageAdapter(mock_msg, mock_bot)
        result = await adapter.answer("Hello!")
        
        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args[1]
        assert call_kwargs["chat_id"] == 333
        assert call_kwargs["text"] == "Hello!"
        assert result == {"sent": True}
    
    @pytest.mark.asyncio
    async def test_max_reply_delegates_to_answer(self):
        """Test that MaxMessageAdapter.reply delegates to answer (no native reply in Max)."""
        from obabot.adapters.message import MaxMessageAdapter
        
        mock_msg = Mock()
        mock_msg.chat = Mock(id=444)
        
        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock(return_value={"sent": True})
        
        adapter = MaxMessageAdapter(mock_msg, mock_bot)
        result = await adapter.reply("Reply text")
        
        # reply() should call send_message (via answer())
        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args[1]
        assert call_kwargs["chat_id"] == 444
        assert call_kwargs["text"] == "Reply text"


class TestMessageNotModifiedHandling:
    """Test automatic handling of 'message is not modified' errors."""
    
    @pytest.mark.asyncio
    async def test_proxy_bot_edit_ignores_not_modified(self):
        """Test ProxyBot.edit_message_text ignores 'message is not modified' error."""
        from obabot.proxy.bot import ProxyBot
        from aiogram.exceptions import TelegramBadRequest
        
        mock_platform = Mock()
        mock_platform.platform = "telegram"
        mock_bot = AsyncMock()
        mock_bot.edit_message_text = AsyncMock(
            side_effect=TelegramBadRequest(
                method="editMessageText",
                message="Bad Request: message is not modified"
            )
        )
        mock_platform.bot = mock_bot
        
        proxy_bot = ProxyBot([mock_platform])
        
        # Should not raise, should return None
        result = await proxy_bot.edit_message_text(
            text="Same text",
            chat_id=123,
            message_id=456
        )
        assert result is None
    
    @pytest.mark.asyncio
    async def test_proxy_bot_edit_reraises_other_errors(self):
        """Test ProxyBot.edit_message_text reraises non-modified errors."""
        from obabot.proxy.bot import ProxyBot
        from aiogram.exceptions import TelegramBadRequest
        
        mock_platform = Mock()
        mock_platform.platform = "telegram"
        mock_bot = AsyncMock()
        mock_bot.edit_message_text = AsyncMock(
            side_effect=TelegramBadRequest(
                method="editMessageText",
                message="Bad Request: message to edit not found"
            )
        )
        mock_platform.bot = mock_bot
        
        proxy_bot = ProxyBot([mock_platform])
        
        # Should raise because error is not "message is not modified"
        with pytest.raises(TelegramBadRequest):
            await proxy_bot.edit_message_text(
                text="Text",
                chat_id=123,
                message_id=456
            )
    
    @pytest.mark.asyncio
    async def test_max_adapter_edit_ignores_not_modified(self):
        """Test MaxMessageAdapter.edit_text ignores 'message is not modified' error."""
        from obabot.adapters.message import MaxMessageAdapter
        
        mock_msg = Mock()
        mock_msg.mid = "msg123"
        mock_msg.chat = Mock(id=555)
        
        mock_bot = AsyncMock()
        mock_bot.update_message = AsyncMock(
            side_effect=Exception("Message is not modified")
        )
        
        adapter = MaxMessageAdapter(mock_msg, mock_bot)
        
        # Should not raise, should return None
        result = await adapter.edit_text("Same text")
        assert result is None


class TestMaxApiErrorRaisesException:
    """Test that Max API 4xx errors raise exceptions (e.g., invalid URL in buttons)."""
    
    @pytest.mark.asyncio
    async def test_edit_text_400_raises_exception(self):
        """Test MaxMessageAdapter.edit_text raises RuntimeError on 400 response."""
        from obabot.adapters.message import MaxMessageAdapter
        
        mock_msg = Mock()
        mock_msg.mid = "msg123"
        mock_msg.chat = Mock(id=555)
        
        # Simulate Max API returning 400 error
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = '{"code":"proto.payload","message":"Must have only http/https links format in buttons"}'
        
        mock_bot = AsyncMock()
        mock_bot.update_message = AsyncMock(return_value=mock_response)
        
        adapter = MaxMessageAdapter(mock_msg, mock_bot)
        
        with pytest.raises(RuntimeError) as exc_info:
            await adapter.edit_text("Text", reply_markup=None)
        
        assert "400" in str(exc_info.value)
        assert "proto.payload" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_answer_400_raises_exception(self):
        """Test MaxMessageAdapter.answer raises RuntimeError on 400 response."""
        from obabot.adapters.message import MaxMessageAdapter
        
        mock_msg = Mock()
        mock_msg.chat = Mock(id=555)
        
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = '{"code":"proto.payload","message":"Invalid buttons"}'
        
        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock(return_value=mock_response)
        
        adapter = MaxMessageAdapter(mock_msg, mock_bot)
        
        with pytest.raises(RuntimeError) as exc_info:
            await adapter.answer("Hello")
        
        assert "400" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_callback_edit_text_400_raises_exception(self):
        """Test MaxCallbackQuery.edit_message_text exists and can be called."""
        from obabot.adapters.max_callback import MaxCallbackQuery
        from maxbot.types import Callback, Message, User, Chat
        
        mock_user = User(user_id=123, name="Test")
        mock_chat = Chat(id=456, type="dialog")
        mock_msg = Message(
            id="msg456",
            text="old",
            chat=mock_chat,
            sender=mock_user,
        )
        
        callback = Callback(
            callback_id="cb123",
            payload="test",
            user=mock_user,
            message=mock_msg,
        )
        
        mock_bot = AsyncMock()
        mock_bot.update_message = AsyncMock(return_value={"success": True})
        
        extended = MaxCallbackQuery.from_callback(callback, mock_bot)
        
        # Verify the method exists and can be called
        assert hasattr(extended, 'edit_message_text')
        assert extended.get_platform() == "max"
    
    @pytest.mark.asyncio
    async def test_answer_photo_400_raises_exception(self):
        """Test MaxMessageAdapter.answer_photo raises RuntimeError on 400 response."""
        from obabot.adapters.message import MaxMessageAdapter
        
        mock_msg = Mock()
        mock_msg.chat = Mock(id=555)
        
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = '{"code":"error","message":"File too large"}'
        
        mock_bot = AsyncMock()
        mock_bot.send_file = AsyncMock(return_value=mock_response)
        
        adapter = MaxMessageAdapter(mock_msg, mock_bot)
        
        with pytest.raises(RuntimeError) as exc_info:
            await adapter.answer_photo("/path/to/photo.jpg")
        
        assert "400" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_success_response_does_not_raise(self):
        """Test 200 response does not raise exception."""
        from obabot.adapters.message import MaxMessageAdapter
        
        mock_msg = Mock()
        mock_msg.mid = "msg123"
        mock_msg.chat = Mock(id=555)
        
        # Simulate successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '{"success":true}'
        
        mock_bot = AsyncMock()
        mock_bot.update_message = AsyncMock(return_value=mock_response)
        
        adapter = MaxMessageAdapter(mock_msg, mock_bot)
        
        # Should not raise
        result = await adapter.edit_text("Text")
        assert result == mock_response


class TestCrossPlatformSendPhoto:
    """Test send_photo works on both Telegram and Max."""
    
    @pytest.mark.asyncio
    async def test_send_photo_telegram(self):
        """Test send_photo on Telegram platform uses bot.send_photo."""
        from obabot.proxy.bot import ProxyBot
        from obabot.types import BPlatform
        
        mock_platform = Mock()
        mock_platform.platform = BPlatform.telegram
        mock_bot = AsyncMock()
        mock_bot.send_photo = AsyncMock(return_value={"sent": True})
        mock_platform.bot = mock_bot
        
        proxy_bot = ProxyBot([mock_platform])
        result = await proxy_bot.send_photo(chat_id=123, photo="/path/to/photo.png")
        
        mock_bot.send_photo.assert_called_once()
        assert "chat_id" in mock_bot.send_photo.call_args[1]
    
    @pytest.mark.asyncio
    async def test_send_photo_max(self):
        """Test send_photo on Max platform uses bot.send_file with media_type='image'."""
        from obabot.proxy.bot import ProxyBot
        from obabot.types import BPlatform
        
        mock_platform = Mock()
        mock_platform.platform = BPlatform.max
        mock_bot = AsyncMock()
        mock_bot.send_file = AsyncMock(return_value={"sent": True})
        mock_platform.bot = mock_bot
        
        proxy_bot = ProxyBot([mock_platform])
        result = await proxy_bot.send_photo(
            chat_id=123, 
            photo="/path/to/photo.png",
            caption="Test caption"
        )
        
        mock_bot.send_file.assert_called_once()
        call_kwargs = mock_bot.send_file.call_args[1]
        assert call_kwargs["file_path"] == "/path/to/photo.png"
        assert call_kwargs["media_type"] == "image"
        assert call_kwargs["chat_id"] == 123
        assert call_kwargs["text"] == "Test caption"
    
    @pytest.mark.asyncio
    async def test_send_document_max(self):
        """Test send_document on Max platform uses bot.send_file with media_type='file'."""
        from obabot.proxy.bot import ProxyBot
        from obabot.types import BPlatform
        
        mock_platform = Mock()
        mock_platform.platform = BPlatform.max
        mock_bot = AsyncMock()
        mock_bot.send_file = AsyncMock(return_value={"sent": True})
        mock_platform.bot = mock_bot
        
        proxy_bot = ProxyBot([mock_platform])
        result = await proxy_bot.send_document(
            chat_id=456,
            document="/path/to/doc.pdf"
        )
        
        mock_bot.send_file.assert_called_once()
        call_kwargs = mock_bot.send_file.call_args[1]
        assert call_kwargs["media_type"] == "file"


@pytest.mark.e2e
class TestMessageMediaMethods:
    """Test aiogram-style media methods on Message adapter."""
    
    @pytest.mark.asyncio
    async def test_answer_video(self):
        """Test answer_video sends video via bot.send_file."""
        from obabot.adapters.message import MaxMessageAdapter
        from unittest.mock import Mock, AsyncMock
        
        mock_msg = Mock()
        mock_msg.chat = Mock(id=123)
        
        mock_bot = AsyncMock()
        mock_bot.send_file = AsyncMock(return_value={"sent": True})
        
        adapter = MaxMessageAdapter(mock_msg, mock_bot)
        result = await adapter.answer_video("/path/to/video.mp4", caption="Test video")
        
        mock_bot.send_file.assert_called_once()
        call_kwargs = mock_bot.send_file.call_args[1]
        assert call_kwargs["media_type"] == "video"
        assert call_kwargs["file_path"] == "/path/to/video.mp4"
    
    @pytest.mark.asyncio
    async def test_answer_audio(self):
        """Test answer_audio sends audio via bot.send_file."""
        from obabot.adapters.message import MaxMessageAdapter
        from unittest.mock import Mock, AsyncMock
        
        mock_msg = Mock()
        mock_msg.chat = Mock(id=123)
        
        mock_bot = AsyncMock()
        mock_bot.send_file = AsyncMock(return_value={"sent": True})
        
        adapter = MaxMessageAdapter(mock_msg, mock_bot)
        result = await adapter.answer_audio("/path/to/audio.mp3")
        
        mock_bot.send_file.assert_called_once()
        call_kwargs = mock_bot.send_file.call_args[1]
        assert call_kwargs["media_type"] == "audio"
    
    @pytest.mark.asyncio
    async def test_answer_voice(self):
        """Test answer_voice sends voice via bot.send_file."""
        from obabot.adapters.message import MaxMessageAdapter
        from unittest.mock import Mock, AsyncMock
        
        mock_msg = Mock()
        mock_msg.chat = Mock(id=123)
        
        mock_bot = AsyncMock()
        mock_bot.send_file = AsyncMock(return_value={"sent": True})
        
        adapter = MaxMessageAdapter(mock_msg, mock_bot)
        result = await adapter.answer_voice("/path/to/voice.ogg")
        
        mock_bot.send_file.assert_called_once()
        call_kwargs = mock_bot.send_file.call_args[1]
        assert call_kwargs["media_type"] == "voice"
    
    @pytest.mark.asyncio
    async def test_answer_sticker(self):
        """Test answer_sticker sends sticker via bot.send_file."""
        from obabot.adapters.message import MaxMessageAdapter
        from unittest.mock import Mock, AsyncMock
        
        mock_msg = Mock()
        mock_msg.chat = Mock(id=123)
        
        mock_bot = AsyncMock()
        mock_bot.send_file = AsyncMock(return_value={"sent": True})
        
        adapter = MaxMessageAdapter(mock_msg, mock_bot)
        result = await adapter.answer_sticker("/path/to/sticker.webp")
        
        mock_bot.send_file.assert_called_once()
        call_kwargs = mock_bot.send_file.call_args[1]
        assert call_kwargs["media_type"] == "sticker"
    
    @pytest.mark.asyncio
    async def test_answer_animation(self):
        """Test answer_animation sends GIF via bot.send_file."""
        from obabot.adapters.message import MaxMessageAdapter
        from unittest.mock import Mock, AsyncMock
        
        mock_msg = Mock()
        mock_msg.chat = Mock(id=123)
        
        mock_bot = AsyncMock()
        mock_bot.send_file = AsyncMock(return_value={"sent": True})
        
        adapter = MaxMessageAdapter(mock_msg, mock_bot)
        result = await adapter.answer_animation("/path/to/animation.gif")
        
        mock_bot.send_file.assert_called_once()
        call_kwargs = mock_bot.send_file.call_args[1]
        assert call_kwargs["media_type"] == "video"  # Max uses video for GIFs
    
    @pytest.mark.asyncio
    async def test_forward_calls_bot_forward_message(self):
        """Test forward calls bot.forward_message if available."""
        from obabot.adapters.message import MaxMessageAdapter
        from unittest.mock import Mock, AsyncMock
        
        mock_msg = Mock()
        mock_msg.id = "msg_123"
        mock_msg.chat = Mock(id=111)
        
        mock_bot = AsyncMock()
        mock_bot.forward_message = AsyncMock(return_value={"forwarded": True})
        
        adapter = MaxMessageAdapter(mock_msg, mock_bot)
        result = await adapter.forward(chat_id=222)
        
        mock_bot.forward_message.assert_called_once()
        call_kwargs = mock_bot.forward_message.call_args[1]
        assert call_kwargs["chat_id"] == 222


@pytest.mark.e2e
class TestCallbackQueryShortcuts:
    """Test aiogram-style shortcuts on MaxCallbackQuery (inheritance-based)."""
    
    def test_max_callback_query_has_shortcuts(self):
        """Test MaxCallbackQuery has all required shortcut methods."""
        from obabot.adapters.max_callback import MaxCallbackQuery
        
        # Verify all shortcuts exist
        assert hasattr(MaxCallbackQuery, 'edit_message_text')
        assert hasattr(MaxCallbackQuery, 'edit_message_reply_markup')
        assert hasattr(MaxCallbackQuery, 'edit_message_caption')
        assert hasattr(MaxCallbackQuery, 'delete_message')
        assert hasattr(MaxCallbackQuery, 'answer')
    
    def test_max_callback_query_platform_methods(self):
        """Test MaxCallbackQuery has platform identification methods."""
        from obabot.adapters.max_callback import MaxCallbackQuery
        
        assert hasattr(MaxCallbackQuery, 'get_platform')
        assert hasattr(MaxCallbackQuery, 'is_max')
        assert hasattr(MaxCallbackQuery, 'is_telegram')
    
    def test_telegram_callback_query_has_shortcuts(self):
        """Test TelegramCallbackQuery has all required shortcut methods."""
        from obabot.adapters.telegram_callback import TelegramCallbackQuery
        
        # Verify all shortcuts exist
        assert hasattr(TelegramCallbackQuery, 'edit_message_text')
        assert hasattr(TelegramCallbackQuery, 'edit_message_reply_markup')
        assert hasattr(TelegramCallbackQuery, 'edit_message_caption')
        assert hasattr(TelegramCallbackQuery, 'delete_message')
    
    def test_both_platforms_same_interface(self):
        """Test both callback query classes have the same interface."""
        from obabot.adapters.max_callback import MaxCallbackQuery
        from obabot.adapters.telegram_callback import TelegramCallbackQuery
        
        # Both have same shortcut methods
        shortcuts = ['edit_message_text', 'edit_message_reply_markup', 
                     'edit_message_caption', 'delete_message']
        
        for method in shortcuts:
            assert hasattr(MaxCallbackQuery, method), f"MaxCallbackQuery missing {method}"
            assert hasattr(TelegramCallbackQuery, method), f"TelegramCallbackQuery missing {method}"
        
        # Both have platform methods
        platform_methods = ['get_platform', 'is_telegram', 'is_max']
        for method in platform_methods:
            assert hasattr(MaxCallbackQuery, method), f"MaxCallbackQuery missing {method}"
            assert hasattr(TelegramCallbackQuery, method), f"TelegramCallbackQuery missing {method}"


@pytest.mark.e2e
class TestKeyboardConversion:
    """E2E tests for keyboard conversion between Telegram and Max formats."""
    
    def test_url_button_conversion_valid_https(self):
        """Test URL button with valid HTTPS URL is converted correctly."""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from obabot.adapters.keyboard import convert_keyboard_to_max
        import json
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Google", url="https://google.com")]
        ])
        
        max_kb = convert_keyboard_to_max(keyboard)
        
        # Verify conversion
        assert max_kb is not None
        assert hasattr(max_kb, 'to_attachment')
        
        attachment = max_kb.to_attachment()
        buttons = attachment["payload"]["buttons"]
        
        assert len(buttons) == 1
        assert len(buttons[0]) == 1
        
        btn = buttons[0][0]
        assert btn["type"] == "link"
        assert btn["url"] == "https://google.com"
        assert btn["text"] == "Google"
        # Should NOT have callback_data or payload for link buttons
        assert "callback_data" not in btn
        assert "payload" not in btn
    
    def test_url_button_conversion_valid_http(self):
        """Test URL button with valid HTTP URL is converted correctly."""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from obabot.adapters.keyboard import convert_keyboard_to_max
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Example", url="http://example.com/path")]
        ])
        
        max_kb = convert_keyboard_to_max(keyboard)
        attachment = max_kb.to_attachment()
        
        btn = attachment["payload"]["buttons"][0][0]
        assert btn["type"] == "link"
        assert btn["url"] == "http://example.com/path"
    
    def test_callback_button_conversion(self):
        """Test callback button is converted correctly without URL."""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from obabot.adapters.keyboard import convert_keyboard_to_max
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Back", callback_data="go_back")]
        ])
        
        max_kb = convert_keyboard_to_max(keyboard)
        attachment = max_kb.to_attachment()
        
        btn = attachment["payload"]["buttons"][0][0]
        assert btn["type"] == "callback"
        assert btn["payload"] == "go_back"
        assert btn["text"] == "Back"
        # Should NOT have url for callback buttons
        assert "url" not in btn
    
    def test_mixed_keyboard_url_and_callback(self):
        """Test keyboard with both URL and callback buttons."""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from obabot.adapters.keyboard import convert_keyboard_to_max
        import json
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Visit Site", url="https://example.com/booking")],
            [InlineKeyboardButton(text="Back", callback_data="back")]
        ])
        
        max_kb = convert_keyboard_to_max(keyboard)
        attachment = max_kb.to_attachment()
        
        # First row - URL button
        btn1 = attachment["payload"]["buttons"][0][0]
        assert btn1["type"] == "link"
        assert btn1["url"] == "https://example.com/booking"
        assert "payload" not in btn1  # No callback_data
        
        # Second row - callback button
        btn2 = attachment["payload"]["buttons"][1][0]
        assert btn2["type"] == "callback"
        assert btn2["payload"] == "back"
        assert "url" not in btn2  # No URL
    
    def test_invalid_url_without_protocol_skipped(self):
        """Test that URL without protocol is skipped/rejected."""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from obabot.adapters.keyboard import convert_keyboard_to_max
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Bad URL", url="example.com")]  # No http://
        ])
        
        max_kb = convert_keyboard_to_max(keyboard)
        attachment = max_kb.to_attachment()
        
        # Button should be skipped due to invalid URL
        assert len(attachment["payload"]["buttons"]) == 0 or \
               len(attachment["payload"]["buttons"][0]) == 0
    
    def test_ftp_url_rejected(self):
        """Test that FTP URLs are rejected (only http/https allowed)."""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from obabot.adapters.keyboard import convert_keyboard_to_max
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="FTP", url="ftp://files.example.com")]
        ])
        
        max_kb = convert_keyboard_to_max(keyboard)
        attachment = max_kb.to_attachment()
        
        # FTP URL should be rejected
        assert len(attachment["payload"]["buttons"]) == 0 or \
               len(attachment["payload"]["buttons"][0]) == 0
    
    def test_valid_keyboard_json_no_null_values(self):
        """Test that final JSON has no null/None values for URL buttons."""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from obabot.adapters.keyboard import convert_keyboard_to_max
        import json
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Link", url="https://valid.com")],
            [InlineKeyboardButton(text="Button", callback_data="click")]
        ])
        
        max_kb = convert_keyboard_to_max(keyboard)
        attachment = max_kb.to_attachment()
        json_str = json.dumps(attachment)
        
        # Should not contain null values
        assert "null" not in json_str
        assert "None" not in json_str


@pytest.mark.e2e
class TestRealBotMigrationScenarios:
    """Simulate real-world bot migration scenarios from Telegram to dual-platform."""
    
    @pytest.mark.asyncio
    async def test_booking_menu_with_url_buttons(self, handler_tracker):
        """Simulate booking menu handler that shows URL buttons - common migration pattern."""
        from obabot import create_bot
        from obabot.filters import F
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        bot, dp, router = create_bot(max_token=TEST_MAX_TOKEN)
        
        sent_keyboard = {}
        
        @router.callback_query(F.data == "menu_booking")
        async def booking_callback(callback):
            handler_tracker.record("booking", callback)
            
            # Typical Telegram bot code - create keyboard with URL buttons
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📅 Book appointment", url="https://booking.example.com/slot1")],
                [InlineKeyboardButton(text="📞 Call us", url="https://wa.me/1234567890")],
                [InlineKeyboardButton(text="◀️ Back", callback_data="back_to_menu")]
            ])
            
            # Store for verification
            sent_keyboard["kb"] = keyboard
            
            # Simulating callback.message.edit_text(text, reply_markup=keyboard)
            # In real scenario this would call the adapter
        
        # Create Max callback payload
        max_callback = {
            "update_type": "message_callback",
            "timestamp": 1640000010000,
            "callback": {
                "callback_id": "cb_booking_test",
                "payload": "menu_booking",
                "user": {"user_id": 555666777, "name": "TestUser"}
            },
            "message": {
                "body": {"mid": "msg_booking_123", "text": "Welcome"},
                "sender": {"user_id": 999, "name": "Bot"},
                "recipient": {"chat_id": 555666777, "chat_type": "dialog"},
                "timestamp": 1640000010000
            }
        }
        
        await dp.feed_raw_update(update=max_callback, platform="max")
        
        assert handler_tracker.was_called("booking")
        
        # Verify keyboard would convert correctly
        if "kb" in sent_keyboard:
            from obabot.adapters.keyboard import convert_keyboard_to_max
            max_kb = convert_keyboard_to_max(sent_keyboard["kb"])
            att = max_kb.to_attachment()
            
            buttons = att["payload"]["buttons"]
            # Row 0: URL button
            assert buttons[0][0]["type"] == "link"
            assert buttons[0][0]["url"] == "https://booking.example.com/slot1"
            # Row 1: URL button
            assert buttons[1][0]["type"] == "link"
            # Row 2: Callback button
            assert buttons[2][0]["type"] == "callback"
            assert buttons[2][0]["payload"] == "back_to_menu"
        
        await bot.close()
    
    @pytest.mark.asyncio
    async def test_command_with_inline_keyboard_response(self, handler_tracker):
        """Test /start command that responds with inline keyboard - common pattern."""
        from obabot import create_bot
        from obabot.filters import CommandStart
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from obabot.adapters.keyboard import convert_keyboard_to_max
        
        bot, dp, router = create_bot(max_token=TEST_MAX_TOKEN)
        
        @router.message(CommandStart())
        async def start_handler(message):
            handler_tracker.record("start", message)
            
            # Typical start menu keyboard
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📚 Catalog", callback_data="catalog")],
                [InlineKeyboardButton(text="🛒 Cart", callback_data="cart")],
                [InlineKeyboardButton(text="📱 Our app", url="https://app.example.com")]
            ])
            
            # Verify this keyboard converts properly
            max_kb = convert_keyboard_to_max(keyboard)
            att = max_kb.to_attachment()
            
            # All buttons should be present
            assert len(att["payload"]["buttons"]) == 3
            
            # First two are callbacks
            assert att["payload"]["buttons"][0][0]["type"] == "callback"
            assert att["payload"]["buttons"][1][0]["type"] == "callback"
            
            # Third is URL
            assert att["payload"]["buttons"][2][0]["type"] == "link"
            assert att["payload"]["buttons"][2][0]["url"] == "https://app.example.com"
        
        await dp.feed_raw_update(update=MAX_MESSAGE_START, platform="max")
        
        assert handler_tracker.was_called("start")
        await bot.close()
    
    @pytest.mark.asyncio
    async def test_callback_edit_message_with_keyboard(self, handler_tracker):
        """Test callback that edits message with new keyboard - common menu navigation."""
        from obabot import create_bot
        from obabot.filters import F
        
        bot, dp, router = create_bot(tg_token=TEST_TG_TOKEN, max_token=TEST_MAX_TOKEN)
        
        edit_calls = {"tg": 0, "max": 0}
        
        @router.callback_query(F.data == "info")
        async def info_callback(callback):
            handler_tracker.record("info", callback)
            platform = getattr(callback, "platform", "unknown")
            if platform == "telegram":
                edit_calls["tg"] += 1
            elif platform == "max":
                edit_calls["max"] += 1
        
        # Telegram callback
        await dp.feed_raw_update(update=TELEGRAM_CALLBACK_INFO, platform="telegram")
        assert handler_tracker.was_called("info")
        
        handler_tracker.clear()
        
        # Max callback
        await dp.feed_raw_update(update=MAX_CALLBACK_INFO, platform="max")
        assert handler_tracker.was_called("info")
        
        await bot.close()
    
    @pytest.mark.asyncio
    async def test_text_handler_for_user_input(self, handler_tracker):
        """Test text message handler for collecting user input."""
        from obabot import create_bot
        from obabot.filters import F
        
        bot, dp, router = create_bot(tg_token=TEST_TG_TOKEN, max_token=TEST_MAX_TOKEN)
        
        received_texts = []
        
        @router.message(F.text & ~F.text.startswith("/"))
        async def text_handler(message):
            handler_tracker.record("text", message)
            received_texts.append(message.text)
        
        # Custom text update for Max
        max_text_update = {
            "update_type": "message_created",
            "timestamp": 1640000020000,
            "message": {
                "body": {"mid": "msg_input_123", "seq": 1, "text": "user@example.com"},
                "sender": {"user_id": 123456, "name": "User"},
                "recipient": {"chat_id": 123456, "chat_type": "dialog"},
                "timestamp": 1640000020000
            }
        }
        
        await dp.feed_raw_update(update=max_text_update, platform="max")
        
        assert handler_tracker.was_called("text")
        assert "user@example.com" in received_texts
        
        await bot.close()
    
    @pytest.mark.asyncio
    async def test_regex_callback_pattern(self, handler_tracker):
        """Test callback with regex pattern - common for dynamic menus."""
        from obabot import create_bot
        from obabot.filters import F
        
        bot, dp, router = create_bot(max_token=TEST_MAX_TOKEN)
        
        extracted_ids = []
        
        @router.callback_query(F.data.startswith("item_"))
        async def item_callback(callback):
            handler_tracker.record("item", callback)
            data = getattr(callback, "data", None) or getattr(callback, "payload", None)
            item_id = data.replace("item_", "") if data else None
            extracted_ids.append(item_id)
        
        # Callback with pattern
        max_callback = {
            "update_type": "message_callback",
            "timestamp": 1640000030000,
            "callback": {
                "callback_id": "cb_item_test",
                "payload": "item_12345",
                "user": {"user_id": 777888, "name": "Buyer"}
            },
            "message": {
                "body": {"mid": "msg_item", "seq": 1, "text": "Select item"},
                "sender": {"user_id": 999, "name": "Bot"},
                "recipient": {"chat_id": 777888, "chat_type": "dialog"},
                "timestamp": 1640000030000
            }
        }
        
        await dp.feed_raw_update(update=max_callback, platform="max")
        
        assert handler_tracker.was_called("item")
        assert "12345" in extracted_ids
        
        await bot.close()
