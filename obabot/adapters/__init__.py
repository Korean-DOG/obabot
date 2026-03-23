"""Adapters for platform compatibility.

Guaranteed update attributes (handlers receive Message or CallbackQuery from obabot):

Message (Telegram: aiogram Message; Max: MaxMessageAdapter; Yandex: YandexMessageAdapter)
— always have:
  .text (str, "" when none), .photo (list, [] when none), .document, .video, .voice,
  .sticker, .location, .contact (present, None when absent), .content_type (str).

CallbackQuery (Telegram: TelegramCallbackQuery; Max: MaxCallbackQuery;
  Yandex: YandexCallbackQuery) — always have:
  .data (str | None), .message (Message | None).
"""

from obabot.adapters.message import MaxMessageAdapter
from obabot.adapters.max_callback import MaxCallbackQuery
from obabot.adapters.max_file import MaxFileFilenameError
from obabot.adapters.telegram_callback import TelegramCallbackQuery
from obabot.adapters.user import MaxUserAdapter, MaxChatAdapter
from obabot.adapters.keyboard import convert_keyboard_to_max, convert_keyboard_from_max, convert_keyboard_to_yandex
from obabot.adapters.yandex_message import YandexMessageAdapter
from obabot.adapters.yandex_callback import YandexCallbackQuery
from obabot.adapters.yandex_user import YandexUserAdapter, YandexChatAdapter

__all__ = [
    'MaxMessageAdapter',
    'MaxCallbackQuery',
    'MaxFileFilenameError',
    'TelegramCallbackQuery',
    'MaxUserAdapter',
    'MaxChatAdapter',
    'convert_keyboard_to_max',
    'convert_keyboard_from_max',
    'convert_keyboard_to_yandex',
    'YandexMessageAdapter',
    'YandexCallbackQuery',
    'YandexUserAdapter',
    'YandexChatAdapter',
]
