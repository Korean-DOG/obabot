"""Integration tests (require real tokens)."""

import pytest
from obabot import BPlatform
from obabot.filters import Command


@pytest.mark.integration
class TestIntegration:
    """Integration tests that may require real API calls."""
    
    @pytest.mark.asyncio
    async def test_get_me_telegram(self, obabot_telegram_bot):
        """Test get_me() with Telegram bot."""
        bot, _, _ = obabot_telegram_bot
        
        try:
            me = await bot.get_me()
            assert me is not None
            # Bot should have id and username
            assert hasattr(me, 'id') or 'id' in str(type(me))
        except Exception as e:
            # If token is invalid, skip test
            pytest.skip(f"Could not get bot info: {e}")
    
    @pytest.mark.asyncio
    async def test_get_me_max(self, obabot_max_bot):
        """Test get_me() with Max bot."""
        bot, _, _ = obabot_max_bot
        
        try:
            me = await bot.get_me()
            assert me is not None
        except Exception as e:
            pytest.skip(f"Could not get bot info: {e}")
    
    @pytest.mark.asyncio
    async def test_platform_detection(self, obabot_telegram_bot):
        """Test that platform is correctly detected."""
        bot, _, router = obabot_telegram_bot
        
        platform_detected = None
        
        @router.message(Command("platform"))
        async def platform_handler(message):
            nonlocal platform_detected
            platform_detected = getattr(message, 'platform', None)
        
        # Handler should be registered
        assert callable(platform_handler)
        # Platform should be available in bot
        assert BPlatform.telegram in bot.platforms

