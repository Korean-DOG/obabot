"""Test dispatcher functionality."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock


class TestDispatcherMethods:
    """Test dispatcher methods."""
    
    def test_dispatcher_methods_exist(self, obabot_telegram_bot):
        """Test that all dispatcher methods exist."""
        _, dp, _ = obabot_telegram_bot
        
        assert hasattr(dp, 'start_polling')
        assert hasattr(dp, 'stop_polling')
        assert hasattr(dp, 'include_router')
        assert hasattr(dp, 'start')
        assert hasattr(dp, 'run_polling')
        assert hasattr(dp, 'middleware')
        assert hasattr(dp, 'workflow_data')
    
    def test_workflow_data_property(self, obabot_telegram_bot):
        """Test workflow_data property."""
        _, dp, _ = obabot_telegram_bot
        
        # Should be accessible
        data = dp.workflow_data
        assert isinstance(data, dict)
        
        # Should be settable
        dp.workflow_data = {"test": "value"}
        assert dp.workflow_data.get("test") == "value"
    
    def test_fsm_storage_property(self, obabot_telegram_bot):
        """Test fsm_storage property for setting FSM storage across platforms."""
        _, dp, _ = obabot_telegram_bot
        
        # Should have fsm_storage property
        assert hasattr(dp, 'fsm_storage')
        
        # Should be settable
        from obabot.fsm import MemoryStorage
        storage = MemoryStorage()
        dp.fsm_storage = storage
        
        # Should return the same storage
        assert dp.fsm_storage is storage
    
    def test_middleware_registration(self, obabot_telegram_bot):
        """Test middleware registration."""
        _, dp, _ = obabot_telegram_bot
        
        class TestMiddleware:
            async def __call__(self, handler, event, data):
                return await handler(event, data)
        
        # Should be able to register middleware
        middleware = dp.middleware(TestMiddleware())
        assert middleware is not None

    def test_router_message_middleware(self, obabot_telegram_bot):
        """Test router.message.middleware() (aiogram-style)."""
        _, _, router = obabot_telegram_bot
        assert hasattr(router.message, 'middleware')
        class Mw:
            async def __call__(self, handler, event, data):
                return await handler(event, data)
        mw = router.message.middleware(Mw())
        assert mw is not None

    def test_router_callback_query_middleware(self, obabot_telegram_bot):
        """Test router.callback_query.middleware() (aiogram-style)."""
        _, _, router = obabot_telegram_bot
        assert hasattr(router.callback_query, 'middleware')
        class Mw:
            async def __call__(self, handler, event, data):
                return await handler(event, data)
        mw = router.callback_query.middleware(Mw())
        assert mw is not None


@pytest.mark.max
class TestDispatcherMethodsMax:
    """Mirror TestDispatcherMethods for Max-only bot."""

    def test_dispatcher_methods_exist(self, obabot_max_bot):
        _, dp, _ = obabot_max_bot

        assert hasattr(dp, "start_polling")
        assert hasattr(dp, "stop_polling")
        assert hasattr(dp, "include_router")
        assert hasattr(dp, "start")
        assert hasattr(dp, "run_polling")
        assert hasattr(dp, "middleware")
        assert hasattr(dp, "workflow_data")

    def test_workflow_data_property(self, obabot_max_bot):
        _, dp, _ = obabot_max_bot

        data = dp.workflow_data
        assert isinstance(data, dict)

        dp.workflow_data = {"test": "value"}
        assert dp.workflow_data.get("test") == "value"

    def test_fsm_storage_property(self, obabot_max_bot):
        _, dp, _ = obabot_max_bot

        assert hasattr(dp, "fsm_storage")

        from obabot.fsm import MemoryStorage

        storage = MemoryStorage()
        dp.fsm_storage = storage

        assert dp.fsm_storage is storage

    def test_middleware_registration(self, obabot_max_bot):
        _, dp, _ = obabot_max_bot

        class TestMiddleware:
            async def __call__(self, handler, event, data):
                return await handler(event, data)

        middleware = dp.middleware(TestMiddleware())
        assert middleware is not None

    def test_router_message_middleware(self, obabot_max_bot):
        _, _, router = obabot_max_bot
        assert hasattr(router.message, "middleware")

        class Mw:
            async def __call__(self, handler, event, data):
                return await handler(event, data)

        mw = router.message.middleware(Mw())
        assert mw is not None

    def test_router_callback_query_middleware(self, obabot_max_bot):
        _, _, router = obabot_max_bot
        assert hasattr(router.callback_query, "middleware")

        class Mw:
            async def __call__(self, handler, event, data):
                return await handler(event, data)

        mw = router.callback_query.middleware(Mw())
        assert mw is not None


class TestFeedUpdateMethods:
    """Test feed_update and feed_raw_update methods."""
    
    def test_feed_update_methods_exist(self, obabot_telegram_bot):
        """Test that feed_update methods exist on dispatcher."""
        _, dp, _ = obabot_telegram_bot
        
        assert hasattr(dp, 'feed_update')
        assert hasattr(dp, 'feed_raw_update')
        assert hasattr(dp, '_resolve_platform')
        assert hasattr(dp, '_get_platform')
        
        # Methods should be callable
        assert callable(dp.feed_update)
        assert callable(dp.feed_raw_update)
    
    def test_resolve_platform_telegram(self, obabot_telegram_bot):
        """Test platform resolution for Telegram updates."""
        _, dp, _ = obabot_telegram_bot
        
        # Telegram update format has "update_id"
        telegram_update = {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "chat": {"id": 123, "type": "private"},
                "text": "Hello"
            }
        }
        
        platform = dp._resolve_platform(telegram_update, None)
        assert platform is not None
        assert str(platform.platform) == "telegram"
    
    def test_resolve_platform_explicit(self, obabot_telegram_bot):
        """Test explicit platform specification."""
        _, dp, _ = obabot_telegram_bot
        
        # Even with no specific update format, explicit platform should work
        update = {"some": "data"}
        
        platform = dp._resolve_platform(update, "telegram")
        assert platform is not None
        assert str(platform.platform) == "telegram"
    
    def test_get_platform_by_name(self, obabot_telegram_bot):
        """Test _get_platform method."""
        _, dp, _ = obabot_telegram_bot
        
        platform = dp._get_platform("telegram")
        assert platform is not None
        assert str(platform.platform) == "telegram"
        
        # Non-existent platform should return None
        platform = dp._get_platform("nonexistent")
        assert platform is None
    
    def test_resolve_platform_fallback(self, obabot_telegram_bot):
        """Test platform resolution fallback to first platform."""
        _, dp, _ = obabot_telegram_bot
        
        # Update with no recognizable format
        unknown_update = {"unknown": "format"}
        
        # Should fall back to first platform
        platform = dp._resolve_platform(unknown_update, None)
        assert platform is not None


class TestFeedUpdateMaxFormat:
    """Test feed_update with Max update format."""
    
    def test_resolve_platform_max_format(self, obabot_telegram_bot):
        """Test that Max update format is recognized."""
        _, dp, _ = obabot_telegram_bot
        
        # Max update format has "update_type"
        max_update = {
            "update_type": "message_created",
            "message": {
                "id": "abc123",
                "body": {"text": "Hello"}
            }
        }
        
        # Since we only have Telegram platform, it should fall back
        # but the detection logic should still work
        platform = dp._resolve_platform(max_update, None)
        # Will return first platform (telegram) since max is not configured
        assert platform is not None


@pytest.mark.max
class TestFeedUpdateMaxFormatWithMaxBot:
    """Max update resolution when only Max platform is configured."""

    def test_resolve_platform_max_selects_max(self, obabot_max_bot):
        _, dp, _ = obabot_max_bot

        max_update = {
            "update_type": "message_created",
            "message": {
                "body": {"mid": "m1", "text": "Hello"},
                "sender": {"user_id": 1, "name": "U"},
                "recipient": {"chat_id": 1, "chat_type": "dialog"},
            },
        }

        platform = dp._resolve_platform(max_update, None)
        assert platform is not None
        assert str(platform.platform) == "max"

    def test_get_platform_max_by_name(self, obabot_max_bot):
        _, dp, _ = obabot_max_bot

        platform = dp._get_platform("max")
        assert platform is not None
        assert str(platform.platform) == "max"

        assert dp._get_platform("telegram") is None

    def test_resolve_platform_explicit_max(self, obabot_max_bot):
        _, dp, _ = obabot_max_bot

        platform = dp._resolve_platform({"some": "data"}, "max")
        assert platform is not None
        assert str(platform.platform) == "max"


class TestPlatformFeedUpdate:
    """Test platform-level feed_update methods."""
    
    def test_telegram_platform_has_feed_update(self, obabot_telegram_bot):
        """Test that TelegramPlatform has feed_update methods."""
        _, dp, _ = obabot_telegram_bot
        
        # Get the telegram platform
        platform = dp._get_platform("telegram")
        assert platform is not None
        
        assert hasattr(platform, 'feed_update')
        assert hasattr(platform, 'feed_raw_update')
        assert callable(platform.feed_update)
        assert callable(platform.feed_raw_update)


@pytest.mark.max
class TestPlatformFeedUpdateMax:
    """Mirror TestPlatformFeedUpdate for Max platform."""

    def test_max_platform_has_feed_update(self, obabot_max_bot):
        _, dp, _ = obabot_max_bot

        platform = dp._get_platform("max")
        assert platform is not None

        assert hasattr(platform, "feed_update")
        assert hasattr(platform, "feed_raw_update")
        assert callable(platform.feed_update)
        assert callable(platform.feed_raw_update)


class TestFeedUpdateMock:
    """Mock-based tests for feed_update that don't require real tokens."""
    
    def test_proxy_dispatcher_feed_update_signature(self):
        """Test ProxyDispatcher.feed_update method signature."""
        from obabot.proxy.dispatcher import ProxyDispatcher
        import inspect
        
        # Check method exists
        assert hasattr(ProxyDispatcher, 'feed_update')
        assert hasattr(ProxyDispatcher, 'feed_raw_update')
        
        # Check it's a coroutine function
        assert inspect.iscoroutinefunction(ProxyDispatcher.feed_update)
        assert inspect.iscoroutinefunction(ProxyDispatcher.feed_raw_update)
    
    def test_base_platform_has_abstract_methods(self):
        """Test BasePlatform has abstract feed_update methods."""
        from obabot.platforms.base import BasePlatform
        import inspect
        
        # Check abstract methods are defined
        assert hasattr(BasePlatform, 'feed_update')
        assert hasattr(BasePlatform, 'feed_raw_update')
        
        # Verify they are abstract
        assert getattr(BasePlatform.feed_update, '__isabstractmethod__', False)
        assert getattr(BasePlatform.feed_raw_update, '__isabstractmethod__', False)
    
    def test_telegram_platform_has_feed_update_methods(self):
        """Test TelegramPlatform implements feed_update methods."""
        from obabot.platforms.telegram import TelegramPlatform
        import inspect
        
        # Check methods exist
        assert hasattr(TelegramPlatform, 'feed_update')
        assert hasattr(TelegramPlatform, 'feed_raw_update')
        
        # Check they are coroutine functions
        assert inspect.iscoroutinefunction(TelegramPlatform.feed_update)
        assert inspect.iscoroutinefunction(TelegramPlatform.feed_raw_update)
    
    def test_max_platform_has_feed_update_methods(self):
        """Test MaxPlatform implements feed_update methods."""
        from obabot.platforms.max import MaxPlatform
        import inspect
        
        # Check methods exist
        assert hasattr(MaxPlatform, 'feed_update')
        assert hasattr(MaxPlatform, 'feed_raw_update')
        
        # Check they are coroutine functions
        assert inspect.iscoroutinefunction(MaxPlatform.feed_update)
        assert inspect.iscoroutinefunction(MaxPlatform.feed_raw_update)
    
    def test_proxy_dispatcher_resolve_platform_logic(self):
        """Test _resolve_platform logic with mocked platforms."""
        from obabot.proxy.dispatcher import ProxyDispatcher
        from obabot.types import BPlatform
        
        # Create mock platforms
        mock_tg_platform = Mock()
        mock_tg_platform.platform = BPlatform.telegram
        
        mock_max_platform = Mock()
        mock_max_platform.platform = BPlatform.max
        
        # Create dispatcher with mock platforms
        dp = ProxyDispatcher([mock_tg_platform, mock_max_platform])
        
        # Test Telegram update detection (has update_id)
        tg_update = {"update_id": 123, "message": {}}
        resolved = dp._resolve_platform(tg_update, None)
        assert resolved == mock_tg_platform
        
        # Test Max update detection (has update_type)
        max_update = {"update_type": "message_created", "message": {}}
        resolved = dp._resolve_platform(max_update, None)
        assert resolved == mock_max_platform
        
        # Test explicit platform selection
        resolved = dp._resolve_platform({}, "telegram")
        assert resolved == mock_tg_platform
        
        resolved = dp._resolve_platform({}, "max")
        assert resolved == mock_max_platform
    
    def test_proxy_dispatcher_get_platform(self):
        """Test _get_platform method."""
        from obabot.proxy.dispatcher import ProxyDispatcher
        from obabot.types import BPlatform
        
        # Create mock platforms
        mock_tg_platform = Mock()
        mock_tg_platform.platform = BPlatform.telegram
        
        dp = ProxyDispatcher([mock_tg_platform])
        
        # Test getting platform by name
        assert dp._get_platform("telegram") == mock_tg_platform
        assert dp._get_platform("nonexistent") is None
    
    @pytest.mark.asyncio
    async def test_proxy_dispatcher_feed_update_delegates(self):
        """Test that feed_update delegates to platform."""
        from obabot.proxy.dispatcher import ProxyDispatcher
        from obabot.types import BPlatform
        
        # Create mock platform with async feed_update
        mock_platform = Mock()
        mock_platform.platform = BPlatform.telegram
        mock_platform.feed_update = AsyncMock(return_value="result")
        
        dp = ProxyDispatcher([mock_platform])
        
        update = {"update_id": 123}
        result = await dp.feed_update(update=update)
        
        mock_platform.feed_update.assert_called_once_with(update)
        assert result == "result"
    
    @pytest.mark.asyncio
    async def test_proxy_dispatcher_feed_raw_update_delegates(self):
        """Test that feed_raw_update delegates to platform."""
        from obabot.proxy.dispatcher import ProxyDispatcher
        from obabot.types import BPlatform
        
        # Create mock platform with async feed_raw_update
        mock_platform = Mock()
        mock_platform.platform = BPlatform.telegram
        mock_platform.feed_raw_update = AsyncMock(return_value="result")
        
        dp = ProxyDispatcher([mock_platform])
        
        update = {"update_id": 456}
        result = await dp.feed_raw_update(update=update)
        
        mock_platform.feed_raw_update.assert_called_once_with(update)
        assert result == "result"
    
    @pytest.mark.asyncio
    async def test_proxy_dispatcher_feed_update_no_platforms(self):
        """Test feed_update with no platforms returns None."""
        from obabot.proxy.dispatcher import ProxyDispatcher
        
        dp = ProxyDispatcher([])
        
        result = await dp.feed_update(update={"update_id": 123})
        assert result is None


class TestLazyDispatcherState:
    """Regression tests: proxy dispatcher state access must not eagerly init lazy platforms."""

    def test_proxy_state_access_does_not_init_lazy_platform(self):
        from obabot.platforms.lazy import LazyPlatform
        from obabot.proxy.dispatcher import ProxyDispatcher

        lazy = LazyPlatform("max", "test_token")
        dp = ProxyDispatcher([lazy])

        class Mw:
            pass

        mw = Mw()

        with patch.object(lazy, "_ensure_inited", side_effect=AssertionError("lazy init not expected")) as ensure:
            assert dp.workflow_data == {}
            dp.workflow_data = {"x": 1}
            assert dp.workflow_data == {"x": 1}
            assert dp.fsm_storage is None
            assert dp.middleware(mw) is mw
            ensure.assert_not_called()

        assert lazy._real is None

    def test_runtime_state_applied_to_new_platform(self):
        from obabot.proxy.dispatcher import ProxyDispatcher

        class DummyObserver:
            def __init__(self):
                self.middlewares = []

            def middleware(self, middleware):
                self.middlewares.append(middleware)

        class DummyFSM:
            def __init__(self):
                self.storage = None

        class DummyDispatcher:
            def __init__(self):
                self.workflow_data = {}
                self.update = DummyObserver()
                self.fsm = DummyFSM()

        class DummyPlatform:
            def __init__(self):
                self.dispatcher = DummyDispatcher()

        dp = ProxyDispatcher([])
        storage = object()
        middleware = object()

        dp.workflow_data = {"answer": 42}
        dp.fsm_storage = storage
        dp.middleware(middleware)

        platform = DummyPlatform()
        dp._apply_runtime_state_to_platform(platform)

        assert platform.dispatcher.workflow_data == {"answer": 42}
        assert platform.dispatcher.fsm.storage is storage
        assert platform.dispatcher.update.middlewares == [middleware]


class TestMaxMiddlewareIntegration:
    """Test Max middleware integration."""
    
    def test_router_edited_message_has_middleware(self, obabot_telegram_bot):
        """Test router.edited_message.middleware() exists."""
        _, _, router = obabot_telegram_bot
        assert hasattr(router.edited_message, 'middleware')
    
    def test_router_outer_middleware(self, obabot_telegram_bot):
        """Test router.message.outer_middleware() exists."""
        _, _, router = obabot_telegram_bot
        assert hasattr(router.message, 'outer_middleware')


@pytest.mark.max
class TestMaxMiddlewareIntegrationRouterMax:
    """Mirror router middleware API checks on Max-only bot."""

    def test_router_edited_message_has_middleware(self, obabot_max_bot):
        _, _, router = obabot_max_bot
        assert hasattr(router.edited_message, "middleware")

    def test_router_outer_middleware(self, obabot_max_bot):
        _, _, router = obabot_max_bot
        assert hasattr(router.message, "outer_middleware")
    
    def test_max_platform_has_middleware_methods(self):
        """Test MaxPlatform has middleware storage and methods."""
        from obabot.platforms.max import MaxPlatform, MIDDLEWARE_OBSERVER_TYPES
        
        assert hasattr(MaxPlatform, 'add_middleware')
        assert hasattr(MaxPlatform, 'get_middlewares')
        assert 'message' in MIDDLEWARE_OBSERVER_TYPES
        assert 'callback_query' in MIDDLEWARE_OBSERVER_TYPES
        assert 'edited_message' in MIDDLEWARE_OBSERVER_TYPES
    
    @pytest.mark.asyncio
    async def test_max_middleware_chain_basic(self):
        """Test basic middleware chain execution."""
        from obabot.platforms.max import _call_with_middlewares
        
        call_order = []
        
        async def handler(event):
            call_order.append("handler")
            return "result"
        
        class TestMiddleware:
            async def __call__(self, inner_handler, event, data):
                call_order.append("mw_before")
                result = await inner_handler(event, data)
                call_order.append("mw_after")
                return result
        
        middlewares = [(TestMiddleware(), False)]
        result = await _call_with_middlewares(handler, "event", {}, middlewares)
        
        assert result == "result"
        assert call_order == ["mw_before", "handler", "mw_after"]
    
    @pytest.mark.asyncio
    async def test_max_middleware_chain_multiple(self):
        """Test multiple middlewares are called in correct order."""
        from obabot.platforms.max import _call_with_middlewares
        
        call_order = []
        
        async def handler(event):
            call_order.append("handler")
            return "result"
        
        class Middleware1:
            async def __call__(self, inner_handler, event, data):
                call_order.append("mw1_before")
                result = await inner_handler(event, data)
                call_order.append("mw1_after")
                return result
        
        class Middleware2:
            async def __call__(self, inner_handler, event, data):
                call_order.append("mw2_before")
                result = await inner_handler(event, data)
                call_order.append("mw2_after")
                return result
        
        middlewares = [(Middleware1(), False), (Middleware2(), False)]
        await _call_with_middlewares(handler, "event", {}, middlewares)
        
        # First middleware is outermost
        assert call_order == ["mw1_before", "mw2_before", "handler", "mw2_after", "mw1_after"]
    
    @pytest.mark.asyncio
    async def test_max_middleware_outer_vs_inner(self):
        """Test outer middlewares run before inner middlewares."""
        from obabot.platforms.max import _call_with_middlewares
        
        call_order = []
        
        async def handler(event):
            call_order.append("handler")
            return "result"
        
        class OuterMiddleware:
            async def __call__(self, inner_handler, event, data):
                call_order.append("outer_before")
                result = await inner_handler(event, data)
                call_order.append("outer_after")
                return result
        
        class InnerMiddleware:
            async def __call__(self, inner_handler, event, data):
                call_order.append("inner_before")
                result = await inner_handler(event, data)
                call_order.append("inner_after")
                return result
        
        middlewares = [
            (OuterMiddleware(), True),   # is_outer=True
            (InnerMiddleware(), False),  # is_outer=False
        ]
        await _call_with_middlewares(handler, "event", {}, middlewares)
        
        # Outer runs first (outermost), then inner, then handler
        assert call_order == ["outer_before", "inner_before", "handler", "inner_after", "outer_after"]
    
    @pytest.mark.asyncio
    async def test_max_middleware_no_middlewares(self):
        """Test handler called directly when no middlewares."""
        from obabot.platforms.max import _call_with_middlewares
        
        called = []
        
        async def handler(event):
            called.append(event)
            return "done"
        
        result = await _call_with_middlewares(handler, "test_event", {}, [])
        
        assert result == "done"
        assert called == ["test_event"]
    
    @pytest.mark.asyncio
    async def test_max_middleware_can_modify_event(self):
        """Test middleware can modify event before handler."""
        from obabot.platforms.max import _call_with_middlewares
        
        received = []
        
        async def handler(event):
            received.append(event)
            return "done"
        
        class ModifyMiddleware:
            async def __call__(self, inner_handler, event, data):
                modified_event = f"modified_{event}"
                return await inner_handler(modified_event, data)
        
        middlewares = [(ModifyMiddleware(), False)]
        await _call_with_middlewares(handler, "original", {}, middlewares)
        
        assert received == ["modified_original"]
    
    @pytest.mark.asyncio
    async def test_max_middleware_can_short_circuit(self):
        """Test middleware can short-circuit and not call handler."""
        from obabot.platforms.max import _call_with_middlewares
        
        handler_called = []
        
        async def handler(event):
            handler_called.append(True)
            return "from_handler"
        
        class BlockingMiddleware:
            async def __call__(self, inner_handler, event, data):
                return "blocked"
        
        middlewares = [(BlockingMiddleware(), False)]
        result = await _call_with_middlewares(handler, "event", {}, middlewares)
        
        assert result == "blocked"
        assert handler_called == []
    
    def test_proxy_router_stores_middlewares(self):
        """Test ProxyRouter stores middlewares by type."""
        from obabot.proxy.router import ProxyRouter, MIDDLEWARE_OBSERVER_TYPES
        
        router = ProxyRouter([])
        
        class TestMw:
            pass
        
        mw = TestMw()
        router.message.middleware(mw)
        
        middlewares = router.get_middlewares("message")
        assert len(middlewares) == 1
        assert middlewares[0][0] is mw
        assert middlewares[0][1] is False  # is_outer=False
    
    def test_proxy_router_stores_outer_middlewares(self):
        """Test ProxyRouter stores outer middlewares."""
        from obabot.proxy.router import ProxyRouter
        
        router = ProxyRouter([])
        
        class TestMw:
            pass
        
        mw = TestMw()
        router.message.outer_middleware(mw)
        
        middlewares = router.get_middlewares("message")
        assert len(middlewares) == 1
        assert middlewares[0][0] is mw
        assert middlewares[0][1] is True  # is_outer=True


class TestMiddlewareZeroAdaptation:
    """
    Test that middleware works identically in aiogram and obabot
    with zero adaptation required (except create_bot).
    
    The same middleware class and registration code works for:
    - Pure aiogram (Telegram only)
    - obabot Telegram platform
    - obabot Max platform
    """
    
    def test_same_middleware_class_works_everywhere(self):
        """
        Middleware class written for aiogram works in obabot without changes.
        
        This is the SAME class that would be used in pure aiogram:
        ```python
        from aiogram import Router
        router = Router()
        router.message.middleware(CountingMiddleware())
        ```
        
        And it works in obabot for both platforms:
        ```python
        from obabot import create_bot
        bot, dp, router = create_bot(telegram_token="...", max_token="...")
        router.message.middleware(CountingMiddleware())  # Works for both!
        ```
        """
        call_log = []
        
        class CountingMiddleware:
            async def __call__(self, handler, event, data):
                call_log.append("before")
                result = await handler(event, data)
                call_log.append("after")
                return result
        
        from obabot.proxy.router import ProxyRouter
        from obabot.platforms.max import _call_with_middlewares
        
        router = ProxyRouter([])
        mw = CountingMiddleware()
        router.message.middleware(mw)
        
        assert len(router.get_middlewares("message")) == 1
        assert router.get_middlewares("message")[0][0] is mw
    
    @pytest.mark.asyncio
    async def test_middleware_signature_compatible_with_aiogram(self):
        """
        obabot middleware uses the exact same signature as aiogram:
        async def __call__(self, handler, event, data)
        
        - handler: next handler in chain (callable)
        - event: Message/CallbackQuery object
        - data: dict with bot, state, etc.
        """
        from obabot.platforms.max import _call_with_middlewares
        
        received_args = {}
        
        class InspectorMiddleware:
            async def __call__(self, handler, event, data):
                received_args["handler"] = handler
                received_args["event"] = event
                received_args["data"] = data
                return await handler(event, data)
        
        async def my_handler(event):
            return f"handled: {event}"
        
        middlewares = [(InspectorMiddleware(), False)]
        result = await _call_with_middlewares(my_handler, "test_event", {"bot": "mock"}, middlewares)
        
        assert result == "handled: test_event"
        assert callable(received_args["handler"])
        assert received_args["event"] == "test_event"
        assert received_args["data"] == {"bot": "mock"}
    
    @pytest.mark.asyncio
    async def test_real_world_logging_middleware(self):
        """
        Real-world example: logging middleware that works in aiogram and obabot.
        
        This exact code works in both:
        
        # aiogram version:
        from aiogram import Router
        router = Router()
        router.message.middleware(LoggingMiddleware())
        
        # obabot version (same middleware class!):
        from obabot import create_bot
        bot, dp, router = create_bot(...)
        router.message.middleware(LoggingMiddleware())
        """
        from obabot.platforms.max import _call_with_middlewares
        
        logs = []
        
        class LoggingMiddleware:
            async def __call__(self, handler, event, data):
                user_id = getattr(event, "user_id", "unknown")
                logs.append(f"[IN] user={user_id}")
                try:
                    result = await handler(event, data)
                    logs.append(f"[OK] user={user_id}")
                    return result
                except Exception as e:
                    logs.append(f"[ERR] user={user_id}: {e}")
                    raise
        
        class MockMessage:
            user_id = 12345
        
        async def message_handler(event):
            return "response"
        
        middlewares = [(LoggingMiddleware(), False)]
        await _call_with_middlewares(message_handler, MockMessage(), {}, middlewares)
        
        assert logs == ["[IN] user=12345", "[OK] user=12345"]
    
    @pytest.mark.asyncio
    async def test_throttling_middleware_same_for_both_platforms(self):
        """
        Throttling middleware example - same code for aiogram and obabot.
        """
        from obabot.platforms.max import _call_with_middlewares
        import time
        
        class ThrottlingMiddleware:
            def __init__(self, rate_limit: float = 1.0):
                self.rate_limit = rate_limit
                self.last_call = {}
            
            async def __call__(self, handler, event, data):
                user_id = getattr(event, "user_id", 0)
                now = time.time()
                
                if user_id in self.last_call:
                    elapsed = now - self.last_call[user_id]
                    if elapsed < self.rate_limit:
                        return None
                
                self.last_call[user_id] = now
                return await handler(event, data)
        
        class MockEvent:
            user_id = 999
        
        call_count = [0]
        
        async def handler(event):
            call_count[0] += 1
            return "ok"
        
        throttle = ThrottlingMiddleware(rate_limit=0.1)
        middlewares = [(throttle, False)]
        
        await _call_with_middlewares(handler, MockEvent(), {}, middlewares)
        assert call_count[0] == 1
        
        await _call_with_middlewares(handler, MockEvent(), {}, middlewares)
        assert call_count[0] == 1
        
        import asyncio
        await asyncio.sleep(0.15)
        
        await _call_with_middlewares(handler, MockEvent(), {}, middlewares)
        assert call_count[0] == 2
    
    def test_router_middleware_api_matches_aiogram(self):
        """
        obabot router has the same middleware API as aiogram.Router.
        
        aiogram:
            router.message.middleware(mw)
            router.callback_query.middleware(mw)
            router.message.outer_middleware(mw)
        
        obabot (identical!):
            router.message.middleware(mw)
            router.callback_query.middleware(mw)
            router.message.outer_middleware(mw)
        """
        from obabot.proxy.router import ProxyRouter
        
        router = ProxyRouter([])
        
        assert hasattr(router, "message")
        assert hasattr(router, "callback_query")
        assert hasattr(router, "edited_message")
        
        assert hasattr(router.message, "middleware")
        assert hasattr(router.message, "outer_middleware")
        assert hasattr(router.callback_query, "middleware")
        assert hasattr(router.callback_query, "outer_middleware")
        assert hasattr(router.edited_message, "middleware")
        
        assert callable(router.message.middleware)
        assert callable(router.callback_query.middleware)
    
    @pytest.mark.asyncio
    async def test_database_session_middleware(self):
        """
        Common pattern: database session middleware.
        Same code works in aiogram and obabot.
        """
        from obabot.platforms.max import _call_with_middlewares
        
        session_log = []
        
        class DbSessionMiddleware:
            async def __call__(self, handler, event, data):
                session_log.append("session_open")
                data["db_session"] = "mock_session"
                try:
                    return await handler(event, data)
                finally:
                    session_log.append("session_close")
        
        received_session = [None]
        
        async def handler(event):
            return "done"
        
        middlewares = [(DbSessionMiddleware(), False)]
        data = {}
        await _call_with_middlewares(handler, "event", data, middlewares)
        
        assert session_log == ["session_open", "session_close"]
        assert data.get("db_session") == "mock_session"
    
    def test_middleware_registration_code_identical(self):
        """
        Demonstrate that middleware registration code is identical
        between aiogram and obabot.
        """
        
        aiogram_style_code = '''
# This code works in BOTH aiogram and obabot:

class MyMiddleware:
    async def __call__(self, handler, event, data):
        print("before")
        result = await handler(event, data)
        print("after")
        return result

# Registration (identical API):
router.message.middleware(MyMiddleware())
router.callback_query.middleware(MyMiddleware())
'''
        
        from obabot.proxy.router import ProxyRouter
        router = ProxyRouter([])
        
        class MyMiddleware:
            async def __call__(self, handler, event, data):
                return await handler(event, data)
        
        router.message.middleware(MyMiddleware())
        router.callback_query.middleware(MyMiddleware())
        
        assert len(router.get_middlewares("message")) == 1
        assert len(router.get_middlewares("callback_query")) == 1

