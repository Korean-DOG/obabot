"""Configuration settings for obabot."""

import logging
import os
import sys

logger = logging.getLogger(__name__)


def setup_logging(
    level: int = logging.INFO,
    format_string: str = None,
    stream=None,
) -> None:
    """
    Configure logging for obabot and show logs in console.
    
    Call this at the start of your application to see obabot logs.
    
    Args:
        level: Logging level (default: logging.INFO)
        format_string: Custom format string (optional)
        stream: Output stream (default: sys.stderr)
        
    Example:
        from obabot import setup_logging
        setup_logging()  # Basic setup
        setup_logging(level=logging.DEBUG)  # More verbose
    """
    if format_string is None:
        format_string = "%(name)s %(levelname)s %(message)s"
    
    if stream is None:
        stream = sys.stderr
    
    # Configure root logger if not already configured
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter(format_string))
        root_logger.addHandler(handler)
    
    root_logger.setLevel(level)
    
    # Also configure obabot logger specifically
    obabot_logger = logging.getLogger("obabot")
    obabot_logger.setLevel(level)
    
    logger.info("obabot logging configured at level %s", logging.getLevelName(level))


class ObabotConfig:
    """Global configuration for obabot."""
    
    # Enable verbose logging with update IDs and platform info
    # Set to True during debugging, False in production
    VERBOSE_LOGGING: bool = True
    
    # Enable logging of outgoing messages to users
    # Set to True during debugging to see all bot responses
    LOG_OUTGOING_MESSAGES: bool = True
    
    # Show full IDs in logs instead of masked (**last6chars)
    # Set to True during debugging to see full chat_id, message_id, etc.
    LOG_FULL_IDS: bool = False  # Default False - show full only once at start
    
    # Track which chat_ids have been logged fully (for "log once" behavior)
    _logged_full_chat_ids: set = set()
    
    # Max API documentation URL for error messages
    MAX_API_DOCS_URL: str = "https://dev.max.ru/docs-api/methods/POST/messages"
    
    @classmethod
    def set_verbose_logging(cls, enabled: bool) -> None:
        """Enable or disable verbose logging."""
        cls.VERBOSE_LOGGING = enabled
    
    @classmethod
    def set_log_outgoing(cls, enabled: bool) -> None:
        """Enable or disable outgoing message logging."""
        cls.LOG_OUTGOING_MESSAGES = enabled
    
    @classmethod
    def set_log_full_ids(cls, enabled: bool) -> None:
        """Enable or disable full ID logging (vs masked)."""
        cls.LOG_FULL_IDS = enabled
    
    @classmethod
    def should_log_full_chat_id(cls, chat_id: any) -> bool:
        """Check if this chat_id should be logged fully (first time only)."""
        if cls.LOG_FULL_IDS:
            return True  # Always full if config says so
        
        chat_id_str = str(chat_id)
        if chat_id_str not in cls._logged_full_chat_ids:
            cls._logged_full_chat_ids.add(chat_id_str)
            return True  # First time - log full
        return False  # Already logged - mask it
    
    @classmethod
    def reset_logged_chat_ids(cls) -> None:
        """Reset the set of logged chat IDs (e.g., on new Lambda cold start)."""
        cls._logged_full_chat_ids.clear()


# Read from environment variables if set
_env_verbose = os.getenv("OBABOT_VERBOSE_LOGGING", "").lower()
if _env_verbose in ("false", "0", "no", "off"):
    ObabotConfig.VERBOSE_LOGGING = False
elif _env_verbose in ("true", "1", "yes", "on"):
    ObabotConfig.VERBOSE_LOGGING = True

_env_log_outgoing = os.getenv("OBABOT_LOG_OUTGOING", "").lower()
if _env_log_outgoing in ("false", "0", "no", "off"):
    ObabotConfig.LOG_OUTGOING_MESSAGES = False
elif _env_log_outgoing in ("true", "1", "yes", "on"):
    ObabotConfig.LOG_OUTGOING_MESSAGES = True

_env_log_full_ids = os.getenv("OBABOT_LOG_FULL_IDS", "").lower()
if _env_log_full_ids in ("false", "0", "no", "off"):
    ObabotConfig.LOG_FULL_IDS = False
elif _env_log_full_ids in ("true", "1", "yes", "on"):
    ObabotConfig.LOG_FULL_IDS = True


def format_update_id(update_id: any, force_full: bool = False) -> str:
    """
    Format update ID for logging.
    
    If LOG_FULL_IDS is True or force_full is True, returns full ID.
    Otherwise, if ID is longer than 8 characters, returns "**" + last 6 chars.
    
    Args:
        update_id: Update ID (int, str, or any)
        force_full: Force full ID output regardless of config
        
    Returns:
        Formatted ID string
    """
    if update_id is None:
        return "?"
    
    id_str = str(update_id)
    
    # Return full ID if configured or forced
    if ObabotConfig.LOG_FULL_IDS or force_full:
        return id_str
    
    # Otherwise mask long IDs
    if len(id_str) > 8:
        return f"**{id_str[-6:]}"
    return id_str


def get_update_context(update: dict, platform: str = None) -> str:
    """
    Extract update context (platform + ID) for logging.
    
    Args:
        update: Update dictionary
        platform: Platform name (optional, auto-detected if not provided)
        
    Returns:
        Formatted context string like "[tg:12345678]" or "[max:**abc123]"
    """
    if not ObabotConfig.VERBOSE_LOGGING:
        return ""
    
    if not isinstance(update, dict):
        return ""
    
    # Detect platform if not provided
    if not platform:
        if "update_id" in update:
            platform = "tg"
        elif "update_type" in update or (
            isinstance(update.get("message"), dict) and 
            isinstance(update["message"].get("body"), dict) and 
            "mid" in update["message"]["body"]
        ):
            platform = "max"
        else:
            platform = "?"
    
    # Shorten platform names for logs
    platform_short = {
        "telegram": "tg",
        "max": "max",
    }.get(str(platform).lower(), str(platform)[:3])
    
    # Extract update ID based on platform
    update_id = None
    
    if platform_short == "tg":
        update_id = update.get("update_id")
    elif platform_short == "max":
        # Try different Max ID fields
        update_id = update.get("timestamp")  # Max uses timestamp as unique ID
        if not update_id:
            message = update.get("message", {})
            if isinstance(message, dict):
                body = message.get("body", {})
                if isinstance(body, dict):
                    update_id = body.get("mid")  # Message ID
        if not update_id:
            callback = update.get("callback", {})
            if isinstance(callback, dict):
                update_id = callback.get("callback_id")
    
    formatted_id = format_update_id(update_id)
    return f"[{platform_short}:{formatted_id}]"


def format_chat_id(chat_id: any) -> str:
    """
    Format chat_id for logging - full on first occurrence, masked after.
    
    Args:
        chat_id: Chat ID
        
    Returns:
        Formatted chat_id string
    """
    if chat_id is None:
        return "?"
    
    chat_id_str = str(chat_id)
    
    # Check if we should log full (first time or config says always full)
    if ObabotConfig.should_log_full_chat_id(chat_id):
        # First time - log full with marker
        if len(chat_id_str) > 8:
            return f"{chat_id_str} (full)"
        return chat_id_str
    
    # Not first time - mask it
    if len(chat_id_str) > 8:
        return f"**{chat_id_str[-6:]}"
    return chat_id_str


def log_outgoing_message(
    platform: str = None,
    chat_id: any = None,
    text: str = "",
    method: str = "answer",
    has_keyboard: bool = False,
    parse_mode: str = None,
) -> None:
    """
    Log outgoing message to user if LOG_OUTGOING_MESSAGES is enabled.
    
    Args:
        platform: Platform name ("tg", "max", "telegram", etc.). 
                  If None, auto-detected from context.
        chat_id: Target chat ID
        text: Message text
        method: Method used ("answer", "reply", "send_message", etc.)
        has_keyboard: Whether message has keyboard attached
        parse_mode: Parse mode used
    """
    if not ObabotConfig.LOG_OUTGOING_MESSAGES:
        return
    
    # Auto-detect platform from context if not provided
    if platform is None:
        from obabot.context import get_current_platform
        ctx_platform = get_current_platform()
        platform = str(ctx_platform) if ctx_platform else "?"
    
    # Shorten platform name
    platform_short = {
        "telegram": "tg",
        "max": "max",
    }.get(str(platform).lower(), str(platform)[:3])
    
    # Format chat_id (full on first occurrence, masked after)
    chat_id_str = format_chat_id(chat_id)
    
    # Truncate long messages
    text_preview = text[:100] if text else ""
    if text and len(text) > 100:
        text_preview += "..."
    
    # Build log message
    extras = []
    if has_keyboard:
        extras.append("kbd")
    if parse_mode:
        extras.append(parse_mode)
    extras_str = f" [{','.join(extras)}]" if extras else ""
    
    logger.info(
        "[%s->%s] %s%s: %r",
        platform_short, chat_id_str, method, extras_str, text_preview
    )
