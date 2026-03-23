"""Web platform emulators for obabot.

Internal classes: WebBot, WebMessage, WebCallbackQuery, WebUpdate, WebUser, WebChat.
These are NOT part of the public API — use create_web / create_mobile instead.
"""

import time
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_msg_counter = 0


def _next_msg_id() -> int:
    global _msg_counter
    _msg_counter += 1
    return _msg_counter


def _serialize_markup(markup: Any) -> Optional[Dict]:
    """Serialize aiogram/maxbot keyboard markup to a JSON-friendly dict."""
    if markup is None:
        return None

    name = type(markup).__name__

    if name == "InlineKeyboardMarkup":
        rows = []
        for row in markup.inline_keyboard:
            btns: List[Dict[str, Any]] = []
            for btn in row:
                d: Dict[str, Any] = {"text": btn.text}
                cb = getattr(btn, "callback_data", None)
                if cb:
                    d["callback_data"] = cb
                url = getattr(btn, "url", None)
                if url:
                    d["url"] = url
                btns.append(d)
            rows.append(btns)
        return {"type": "inline_keyboard", "inline_keyboard": rows}

    if name == "ReplyKeyboardMarkup":
        rows = []
        for row in markup.keyboard:
            rows.append([{"text": getattr(b, "text", str(b))} for b in row])
        return {
            "type": "reply_keyboard",
            "keyboard": rows,
            "resize_keyboard": getattr(markup, "resize_keyboard", True),
            "one_time_keyboard": getattr(markup, "one_time_keyboard", False),
        }

    if name == "ReplyKeyboardRemove":
        return {"type": "reply_keyboard_remove"}

    if isinstance(markup, dict):
        return markup

    return None


# ---------------------------------------------------------------------------
# Lightweight user / chat stubs
# ---------------------------------------------------------------------------

class WebUser:
    """Emulated user for the web platform."""

    def __init__(
        self,
        user_id: int,
        first_name: str = "WebUser",
        last_name: Optional[str] = None,
        username: Optional[str] = None,
    ):
        self.id = user_id
        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.is_bot = False
        self.language_code = None

    @property
    def full_name(self) -> str:
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name

    def __repr__(self) -> str:
        return f"WebUser(id={self.id}, name={self.full_name})"


class WebChat:
    """Emulated chat for the web platform."""

    def __init__(self, chat_id: int, chat_type: str = "private"):
        self.id = chat_id
        self.type = chat_type
        self.title = None
        self.username = None
        self.first_name = None
        self.last_name = None

    def __repr__(self) -> str:
        return f"WebChat(id={self.id}, type={self.type})"


# ---------------------------------------------------------------------------
# WebBot — captures outgoing messages
# ---------------------------------------------------------------------------

class WebBot:
    """Bot emulator that records every outgoing action in *outgoing* list."""

    def __init__(self) -> None:
        self.outgoing: List[Dict[str, Any]] = []

    # -- send methods -------------------------------------------------------

    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: Any = None,
        parse_mode: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        msg_id = _next_msg_id()
        entry: Dict[str, Any] = {
            "method": "send_message",
            "chat_id": chat_id,
            "text": text,
            "message_id": msg_id,
        }
        if reply_markup is not None:
            entry["reply_markup"] = _serialize_markup(reply_markup)
        if parse_mode:
            entry["parse_mode"] = parse_mode
        self.outgoing.append(entry)
        return entry

    async def send_photo(
        self, chat_id: int, photo: Any, caption: Optional[str] = None,
        reply_markup: Any = None, parse_mode: Optional[str] = None, **kw: Any,
    ) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "method": "send_photo", "chat_id": chat_id,
            "photo": str(photo), "message_id": _next_msg_id(),
        }
        if caption:
            entry["caption"] = caption
        if reply_markup is not None:
            entry["reply_markup"] = _serialize_markup(reply_markup)
        if parse_mode:
            entry["parse_mode"] = parse_mode
        self.outgoing.append(entry)
        return entry

    async def send_document(
        self, chat_id: int, document: Any, caption: Optional[str] = None,
        reply_markup: Any = None, parse_mode: Optional[str] = None, **kw: Any,
    ) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "method": "send_document", "chat_id": chat_id,
            "document": str(document), "message_id": _next_msg_id(),
        }
        if caption:
            entry["caption"] = caption
        if reply_markup is not None:
            entry["reply_markup"] = _serialize_markup(reply_markup)
        if parse_mode:
            entry["parse_mode"] = parse_mode
        self.outgoing.append(entry)
        return entry

    # -- edit / delete ------------------------------------------------------

    async def edit_message_text(
        self, text: str, chat_id: Optional[int] = None,
        message_id: Optional[int] = None, reply_markup: Any = None,
        parse_mode: Optional[str] = None, **kw: Any,
    ) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "method": "edit_message_text",
            "chat_id": chat_id, "message_id": message_id, "text": text,
        }
        if reply_markup is not None:
            entry["reply_markup"] = _serialize_markup(reply_markup)
        if parse_mode:
            entry["parse_mode"] = parse_mode
        self.outgoing.append(entry)
        return entry

    async def update_message(
        self, message_id: Any, text: str,
        reply_markup: Any = None, **kw: Any,
    ) -> Dict[str, Any]:
        """Max-style update_message (used by MaxMessageAdapter.edit_text)."""
        return await self.edit_message_text(
            text=text, message_id=message_id, reply_markup=reply_markup,
        )

    async def answer_callback_query(
        self, callback_query_id: Any, text: Optional[str] = None,
        show_alert: bool = False, **kw: Any,
    ) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "method": "answer_callback_query",
            "callback_query_id": callback_query_id,
        }
        if text:
            entry["text"] = text
        if show_alert:
            entry["show_alert"] = True
        self.outgoing.append(entry)
        return entry

    async def delete_message(
        self, chat_id: int = 0, message_id: int = 0, **kw: Any,
    ) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "method": "delete_message",
            "chat_id": chat_id, "message_id": message_id,
        }
        self.outgoing.append(entry)
        return entry


# ---------------------------------------------------------------------------
# WebMessage
# ---------------------------------------------------------------------------

class WebMessage:
    """Message emulator compatible with aiogram Message and MaxMessageAdapter."""

    _platform_id: str = "web"

    def __init__(
        self,
        bot: WebBot,
        user_id: int,
        text: str = "",
        chat_id: Optional[int] = None,
        message_id: Optional[int] = None,
        first_name: str = "WebUser",
    ):
        self._bot = bot
        self._user_id = user_id
        self._text = text
        self._chat_id = chat_id or user_id
        self._message_id = message_id or _next_msg_id()
        self._first_name = first_name
        # FSM storage — set by dispatch layer when available
        self._fsm_storage: Any = None
        self._fsm_bot_id: int = 0

    # -- platform helpers ---------------------------------------------------

    def get_platform(self) -> str:
        return "web"

    def is_telegram(self) -> bool:
        return False

    def is_max(self) -> bool:
        return False

    @property
    def platform(self) -> str:
        return "web"

    # -- core properties ----------------------------------------------------

    @property
    def text(self) -> str:
        return self._text

    @property
    def message_id(self) -> int:
        return self._message_id

    @property
    def id(self) -> int:
        return self._message_id

    @property
    def mid(self) -> int:
        return self._message_id

    @property
    def from_user(self) -> WebUser:
        return WebUser(self._user_id, first_name=self._first_name)

    @property
    def sender(self) -> WebUser:
        return self.from_user

    @property
    def chat(self) -> WebChat:
        return WebChat(self._chat_id)

    # -- attachment stubs (web messages are text-only) ----------------------

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
    def sticker(self) -> None:
        return None

    @property
    def location(self) -> None:
        return None

    @property
    def contact(self) -> None:
        return None

    @property
    def animation(self) -> None:
        return None

    @property
    def video_note(self) -> None:
        return None

    @property
    def successful_payment(self) -> None:
        return None

    @property
    def content_type(self) -> str:
        return "text" if self._text else "unknown"

    # -- reply / edit -------------------------------------------------------

    async def answer(
        self, text: str, reply_markup: Any = None,
        parse_mode: Optional[str] = None, **kw: Any,
    ) -> Any:
        return await self._bot.send_message(
            chat_id=self._chat_id, text=text,
            reply_markup=reply_markup, parse_mode=parse_mode,
        )

    async def reply(
        self, text: str, reply_markup: Any = None,
        parse_mode: Optional[str] = None, **kw: Any,
    ) -> Any:
        return await self.answer(text, reply_markup=reply_markup,
                                 parse_mode=parse_mode, **kw)

    async def edit_text(
        self, text: str, reply_markup: Any = None,
        parse_mode: Optional[str] = None, **kw: Any,
    ) -> Any:
        return await self._bot.edit_message_text(
            text=text, chat_id=self._chat_id,
            message_id=self._message_id,
            reply_markup=reply_markup, parse_mode=parse_mode,
        )

    async def edit_reply_markup(self, reply_markup: Any = None, **kw: Any) -> Any:
        return await self._bot.edit_message_text(
            text=self._text, chat_id=self._chat_id,
            message_id=self._message_id, reply_markup=reply_markup,
        )

    async def edit_caption(
        self, caption: Optional[str] = None, reply_markup: Any = None,
        parse_mode: Optional[str] = None, **kw: Any,
    ) -> Any:
        return await self.edit_text(
            text=caption or "", reply_markup=reply_markup,
            parse_mode=parse_mode,
        )

    async def delete(self, **kw: Any) -> Any:
        return await self._bot.delete_message(
            chat_id=self._chat_id, message_id=self._message_id,
        )

    # -- FSM methods (Max-style: message.set_state / get_state) ------------

    def _fsm_key(self) -> Any:
        """Build aiogram StorageKey for this user/chat."""
        try:
            from aiogram.fsm.storage.base import StorageKey
            return StorageKey(
                bot_id=self._fsm_bot_id,
                chat_id=self._chat_id,
                user_id=self._user_id,
            )
        except ImportError:
            return None

    async def set_state(self, state: Any = None) -> None:
        if not self._fsm_storage:
            return
        key = self._fsm_key()
        if key is None:
            return
        state_str = getattr(state, "state", None) if state is not None else None
        if state_str is None and state is not None:
            state_str = str(state)
        await self._fsm_storage.set_state(key=key, state=state_str)

    async def get_state(self) -> Optional[str]:
        if not self._fsm_storage:
            return None
        key = self._fsm_key()
        return await self._fsm_storage.get_state(key=key) if key else None

    async def reset_state(self) -> None:
        await self.set_state(None)

    async def get_data(self) -> Dict[str, Any]:
        if not self._fsm_storage:
            return {}
        key = self._fsm_key()
        return await self._fsm_storage.get_data(key=key) if key else {}

    async def update_data(self, **data: Any) -> Dict[str, Any]:
        if not self._fsm_storage:
            return {}
        key = self._fsm_key()
        if key is None:
            return {}
        return await self._fsm_storage.update_data(key=key, data=data)

    def __repr__(self) -> str:
        return (
            f"WebMessage(user={self._user_id}, chat={self._chat_id}, "
            f"text={self._text!r:.40})"
        )


# ---------------------------------------------------------------------------
# WebCallbackQuery
# ---------------------------------------------------------------------------

class WebCallbackQuery:
    """Callback query emulator for the web platform."""

    _platform_id: str = "web"

    def __init__(
        self,
        bot: WebBot,
        user_id: int,
        callback_data: str,
        chat_id: Optional[int] = None,
        message_id: Optional[int] = None,
        message_text: str = "",
        first_name: str = "WebUser",
    ):
        self._bot = bot
        self._user_id = user_id
        self._data = callback_data
        self._chat_id = chat_id or user_id
        self._message_id = message_id or _next_msg_id()
        self._message_text = message_text
        self._first_name = first_name
        self._id = f"web_cb_{int(time.time() * 1000)}"
        self._fsm_storage: Any = None
        self._fsm_bot_id: int = 0

    # -- platform helpers ---------------------------------------------------

    def get_platform(self) -> str:
        return "web"

    def is_telegram(self) -> bool:
        return False

    def is_max(self) -> bool:
        return False

    @property
    def platform(self) -> str:
        return "web"

    # -- core properties ----------------------------------------------------

    @property
    def data(self) -> Optional[str]:
        return self._data

    @property
    def payload(self) -> Optional[str]:
        """Max-style alias for callback_data."""
        return self._data

    @property
    def id(self) -> str:
        return self._id

    @property
    def from_user(self) -> WebUser:
        return WebUser(self._user_id, first_name=self._first_name)

    @property
    def user(self) -> WebUser:
        return self.from_user

    @property
    def message(self) -> "WebMessage":
        msg = WebMessage(
            bot=self._bot, user_id=self._user_id,
            text=self._message_text, chat_id=self._chat_id,
            message_id=self._message_id, first_name=self._first_name,
        )
        msg._fsm_storage = self._fsm_storage
        msg._fsm_bot_id = self._fsm_bot_id
        return msg

    # -- actions ------------------------------------------------------------

    async def answer(
        self, text: Optional[str] = None,
        show_alert: bool = False, **kw: Any,
    ) -> Any:
        return await self._bot.answer_callback_query(
            callback_query_id=self._id, text=text, show_alert=show_alert,
        )

    async def edit_message_text(
        self, text: str, reply_markup: Any = None,
        parse_mode: Optional[str] = None, **kw: Any,
    ) -> Any:
        return await self._bot.edit_message_text(
            text=text, chat_id=self._chat_id,
            message_id=self._message_id,
            reply_markup=reply_markup, parse_mode=parse_mode,
        )

    async def edit_message_reply_markup(
        self, reply_markup: Any = None, **kw: Any,
    ) -> Any:
        return await self._bot.edit_message_text(
            text=self._message_text, chat_id=self._chat_id,
            message_id=self._message_id, reply_markup=reply_markup,
        )

    async def edit_message_caption(
        self, caption: Optional[str] = None,
        reply_markup: Any = None, parse_mode: Optional[str] = None, **kw: Any,
    ) -> Any:
        return await self.edit_message_text(
            text=caption or "", reply_markup=reply_markup,
            parse_mode=parse_mode,
        )

    async def delete_message(self, **kw: Any) -> Any:
        return await self._bot.delete_message(
            chat_id=self._chat_id, message_id=self._message_id,
        )

    def __repr__(self) -> str:
        return (
            f"WebCallbackQuery(user={self._user_id}, data={self._data!r:.30})"
        )


# ---------------------------------------------------------------------------
# WebUpdate — thin container
# ---------------------------------------------------------------------------

class WebUpdate:
    """Container for a web update (either message or callback)."""

    def __init__(
        self,
        message: Optional[WebMessage] = None,
        callback_query: Optional[WebCallbackQuery] = None,
    ):
        self.message = message
        self.callback_query = callback_query
