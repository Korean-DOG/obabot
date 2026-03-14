"""Context management for platform detection and event helpers."""

import contextvars
from typing import Any, Optional

from obabot.types import BPlatform

# Context variable for current platform
_current_platform: contextvars.ContextVar[Optional[BPlatform]] = contextvars.ContextVar(
    'current_platform', default=None
)


def get_current_platform() -> Optional[BPlatform]:
    """Get the current platform from context.
    
    Returns:
        Current platform if set, None otherwise.
    """
    return _current_platform.get()


def set_current_platform(platform: Optional[BPlatform]) -> contextvars.Token:
    """Set the current platform in context.
    
    Args:
        platform: Platform to set
        
    Returns:
        Token for resetting the context
    """
    return _current_platform.set(platform)


def reset_current_platform(token: contextvars.Token) -> None:
    """Reset platform context to previous value.
    
    Args:
        token: Token from set_current_platform
    """
    _current_platform.reset(token)


def get_user_id(event: Any) -> Optional[int]:
    """Get user id from message or callback (aiogram-style, no getattr in your code).
    
    Works with Message, CallbackQuery, and any object that has from_user.id.
    
    Usage:
        user_id = get_user_id(message)   # or callback
        if user_id:
            ...
    """
    fu = getattr(event, "from_user", None)
    if fu is None:
        return None
    uid = getattr(fu, "id", None)
    if uid is not None:
        return int(uid)
    u = getattr(fu, "user_id", None)
    return int(u) if u is not None else None
