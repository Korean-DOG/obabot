"""Factory function for creating bots."""

import os
from typing import Any, Optional, Tuple, Union
import logging

from obabot.proxy.bot import ProxyBot
from obabot.proxy.dispatcher import ProxyDispatcher
from obabot.proxy.router import ProxyRouter
from obabot.platforms.base import BasePlatform
from obabot.platforms.lazy import LazyPlatform

logger = logging.getLogger(__name__)


def _is_test_mode(test_mode: Optional[bool]) -> bool:
    """True if test mode is enabled via argument or TESTING=1."""
    if test_mode is not None:
        return test_mode is True
    return os.environ.get("TESTING") == "1"


class _StubSession:
    """Minimal session stub: no network, close() is a no-op."""

    async def close(self) -> None:
        pass


class StubBot:
    """
    Stub bot for test mode: same interface as aiogram Bot for passing to
    set_notification_bot(bot) and feed_webhook(..., bot=bot), but no real
    connections or token validation.
    """

    def __init__(self, token: str = "test:noop") -> None:
        self._token = token
        self.id: Optional[int] = None  # no-op for compatibility

    @property
    def token(self) -> str:
        return self._token

    @property
    def session(self) -> _StubSession:
        return _StubSession()

    async def get_me(self) -> Any:
        return None

    async def close(self) -> None:
        pass


def create_bot(
    tg_token: Optional[str] = None,
    max_token: Optional[str] = None,
    yandex_token: Optional[str] = None,
    fsm_storage: Optional[Any] = None,
    test_mode: Optional[bool] = None,
) -> Tuple[Union[ProxyBot, StubBot], Union[ProxyDispatcher, Any], Union[ProxyRouter, Any]]:
    """
    Create a bot with the specified platform configuration.
    
    Uses lazy platform loading: aiogram/maxbot/yandex are imported only when the first
    event for that platform is processed (e.g. webhook). This reduces cold start time.
    
    Test mode (test_mode=True or TESTING=1): no real tokens or connections;
    returns (StubBot, aiogram Dispatcher, aiogram Router) so the app can register
    handlers on the same router and tests can include_router(router) in their
    dispatcher (e.g. aiogram-test-framework).
    
    Args:
        tg_token: Telegram bot token (optional; not required in test_mode)
        max_token: Max bot token (optional; not required in test_mode)
        yandex_token: Yandex Messenger bot token (optional; not required in test_mode)
        fsm_storage: FSM storage instance for state management (optional).
                     Will be shared across all platforms. Example:
                     MemoryStorage(), RedisStorage(redis=redis_client)
        test_mode: If True, enable test mode (no tokens/network). If None,
                   use os.environ.get("TESTING") == "1".
    
    Returns:
        Tuple of (bot, dispatcher, router). In normal mode: ProxyBot, ProxyDispatcher,
        ProxyRouter. In test mode: StubBot, aiogram Dispatcher, aiogram Router.
    """
    if _is_test_mode(test_mode):
        return _create_bot_test_mode(fsm_storage=fsm_storage)

    if not tg_token and not max_token and not yandex_token:
        raise ValueError(
            "At least one token must be provided. "
            "Use tg_token for Telegram, max_token for Max, yandex_token for Yandex Messenger, or any combination."
        )

    platforms: list[BasePlatform] = []

    if tg_token:
        platforms.append(LazyPlatform("telegram", tg_token))
        logger.info("Telegram platform (lazy) registered")
    if max_token:
        platforms.append(LazyPlatform("max", max_token))
        logger.info("Max platform (lazy) registered")
    if yandex_token:
        platforms.append(LazyPlatform("yandex", yandex_token))
        logger.info("Yandex Messenger platform (lazy) registered")

    platform_names = [str(p.platform) for p in platforms]
    if len(platforms) > 1:
        logger.info("Multi-platform mode (lazy): %s", ", ".join(platform_names))
    else:
        logger.info("Single-platform mode (lazy): %s", platform_names[0])

    proxy_bot = ProxyBot(platforms)
    proxy_router = ProxyRouter(platforms)
    proxy_dispatcher = ProxyDispatcher(platforms, router=proxy_router)

    for p in platforms:
        if hasattr(p, "set_router_ref"):
            p.set_router_ref(proxy_router)
        if hasattr(p, "set_dispatcher_ref"):
            p.set_dispatcher_ref(proxy_dispatcher)

    if fsm_storage is not None:
        proxy_dispatcher.fsm_storage = fsm_storage

    _register_coverage_middleware_if_enabled(proxy_router)

    return proxy_bot, proxy_dispatcher, proxy_router


def _register_coverage_middleware_if_enabled(router: Any) -> None:
    """
    Register FSMCoverageMiddleware if COVERAGE_LOG or COVERAGE_LOG_DIR is set.
    
    This enables automatic FSM transition logging for use with fsm-voyager.
    """
    from obabot.middleware.fsm_coverage import is_coverage_enabled, FSMCoverageMiddleware
    
    if not is_coverage_enabled():
        return
    
    middleware = FSMCoverageMiddleware()
    
    if hasattr(router, "message") and hasattr(router.message, "middleware"):
        router.message.middleware(middleware)
        logger.info("FSMCoverageMiddleware registered for message handlers")
    
    if hasattr(router, "callback_query") and hasattr(router.callback_query, "middleware"):
        router.callback_query.middleware(middleware)
        logger.info("FSMCoverageMiddleware registered for callback_query handlers")


def _create_bot_test_mode(fsm_storage: Optional[Any] = None) -> Tuple[StubBot, Any, Any]:
    """
    Create (stub_bot, aiogram Dispatcher, aiogram Router) for tests.
    No tokens required, no network. Router is an instance, already included
    in the returned dispatcher, so dp.include_router(router) in tests is not
    needed and does not fail. When feeding updates, pass MockBot (e.g. from
    aiogram-test-framework) so handlers do not hit Telegram (no TelegramUnauthorizedError).
    """
    from aiogram import Dispatcher, Router

    stub_bot = StubBot()
    router = Router()
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    if fsm_storage is not None:
        dispatcher.fsm_storage = fsm_storage
    
    _register_coverage_middleware_if_enabled_aiogram(router)
    
    logger.info("Test mode: returning StubBot, aiogram Dispatcher, aiogram Router (router included in dp)")
    return stub_bot, dispatcher, router


def _register_coverage_middleware_if_enabled_aiogram(router: Any) -> None:
    """
    Register FSMCoverageMiddleware on aiogram Router if coverage is enabled.
    
    Used for test mode where we have a native aiogram Router.
    """
    from obabot.middleware.fsm_coverage import is_coverage_enabled, FSMCoverageMiddleware
    
    if not is_coverage_enabled():
        return
    
    middleware = FSMCoverageMiddleware()
    
    router.message.middleware(middleware)
    router.callback_query.middleware(middleware)
    logger.info("FSMCoverageMiddleware registered for test mode router")


# ---------------------------------------------------------------------------
# Чеклист реализации тестового режима (поддержка тестирования)
# ---------------------------------------------------------------------------
# [x] Включение тестового режима: create_bot(..., test_mode=True) или TESTING=1
# [x] В test_mode не требуются валидные токены (можно вызывать без токенов)
# [x] В test_mode не открываются соединения к Telegram/Max
# [x] Возвращается кортеж (bot, dispatcher, router): bot — StubBot, dispatcher —
#     aiogram Dispatcher, router — экземпляр aiogram Router, уже включён в dp
# [x] Контракт: bot, dp, router = create_bot(...), хендлеры вешаются на router
# [x] dp.include_router(router) в тестах не нужен и не падает; при прогоне апдейтов
#     передавать MockBot, чтобы не было TelegramUnauthorizedError
#
# Примечание: если в obabot появится другой способ тестового режима (например,
# отдельная функция create_bot_for_tests()), тесты можно подстроить под него:
# достаточно получать оттуда (bot, dispatcher, router) тем же способом.
