"""Message adapter for Yandex Messenger platform.

Provides aiogram-compatible interface for Yandex Messenger updates.
"""

import asyncio
import logging
from typing import Any, Optional, TYPE_CHECKING

from obabot.adapters.yandex_user import YandexUserAdapter, YandexChatAdapter
from obabot.utils.text_format import format_text_for_platform

if TYPE_CHECKING:
    from obabot.adapters.keyboard import KeyboardType

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0


class YandexMessageAdapter:
    """Yandex Messenger message adapter with aiogram-style attributes.

    Guaranteed (safe to use without getattr):
    - .text: str (empty string when no text)
    - .photo: list (always empty — Yandex file handling is separate)
    - .document, .video, .voice, .sticker, .location, .contact: None
    - .content_type: str ("text" | "unknown")
    - .from_user, .chat, .message_id
    """

    _platform_id: str = "yandex"

    def __init__(self, raw_update: dict, bot: Any = None):
        self._raw = raw_update
        self._bot = bot

    def get_platform(self) -> str:
        return self._platform_id

    def is_telegram(self) -> bool:
        return False

    def is_max(self) -> bool:
        return False

    def is_yandex(self) -> bool:
        return True

    @property
    def platform(self) -> str:
        return self._platform_id

    @property
    def text(self) -> str:
        return self._raw.get("text", "") or ""

    @property
    def message_id(self) -> int:
        return self._raw.get("message_id", 0)

    @property
    def id(self) -> Any:
        return self.message_id

    @property
    def from_user(self) -> Optional[YandexUserAdapter]:
        from_data = self._raw.get("from")
        if from_data is None:
            return None
        return YandexUserAdapter(from_data)

    @property
    def sender(self) -> Optional[YandexUserAdapter]:
        return self.from_user

    @property
    def chat(self) -> Optional[YandexChatAdapter]:
        chat_data = self._raw.get("chat")
        if chat_data is None:
            return None
        return YandexChatAdapter(chat_data)

    @property
    def date(self) -> Optional[int]:
        return self._raw.get("timestamp")

    @property
    def update_id(self) -> int:
        return self._raw.get("update_id", 0)

    # --- Attachment properties (stubs, Yandex file handling TBD) ---

    @property
    def photo(self) -> list:
        return []

    @property
    def document(self) -> None:
        return None

    @property
    def audio(self) -> None:
        return None

    @property
    def video(self) -> None:
        return None

    @property
    def voice(self) -> None:
        return None

    @property
    def video_note(self) -> None:
        return None

    @property
    def sticker(self) -> None:
        return None

    @property
    def animation(self) -> None:
        return None

    @property
    def contact(self) -> None:
        return None

    @property
    def location(self) -> None:
        return None

    @property
    def successful_payment(self) -> None:
        return None

    @property
    def content_type(self) -> str:
        if self.text:
            return "text"
        return "unknown"

    # --- Send methods ---

    def _resolve_target(self) -> dict:
        """Build target dict (login or chat_id) for outgoing messages."""
        chat = self._raw.get("chat", {})
        chat_type = chat.get("type", "private")
        if chat_type == "private":
            from_data = self._raw.get("from", {})
            login = from_data.get("login")
            if login:
                return {"login": login}
        chat_id = chat.get("id")
        if chat_id:
            return {"chat_id": chat_id}
        return {}

    async def answer(
        self,
        text: str,
        reply_markup: Optional["KeyboardType"] = None,
        parse_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        formatted_text = format_text_for_platform(text, parse_mode, "yandex")

        if not self._bot or not hasattr(self._bot, "send_message"):
            logger.error("[Yandex send] answer: bot.send_message not available")
            raise NotImplementedError("Cannot send message: bot.send_message not available")

        target = self._resolve_target()
        if not target:
            logger.error("[Yandex send] answer: no target (login/chat_id)")
            raise ValueError("Cannot send: target is missing")

        try:
            coro = self._bot.send_message(
                text=formatted_text, reply_markup=reply_markup, **target, **kwargs,
            )
            return await asyncio.wait_for(coro, timeout=DEFAULT_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning("[Yandex send] answer() timeout after %.1fs", DEFAULT_TIMEOUT)
            return None
        except asyncio.CancelledError:
            return None
        except Exception:
            logger.exception("[Yandex send] answer() failed")
            raise

    async def reply(
        self,
        text: str,
        reply_markup: Optional["KeyboardType"] = None,
        parse_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        return await self.answer(text, reply_markup=reply_markup, parse_mode=parse_mode, **kwargs)

    async def edit_text(
        self,
        text: str,
        reply_markup: Optional["KeyboardType"] = None,
        parse_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        formatted_text = format_text_for_platform(text, parse_mode, "yandex")

        if not self._bot or not hasattr(self._bot, "edit_message_text"):
            logger.warning("[Yandex send] edit_text: bot.edit_message_text not available")
            return None

        msg_id = self.message_id
        target = self._resolve_target()
        try:
            coro = self._bot.edit_message_text(
                text=formatted_text, message_id=msg_id, reply_markup=reply_markup,
                **target, **kwargs,
            )
            return await asyncio.wait_for(coro, timeout=DEFAULT_TIMEOUT)
        except asyncio.TimeoutError:
            logger.warning("[Yandex send] edit_text() timeout")
            return None
        except asyncio.CancelledError:
            return None
        except Exception:
            logger.exception("[Yandex send] edit_text() failed")
            raise

    async def edit_reply_markup(
        self,
        reply_markup: Optional["KeyboardType"] = None,
        **kwargs: Any,
    ) -> Any:
        return await self.edit_text(
            text=self.text, reply_markup=reply_markup, **kwargs,
        )

    async def delete(self, **kwargs: Any) -> Any:
        logger.warning("[Yandex send] delete: not supported by Yandex Messenger API")
        return None

    # --- FSM passthrough (no native FSM in Yandex) ---

    async def set_state(self, state: Any) -> None:
        pass

    async def get_state(self) -> Any:
        return None

    async def reset_state(self) -> None:
        pass

    async def update_data(self, **data: Any) -> None:
        pass

    async def get_data(self) -> dict:
        return {}

    def __getattr__(self, name: str) -> Any:
        if name in self._raw:
            return self._raw[name]
        raise AttributeError(f"YandexMessageAdapter has no attribute {name!r}")
