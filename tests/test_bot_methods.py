"""Test bot methods for sending messages."""

import pytest


class TestBotSendMethods:
    """Test bot send methods."""
    
    @pytest.mark.asyncio
    async def test_send_message_exists(self, obabot_telegram_bot):
        """Test that send_message method exists and is callable."""
        bot, _, _ = obabot_telegram_bot
        
        assert hasattr(bot, 'send_message')
        assert callable(bot.send_message)
    
    @pytest.mark.asyncio
    async def test_send_photo_exists(self, obabot_telegram_bot):
        """Test that send_photo method exists."""
        bot, _, _ = obabot_telegram_bot
        assert hasattr(bot, 'send_photo')
    
    @pytest.mark.asyncio
    async def test_send_voice_exists(self, obabot_telegram_bot):
        """Test that send_voice method exists."""
        bot, _, _ = obabot_telegram_bot
        assert hasattr(bot, 'send_voice')
    
    @pytest.mark.asyncio
    async def test_send_video_note_exists(self, obabot_telegram_bot):
        """Test that send_video_note method exists."""
        bot, _, _ = obabot_telegram_bot
        assert hasattr(bot, 'send_video_note')
    
    @pytest.mark.asyncio
    async def test_send_location_exists(self, obabot_telegram_bot):
        """Test that send_location method exists."""
        bot, _, _ = obabot_telegram_bot
        assert hasattr(bot, 'send_location')
    
    @pytest.mark.asyncio
    async def test_send_contact_exists(self, obabot_telegram_bot):
        """Test that send_contact method exists."""
        bot, _, _ = obabot_telegram_bot
        assert hasattr(bot, 'send_contact')
    
    @pytest.mark.asyncio
    async def test_send_poll_exists(self, obabot_telegram_bot):
        """Test that send_poll method exists."""
        bot, _, _ = obabot_telegram_bot
        assert hasattr(bot, 'send_poll')
    
    @pytest.mark.asyncio
    async def test_forward_message_exists(self, obabot_telegram_bot):
        """Test that forward_message method exists."""
        bot, _, _ = obabot_telegram_bot
        assert hasattr(bot, 'forward_message')
    
    @pytest.mark.asyncio
    async def test_copy_message_exists(self, obabot_telegram_bot):
        """Test that copy_message method exists."""
        bot, _, _ = obabot_telegram_bot
        assert hasattr(bot, 'copy_message')
    
    @pytest.mark.asyncio
    async def test_edit_methods_exist(self, obabot_telegram_bot):
        """Test that edit methods exist."""
        bot, _, _ = obabot_telegram_bot
        assert hasattr(bot, 'edit_message_text')
        assert hasattr(bot, 'edit_message_caption')
        assert hasattr(bot, 'edit_message_media')
        assert hasattr(bot, 'edit_message_reply_markup')
    
    @pytest.mark.asyncio
    async def test_chat_methods_exist(self, obabot_telegram_bot):
        """Test that chat info methods exist."""
        bot, _, _ = obabot_telegram_bot
        assert hasattr(bot, 'get_chat')
        assert hasattr(bot, 'get_chat_member')
        assert hasattr(bot, 'get_chat_members_count')
        assert hasattr(bot, 'get_chat_administrators')
    
    @pytest.mark.asyncio
    async def test_pin_methods_exist(self, obabot_telegram_bot):
        """Test that pin/unpin methods exist."""
        bot, _, _ = obabot_telegram_bot
        assert hasattr(bot, 'pin_message')
        assert hasattr(bot, 'unpin_message')
        assert hasattr(bot, 'unpin_all_chat_messages')
    
    @pytest.mark.asyncio
    async def test_low_priority_methods_exist(self, obabot_telegram_bot):
        """Test that low priority methods exist."""
        bot, _, _ = obabot_telegram_bot
        assert hasattr(bot, 'send_dice')
        assert hasattr(bot, 'send_venue')
        assert hasattr(bot, 'leave_chat')
        assert hasattr(bot, 'get_chat_member_count')


class TestBotGetMethods:
    """Test bot get methods."""
    
    @pytest.mark.asyncio
    async def test_get_me_exists(self, obabot_telegram_bot):
        """Test that get_me method exists."""
        bot, _, _ = obabot_telegram_bot
        assert hasattr(bot, 'get_me')
        assert callable(bot.get_me)
    
    @pytest.mark.asyncio
    async def test_get_bot_method(self, obabot_telegram_bot):
        """Test get_bot method for platform-specific access."""
        from obabot.types import BPlatform
        bot, _, _ = obabot_telegram_bot
        
        # Should be able to get bot for configured platform
        platform_bot = bot.get_bot(BPlatform.telegram)
        assert platform_bot is not None
        
        # Should raise error for unconfigured platform
        with pytest.raises(ValueError):
            bot.get_bot(BPlatform.max)


class TestContextPlatformDetection:
    """Test automatic platform detection via context."""
    
    @pytest.mark.asyncio
    async def test_context_platform_detection_telegram(self):
        """Test bot uses context platform when no explicit platform given."""
        from obabot.context import set_current_platform, reset_current_platform, get_current_platform
        from obabot.types import BPlatform
        
        # Initially no platform in context
        assert get_current_platform() is None
        
        # Set telegram platform
        token = set_current_platform(BPlatform.telegram)
        assert get_current_platform() == BPlatform.telegram
        
        # Reset context
        reset_current_platform(token)
        assert get_current_platform() is None
    
    @pytest.mark.asyncio
    async def test_context_platform_detection_max(self):
        """Test context platform detection for Max."""
        from obabot.context import set_current_platform, reset_current_platform, get_current_platform
        from obabot.types import BPlatform
        
        token = set_current_platform(BPlatform.max)
        assert get_current_platform() == BPlatform.max
        
        reset_current_platform(token)
        assert get_current_platform() is None
    
    @pytest.mark.asyncio
    async def test_proxy_bot_uses_context_platform(self):
        """Test ProxyBot._get_bot_for_operation uses context when no platform specified."""
        from unittest.mock import Mock, MagicMock
        from obabot.proxy.bot import ProxyBot
        from obabot.context import set_current_platform, reset_current_platform
        from obabot.types import BPlatform
        
        # Create mock platforms
        tg_platform = Mock()
        tg_platform.platform = BPlatform.telegram
        tg_platform.bot = MagicMock(name="tg_bot")
        
        max_platform = Mock()
        max_platform.platform = BPlatform.max
        max_platform.bot = MagicMock(name="max_bot")
        
        proxy_bot = ProxyBot([tg_platform, max_platform])
        
        # Without context, should raise error (multiple platforms)
        with pytest.raises(ValueError, match="Multiple platforms"):
            proxy_bot._get_bot_for_operation()
        
        # With telegram context, should return telegram bot
        token = set_current_platform(BPlatform.telegram)
        try:
            bot = proxy_bot._get_bot_for_operation()
            assert bot == tg_platform.bot
        finally:
            reset_current_platform(token)
        
        # With max context, should return max bot
        token = set_current_platform(BPlatform.max)
        try:
            bot = proxy_bot._get_bot_for_operation()
            assert bot == max_platform.bot
        finally:
            reset_current_platform(token)
        
        # Explicit platform overrides context
        token = set_current_platform(BPlatform.telegram)
        try:
            bot = proxy_bot._get_bot_for_operation(platform=BPlatform.max)
            assert bot == max_platform.bot
        finally:
            reset_current_platform(token)


class TestFileConversion:
    """Test automatic file conversion for aiogram compatibility."""
    
    def test_convert_string_passthrough(self):
        """Test that strings are passed through unchanged."""
        from obabot.proxy.bot import _convert_to_input_file
        
        # File path
        result = _convert_to_input_file("/path/to/file.png")
        assert result == "/path/to/file.png"
        
        # URL
        result = _convert_to_input_file("https://example.com/image.png")
        assert result == "https://example.com/image.png"
        
        # File ID
        result = _convert_to_input_file("AgACAgIAAxkBAAI")
        assert result == "AgACAgIAAxkBAAI"
    
    def test_convert_buffered_reader(self):
        """Test conversion of BufferedReader to InputFile."""
        import io
        from obabot.proxy.bot import _convert_to_input_file
        
        # Create a BytesIO with some data
        data = b"fake image content"
        buffer = io.BytesIO(data)
        buffer.name = "test.png"
        
        result = _convert_to_input_file(buffer)
        
        # Should be converted to BufferedInputFile
        from aiogram.types import BufferedInputFile
        assert isinstance(result, BufferedInputFile)
    
    def test_convert_inputfile_passthrough(self):
        """Test that InputFile is passed through unchanged."""
        from obabot.proxy.bot import _convert_to_input_file
        from aiogram.types import BufferedInputFile
        
        original = BufferedInputFile(b"content", filename="test.txt")
        result = _convert_to_input_file(original)
        
        assert result is original

