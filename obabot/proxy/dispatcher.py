"""Proxy dispatcher that manages polling across multiple platforms."""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from obabot.config import get_update_context
from obabot.detection import detect_platform
from obabot.platforms.lazy import LazyPlatform

if TYPE_CHECKING:
    from obabot.platforms.base import BasePlatform
    from obabot.proxy.bot import ProxyBot
    from obabot.proxy.router import ProxyRouter

logger = logging.getLogger(__name__)


class ProxyDispatcher:
    """
    Dispatcher proxy that manages polling for all platforms.
    
    Provides the same API as aiogram.Dispatcher:
    - start_polling(bot)
    - stop_polling()
    
    When multiple platforms are configured, starts polling
    for all of them in parallel using asyncio.gather().
    
    Usage:
        await dp.start_polling(bot)  # Starts all platforms
    """
    
    def __init__(self, platforms: List["BasePlatform"], router: Optional["ProxyRouter"] = None):
        """
        Initialize proxy dispatcher.
        
        Args:
            platforms: List of platform instances to manage
            router: ProxyRouter instance (for dp.message() compatibility)
        """
        self._platforms = platforms
        self._router = router
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._fsm_storage: Any = None
        # umaxbot Dispatcher has no workflow_data; keep aiogram-compatible dict on the proxy
        self._proxy_workflow_data: Dict[str, Any] = {}
        # Defer dispatcher-level middlewares until lazy platforms are initialized.
        self._deferred_dispatcher_middlewares: List[Any] = []
    
    async def start_polling(
        self,
        bot: Optional["ProxyBot"] = None,
        **kwargs: Any
    ) -> None:
        """
        Start polling for all platforms.
        
        Runs all platform polling loops in parallel.
        
        Args:
            bot: ProxyBot instance (optional, for aiogram compatibility)
            **kwargs: Additional arguments passed to platform polling
        """
        if self._running:
            logger.warning("Polling is already running")
            return
        
        self._running = True
        logger.info(f"Starting polling for {len(self._platforms)} platform(s)")
        
        # Create polling tasks for each platform
        self._tasks = [
            asyncio.create_task(
                self._run_platform_polling(platform),
                name=f"polling_{platform.platform}"
            )
            for platform in self._platforms
        ]
        
        try:
            results = await asyncio.gather(*self._tasks, return_exceptions=True)
            for task, result in zip(self._tasks, results):
                if isinstance(result, asyncio.CancelledError):
                    logger.info("Polling task %r cancelled", task.get_name())
                elif isinstance(result, Exception):
                    logger.error(
                        "Polling task %r failed",
                        task.get_name(),
                        exc_info=result,
                    )
                elif isinstance(result, BaseException):
                    logger.error(
                        "Polling task %r ended with %s",
                        task.get_name(),
                        type(result).__name__,
                    )
        except asyncio.CancelledError:
            logger.info("Polling cancelled")
        finally:
            self._running = False
    
    async def _run_platform_polling(self, platform: "BasePlatform") -> None:
        """Run polling for a single platform with error handling."""
        platform_name = str(platform.platform)
        logger.info(f"Starting polling for {platform_name}")
        
        try:
            await platform.start_polling()
        except asyncio.CancelledError:
            logger.info(f"Polling cancelled for {platform_name}")
            raise
        except Exception as e:
            logger.error(f"Polling error for {platform_name}: {e}")
            raise
        finally:
            logger.info(f"Polling stopped for {platform_name}")
    
    async def stop_polling(self) -> None:
        """Stop polling for all platforms."""
        if not self._running:
            return
        
        logger.info("Stopping polling for all platforms")
        self._running = False
        
        # Cancel all polling tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        # Stop each platform
        for platform in self._platforms:
            try:
                await platform.stop_polling()
            except Exception as e:
                logger.error(f"Error stopping {platform.platform}: {e}")
        
        self._tasks = []
    
    def include_router(self, router: Any) -> None:
        """
        Include a router (for aiogram compatibility).
        
        In obabot, routers are automatically included during create_bot(),
        but this method is provided for compatibility with aiogram code.
        """
        # For proxy dispatcher, routers are already included in platforms
        # This is a no-op for compatibility
        pass
    
    async def start(self) -> None:
        """
        Start the dispatcher (alternative to start_polling).
        
        This is an alias for start_polling() for aiogram compatibility.
        """
        await self.start_polling()
    
    async def run_polling(
        self,
        bot: Optional["ProxyBot"] = None,
        **kwargs: Any
    ) -> None:
        """
        Run polling (alternative method name).
        
        This is an alias for start_polling() for aiogram compatibility.
        """
        await self.start_polling(bot, **kwargs)
    
    def middleware(self, middleware: Any) -> Any:
        """
        Register middleware (for aiogram compatibility).
        
        Registers middleware for all platforms.
        
        Usage:
            @dp.middleware()
            class MyMiddleware:
                async def __call__(self, handler, event, data):
                    # middleware logic
                    return await handler(event, data)
        """
        self._deferred_dispatcher_middlewares.append(middleware)
        for _, dp in self._iter_initialized_platform_dispatchers():
            self._apply_dispatcher_middleware(dp, middleware)
        
        return middleware
    
    @property
    def workflow_data(self) -> dict:
        """
        Get workflow data (for FSM compatibility).
        
        Returns merged workflow data from all platforms' dispatchers.
        If multiple platforms have workflow_data, they are merged.
        """
        if not self._platforms:
            return dict(self._proxy_workflow_data)
        
        # Merge workflow_data from all platforms
        merged: Dict[str, Any] = {}
        for _, dp in self._iter_initialized_platform_dispatchers():
            platform_data = getattr(dp, 'workflow_data', {})
            if isinstance(platform_data, dict):
                merged.update(platform_data)
        merged.update(self._proxy_workflow_data)
        return merged
    
    @workflow_data.setter
    def workflow_data(self, value: dict) -> None:
        """Set workflow data for all platforms."""
        self._proxy_workflow_data = dict(value)
        for _, dp in self._iter_initialized_platform_dispatchers():
            if hasattr(dp, 'workflow_data'):
                dp.workflow_data = value
    
    @property
    def fsm_storage(self) -> Any:
        """
        Get FSM storage.
        
        Returns the shared FSM storage, or storage from the first platform
        if no shared storage was set.
        """
        if self._fsm_storage is not None:
            return self._fsm_storage

        from obabot.platforms.max import MaxPlatform

        for platform in self._platforms:
            if isinstance(platform, LazyPlatform):
                real = platform._real
                if real is not None and isinstance(real, MaxPlatform):
                    stor = real._obabot_fsm_storage
                    if stor is not None:
                        return stor
            elif isinstance(platform, MaxPlatform):
                if platform._obabot_fsm_storage is not None:
                    return platform._obabot_fsm_storage

        for _, dp in self._iter_initialized_platform_dispatchers():
            if hasattr(dp, "fsm") and hasattr(dp.fsm, "storage"):
                return dp.fsm.storage

        return None
    
    @fsm_storage.setter
    def fsm_storage(self, storage: Any) -> None:
        """
        Set FSM storage for all platforms.
        
        This storage will be applied to:
        - All already-initialized platforms immediately
        - Lazy platforms when they are first initialized
        
        Usage:
            from obabot.fsm import MemoryStorage, RedisStorage
            
            dp.fsm_storage = MemoryStorage()
            # or
            dp.fsm_storage = RedisStorage(redis=redis_client)
        """
        self._fsm_storage = storage
        
        # Apply to already-initialized platforms
        for platform in self._platforms:
            self._apply_fsm_storage_to_platform(platform)
    
    def _apply_fsm_storage_to_platform(self, platform: "BasePlatform") -> None:
        """Apply FSM storage to a single platform if initialized."""
        if self._fsm_storage is None:
            return
        
        from obabot.platforms.max import MaxPlatform

        # For lazy platforms, check if already initialized
        if isinstance(platform, LazyPlatform):
            if platform._real is not None:
                if isinstance(platform._real, MaxPlatform):
                    platform._real.set_obabot_fsm_storage(self._fsm_storage)
                real_dp = platform._real.dispatcher
                if hasattr(real_dp, 'fsm') and hasattr(real_dp.fsm, 'storage'):
                    real_dp.fsm.storage = self._fsm_storage
        else:
            if isinstance(platform, MaxPlatform):
                platform.set_obabot_fsm_storage(self._fsm_storage)
            dp = platform.dispatcher
            if hasattr(dp, 'fsm') and hasattr(dp.fsm, 'storage'):
                dp.fsm.storage = self._fsm_storage

    def _iter_initialized_platform_dispatchers(self) -> List[tuple["BasePlatform", Any]]:
        """Return (platform, dispatcher) only for already initialized platforms."""
        initialized: List[tuple["BasePlatform", Any]] = []
        for platform in self._platforms:
            real_platform: Optional["BasePlatform"] = None
            if isinstance(platform, LazyPlatform):
                real_platform = platform._real
            else:
                real_platform = platform

            if real_platform is None:
                continue

            initialized.append((real_platform, real_platform.dispatcher))
        return initialized

    def _apply_dispatcher_middleware(self, dp: Any, middleware: Any) -> None:
        """Apply dispatcher-level middleware to an already initialized dispatcher."""
        if hasattr(dp, 'middleware'):
            dp.middleware(middleware)
        elif hasattr(dp, 'update') and hasattr(dp.update, 'middleware'):
            dp.update.middleware(middleware)

    def _apply_runtime_state_to_platform(self, platform: "BasePlatform") -> None:
        """Apply deferred proxy state to a newly initialized real platform."""
        dp = platform.dispatcher

        if self._proxy_workflow_data and hasattr(dp, 'workflow_data'):
            dp.workflow_data = dict(self._proxy_workflow_data)

        for middleware in self._deferred_dispatcher_middlewares:
            self._apply_dispatcher_middleware(dp, middleware)

        self._apply_fsm_storage_to_platform(platform)
    
    # Delegate all handler decorators to router for aiogram compatibility
    # This allows using dp.message() instead of router.message()
    
    def message(self, *filters: Any, **kwargs: Any) -> Callable:
        """
        Register a message handler (delegates to router).
        
        This allows using dp.message() decorator like in aiogram:
        
            @dp.message(Command("start"))
            async def start(message):
                await message.answer("Hello!")
        """
        if self._router:
            return self._router.message(*filters, **kwargs)
        raise RuntimeError("Router not initialized. Use router.message() instead.")
    
    def callback_query(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register a callback query handler (delegates to router)."""
        if self._router:
            return self._router.callback_query(*filters, **kwargs)
        raise RuntimeError("Router not initialized. Use router.callback_query() instead.")
    
    def edited_message(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register edited message handler (delegates to router)."""
        if self._router:
            return self._router.edited_message(*filters, **kwargs)
        raise RuntimeError("Router not initialized. Use router.edited_message() instead.")
    
    def channel_post(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register channel post handler (delegates to router)."""
        if self._router:
            return self._router.channel_post(*filters, **kwargs)
        raise RuntimeError("Router not initialized. Use router.channel_post() instead.")
    
    def inline_query(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register inline query handler (delegates to router)."""
        if self._router:
            return self._router.inline_query(*filters, **kwargs)
        raise RuntimeError("Router not initialized. Use router.inline_query() instead.")
    
    def chosen_inline_result(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register chosen inline result handler (delegates to router)."""
        if self._router:
            return self._router.chosen_inline_result(*filters, **kwargs)
        raise RuntimeError("Router not initialized. Use router.chosen_inline_result() instead.")
    
    def shipping_query(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register shipping query handler (delegates to router)."""
        if self._router:
            return self._router.shipping_query(*filters, **kwargs)
        raise RuntimeError("Router not initialized. Use router.shipping_query() instead.")
    
    def pre_checkout_query(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register pre-checkout query handler (delegates to router)."""
        if self._router:
            return self._router.pre_checkout_query(*filters, **kwargs)
        raise RuntimeError("Router not initialized. Use router.pre_checkout_query() instead.")
    
    def my_chat_member(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register my_chat_member handler (delegates to router)."""
        if self._router:
            return self._router.my_chat_member(*filters, **kwargs)
        raise RuntimeError("Router not initialized. Use router.my_chat_member() instead.")
    
    def chat_member(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register chat_member handler (delegates to router)."""
        if self._router:
            return self._router.chat_member(*filters, **kwargs)
        raise RuntimeError("Router not initialized. Use router.chat_member() instead.")
    
    def error(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register error handler (delegates to router)."""
        if self._router:
            return self._router.error(*filters, **kwargs)
        raise RuntimeError("Router not initialized. Use router.error() instead.")
    
    def poll(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register poll handler (delegates to router)."""
        if self._router:
            return self._router.poll(*filters, **kwargs)
        raise RuntimeError("Router not initialized. Use router.poll() instead.")
    
    def poll_answer(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register poll answer handler (delegates to router)."""
        if self._router:
            return self._router.poll_answer(*filters, **kwargs)
        raise RuntimeError("Router not initialized. Use router.poll_answer() instead.")
    
    def chat_join_request(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register chat join request handler (delegates to router)."""
        if self._router:
            return self._router.chat_join_request(*filters, **kwargs)
        raise RuntimeError("Router not initialized. Use router.chat_join_request() instead.")
    
    def edited_channel_post(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register edited channel post handler (delegates to router)."""
        if self._router:
            return self._router.edited_channel_post(*filters, **kwargs)
        raise RuntimeError("Router not initialized. Use router.edited_channel_post() instead.")
    
    async def feed_update(
        self,
        bot: Optional["ProxyBot"] = None,
        update: Any = None,
        *,
        platform: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """
        Process a single update (aiogram-compatible).
        
        This method allows manual processing of updates, typically used
        in webhook scenarios where updates are received via HTTP.
        
        Args:
            bot: ProxyBot instance (for aiogram compatibility, optional)
            update: Update object to process
            platform: Platform identifier ("telegram" or "max"). If not provided,
                     the platform is auto-detected from the update structure.
            **kwargs: Additional arguments passed to the platform's feed_update
            
        Returns:
            Result from the platform's update processing (can be used as webhook response)
            
        Example:
            # Telegram webhook
            @app.post("/webhook/telegram")
            async def telegram_webhook(request):
                update = await request.json()
                result = await dp.feed_update(update=update, platform="telegram")
                return result
                
            # Auto-detect platform
            result = await dp.feed_update(update=update_dict)
        """
        target_platform = self._resolve_platform(update, platform)
        if target_platform:
            return await target_platform.feed_update(update, **kwargs)
        
        logger.warning("No platform found to handle update")
        return None
    
    async def feed_raw_update(
        self,
        bot: Optional["ProxyBot"] = None,
        update: Optional[dict] = None,
        *,
        platform: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """
        Process a raw update dict (aiogram-compatible).
        
        Similar to feed_update but explicitly expects a dictionary.
        
        Args:
            bot: ProxyBot instance (for aiogram compatibility, optional)
            update: Raw update dictionary
            platform: Platform identifier ("telegram" or "max"). If not provided,
                     the platform is auto-detected from the update structure.
            **kwargs: Additional arguments passed to the platform's feed_raw_update
            
        Returns:
            Result from the platform's update processing
        """
        ctx = get_update_context(update or {}, platform)
        logger.info("%s feed_raw_update: platform=%s", ctx, platform)
        target_platform = self._resolve_platform(update, platform)
        logger.info(
            "%s feed_raw_update: resolved platform=%s",
            ctx, target_platform.__class__.__name__ if target_platform else None,
        )

        if not target_platform:
            logger.warning("%s feed_raw_update: No platform found to handle raw update", ctx)
            return None

        # Ensure lazy platforms are initialized before first update so that
        # real dispatchers/routers already have all pending handlers applied.
        real_platform = target_platform
        if isinstance(target_platform, LazyPlatform):
            real_platform = target_platform._ensure_inited()
            logger.info(
                "%s feed_raw_update: lazy platform %s -> real %s",
                ctx, type(target_platform).__name__, type(real_platform).__name__,
            )
            # Safety net: re-apply pending handlers if router supports it
            if self._router and hasattr(self._router, "apply_pending_handlers"):
                self._router.apply_pending_handlers(real_platform)  # type: ignore[arg-type]

        logger.info("%s feed_raw_update: calling %s.feed_raw_update()", ctx, type(real_platform).__name__)
        return await real_platform.feed_raw_update(update or {}, **kwargs)
    
    async def feed_webhook(
        self,
        body: dict,
        event: Optional[dict] = None,
        bot: Optional["ProxyBot"] = None,
        **kwargs: Any
    ) -> Any:
        """
        Auto-detect platform and route webhook to appropriate handler.
        
        This is the main entry point for webhook handlers. It automatically
        detects the platform (Telegram or Max) based on:
        1. Source IP address (from event headers/requestContext)
        2. Payload structure (fallback)
        
        Args:
            body: Parsed webhook body (JSON payload)
            event: Optional AWS Lambda event dict or similar containing
                   request metadata (headers, requestContext, etc.)
            bot: ProxyBot instance (optional, for compatibility)
            **kwargs: Additional arguments passed to platform handlers
            
        Returns:
            Result from the platform's update processing
            
        Raises:
            ValueError: If platform cannot be determined
            
        Example:
            # AWS Lambda handler
            async def handler(event, context):
                body = json.loads(event["body"])
                result = await dp.feed_webhook(body, event)
                return {"statusCode": 200, "body": "ok"}
        """
        # Unwrap nested body (e.g. Yandex Cloud / some gateways send payload inside body["body"])
        if isinstance(body, dict) and "body" in body and len(body) == 1 and isinstance(body.get("body"), dict):
            body = body["body"]
        elif isinstance(body, dict) and "body" in body and isinstance(body.get("body"), dict):
            body = body["body"]
        
        platform = detect_platform(body, event)
        ctx = get_update_context(body, platform)
        body_keys = list(body.keys()) if isinstance(body, dict) else "not a dict"
        logger.info("%s feed_webhook: keys=%s detected=%s", ctx, body_keys, platform)
        
        if platform == "telegram":
            logger.info("%s feed_webhook: routing to Telegram", ctx)
            return await self.feed_raw_update(bot, body, platform="telegram", **kwargs)
        
        elif platform == "max":
            logger.info("%s feed_webhook: routing to Max", ctx)
            return await self.feed_raw_update(bot, body, platform="max", **kwargs)
        
        else:
            logger.error("%s feed_webhook: unknown platform", ctx)
            raise ValueError(
                f"Unknown platform, cannot route webhook. "
                f"Body keys: {list(body.keys()) if isinstance(body, dict) else 'not a dict'}"
            )
    
    def _resolve_platform(
        self, 
        update: Any, 
        platform: Optional[str]
    ) -> Optional["BasePlatform"]:
        """
        Determine which platform should handle the update.
        
        Args:
            update: Update object or dict
            platform: Explicit platform identifier (optional)
            
        Returns:
            Platform instance or None if no platform matches
        """
        logger.debug("[Dispatcher] _resolve_platform: platform=%s, available=%s", platform, [str(p.platform) for p in self._platforms])
        
        resolved = None
        
        # If platform is explicitly specified, use it
        if platform:
            resolved = self._get_platform(platform)
            logger.debug("[Dispatcher] _resolve_platform: by name %s -> %s", platform, resolved)
            if resolved:
                return resolved
        
        # Auto-detect by update structure
        if isinstance(update, dict):
            # Telegram updates have "update_id" field
            if "update_id" in update:
                resolved = self._get_platform("telegram")
                logger.debug("[Dispatcher] _resolve_platform: detected Telegram by update_id")
            # Max updates detection:
            # 1. Primary: "mid" in message.body (unique to Max)
            # 2. Secondary: "update_type" field
            else:
                message = update.get("message", {})
                if isinstance(message, dict):
                    msg_body = message.get("body", {})
                    if isinstance(msg_body, dict) and "mid" in msg_body:
                        resolved = self._get_platform("max")
                        logger.debug("[Dispatcher] _resolve_platform: detected Max by mid")
                
                if not resolved and "update_type" in update:
                    resolved = self._get_platform("max")
                    logger.debug("[Dispatcher] _resolve_platform: detected Max by update_type")
        
        # Check if update object has platform-specific attributes
        if not resolved:
            if hasattr(update, 'update_id'):
                resolved = self._get_platform("telegram")
            elif hasattr(update, 'update_type'):
                resolved = self._get_platform("max")
        
        # If detected platform exists, return it
        if resolved:
            return resolved
        
        # Fallback: use first available platform
        if self._platforms:
            logger.debug("[Dispatcher] _resolve_platform: fallback to first platform %s", self._platforms[0].platform)
            return self._platforms[0]
        
        logger.debug("[Dispatcher] _resolve_platform: no platform found")
        return None
    
    def _get_platform(self, platform_name: str) -> Optional["BasePlatform"]:
        """
        Get platform by name.
        
        Args:
            platform_name: Platform identifier ("telegram" or "max")
            
        Returns:
            Platform instance or None if not found
        """
        logger.debug("[Dispatcher] _get_platform: looking for %s", platform_name)
        for p in self._platforms:
            # Check both string representation and enum value
            if str(p.platform) == platform_name or getattr(p.platform, 'value', None) == platform_name:
                logger.debug("[Dispatcher] _get_platform: found %s", platform_name)
                return p
        
        logger.warning("[Dispatcher] _get_platform: platform %s not found", platform_name)
        return None

