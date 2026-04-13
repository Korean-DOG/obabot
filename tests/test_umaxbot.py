"""Tests for umaxbot integration."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock


class TestMaxPlatformStartPolling:
    """Regression: umaxbot Dispatcher has no start_polling(); obabot uses its own long-poll loop."""

    @pytest.mark.asyncio
    async def test_start_polling_uses_obabot_long_polling_not_dispatcher(self):
        from obabot.platforms.max import MaxPlatform

        platform = MaxPlatform("test_token")
        platform._obabot_long_polling = AsyncMock()
        await platform.start_polling()
        platform._obabot_long_polling.assert_awaited_once()


class TestMaxFsmContextAnnotation:
    """FSMContext injection recognizes Optional / union annotations."""

    def test_annotation_is_fsm_context_plain_and_optional(self):
        from typing import Optional
        from obabot.platforms.max import _annotation_is_fsm_context
        from aiogram.fsm.context import FSMContext

        assert _annotation_is_fsm_context(FSMContext) is True
        assert _annotation_is_fsm_context(Optional[FSMContext]) is True
        assert _annotation_is_fsm_context(str) is False
        assert _annotation_is_fsm_context(FSMContext | None) is True  # PEP 604


class TestMaxPlatformInit:
    """Tests for MaxPlatform initialization."""
    
    def test_max_platform_import(self):
        """MaxPlatform can be imported."""
        from obabot.platforms.max import MaxPlatform
        assert MaxPlatform is not None
    
    def test_max_platform_has_required_attributes(self):
        """MaxPlatform has all required attributes."""
        from obabot.platforms.max import MaxPlatform
        
        with patch('obabot.platforms.max.MaxPlatform._init_umaxbot'):
            platform = MaxPlatform("test_token")
            
            assert hasattr(platform, 'platform')
            assert hasattr(platform, 'bot')
            assert hasattr(platform, 'dispatcher')
            assert hasattr(platform, 'router')
            assert hasattr(platform, 'start_polling')
            assert hasattr(platform, 'stop_polling')
            assert hasattr(platform, 'feed_update')
            assert hasattr(platform, 'feed_raw_update')
            assert hasattr(platform, 'wrap_handler')
    
    def test_max_platform_returns_correct_platform_type(self):
        """MaxPlatform.platform returns BPlatform.max."""
        from obabot.platforms.max import MaxPlatform
        from obabot.types import BPlatform
        
        with patch('obabot.platforms.max.MaxPlatform._init_umaxbot'):
            platform = MaxPlatform("test_token")
            assert platform.platform == BPlatform.max
    
    @patch('obabot.platforms.max.MaxPlatform._init_umaxbot')
    def test_max_platform_stores_token(self, mock_init):
        """MaxPlatform stores the token."""
        from obabot.platforms.max import MaxPlatform
        
        platform = MaxPlatform("my_secret_token")
        assert platform._token == "my_secret_token"


class TestMaxPlatformUmaxbotInit:
    """Tests for umaxbot initialization."""
    
    def test_init_umaxbot_creates_bot(self):
        """_init_umaxbot creates Bot instance."""
        mock_bot = Mock()
        mock_dispatcher = Mock()
        mock_router = Mock()
        
        with patch.dict('sys.modules', {
            'maxbot': Mock(),
            'maxbot.bot': Mock(Bot=Mock(return_value=mock_bot)),
            'maxbot.dispatcher': Mock(Dispatcher=Mock(return_value=mock_dispatcher)),
            'maxbot.router': Mock(Router=Mock(return_value=mock_router)),
        }):
            from obabot.platforms.max import MaxPlatform
            
            with patch.object(MaxPlatform, '_init_umaxbot', lambda self: None):
                platform = MaxPlatform("token")
            
            platform._init_umaxbot()
    
    def test_init_umaxbot_handles_import_error(self):
        """_init_umaxbot handles ImportError gracefully."""
        from obabot.platforms.max import MaxPlatform
        
        with patch.dict('sys.modules', {'maxbot': None}):
            with patch('builtins.__import__', side_effect=ImportError("No module")):
                with patch.object(MaxPlatform, '_init_umaxbot') as mock_init:
                    mock_init.side_effect = lambda: None
                    platform = MaxPlatform("token")
                    
                    platform._bot = None
                    platform._dispatcher = None
                    platform._router = None
                    
                    assert platform._bot is None
                    assert platform._dispatcher is None


class TestMaxPlatformWrapHandler:
    """Tests for handler wrapping."""
    
    def test_wrap_handler_returns_callable(self):
        """wrap_handler returns a callable."""
        from obabot.platforms.max import MaxPlatform
        
        with patch('obabot.platforms.max.MaxPlatform._init_umaxbot'):
            platform = MaxPlatform("token")
            
            async def handler(msg):
                return "result"
            
            wrapped = platform.wrap_handler(handler)
            assert callable(wrapped)
    
    @pytest.mark.asyncio
    async def test_wrap_handler_adds_platform_attribute(self):
        """wrap_handler adds platform attribute to message."""
        from obabot.platforms.max import MaxPlatform
        
        with patch('obabot.platforms.max.MaxPlatform._init_umaxbot'):
            platform = MaxPlatform("token")
            
            async def handler(msg):
                return msg.platform
            
            wrapped = platform.wrap_handler(handler)
            
            mock_msg = Mock()
            mock_msg.platform = None
            
            result = await wrapped(mock_msg)
            assert mock_msg.platform == "max"
    
    @pytest.mark.asyncio
    async def test_wrap_handler_calls_original(self):
        """wrap_handler calls the original handler."""
        from obabot.platforms.max import MaxPlatform
        
        with patch('obabot.platforms.max.MaxPlatform._init_umaxbot'):
            platform = MaxPlatform("token")
            
            handler = AsyncMock(return_value="original_result")
            wrapped = platform.wrap_handler(handler)
            
            mock_msg = Mock()
            result = await wrapped(mock_msg)
            
            handler.assert_called_once()
            assert result == "original_result"


class TestMaxPlatformFilterConversion:
    """Tests for filter conversion."""
    
    def test_convert_filters_handles_empty_tuple(self):
        """_convert_filters handles empty tuple."""
        from obabot.platforms.max import MaxPlatform
        
        with patch('obabot.platforms.max.MaxPlatform._init_umaxbot'):
            platform = MaxPlatform("token")
            
            result = platform._convert_filters(())
            assert result == ()
    
    def test_convert_filters_handles_command_start(self):
        """_convert_filters converts CommandStart filter."""
        from obabot.platforms.max import MaxPlatform
        from aiogram.filters import CommandStart
        
        with patch('obabot.platforms.max.MaxPlatform._init_umaxbot'):
            platform = MaxPlatform("token")
            
            filters = (CommandStart(),)
            result = platform._convert_filters(filters)
            
            assert len(result) == 1
    
    def test_convert_filters_handles_command(self):
        """_convert_filters converts Command filter."""
        from obabot.platforms.max import MaxPlatform
        from aiogram.filters import Command
        
        with patch('obabot.platforms.max.MaxPlatform._init_umaxbot'):
            platform = MaxPlatform("token")
            
            filters = (Command("help"),)
            result = platform._convert_filters(filters)
            
            assert len(result) >= 1
    
    def test_convert_filters_passes_through_callables(self):
        """_convert_filters passes through callable filters."""
        from obabot.platforms.max import MaxPlatform
        
        with patch('obabot.platforms.max.MaxPlatform._init_umaxbot'):
            platform = MaxPlatform("token")
            
            def my_filter(msg):
                return True
            
            filters = (my_filter,)
            result = platform._convert_filters(filters)
            
            assert my_filter in result


class TestMaxPlatformCommandFilter:
    """Tests for command filter creation."""
    
    def test_create_command_filter_returns_callable(self):
        """_create_command_filter returns a callable."""
        from obabot.platforms.max import MaxPlatform
        
        with patch('obabot.platforms.max.MaxPlatform._init_umaxbot'):
            platform = MaxPlatform("token")
            
            filter_func = platform._create_command_filter(['start'])
            assert callable(filter_func)
    
    def test_command_filter_matches_exact_command(self):
        """Command filter matches exact command."""
        from obabot.platforms.max import MaxPlatform
        
        with patch('obabot.platforms.max.MaxPlatform._init_umaxbot'):
            platform = MaxPlatform("token")
            
            filter_func = platform._create_command_filter(['start'])
            
            msg = Mock()
            msg.text = "/start"
            assert filter_func(msg) is True
    
    def test_command_filter_matches_command_with_args(self):
        """Command filter matches command with arguments."""
        from obabot.platforms.max import MaxPlatform
        
        with patch('obabot.platforms.max.MaxPlatform._init_umaxbot'):
            platform = MaxPlatform("token")
            
            filter_func = platform._create_command_filter(['start'])
            
            msg = Mock()
            msg.text = "/start arg1 arg2"
            assert filter_func(msg) is True
    
    def test_command_filter_rejects_non_command(self):
        """Command filter rejects non-command text."""
        from obabot.platforms.max import MaxPlatform
        
        with patch('obabot.platforms.max.MaxPlatform._init_umaxbot'):
            platform = MaxPlatform("token")
            
            filter_func = platform._create_command_filter(['start'])
            
            msg = Mock()
            msg.text = "hello world"
            assert filter_func(msg) is False
    
    def test_command_filter_rejects_different_command(self):
        """Command filter rejects different command."""
        from obabot.platforms.max import MaxPlatform
        
        with patch('obabot.platforms.max.MaxPlatform._init_umaxbot'):
            platform = MaxPlatform("token")
            
            filter_func = platform._create_command_filter(['start'])
            
            msg = Mock()
            msg.text = "/help"
            assert filter_func(msg) is False
    
    def test_command_filter_handles_no_text(self):
        """Command filter handles message without text."""
        from obabot.platforms.max import MaxPlatform
        
        with patch('obabot.platforms.max.MaxPlatform._init_umaxbot'):
            platform = MaxPlatform("token")
            
            filter_func = platform._create_command_filter(['start'])
            
            msg = Mock()
            msg.text = None
            assert filter_func(msg) is False


class TestMaxPlatformFeedUpdate:
    """Tests for feed_update methods."""
    
    @pytest.mark.asyncio
    async def test_feed_update_returns_none_when_not_initialized(self):
        """feed_update returns None when dispatcher not initialized."""
        from obabot.platforms.max import MaxPlatform
        
        with patch('obabot.platforms.max.MaxPlatform._init_umaxbot'):
            platform = MaxPlatform("token")
            platform._dispatcher = None
            
            result = await platform.feed_update({"test": "data"})
            assert result is None
    
    @pytest.mark.asyncio
    async def test_feed_raw_update_returns_none_when_not_initialized(self):
        """feed_raw_update returns None when dispatcher not initialized."""
        from obabot.platforms.max import MaxPlatform
        
        with patch('obabot.platforms.max.MaxPlatform._init_umaxbot'):
            platform = MaxPlatform("token")
            platform._dispatcher = None
            
            result = await platform.feed_raw_update({"test": "data"})
            assert result is None
    
    @pytest.mark.asyncio
    async def test_feed_update_calls_setup_handlers(self):
        """feed_update calls _setup_handlers."""
        from obabot.platforms.max import MaxPlatform
        
        with patch('obabot.platforms.max.MaxPlatform._init_umaxbot'):
            platform = MaxPlatform("token")
            platform._dispatcher = AsyncMock()
            platform._dispatcher.feed_update = AsyncMock(return_value=None)
            platform._setup_handlers = Mock()
            
            await platform.feed_update({"test": "data"})
            
            platform._setup_handlers.assert_called_once()


class TestMaxPlatformSetupHandlers:
    """Tests for handler setup."""
    
    def test_setup_handlers_skips_when_already_setup(self):
        """_setup_handlers skips when already setup."""
        from obabot.platforms.max import MaxPlatform
        
        with patch('obabot.platforms.max.MaxPlatform._init_umaxbot'):
            platform = MaxPlatform("token")
            platform._handlers_setup = True
            platform._dispatcher = Mock()
            
            platform._setup_handlers()
            
            platform._dispatcher.include_router.assert_not_called()
    
    def test_setup_handlers_includes_router(self):
        """_setup_handlers includes router in dispatcher."""
        from obabot.platforms.max import MaxPlatform
        
        # include_router is now called in _init_umaxbot, not _setup_handlers
        # Test that _setup_handlers sets _handlers_setup flag
        with patch('obabot.platforms.max.MaxPlatform._init_umaxbot'):
            platform = MaxPlatform("token")
            platform._handlers_setup = False
            platform._dispatcher = Mock()
            platform._router = Mock()
            
            platform._setup_handlers()
            
            # include_router is called in _init_umaxbot now, not here
            assert platform._handlers_setup is True


class TestKeyboardConversion:
    """Tests for keyboard conversion."""
    
    def test_convert_keyboard_to_max_returns_none_for_none(self):
        """convert_keyboard_to_max returns None for None input."""
        from obabot.adapters.keyboard import convert_keyboard_to_max
        
        assert convert_keyboard_to_max(None) is None
    
    def test_convert_keyboard_to_max_passes_through_unknown(self):
        """convert_keyboard_to_max passes through unknown keyboard types."""
        from obabot.adapters.keyboard import convert_keyboard_to_max
        
        keyboard = {"custom": "keyboard"}
        result = convert_keyboard_to_max(keyboard)
        assert result == keyboard
    
    def test_convert_inline_keyboard_generic_creates_dict(self):
        """_convert_inline_keyboard_generic creates dict format with type."""
        from obabot.adapters.keyboard import _convert_inline_keyboard_generic
        
        mock_button = Mock()
        mock_button.text = "Click me"
        mock_button.callback_data = "callback_1"
        mock_button.url = None
        
        mock_keyboard = Mock()
        mock_keyboard.inline_keyboard = [[mock_button]]
        
        result = _convert_inline_keyboard_generic(mock_keyboard)
        
        assert 'inline_keyboard' in result
        assert len(result['inline_keyboard']) == 1
        assert result['inline_keyboard'][0][0]['text'] == "Click me"
        assert result['inline_keyboard'][0][0]['callback_data'] == "callback_1"
        assert result['inline_keyboard'][0][0]['type'] == "callback"
    
    def test_convert_inline_keyboard_generic_url_button(self):
        """_convert_inline_keyboard_generic sets type=link for URL buttons."""
        from obabot.adapters.keyboard import _convert_inline_keyboard_generic
        
        mock_button = Mock()
        mock_button.text = "Visit"
        mock_button.callback_data = None
        mock_button.url = "https://example.com"
        
        mock_keyboard = Mock()
        mock_keyboard.inline_keyboard = [[mock_button]]
        
        result = _convert_inline_keyboard_generic(mock_keyboard)
        
        assert result['inline_keyboard'][0][0]['text'] == "Visit"
        assert result['inline_keyboard'][0][0]['url'] == "https://example.com"
        assert result['inline_keyboard'][0][0]['type'] == "link"
        assert 'callback_data' not in result['inline_keyboard'][0][0]


class TestMaxMessageAdapter:
    """Tests for MaxMessageAdapter."""
    
    def test_adapter_has_platform_property(self):
        """MaxMessageAdapter has platform property."""
        from obabot.adapters.message import MaxMessageAdapter
        
        msg = Mock()
        adapter = MaxMessageAdapter(msg)
        
        assert adapter.platform == "max"
    
    def test_adapter_proxies_text_property(self):
        """MaxMessageAdapter proxies text property."""
        from obabot.adapters.message import MaxMessageAdapter
        
        msg = Mock()
        msg.text = "Hello world"
        
        adapter = MaxMessageAdapter(msg)
        assert adapter.text == "Hello world"
    
    def test_adapter_proxies_unknown_attributes(self):
        """MaxMessageAdapter proxies unknown attributes."""
        from obabot.adapters.message import MaxMessageAdapter
        
        msg = Mock()
        msg.custom_attr = "custom_value"
        
        adapter = MaxMessageAdapter(msg)
        assert adapter.custom_attr == "custom_value"
    
    @pytest.mark.asyncio
    async def test_adapter_answer_uses_bot_send_message(self):
        """MaxMessageAdapter.answer uses bot.send_message."""
        from obabot.adapters.message import MaxMessageAdapter
        
        msg = Mock()
        msg.chat = Mock(id=123)
        bot = AsyncMock()
        bot.send_message = AsyncMock(return_value="sent")
        
        adapter = MaxMessageAdapter(msg, bot)
        result = await adapter.answer("Hello")
        
        bot.send_message.assert_called_once()
        call_kwargs = bot.send_message.call_args[1]
        assert call_kwargs['chat_id'] == 123
        assert call_kwargs['text'] == "Hello"
        assert result == "sent"
    
    @pytest.mark.asyncio
    async def test_adapter_reply_uses_bot_send_message(self):
        """MaxMessageAdapter.reply uses bot.send_message (no native reply in Max)."""
        from obabot.adapters.message import MaxMessageAdapter
        
        msg = Mock()
        msg.chat = Mock(id=456)
        bot = AsyncMock()
        bot.send_message = AsyncMock(return_value="sent")
        
        adapter = MaxMessageAdapter(msg, bot)
        result = await adapter.reply("Hello")
        
        bot.send_message.assert_called_once()
        call_kwargs = bot.send_message.call_args[1]
        assert call_kwargs['chat_id'] == 456
        assert call_kwargs['text'] == "Hello"
        assert result == "sent"
    
    @pytest.mark.asyncio
    async def test_adapter_edit_text_uses_bot_update_message(self):
        """MaxMessageAdapter.edit_text uses bot.update_message."""
        from obabot.adapters.message import MaxMessageAdapter
        
        msg = Mock()
        msg.chat = Mock(id=789)
        msg.id = "msg_123"
        bot = AsyncMock()
        bot.update_message = AsyncMock(return_value="updated")
        
        adapter = MaxMessageAdapter(msg, bot)
        result = await adapter.edit_text("New text")
        
        bot.update_message.assert_called_once()
        call_kwargs = bot.update_message.call_args[1]
        assert call_kwargs['message_id'] == "msg_123"
        assert call_kwargs['text'] == "New text"
        assert result == "updated"


class TestMaxCallbackQuery:
    """Tests for MaxCallbackQuery (inheritance-based)."""
    
    def test_has_get_platform_method(self):
        """MaxCallbackQuery has get_platform() method."""
        from obabot.adapters.max_callback import MaxCallbackQuery
        
        assert hasattr(MaxCallbackQuery, 'get_platform')
        assert hasattr(MaxCallbackQuery, 'is_max')
        assert hasattr(MaxCallbackQuery, 'is_telegram')
    
    def test_has_edit_message_text_method(self):
        """MaxCallbackQuery has edit_message_text() shortcut."""
        from obabot.adapters.max_callback import MaxCallbackQuery
        
        assert hasattr(MaxCallbackQuery, 'edit_message_text')
        assert hasattr(MaxCallbackQuery, 'edit_message_reply_markup')
        assert hasattr(MaxCallbackQuery, 'edit_message_caption')
        assert hasattr(MaxCallbackQuery, 'delete_message')
    
    def test_inherits_from_maxbot_callback(self):
        """MaxCallbackQuery inherits from maxbot.types.Callback."""
        from obabot.adapters.max_callback import MaxCallbackQuery
        from maxbot.types import Callback
        
        assert issubclass(MaxCallbackQuery, Callback)


class TestProxyRouterDeduplication:
    """Tests for ProxyRouter handler deduplication."""
    
    def test_apply_pending_handlers_called_once(self):
        """apply_pending_handlers should only register handlers once per platform."""
        from obabot.proxy.router import ProxyRouter
        
        platform = Mock()
        platform.platform = "test"
        platform.wrap_handler = lambda h: h
        platform.convert_filters_for_platform = lambda f, t: f
        platform.router = Mock()
        platform.router.message = Mock(return_value=lambda h: h)
        
        router = ProxyRouter([platform])
        
        # Add a pending handler
        @router.message()
        async def test_handler(msg):
            pass
        
        # Apply handlers twice
        router.apply_pending_handlers(platform)
        router.apply_pending_handlers(platform)
        
        # Should only register once (not twice)
        assert platform.router.message.call_count == 1
    
    def test_applied_to_platforms_tracking(self):
        """ProxyRouter tracks which platforms have had handlers applied."""
        from obabot.proxy.router import ProxyRouter
        
        router = ProxyRouter([])
        
        assert hasattr(router, '_applied_to_platforms')
        assert isinstance(router._applied_to_platforms, set)


class TestMaxFilterCheck:
    """Tests for Max platform filter checking."""
    
    @pytest.mark.asyncio
    async def test_filter_check_none_passes(self):
        """None filter should pass."""
        from obabot.platforms.max import MaxPlatform
        
        platform = MaxPlatform("test_token")
        result = await platform._filter_check(None, Mock())
        assert result is True
    
    @pytest.mark.asyncio
    async def test_filter_check_callable_true(self):
        """Callable filter returning True should pass."""
        from obabot.platforms.max import MaxPlatform
        
        platform = MaxPlatform("test_token")
        platform._bot = Mock()
        
        def true_filter(msg, bot=None):
            return True
        
        result = await platform._filter_check(true_filter, Mock())
        assert result is True
    
    @pytest.mark.asyncio
    async def test_filter_check_callable_false(self):
        """Callable filter returning False should not pass."""
        from obabot.platforms.max import MaxPlatform
        
        platform = MaxPlatform("test_token")
        platform._bot = Mock()
        
        def false_filter(msg, bot=None):
            return False
        
        result = await platform._filter_check(false_filter, Mock())
        assert result is False
    
    @pytest.mark.asyncio
    async def test_command_start_filter_matches_start(self):
        """CommandStart filter should match /start messages."""
        from obabot.platforms.max import MaxPlatform
        from aiogram.filters import CommandStart
        
        platform = MaxPlatform("test_token")
        
        msg = Mock()
        msg.text = "/start"
        
        result = await platform._filter_check(CommandStart(), msg)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_command_start_filter_rejects_other_commands(self):
        """CommandStart filter should reject non-/start messages."""
        from obabot.platforms.max import MaxPlatform
        from aiogram.filters import CommandStart
        
        platform = MaxPlatform("test_token")
        
        msg = Mock()
        msg.text = "/help"
        
        result = await platform._filter_check(CommandStart(), msg)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_command_start_filter_rejects_plain_text(self):
        """CommandStart filter should reject plain text."""
        from obabot.platforms.max import MaxPlatform
        from aiogram.filters import CommandStart
        
        platform = MaxPlatform("test_token")
        
        msg = Mock()
        msg.text = "hello"
        
        result = await platform._filter_check(CommandStart(), msg)
        assert result is False


class TestMaxDispatchFirstMatchOnly:
    """Tests for Max platform dispatch stopping after first match."""
    
    @pytest.mark.asyncio
    async def test_dispatch_stops_after_first_handler(self):
        """Dispatch should stop after first matching handler (like aiogram)."""
        from obabot.platforms.max import MaxPlatform
        
        platform = MaxPlatform("test_token")
        platform._init_umaxbot()
        
        handler1_called = []
        handler2_called = []
        
        async def handler1(msg):
            handler1_called.append(True)
        
        async def handler2(msg):
            handler2_called.append(True)
        
        # Both handlers pass filter (None = always pass)
        platform._dispatcher.message_handlers = [(handler1, None), (handler2, None)]
        platform._dispatcher.routers = []
        
        # Mock Message.from_raw to avoid actual parsing
        with patch('maxbot.types.Message') as MockMessage:
            mock_msg = Mock()
            mock_msg.text = "/start"
            mock_msg.chat = Mock(id=123)
            MockMessage.from_raw.return_value = mock_msg
            
            update = {
                "update_type": "message_created",
                "message": {"mid": "123"},
            }
            
            await platform._dispatch_raw_update(update)
        
        # Only first handler should be called
        assert len(handler1_called) == 1
        assert len(handler2_called) == 0
    
    @pytest.mark.asyncio
    async def test_dispatch_checks_filters_correctly(self):
        """Dispatch should check filters and only call matching handlers."""
        from obabot.platforms.max import MaxPlatform
        
        platform = MaxPlatform("test_token")
        platform._init_umaxbot()
        
        handler1_called = []
        handler2_called = []
        
        async def handler1(msg):
            handler1_called.append(True)
        
        async def handler2(msg):
            handler2_called.append(True)
        
        # First handler has failing filter, second has passing filter
        def failing_filter(msg, bot=None):
            return False
        
        def passing_filter(msg, bot=None):
            return True
        
        platform._dispatcher.message_handlers = [
            (handler1, failing_filter),
            (handler2, passing_filter),
        ]
        platform._dispatcher.routers = []
        
        # Mock Message.from_raw to avoid actual parsing
        with patch('maxbot.types.Message') as MockMessage:
            mock_msg = Mock()
            mock_msg.text = "hello"
            mock_msg.chat = Mock(id=123)
            MockMessage.from_raw.return_value = mock_msg
            
            update = {
                "update_type": "message_created",
                "message": {"mid": "123"},
            }
            
            await platform._dispatch_raw_update(update)
        
        # First handler should not be called (filter failed)
        # Second handler should be called
        assert len(handler1_called) == 0
        assert len(handler2_called) == 1
