"""Platform implementations."""

from obabot.platforms.base import BasePlatform
from obabot.platforms.telegram import TelegramPlatform
from obabot.platforms.max import MaxPlatform
from obabot.platforms.yandex import YandexPlatform

__all__ = ["BasePlatform", "TelegramPlatform", "MaxPlatform", "YandexPlatform"]

