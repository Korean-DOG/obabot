"""Test all router handler types."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from obabot.filters import Command, F
from obabot import BPlatform


class TestRouterHandlerTypes:
    """Test all handler types in router."""
    
    def test_all_handler_types_exist(self, obabot_telegram_bot):
        """Test that all handler types are available."""
        _, _, router = obabot_telegram_bot
        
        # Check all handler types exist
        handler_types = [
            'message', 'callback_query', 'edited_message', 'channel_post',
            'inline_query', 'chosen_inline_result', 'shipping_query',
            'pre_checkout_query', 'my_chat_member', 'chat_member',
            'error', 'poll', 'poll_answer', 'chat_join_request',
            'edited_channel_post'
        ]
        
        for handler_type in handler_types:
            assert hasattr(router, handler_type), f"Handler type {handler_type} not found"
            handler_method = getattr(router, handler_type)
            assert callable(handler_method), f"Handler {handler_type} is not callable"
    
    def test_all_handlers_are_callable(self, obabot_telegram_bot):
        """Test that all handlers can be used as decorators."""
        _, _, router = obabot_telegram_bot
        
        @router.message()
        async def msg_handler(message):
            pass
        
        @router.callback_query()
        async def cb_handler(callback):
            pass
        
        @router.poll()
        async def poll_handler(poll):
            pass
        
        # All should be registered and callable
        assert callable(msg_handler)
        assert callable(cb_handler)
        assert callable(poll_handler)
    
    def test_handler_decorator_returns_handler(self, obabot_telegram_bot):
        """Test that decorators return the original handler function."""
        _, _, router = obabot_telegram_bot
        
        async def original_handler(message):
            return "test"
        
        # Decorator should return the same function
        decorated = router.message()(original_handler)
        assert decorated is original_handler
        
        # With filters
        decorated_with_filter = router.message(Command("test"))(original_handler)
        assert decorated_with_filter is original_handler
    
    def test_multiple_handlers_same_type(self, obabot_telegram_bot):
        """Test registering multiple handlers of the same type."""
        _, _, router = obabot_telegram_bot
        
        @router.message(Command("cmd1"))
        async def handler1(message):
            pass
        
        @router.message(Command("cmd2"))
        async def handler2(message):
            pass
        
        @router.message(Command("cmd3"))
        async def handler3(message):
            pass
        
        # All should be registered
        assert all(callable(h) for h in [handler1, handler2, handler3])
    
    def test_platform_specific_handlers(self, obabot_telegram_bot, obabot_dual_bot):
        """Test that platform-specific handlers work correctly."""
        # Telegram-specific handlers
        _, _, tg_router = obabot_telegram_bot
        
        @tg_router.channel_post()
        async def channel_post_handler(post):
            pass
        
        @tg_router.inline_query()
        async def inline_query_handler(query):
            pass
        
        assert callable(channel_post_handler)
        assert callable(inline_query_handler)
        
        # Dual platform - handlers should register on both
        bot, _, dual_router = obabot_dual_bot
        
        @dual_router.message(Command("test"))
        async def dual_handler(message):
            pass
        
        assert callable(dual_handler)
        assert len(bot.platforms) == 2


class TestDispatcherDelegation:
    """Test that dispatcher delegates to router."""
    
    def test_dp_handlers_delegate_to_router(self, obabot_telegram_bot):
        """Test that dp.message() delegates to router.message()."""
        _, dp, router = obabot_telegram_bot
        
        # Both should work
        @router.message(Command("test"))
        async def router_handler(message):
            pass
        
        @dp.message(Command("test2"))
        async def dp_handler(message):
            pass
        
        assert callable(router_handler)
        assert callable(dp_handler)
    
    def test_all_dp_handlers_delegate(self, obabot_telegram_bot):
        """Test that all dp.* handlers delegate to router."""
        _, dp, router = obabot_telegram_bot
        
        handler_types = [
            'message', 'callback_query', 'edited_message', 'channel_post',
            'inline_query', 'chosen_inline_result', 'shipping_query',
            'pre_checkout_query', 'my_chat_member', 'chat_member',
            'error', 'poll', 'poll_answer', 'chat_join_request',
            'edited_channel_post'
        ]
        
        for handler_type in handler_types:
            dp_method = getattr(dp, handler_type)
            router_method = getattr(router, handler_type)
            assert callable(dp_method), f"dp.{handler_type} is not callable"
            assert callable(router_method), f"router.{handler_type} is not callable"
    
    def test_dp_handler_without_router_raises(self, tg_token, skip_if_no_tg_token):
        """Test that dp handlers raise error if router is not initialized."""
        from obabot.proxy.dispatcher import ProxyDispatcher
        from obabot.platforms.telegram import TelegramPlatform
        
        # Create dispatcher without router using valid token
        platform = TelegramPlatform(tg_token)
        dp = ProxyDispatcher([platform], router=None)
        
        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="Router not initialized"):
            @dp.message(Command("test"))
            async def handler(message):
                pass


class TestRouterHandlerExecution:
    """Test that router handlers actually execute."""
    
    @pytest.mark.asyncio
    async def test_handler_execution_through_platform(self, obabot_telegram_bot):
        """Test that handlers execute when called through platform."""
        bot, _, router = obabot_telegram_bot
        
        handler_called = False
        
        @router.message(Command("test"))
        async def test_handler(message):
            nonlocal handler_called
            handler_called = True
        
        # Get platform and wrap handler
        platform = bot._platforms[0]
        wrapped = platform.wrap_handler(test_handler)
        
        # Create mock message
        mock_message = MagicMock()
        mock_message.text = "/test"
        mock_message.from_user = MagicMock()
        mock_message.chat = MagicMock()
        
        # Execute wrapped handler
        await wrapped(mock_message)
        
        assert handler_called is True
    
    @pytest.mark.asyncio
    async def test_handler_registration_on_all_platforms(self, obabot_dual_bot):
        """Test that handlers are registered on all platforms in dual mode."""
        bot, _, router = obabot_dual_bot
        
        handler_calls = []
        
        @router.message(Command("test"))
        async def test_handler(message):
            handler_calls.append(getattr(message, 'platform', 'unknown'))
        
        # Handler should be registered for both platforms
        assert callable(test_handler)
        assert len(bot.platforms) == 2
        
        # Execute handler through each platform
        for platform_type in bot.platforms:
            platform = bot._platform_map[platform_type]
            wrapped = platform.wrap_handler(test_handler)
            
            mock_message = MagicMock()
            mock_message.text = "/test"
            mock_message.from_user = MagicMock()
            mock_message.chat = MagicMock()
            
            await wrapped(mock_message)
        
        # Handler should have been called for both platforms
        assert len(handler_calls) == 2
    
    @pytest.mark.asyncio
    async def test_handler_wrapping(self, obabot_telegram_bot):
        """Test that handlers are properly wrapped by platform."""
        bot, _, router = obabot_telegram_bot
        
        original_handler_called = False
        
        async def original_handler(message):
            nonlocal original_handler_called
            original_handler_called = True
            return "result"
        
        # Register handler
        wrapped = router.message(Command("test"))(original_handler)
        
        # Get platform and wrap handler
        platform = bot._platforms[0]
        platform_wrapped = platform.wrap_handler(original_handler)
        
        # Create mock message
        mock_message = MagicMock()
        mock_message.text = "/test"
        mock_message.from_user = MagicMock()
        mock_message.chat = MagicMock()
        
        # Execute wrapped handler
        result = await platform_wrapped(mock_message)
        
        assert original_handler_called is True
        assert result == "result"
    
    @pytest.mark.asyncio
    async def test_handler_with_fsm_state(self, obabot_telegram_bot):
        """Test handlers with FSM state (state is injected automatically, not via kwargs)."""
        from obabot.fsm import State, StatesGroup, FSMContext
        
        bot, _, router = obabot_telegram_bot
        
        handler_called = False
        received_state = None
        
        class TestStates(StatesGroup):
            waiting = State()
        
        # In aiogram 3.x, state is injected automatically via dependency injection
        # We register handler with state filter, not state kwarg
        @router.message(Command("test"), TestStates.waiting)
        async def handler_with_state(message, state: FSMContext):
            nonlocal handler_called, received_state
            handler_called = True
            received_state = state
        
        # Create mock message and state
        mock_message = MagicMock()
        mock_message.text = "/test"
        mock_message.from_user = MagicMock()
        mock_message.chat = MagicMock()
        
        mock_state = AsyncMock(spec=FSMContext)
        
        # Execute handler directly (state would be injected by dispatcher in real scenario)
        await handler_with_state(mock_message, mock_state)
        
        assert handler_called is True
        assert received_state is mock_state
    
    @pytest.mark.asyncio
    async def test_handler_filter_combinations(self, obabot_telegram_bot):
        """Test handlers with multiple filters."""
        bot, _, router = obabot_telegram_bot
        
        handler_called = False
        
        @router.message(Command("start"), F.text)
        async def handler_with_multiple_filters(message):
            nonlocal handler_called
            handler_called = True
        
        # Get platform and wrap handler
        platform = bot._platforms[0]
        wrapped = platform.wrap_handler(handler_with_multiple_filters)
        
        # Create mock message that matches filters
        mock_message = MagicMock()
        mock_message.text = "/start"
        mock_message.from_user = MagicMock()
        mock_message.chat = MagicMock()
        
        # Execute handler
        await wrapped(mock_message)
        
        assert handler_called is True


class TestErrorHandlerWrapper:
    """Test error handler wrapping for aiogram 3.x compatibility."""
    
    @pytest.mark.asyncio
    async def test_error_handler_wrapper_extracts_exception(self):
        """Test that error handler wrapper extracts exception from ErrorEvent."""
        from obabot.proxy.router import _wrap_error_handler
        
        received_event = None
        received_exc = None
        
        async def error_handler(event, exc):
            nonlocal received_event, received_exc
            received_event = event
            received_exc = exc
        
        wrapped = _wrap_error_handler(error_handler)
        
        # Simulate aiogram ErrorEvent
        mock_error_event = MagicMock()
        mock_error_event.exception = ValueError("Test error")
        mock_error_event.update = MagicMock()
        
        await wrapped(mock_error_event)
        
        assert received_event == mock_error_event.update
        assert isinstance(received_exc, ValueError)
        assert str(received_exc) == "Test error"
    
    @pytest.mark.asyncio
    async def test_error_handler_wrapper_single_param(self):
        """Test error handler with single parameter signature."""
        from obabot.proxy.router import _wrap_error_handler
        
        received = None
        
        async def error_handler(error_event):
            nonlocal received
            received = error_event
        
        wrapped = _wrap_error_handler(error_handler)
        
        mock_error_event = MagicMock()
        mock_error_event.exception = RuntimeError("Error")
        
        await wrapped(mock_error_event)
        
        assert received == mock_error_event
