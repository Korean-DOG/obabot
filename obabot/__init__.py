"""
obabot - Universal async bot library for Telegram and Max

Usage:
    from obabot import create_bot
    
    # Telegram only
    bot, dp, router = create_bot(tg_token="YOUR_TOKEN")
    
    # Max only
    bot, dp, router = create_bot(max_token="YOUR_TOKEN")
    
    # Both platforms
    bot, dp, router = create_bot(tg_token="TG_TOKEN", max_token="MAX_TOKEN")
"""

from obabot.factory import create_bot, StubBot
from obabot.types import BPlatform
from obabot.context import get_user_id
from obabot.detection import detect_platform, extract_source_ip
from obabot.config import ObabotConfig, setup_logging
from obabot.utils.safe_send import safe_telegram_call, with_timeout_handling
from obabot.mixins import PlatformAwareMixin

__version__ = "0.2.2"
__all__ = [
    "create_bot",
    "StubBot",
    "BPlatform",
    "get_user_id",
    "detect_platform",
    "extract_source_ip",
    "ObabotConfig",
    "setup_logging",
    "safe_telegram_call",
    "with_timeout_handling",
    "PlatformAwareMixin",
]

