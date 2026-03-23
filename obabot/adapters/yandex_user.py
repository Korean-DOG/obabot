"""User and chat adapters for Yandex Messenger platform."""

from typing import Any, Optional


class YandexUserAdapter:
    """Wraps Yandex 'from' object to provide aiogram-compatible User interface.

    Yandex from: {id, login, display_name, robot}
    Aiogram User: id, first_name, last_name, username, is_bot, language_code
    """

    def __init__(self, raw: dict):
        self._raw = raw

    @property
    def id(self) -> str:
        return self._raw.get("id", "")

    @property
    def first_name(self) -> str:
        return self._raw.get("display_name", "")

    @property
    def last_name(self) -> Optional[str]:
        return None

    @property
    def username(self) -> Optional[str]:
        return self._raw.get("login")

    @property
    def is_bot(self) -> bool:
        return self._raw.get("robot", False)

    @property
    def language_code(self) -> Optional[str]:
        return None

    @property
    def full_name(self) -> str:
        return self.first_name

    def __repr__(self) -> str:
        return f"YandexUserAdapter(id={self.id!r}, name={self.first_name!r})"


class YandexChatAdapter:
    """Wraps Yandex 'chat' object to provide aiogram-compatible Chat interface.

    Yandex chat: {id, type}  (type = "private" | "group")
    Aiogram Chat: id, type, title, username, first_name
    """

    def __init__(self, raw: dict):
        self._raw = raw

    @property
    def id(self) -> str:
        return self._raw.get("id", "")

    @property
    def type(self) -> str:
        return self._raw.get("type", "private")

    @property
    def title(self) -> Optional[str]:
        return None

    @property
    def username(self) -> Optional[str]:
        return None

    @property
    def first_name(self) -> Optional[str]:
        return None

    def __repr__(self) -> str:
        return f"YandexChatAdapter(id={self.id!r}, type={self.type!r})"
