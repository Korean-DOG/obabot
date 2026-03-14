"""Platform implementations."""

from obabot.platforms.base import BasePlatform
from obabot.platforms.telegram import TelegramPlatform
from obabot.platforms.max import MaxPlatform

__all__ = ["BasePlatform", "TelegramPlatform", "MaxPlatform"]

