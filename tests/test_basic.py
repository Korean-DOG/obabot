"""Basic functionality tests for obabot."""

import pytest
from obabot import create_bot, BPlatform


class TestBasicCreation:
    """Test basic bot creation."""
    
    def test_create_bot_telegram_only(self, tg_token, skip_if_no_tg_token):
        """Test creating bot with Telegram token only."""
        bot, dp, router = create_bot(tg_token=tg_token)
        
        assert bot is not None
        assert dp is not None
        assert router is not None
        assert BPlatform.telegram in bot.platforms
        assert len(bot.platforms) == 1
    
    def test_create_bot_max_only(self, max_token, skip_if_no_max_token):
        """Test creating bot with Max token only."""
        bot, dp, router = create_bot(max_token=max_token)
        
        assert bot is not None
        assert dp is not None
        assert router is not None
        assert BPlatform.max in bot.platforms
        assert len(bot.platforms) == 1
    
    def test_create_bot_dual(self, tg_token, max_token):
        """Test creating bot with both tokens."""
        if not tg_token or not max_token:
            pytest.skip("Both tokens required")
        
        bot, dp, router = create_bot(tg_token=tg_token, max_token=max_token)
        
        assert bot is not None
        assert dp is not None
        assert router is not None
        assert len(bot.platforms) == 2
        assert BPlatform.telegram in bot.platforms
        assert BPlatform.max in bot.platforms
        assert bot.is_multi_platform is True
    
    def test_create_bot_no_tokens(self):
        """Test that creating bot without tokens raises error."""
        with pytest.raises(ValueError, match="At least one token"):
            create_bot()

    def test_create_bot_test_mode_no_tokens(self):
        """In test_mode tokens are not required; returns StubBot, Dispatcher, Router."""
        bot, dp, router = create_bot(test_mode=True)
        assert bot is not None
        assert dp is not None
        assert router is not None
        from obabot.factory import StubBot
        assert isinstance(bot, StubBot)
        assert hasattr(bot, "token") and bot.token
        assert hasattr(bot, "id")
        from aiogram import Dispatcher, Router
        assert isinstance(dp, Dispatcher)
        assert isinstance(router, Router)

    def test_create_bot_test_mode_dp_has_router(self):
        """Test-mode dp already has router included; no need to call include_router(router) in tests."""
        from aiogram import Dispatcher, Router
        _, dp, router = create_bot(test_mode=True)
        assert isinstance(dp, Dispatcher)
        assert isinstance(router, Router)
        assert getattr(router, "parent_router", None) is not None

    def test_create_bot_test_mode_env(self, monkeypatch):
        """TESTING=1 enables test mode without test_mode=True."""
        monkeypatch.setenv("TESTING", "1")
        bot, dp, router = create_bot()  # no tokens
        from obabot.factory import StubBot
        assert isinstance(bot, StubBot)
        monkeypatch.delenv("TESTING", raising=False)

    def test_create_bot_test_mode_fsm_storage(self):
        """In test_mode fsm_storage is set on the dispatcher."""
        from obabot.fsm import MemoryStorage
        storage = MemoryStorage()
        _, dp, _ = create_bot(test_mode=True, fsm_storage=storage)
        assert dp.fsm_storage is storage

    def test_create_bot_with_fsm_storage(self, tg_token, skip_if_no_tg_token):
        """Test creating bot with FSM storage parameter."""
        from obabot.fsm import MemoryStorage
        
        storage = MemoryStorage()
        bot, dp, router = create_bot(tg_token=tg_token, fsm_storage=storage)
        
        assert dp.fsm_storage is storage


class TestBotProperties:
    """Test bot properties."""
    
    def test_bot_platforms(self, obabot_telegram_bot):
        """Test bot.platforms property."""
        bot, _, _ = obabot_telegram_bot
        assert isinstance(bot.platforms, list)
        assert len(bot.platforms) > 0
    
    def test_bot_get_ids(self, obabot_telegram_bot):
        """Test get_ids() method."""
        bot, _, _ = obabot_telegram_bot
        ids = bot.get_ids()
        assert isinstance(ids, dict)
        assert len(ids) > 0
    
    def test_bot_get_tokens(self, obabot_telegram_bot):
        """Test get_tokens() method."""
        bot, _, _ = obabot_telegram_bot
        tokens = bot.get_tokens()
        assert isinstance(tokens, dict)
        assert len(tokens) > 0


class TestRouterHandlers:
    """Test router handler registration."""
    
    def test_router_message_handler(self, obabot_telegram_bot):
        """Test registering message handler."""
        _, _, router = obabot_telegram_bot
        
        @router.message()
        async def test_handler(message):
            pass
        
        # Handler should be registered without errors
        assert callable(test_handler)
    
    def test_router_callback_handler(self, obabot_telegram_bot):
        """Test registering callback handler."""
        _, _, router = obabot_telegram_bot
        
        @router.callback_query()
        async def test_handler(callback):
            pass
        
        assert callable(test_handler)
    
    def test_dispatcher_message_handler(self, obabot_telegram_bot):
        """Test registering handler via dispatcher (dp.message)."""
        _, dp, _ = obabot_telegram_bot
        
        @dp.message()
        async def test_handler(message):
            pass
        
        assert callable(test_handler)


class TestCompatibility:
    """Test compatibility with aiogram API."""
    
    def test_same_api_structure(self, obabot_telegram_bot, aiogram_bot):
        """Test that obabot has same API structure as aiogram."""
        obabot_bot, obabot_dp, obabot_router = obabot_telegram_bot
        aiogram_bot_obj, aiogram_dp, aiogram_router = aiogram_bot
        
        # Check that all main methods exist
        assert hasattr(obabot_bot, 'send_message')
        assert hasattr(obabot_dp, 'start_polling')
        assert hasattr(obabot_router, 'message')
        
        # Check that aiogram methods also exist
        assert hasattr(aiogram_bot_obj, 'send_message')
        assert hasattr(aiogram_dp, 'start_polling')
        assert hasattr(aiogram_router, 'message')

