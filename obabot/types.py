"""Core types and enums for obabot."""

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from obabot.platforms.base import BasePlatform


class BPlatform(str, Enum):
    """Bot platform enumeration."""
    
    telegram = "telegram"
    tg = "telegram"  # alias
    max = "max"
    
    def __str__(self) -> str:
        return self.value


# Re-export commonly used aiogram types for convenience
try:
    from aiogram.types import (
        Message,
        CallbackQuery,
        User,
        Chat,
        InlineKeyboardMarkup,
        InlineKeyboardButton,
        ReplyKeyboardMarkup,
        KeyboardButton,
        ReplyKeyboardRemove,
        ForceReply,
        PhotoSize,
        Document,
        Audio,
        Video,
        Voice,
        VideoNote,
        Contact,
        Location,
        Venue,
        Sticker,
        Animation,
        BufferedInputFile,
        FSInputFile,
        URLInputFile,
    )
    
    __all__ = [
        "BPlatform",
        "Message",
        "CallbackQuery",
        "User",
        "Chat",
        "InlineKeyboardMarkup",
        "InlineKeyboardButton",
        "ReplyKeyboardMarkup",
        "KeyboardButton",
        "ReplyKeyboardRemove",
        "ForceReply",
        "PhotoSize",
        "Document",
        "Audio",
        "Video",
        "Voice",
        "VideoNote",
        "Contact",
        "Location",
        "Venue",
        "Sticker",
        "Animation",
        "BufferedInputFile",
        "FSInputFile",
        "URLInputFile",
    ]
except ImportError:
    __all__ = ["BPlatform"]

