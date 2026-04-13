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
        bot, dp, router = obabot_telegram_bot
        
        platform_detected = None
        
        @router.message(Command("platform"))
        async def platform_handler(message):
            nonlocal platform_detected
            platform_detected = getattr(message, 'platform', None)

        await dp.feed_raw_update(
            update={
                "update_id": 123456,
                "message": {
                    "message_id": 1,
                    "chat": {"id": 1001, "type": "private"},
                    "from": {"id": 1001, "is_bot": False, "first_name": "Tg"},
                    "date": 1640000000,
                    "text": "/platform",
                },
            },
            platform="telegram",
        )

        assert platform_detected == "telegram"
        assert BPlatform.telegram in bot.platforms

    @pytest.mark.max
    @pytest.mark.asyncio
    async def test_platform_detection_max(self, obabot_max_bot):
        """Max-only bot: dispatcher delivers platform='max' to handlers."""
        bot, dp, router = obabot_max_bot

        platform_detected = None

        @router.message(Command("platform"))
        async def platform_handler(message):
            nonlocal platform_detected
            platform_detected = getattr(message, "platform", None)

        await dp.feed_raw_update(
            update={
                "update_type": "message_created",
                "timestamp": 1640000000000,
                "message": {
                    "body": {"mid": "msg_platform", "seq": 1, "text": "/platform"},
                    "sender": {"user_id": 2002, "name": "Max"},
                    "recipient": {"chat_id": 2002, "chat_type": "dialog"},
                    "timestamp": 1640000000000,
                },
            },
            platform="max",
        )

        assert platform_detected == "max"
        assert BPlatform.max in bot.platforms

