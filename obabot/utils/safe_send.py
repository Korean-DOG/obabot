"""Safe send utilities with timeout handling for Telegram API."""

import asyncio
import logging
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Telegram-specific exceptions that should be silently ignored
TELEGRAM_TIMEOUT_EXCEPTIONS = (
    "TelegramNetworkError",
    "TelegramRetryAfter",
    "TelegramServerError",
)


async def safe_telegram_call(
    coro: Any,
    timeout: float = 30.0,
    silent: bool = True,
    context: str = "telegram_call"
) -> Any:
    """
    Execute a Telegram API call with timeout handling.
    
    Catches common timeout and network errors that occur when
    Telegram API is slow or unresponsive.
    
    Args:
        coro: Coroutine to execute (e.g., message.answer(...))
        timeout: Timeout in seconds (default 30)
        silent: If True, don't raise exceptions, return None
        context: Context string for logging
        
    Returns:
        Result of the coroutine, or None if error occurred and silent=True
        
    Example:
        result = await safe_telegram_call(
            message.answer("Hello!"),
            context="answer_hello"
        )
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("[%s] Timeout after %.1fs", context, timeout)
        if not silent:
            raise
        return None
    except asyncio.CancelledError:
        logger.debug("[%s] Cancelled", context)
        if not silent:
            raise
        return None
    except Exception as e:
        exc_name = type(e).__name__
        
        # Check for known Telegram network/timeout exceptions
        if exc_name in TELEGRAM_TIMEOUT_EXCEPTIONS or "Timeout" in exc_name:
            logger.warning("[%s] %s: %s", context, exc_name, str(e)[:100])
            if not silent:
                raise
            return None
        
        # Check for aiohttp/httpx timeout errors
        if "timeout" in str(e).lower() or "timed out" in str(e).lower():
            logger.warning("[%s] Timeout error: %s", context, str(e)[:100])
            if not silent:
                raise
            return None
        
        # Unknown exception - log and re-raise if not silent
        logger.exception("[%s] Unexpected error: %s", context, exc_name)
        if not silent:
            raise
        return None


def with_timeout_handling(timeout: float = 30.0, silent: bool = True):
    """
    Decorator for async functions to add timeout handling.
    
    Args:
        timeout: Timeout in seconds
        silent: If True, return None on timeout instead of raising
        
    Example:
        @with_timeout_handling(timeout=10.0)
        async def send_notification(message, text):
            await message.answer(text)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            coro = func(*args, **kwargs)
            return await safe_telegram_call(
                coro,
                timeout=timeout,
                silent=silent,
                context=func.__name__
            )
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper
    return decorator
