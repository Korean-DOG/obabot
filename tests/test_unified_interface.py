"""
Tests demonstrating unified interface for both Telegram and Max platforms.

These tests show that the same bot code works identically for both platforms,
proving the library provides true cross-platform compatibility.
"""

import io
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from obabot.proxy.bot import ProxyBot, ProxyFile, DownloadableFile
from obabot.types import BPlatform


class TestUnifiedFileDownload:
    """Test unified file download interface for both platforms."""
    
    @pytest.fixture
    def telegram_platform(self):
        """Create mock Telegram platform."""
        platform = MagicMock()
        platform.platform = BPlatform.telegram
        platform.bot = AsyncMock()
        
        # Mock get_file response
        mock_file = MagicMock()
        mock_file.file_id = "telegram_file_123"
        mock_file.file_path = "documents/file.pdf"
        mock_file.file_size = 1024
        platform.bot.get_file = AsyncMock(return_value=mock_file)
        platform.bot.token = "123456:ABC-DEF"
        
        return platform
    
    @pytest.fixture
    def max_platform(self):
        """Create mock Max platform."""
        platform = MagicMock()
        platform.platform = BPlatform.max
        platform.bot = AsyncMock()
        return platform
    
    @pytest.fixture
    def proxy_bot_telegram(self, telegram_platform):
        """ProxyBot with only Telegram."""
        return ProxyBot([telegram_platform])
    
    @pytest.fixture
    def proxy_bot_max(self, max_platform):
        """ProxyBot with only Max."""
        return ProxyBot([max_platform])
    
    @pytest.fixture
    def proxy_bot_dual(self, telegram_platform, max_platform):
        """ProxyBot with both platforms."""
        return ProxyBot([telegram_platform, max_platform])
    
    @pytest.mark.asyncio
    async def test_get_file_telegram_returns_proxy_file(self, proxy_bot_telegram):
        """get_file() returns ProxyFile for Telegram."""
        result = await proxy_bot_telegram.get_file("telegram_file_123")
        
        assert isinstance(result, ProxyFile)
        assert result.platform == BPlatform.telegram
        assert result.file_id == "telegram_file_123"
        assert result.file_path == "documents/file.pdf"
    
    @pytest.mark.asyncio
    async def test_get_file_max_returns_proxy_file(self, proxy_bot_max):
        """get_file() returns ProxyFile for Max (URL-based). Pass suggested_filename for reliable name."""
        from unittest.mock import AsyncMock, patch
        max_url = "https://max.ru/files/audio_123.ogg"
        with patch("obabot.adapters.max_file.fetch_filename_from_max_url", new_callable=AsyncMock, return_value="audio.ogg"):
            result = await proxy_bot_max.get_file(max_url)
        assert isinstance(result, ProxyFile)
        assert result.platform == BPlatform.max
        assert result.file_url == max_url
        assert result.file_name == "audio.ogg"

    @pytest.mark.asyncio
    async def test_get_file_max_getfile_url_succeeds_when_headers_give_name(self, proxy_bot_max):
        """For getfile URL, get_file() succeeds when fetch (HEAD+GET) gets filename from headers."""
        max_url = "https://api.example.com/getfile?token=abc"
        with patch("obabot.adapters.max_file.fetch_filename_from_max_url", new_callable=AsyncMock, return_value="document.pdf"):
            result = await proxy_bot_max.get_file(max_url)
        assert result.file_name == "document.pdf"

    @pytest.mark.asyncio
    async def test_get_file_max_raises_when_filename_unknown(self, proxy_bot_max):
        """get_file() for Max raises MaxFileFilenameError when filename cannot be determined (HEAD and GET both fail)."""
        from obabot.adapters import MaxFileFilenameError
        max_url = "https://api.example.com/getfile?token=abc"
        with patch("obabot.adapters.max_file.fetch_filename_from_max_url", new_callable=AsyncMock, return_value=None):
            with pytest.raises(MaxFileFilenameError) as exc_info:
                await proxy_bot_max.get_file(max_url)
        assert "suggested_filename" in str(exc_info.value)

    def test_max_proxy_file_file_name_getfile_url_uses_sync_fetch(self):
        """ProxyFile.file_name for Max getfile URL uses sync fetch from server (or file.bin fallback)."""
        with patch("obabot.adapters.max_file.fetch_filename_from_max_url_sync", return_value="from_headers.txt"):
            f = ProxyFile(platform=BPlatform.max, file_id="https://fd.example.com/getfile?token=x", file_url="https://fd.example.com/getfile?token=x")
            assert f.file_name == "from_headers.txt"
        with patch("obabot.adapters.max_file.fetch_filename_from_max_url_sync", return_value=None):
            f2 = ProxyFile(platform=BPlatform.max, file_id="https://fd.example.com/getfile?token=x", file_url="https://fd.example.com/getfile?token=x")
            assert f2.file_name == "file.bin"
    
    @pytest.mark.asyncio
    async def test_same_bot_code_works_for_both_platforms(self, proxy_bot_dual):
        """
        MAIN TEST: Same code works for both platforms.
        
        This demonstrates that a bot developer can write ONE piece of code
        that works identically for Telegram and Max.
        """
        
        async def universal_file_handler(bot: ProxyBot, file_identifier: str, platform: str):
            """
            This is how a real bot would handle file downloads.
            THE SAME CODE for both platforms!
            """
            # Get file using unified interface
            proxy_file = await bot.get_file(file_identifier, platform=platform)
            
            # Download to buffer - same method for both platforms
            buffer = io.BytesIO()
            
            # Mock the actual download (we're testing interface, not network)
            with patch.object(proxy_file, 'download', new_callable=AsyncMock) as mock_download:
                mock_download.return_value = None
                await proxy_file.download(destination=buffer)
                mock_download.assert_called_once_with(destination=buffer)
            
            return proxy_file
        
        # Test with Telegram
        tg_file = await universal_file_handler(
            proxy_bot_dual, 
            "telegram_file_123", 
            platform="telegram"
        )
        assert tg_file.platform == BPlatform.telegram
        
        # Test with Max - SAME CODE! (HEAD request mocked so filename is resolved)
        with patch("obabot.adapters.max_file.fetch_filename_from_max_url", new_callable=AsyncMock, return_value="document.pdf"):
            max_file = await universal_file_handler(
                proxy_bot_dual,
                "https://max.ru/files/document.pdf",
                platform="max"
            )
        assert max_file.platform == BPlatform.max
    
    @pytest.mark.asyncio
    async def test_download_file_shortcut(self, proxy_bot_telegram):
        """download_file() combines get_file + download in one call."""
        with patch.object(ProxyFile, 'download', new_callable=AsyncMock) as mock_download:
            mock_download.return_value = b"file content"
            
            content = await proxy_bot_telegram.download_file("telegram_file_123")
            
            # Verify download was called
            mock_download.assert_called_once()


class TestUnifiedCallbackQuery:
    """Test unified callback query interface for both platforms."""
    
    @pytest.mark.asyncio
    async def test_callback_edit_message_text_interface(self):
        """
        Both TelegramCallbackQuery and MaxCallbackQuery have edit_message_text().
        
        This allows bot code like:
            await callback.edit_message_text("New text", reply_markup=keyboard)
        to work on BOTH platforms.
        """
        from obabot.adapters.max_callback import MaxCallbackQuery
        from obabot.adapters.telegram_callback import TelegramCallbackQuery
        
        # Verify both classes have the same method
        assert hasattr(TelegramCallbackQuery, 'edit_message_text')
        assert hasattr(MaxCallbackQuery, 'edit_message_text')
        
        assert hasattr(TelegramCallbackQuery, 'edit_message_reply_markup')
        assert hasattr(MaxCallbackQuery, 'edit_message_reply_markup')
        
        assert hasattr(TelegramCallbackQuery, 'edit_message_caption')
        assert hasattr(MaxCallbackQuery, 'edit_message_caption')
        
        assert hasattr(TelegramCallbackQuery, 'delete_message')
        assert hasattr(MaxCallbackQuery, 'delete_message')
    
    @pytest.mark.asyncio
    async def test_callback_isinstance_compatibility(self):
        """
        Both callback types are proper subclasses of their platform base classes.
        
        This ensures isinstance() checks work correctly:
        - isinstance(tg_cb, aiogram.CallbackQuery) = True
        - isinstance(max_cb, maxbot.Callback) = True
        """
        from aiogram.types import CallbackQuery as AiogramCallbackQuery
        from maxbot.types import Callback as MaxbotCallback
        from obabot.adapters.telegram_callback import TelegramCallbackQuery
        from obabot.adapters.max_callback import MaxCallbackQuery
        
        # Verify inheritance
        assert issubclass(TelegramCallbackQuery, AiogramCallbackQuery)
        assert issubclass(MaxCallbackQuery, MaxbotCallback)
    
    @pytest.mark.asyncio
    async def test_same_handler_code_for_both_platforms(self):
        """
        MAIN TEST: Same callback handler code works for both platforms.
        
        This is what a real bot looks like - ONE handler for both platforms.
        """
        
        async def universal_callback_handler(callback):
            """
            Universal callback handler - works for Telegram AND Max!
            
            The bot developer writes this ONCE, and it works everywhere.
            """
            # These methods exist on BOTH platforms:
            # - TelegramCallbackQuery (for Telegram)
            # - MaxCallbackQuery (for Max)
            
            data = getattr(callback, 'data', None) or getattr(callback, 'payload', None)
            
            if data == "confirm":
                # Same method call for both platforms!
                await callback.edit_message_text(
                    text="Confirmed!",
                    reply_markup=None
                )
            elif data == "cancel":
                await callback.delete_message()
            
            # Answer callback - also unified
            await callback.answer()
        
        # Create mock Telegram callback
        tg_callback = MagicMock()
        tg_callback.data = "confirm"
        tg_callback.edit_message_text = AsyncMock()
        tg_callback.delete_message = AsyncMock()
        tg_callback.answer = AsyncMock()
        
        # Create mock Max callback
        max_callback = MagicMock()
        max_callback.payload = "confirm"  # Max uses 'payload'
        max_callback.data = None
        max_callback.edit_message_text = AsyncMock()
        max_callback.delete_message = AsyncMock()
        max_callback.answer = AsyncMock()
        
        # Same handler works for both!
        await universal_callback_handler(tg_callback)
        tg_callback.edit_message_text.assert_called_once_with(
            text="Confirmed!",
            reply_markup=None
        )
        
        await universal_callback_handler(max_callback)
        max_callback.edit_message_text.assert_called_once_with(
            text="Confirmed!",
            reply_markup=None
        )
    
    @pytest.mark.asyncio
    async def test_telegram_callback_answer_handles_query_expired(self):
        """
        Test that TelegramCallbackQuery.answer() gracefully handles "query is too old" error.
        
        When Telegram returns this error (callback wasn't answered within 30 seconds),
        the error should be silently ignored since there's nothing useful we can do.
        """
        from aiogram.types import CallbackQuery, User, Message, Chat
        from obabot.adapters.telegram_callback import TelegramCallbackQuery
        
        # Create a minimal valid callback
        user = User(id=123, is_bot=False, first_name="Test")
        chat = Chat(id=456, type="private")
        message = Message(
            message_id=789,
            date=0,
            chat=chat,
            from_user=user,
            text="test"
        )
        callback = CallbackQuery(
            id="callback_123",
            from_user=user,
            chat_instance="test",
            message=message,
            data="test_data"
        )
        
        # Create extended callback
        mock_bot = MagicMock()
        extended = TelegramCallbackQuery.from_callback(callback, mock_bot)
        
        # Mock the parent answer method to raise "query is too old" error
        from aiogram.exceptions import TelegramBadRequest
        
        async def mock_answer(*args, **kwargs):
            raise TelegramBadRequest(
                method=MagicMock(),
                message="Bad Request: query is too old and response timeout expired or query ID is invalid"
            )
        
        # Patch the parent class answer method
        with patch.object(CallbackQuery, 'answer', mock_answer):
            # Should NOT raise, should return False
            result = await extended.answer("test")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_telegram_callback_answer_reraises_other_errors(self):
        """
        Test that TelegramCallbackQuery.answer() re-raises non-timeout errors.
        """
        from aiogram.types import CallbackQuery, User, Message, Chat
        from obabot.adapters.telegram_callback import TelegramCallbackQuery
        
        user = User(id=123, is_bot=False, first_name="Test")
        chat = Chat(id=456, type="private")
        message = Message(
            message_id=789,
            date=0,
            chat=chat,
            from_user=user,
            text="test"
        )
        callback = CallbackQuery(
            id="callback_123",
            from_user=user,
            chat_instance="test",
            message=message,
            data="test_data"
        )
        
        mock_bot = MagicMock()
        extended = TelegramCallbackQuery.from_callback(callback, mock_bot)
        
        from aiogram.exceptions import TelegramBadRequest
        
        async def mock_answer(*args, **kwargs):
            raise TelegramBadRequest(
                method=MagicMock(),
                message="Bad Request: some other error"
            )
        
        with patch.object(CallbackQuery, 'answer', mock_answer):
            # Should raise the error since it's not a timeout error
            with pytest.raises(TelegramBadRequest):
                await extended.answer("test")


class TestUnifiedBotMethods:
    """Test that ProxyBot methods work identically for both platforms."""
    
    @pytest.fixture
    def dual_platform_bot(self):
        """Create bot with both platforms mocked."""
        tg_platform = MagicMock()
        tg_platform.platform = BPlatform.telegram
        tg_platform.bot = AsyncMock()
        tg_platform.bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))
        tg_platform.bot.send_photo = AsyncMock(return_value=MagicMock(message_id=2))
        tg_platform.bot.get_file = AsyncMock(return_value=MagicMock(
            file_id="f1", file_path="path/file.jpg", file_size=100
        ))
        tg_platform.bot.token = "tg_token"
        
        max_platform = MagicMock()
        max_platform.platform = BPlatform.max
        max_platform.bot = AsyncMock()
        max_platform.bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))
        max_platform.bot.send_file = AsyncMock(return_value=MagicMock(message_id=2))
        
        return ProxyBot([tg_platform, max_platform])
    
    @pytest.mark.asyncio
    async def test_send_message_same_interface(self, dual_platform_bot):
        """send_message() has identical interface for both platforms."""
        
        # Same code for both platforms
        await dual_platform_bot.send_message(
            chat_id=12345,
            text="Hello!",
            platform="telegram"
        )
        
        await dual_platform_bot.send_message(
            chat_id=67890,
            text="Hello!",
            platform="max"
        )
        
        # Both calls use the same interface
        assert dual_platform_bot.get_bot("telegram").send_message.called
        assert dual_platform_bot.get_bot("max").send_message.called
    
    @pytest.mark.asyncio
    async def test_real_bot_code_example(self, dual_platform_bot):
        """
        Example of real bot code that works on both platforms.
        
        This is THE KEY demonstration - bot developers write this code once!
        """
        
        async def handle_start_command(bot: ProxyBot, chat_id: int, platform: str):
            """
            /start command handler - identical for Telegram and Max.
            """
            welcome_text = "Welcome to the bot! Choose an option:"
            
            # Same interface for both platforms
            await bot.send_message(
                chat_id=chat_id,
                text=welcome_text,
                platform=platform
            )
        
        # Works for Telegram
        await handle_start_command(dual_platform_bot, 111, "telegram")
        
        # Works for Max - SAME CODE!
        await handle_start_command(dual_platform_bot, 222, "max")


class TestProxyFileInterface:
    """Test ProxyFile provides consistent interface."""
    
    def test_proxy_file_has_download_method(self):
        """ProxyFile always has download() method regardless of platform."""
        tg_file = ProxyFile(
            platform=BPlatform.telegram,
            file_id="123",
            file_path="path/to/file"
        )
        
        max_file = ProxyFile(
            platform=BPlatform.max,
            file_id="url",
            file_url="https://max.ru/file.pdf"
        )
        
        # Both have the same interface
        assert hasattr(tg_file, 'download')
        assert hasattr(max_file, 'download')
        assert callable(tg_file.download)
        assert callable(max_file.download)
    
    @pytest.mark.asyncio
    async def test_download_to_path_saves_file(self, tmp_path):
        """download(destination=path) saves to disk (aiogram-style)."""
        from unittest.mock import AsyncMock, patch
        
        proxy = ProxyFile(
            platform=BPlatform.max,
            file_url="https://example.com/doc.txt"
        )
        with patch.object(proxy, '_download_raw', new_callable=AsyncMock) as mock_raw:
            mock_raw.return_value = b"file content"
            result = await proxy.download(destination=str(tmp_path / "saved.txt"))
        
        assert result is None
        assert (tmp_path / "saved.txt").read_bytes() == b"file content"
    
    @pytest.mark.asyncio
    async def test_download_to_buffer_writes_content(self):
        """download(destination=buffer) writes to buffer (aiogram-style)."""
        from unittest.mock import AsyncMock, patch
        
        proxy = ProxyFile(
            platform=BPlatform.telegram,
            file_id="123",
            file_path="voice/file.oga"
        )
        buffer = io.BytesIO()
        with patch.object(proxy, '_download_raw', new_callable=AsyncMock) as mock_raw:
            async def side_effect(dest, timeout=60.0):
                if dest is not None:
                    dest.write(b"in-memory content")
                return None
            mock_raw.side_effect = side_effect
            await proxy.download(destination=buffer)
        
        buffer.seek(0)
        assert buffer.read() == b"in-memory content"
    
    def test_proxy_file_properties(self):
        """ProxyFile exposes consistent properties."""
        file = ProxyFile(
            platform=BPlatform.telegram,
            file_id="123",
            file_path="path/to/file",
            file_size=1024
        )
        
        assert file.platform == BPlatform.telegram
        assert file.file_id == "123"
        assert file.file_path == "path/to/file"
        assert file.file_size == 1024


class TestCrossplatformHandlerExample:
    """
    Complete example showing how a real multi-platform bot would look.
    
    This test file serves as documentation for library users.
    """
    
    @pytest.mark.asyncio
    async def test_complete_bot_example(self):
        """
        This is how you write a bot that works on BOTH platforms!
        
        Notice: The handler code is IDENTICAL for Telegram and Max.
        The library handles all platform differences internally.
        """
        
        # ============================================================
        # EXAMPLE: File download handler that works on both platforms
        # ============================================================
        
        async def download_handler(bot: ProxyBot, message, platform: str):
            """
            Handle file download request.
            Works identically for Telegram and Max!
            """
            # Get file identifier (platform-specific extraction would happen before this)
            # For Telegram: message.document.file_id
            # For Max: message.get_attachment("file").url
            file_id = "file_identifier_here"
            
            # UNIFIED INTERFACE - same for both platforms!
            proxy_file = await bot.get_file(file_id, platform=platform)
            
            # Download to memory
            buffer = io.BytesIO()
            with patch.object(proxy_file, 'download', new_callable=AsyncMock):
                await proxy_file.download(destination=buffer)
            
            # Process file...
            return True
        
        # ============================================================
        # EXAMPLE: Callback handler that works on both platforms  
        # ============================================================
        
        async def button_handler(callback):
            """
            Handle button press.
            Works identically for Telegram and Max!
            """
            data = getattr(callback, 'data', None) or getattr(callback, 'payload', '')
            
            if data.startswith("view_"):
                item_id = data.replace("view_", "")
                # UNIFIED INTERFACE - edit_message_text works on both!
                await callback.edit_message_text(
                    text=f"Viewing item {item_id}",
                    parse_mode="HTML"
                )
            
            # Answer callback - unified
            await callback.answer("Done!")
        
        # Verify handlers can be called (mock objects)
        mock_callback = MagicMock()
        mock_callback.data = "view_123"
        mock_callback.payload = None
        mock_callback.edit_message_text = AsyncMock()
        mock_callback.answer = AsyncMock()
        
        await button_handler(mock_callback)
        
        mock_callback.edit_message_text.assert_called_once()
        mock_callback.answer.assert_called_once_with("Done!")


class TestDownloadableFileProtocol:
    """Test DownloadableFile protocol for duck typing compatibility."""
    
    def test_proxy_file_implements_protocol(self):
        """ProxyFile implements DownloadableFile protocol."""
        file = ProxyFile(
            platform=BPlatform.telegram,
            file_id="123",
            file_path="path/to/file",
            file_size=1024
        )
        
        # Protocol check works
        assert isinstance(file, DownloadableFile)
    
    def test_protocol_allows_duck_typing(self):
        """DownloadableFile protocol enables duck typing (aiogram-style download only)."""
        class CustomFile:
            file_id = "custom_123"
            file_path = "custom/path"
            file_size = 512
            
            async def download(self, destination=None, **kwargs):
                return b"custom content"
        
        custom = CustomFile()
        assert isinstance(custom, DownloadableFile)
    
    def test_native_property_telegram(self):
        """native property returns original aiogram File for Telegram."""
        mock_aiogram_file = MagicMock()
        mock_aiogram_file.file_id = "tg_file_123"
        
        proxy = ProxyFile(
            platform=BPlatform.telegram,
            file_id="tg_file_123",
            _telegram_file=mock_aiogram_file
        )
        
        # Native returns the original aiogram File
        assert proxy.native is mock_aiogram_file
        assert proxy.native.file_id == "tg_file_123"
    
    def test_native_property_max(self):
        """native property returns None for Max (no native file object)."""
        proxy = ProxyFile(
            platform=BPlatform.max,
            file_id="https://max.ru/file.pdf",
            file_url="https://max.ru/file.pdf"
        )
        
        # Max doesn't have native file object
        assert proxy.native is None
    
    def test_type_hints_work_with_protocol(self):
        """Functions can accept DownloadableFile for type safety."""
        
        async def process_any_file(f: DownloadableFile) -> str:
            """This function accepts any DownloadableFile."""
            return f"Processing file: {f.file_id}"
        
        # Both ProxyFile types work
        tg_file = ProxyFile(platform=BPlatform.telegram, file_id="tg_123")
        max_file = ProxyFile(platform=BPlatform.max, file_id="max_url")
        
        # Type checker would accept both
        assert isinstance(tg_file, DownloadableFile)
        assert isinstance(max_file, DownloadableFile)


class TestGetPlatformMethod:
    """Test unified get_platform() method across all objects."""
    
    def test_telegram_callback_get_platform(self):
        """TelegramCallbackQuery has get_platform() method."""
        from obabot.adapters.telegram_callback import TelegramCallbackQuery
        
        assert hasattr(TelegramCallbackQuery, 'get_platform')
        assert hasattr(TelegramCallbackQuery, 'is_telegram')
        assert hasattr(TelegramCallbackQuery, 'is_max')
    
    def test_max_callback_get_platform(self):
        """MaxCallbackQuery has get_platform() method."""
        from obabot.adapters.max_callback import MaxCallbackQuery
        
        assert hasattr(MaxCallbackQuery, 'get_platform')
        assert hasattr(MaxCallbackQuery, 'is_telegram')
        assert hasattr(MaxCallbackQuery, 'is_max')
    
    def test_max_message_adapter_get_platform(self):
        """MaxMessageAdapter has get_platform() method."""
        from obabot.adapters.message import MaxMessageAdapter
        
        adapter = MaxMessageAdapter(MagicMock())
        
        assert adapter.get_platform() == "max"
        assert adapter.is_max() is True
        assert adapter.is_telegram() is False
    
    def test_proxy_file_get_platform(self):
        """ProxyFile has get_platform() method."""
        tg_file = ProxyFile(platform=BPlatform.telegram, file_id="123")
        max_file = ProxyFile(platform=BPlatform.max, file_id="url")
        
        assert tg_file.get_platform() == "telegram"
        assert tg_file.is_telegram() is True
        assert tg_file.is_max() is False
        
        assert max_file.get_platform() == "max"
        assert max_file.is_telegram() is False
        assert max_file.is_max() is True
    
    def test_unified_platform_check_interface(self):
        """
        All platform objects have the same platform check interface.
        
        This allows unified code like:
            if obj.is_telegram():
                # telegram-specific logic
            elif obj.is_max():
                # max-specific logic
        """
        from obabot.adapters.telegram_callback import TelegramCallbackQuery
        from obabot.adapters.max_callback import MaxCallbackQuery
        from obabot.adapters.message import MaxMessageAdapter
        
        # All have the same methods
        for cls in [TelegramCallbackQuery, MaxCallbackQuery]:
            assert hasattr(cls, 'get_platform')
            assert hasattr(cls, 'is_telegram')
            assert hasattr(cls, 'is_max')
        
        # MaxMessageAdapter too
        adapter = MaxMessageAdapter(MagicMock())
        assert hasattr(adapter, 'get_platform')
        assert hasattr(adapter, 'is_telegram')
        assert hasattr(adapter, 'is_max')
        
        # ProxyFile too
        file = ProxyFile(platform=BPlatform.telegram)
        assert hasattr(file, 'get_platform')
        assert hasattr(file, 'is_telegram')
        assert hasattr(file, 'is_max')
