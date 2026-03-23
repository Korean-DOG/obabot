"""Callback query adapter for Yandex Messenger platform.

Yandex Messenger inline keyboard buttons send callback_data when pressed.
This adapter normalises the callback payload to an aiogram-compatible
CallbackQuery-like object.
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


def _extract_callback_data(raw_cb: Any) -> Optional[str]:
    """Normalise Yandex callback_data to a plain string.

    Yandex allows callback_data to be a string **or** a JSON object.
    If it is a dict, try ``raw_cb["data"]`` first, then fall back to
    ``json.dumps``.
    """
    if raw_cb is None:
        return None
    if isinstance(raw_cb, str):
        return raw_cb
    if isinstance(raw_cb, dict):
        if "data" in raw_cb:
            return str(raw_cb["data"])
        import json
        return json.dumps(raw_cb, ensure_ascii=False)
    return str(raw_cb)


class YandexCallbackQuery:
    """Aiogram-compatible wrapper around a Yandex callback update.

    Guaranteed attributes:
    - .data  (str | None)
    - .message  (YandexMessageAdapter | None)
    - .from_user  (YandexUserAdapter | None)
    """

    _platform_id: str = "yandex"

    def __init__(self, raw_update: dict, bot: Any = None):
        self._raw = raw_update
        self._bot = bot
        self._message: Any = None

    # --- Core properties ---

    @property
    def platform(self) -> str:
        return self._platform_id

    @property
    def data(self) -> Optional[str]:
        return _extract_callback_data(self._raw.get("callback_data"))

    @property
    def id(self) -> int:
        return self._raw.get("update_id", 0)

    @property
    def message_id(self) -> int:
        return self._raw.get("message_id", 0)

    @property
    def from_user(self) -> Optional[YandexUserAdapter]:
        from_data = self._raw.get("from")
        if from_data is None:
            return None
        return YandexUserAdapter(from_data)

    @property
    def chat(self) -> Optional[YandexChatAdapter]:
        chat_data = self._raw.get("chat")
        if chat_data is None:
            return None
        return YandexChatAdapter(chat_data)

    @property
    def message(self) -> Any:
        if self._message is None:
            from obabot.adapters.yandex_message import YandexMessageAdapter
            self._message = YandexMessageAdapter(self._raw, self._bot)
        return self._message

    # --- Action methods ---

    async def answer(
        self,
        text: Optional[str] = None,
        show_alert: bool = False,
        **kwargs: Any,
    ) -> Any:
        """Answer callback query.

        Yandex Messenger may not have a native answerCallbackQuery endpoint.
        If the bot supports it, call it; otherwise this is a no-op.
        """
        if self._bot and hasattr(self._bot, "answer_callback_query"):
            try:
                coro = self._bot.answer_callback_query(
                    callback_query_id=self.id,
                    text=text,
                    show_alert=show_alert,
                    **kwargs,
                )
                return await asyncio.wait_for(coro, timeout=DEFAULT_TIMEOUT)
            except Exception:
                logger.debug("[Yandex] answer_callback_query failed, ignoring")
        return None

    async def edit_message_text(
        self,
        text: str,
        reply_markup: Optional["KeyboardType"] = None,
        parse_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:
        formatted_text = format_text_for_platform(text, parse_mode, "yandex")
        if self._bot and hasattr(self._bot, "edit_message_text"):
            target = self.message._resolve_target() if self.message else {}
            try:
                coro = self._bot.edit_message_text(
                    text=formatted_text,
                    message_id=self.message_id,
                    reply_markup=reply_markup,
                    **target,
                    **kwargs,
                )
                return await asyncio.wait_for(coro, timeout=DEFAULT_TIMEOUT)
            except Exception:
                logger.exception("[Yandex] edit_message_text failed")
                raise
        return None

    async def edit_message_reply_markup(
        self,
        reply_markup: Optional["KeyboardType"] = None,
        **kwargs: Any,
    ) -> Any:
        text = self.message.text if self.message else ""
        return await self.edit_message_text(text, reply_markup=reply_markup, **kwargs)

    async def delete_message(self, **kwargs: Any) -> Any:
        logger.warning("[Yandex] delete_message: not supported by Yandex Messenger API")
        return None

    def __repr__(self) -> str:
        return f"YandexCallbackQuery(data={self.data!r}, msg_id={self.message_id})"
