"""Lazy platform wrapper: real platform (and its lib) is created only on first use by event source."""

import asyncio
import logging
from typing import Any, Callable, List, Optional, TYPE_CHECKING

from obabot.platforms.base import BasePlatform, HandlerType
from obabot.types import BPlatform

if TYPE_CHECKING:
    from obabot.proxy.router import ProxyRouter

logger = logging.getLogger(__name__)


class LazyPlatform(BasePlatform):
    """
    Wrapper that defers loading the real platform (and aiogram/maxbot) until first use.
    Used for webhook: only the platform that handles the event is loaded.
    """

    def __init__(self, platform_type: str, token: str):
        if platform_type not in ("telegram", "max"):
            raise ValueError(f"platform_type must be 'telegram' or 'max', got {platform_type!r}")
        self._platform_type = platform_type
        self._token = token
        self._real: Optional[BasePlatform] = None
        self._router_ref: Optional["ProxyRouter"] = None
        self._dispatcher_ref: Optional[Any] = None

    def set_router_ref(self, router: "ProxyRouter") -> None:
        """Set router so we can apply pending handlers when real platform is first created."""
        self._router_ref = router
    
    def set_dispatcher_ref(self, dispatcher: Any) -> None:
        """Set dispatcher so we can apply FSM storage when real platform is first created."""
        self._dispatcher_ref = dispatcher

    def _ensure_inited(self) -> BasePlatform:
        if self._real is not None:
            return self._real
        if self._platform_type == "telegram":
            from obabot.platforms.telegram import TelegramPlatform
            self._real = TelegramPlatform(self._token)
            logger.info("[Lazy] Telegram platform loaded (first use)")
        elif self._platform_type == "max":
            from obabot.platforms.max import MaxPlatform
            self._real = MaxPlatform(self._token)
            logger.info("[Lazy] Max platform loaded (first use)")
        else:
            raise RuntimeError(f"Unknown platform_type: {self._platform_type}")
        if self._router_ref:
            self._router_ref.apply_pending_handlers(self._real)
        if self._dispatcher_ref:
            self._dispatcher_ref._apply_runtime_state_to_platform(self._real)
        return self._real

    @property
    def platform(self) -> BPlatform:
        return BPlatform.telegram if self._platform_type == "telegram" else BPlatform.max

    @property
    def bot(self) -> Any:
        return self._ensure_inited().bot

    @property
    def dispatcher(self) -> Any:
        return self._ensure_inited().dispatcher

    @property
    def router(self) -> Any:
        return self._ensure_inited().router

    def wrap_handler(self, handler: HandlerType) -> HandlerType:
        return self._ensure_inited().wrap_handler(handler)

    def convert_filters_for_platform(self, filters: tuple, handler_type: str = "message") -> tuple:
        real = self._ensure_inited()
        if hasattr(real, "convert_filters_for_platform"):
            return real.convert_filters_for_platform(filters, handler_type)
        return filters

    async def start_polling(self) -> None:
        await self._ensure_inited().start_polling()

    async def stop_polling(self) -> None:
        if self._real is not None:
            await self._real.stop_polling()

    async def feed_update(self, update: Any, **kwargs: Any) -> Any:
        return await self._ensure_inited().feed_update(update, **kwargs)

    async def feed_raw_update(self, update: dict, **kwargs: Any) -> Any:
        return await self._ensure_inited().feed_raw_update(update, **kwargs)
