"""Yandex Messenger platform implementation via HTTP Bot API.

API base: https://botapi.messenger.yandex.net/bot/v1/messages/
Auth: Authorization: OAuth <token>
"""

import asyncio
import logging
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

import httpx

from obabot.context import set_current_platform, reset_current_platform
from obabot.platforms.base import BasePlatform, HandlerType
from obabot.types import BPlatform

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

BASE_URL = "https://botapi.messenger.yandex.net/bot/v1/messages"

MIDDLEWARE_OBSERVER_TYPES = ("message", "callback_query", "edited_message")


# ---------------------------------------------------------------------------
# Lightweight bot / router stubs (no external library needed)
# ---------------------------------------------------------------------------

class YandexBot:
    """Async HTTP client for Yandex Messenger Bot API."""

    def __init__(self, token: str):
        self._token = token
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def token(self) -> str:
        return self._token

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={
                    "Authorization": f"OAuth {self._token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
        return self._client

    async def _request(self, method: str, data: Optional[dict] = None) -> dict:
        client = await self._ensure_client()
        url = f"{BASE_URL}/{method}/"
        logger.debug("[YandexBot] POST %s payload=%s", url, data)
        response = await client.post(url, json=data or {})
        result = response.json()
        if not result.get("ok", True):
            logger.error("[YandexBot] API error %s: %s", method, result)
        return result

    # --- Public API methods ---

    async def send_message(
        self,
        text: str,
        chat_id: Optional[str] = None,
        login: Optional[str] = None,
        reply_markup: Any = None,
        thread_id: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        from obabot.adapters.keyboard import convert_keyboard_to_yandex

        payload: dict = {"text": text}
        if chat_id:
            payload["chat_id"] = str(chat_id)
        elif login:
            payload["login"] = login
        if thread_id:
            payload["thread_id"] = str(thread_id)

        kb = convert_keyboard_to_yandex(reply_markup)
        if kb:
            payload["inline_keyboard"] = kb

        return await self._request("sendText", payload)

    async def edit_message_text(
        self,
        text: str,
        message_id: int,
        chat_id: Optional[str] = None,
        login: Optional[str] = None,
        reply_markup: Any = None,
        **kwargs: Any,
    ) -> dict:
        from obabot.adapters.keyboard import convert_keyboard_to_yandex

        payload: dict = {"message_id": message_id, "text": text}
        if chat_id:
            payload["chat_id"] = str(chat_id)
        elif login:
            payload["login"] = login

        kb = convert_keyboard_to_yandex(reply_markup)
        if kb:
            payload["inline_keyboard"] = kb

        return await self._request("editText", payload)

    async def send_file(
        self,
        chat_id: Optional[str] = None,
        login: Optional[str] = None,
        file_path: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        """Send file via multipart POST to sendFile endpoint."""
        client = await self._ensure_client()
        url = f"{BASE_URL}/sendFile/"

        data: dict = {}
        if chat_id:
            data["chat_id"] = str(chat_id)
        elif login:
            data["login"] = login

        files = None
        if file_path:
            import os
            filename = os.path.basename(file_path)
            files = {"document": (filename, open(file_path, "rb"))}

        response = await client.post(url, data=data, files=files)
        return response.json()

    async def answer_callback_query(
        self,
        callback_query_id: Any = None,
        text: Optional[str] = None,
        show_alert: bool = False,
        **kwargs: Any,
    ) -> dict:
        """Answer callback query (best-effort; endpoint may not exist)."""
        try:
            payload: dict = {}
            if callback_query_id:
                payload["callback_query_id"] = str(callback_query_id)
            if text:
                payload["text"] = text
            if show_alert:
                payload["show_alert"] = True
            return await self._request("answerCallbackQuery", payload)
        except Exception:
            logger.debug("[YandexBot] answerCallbackQuery not supported or failed")
            return {"ok": False}

    async def get_updates(self, offset: int = 0, limit: int = 100) -> dict:
        return await self._request("getUpdates", {"offset": offset, "limit": limit})

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @property
    def session(self) -> "YandexBot":
        return self


class YandexRouter:
    """Minimal router storing (handler, filter) pairs — no external library needed."""

    def __init__(self) -> None:
        self.message_handlers: List[Tuple[Callable, Any]] = []
        self.callback_handlers: List[Tuple[Callable, Any]] = []

    def message(self, *filters: Any, **kwargs: Any) -> Callable:
        def decorator(handler: Callable) -> Callable:
            flt = filters[0] if filters else None
            self.message_handlers.append((handler, flt))
            return handler
        return decorator

    def callback_query(self, *filters: Any, **kwargs: Any) -> Callable:
        def decorator(handler: Callable) -> Callable:
            flt = filters[0] if filters else None
            self.callback_handlers.append((handler, flt))
            return handler
        return decorator

    callback = callback_query

    def edited_message(self, *filters: Any, **kwargs: Any) -> Callable:
        return self.message(*filters, **kwargs)


# ---------------------------------------------------------------------------
# Middleware helpers (same pattern as MaxPlatform)
# ---------------------------------------------------------------------------

def _make_middleware_chain(handler: Callable, middlewares: List[Any]) -> Callable:
    if not middlewares:
        async def no_mw(event: Any, data: Dict[str, Any]) -> Any:
            return await handler(event)
        return no_mw

    async def final(event: Any, data: Dict[str, Any]) -> Any:
        return await handler(event)

    chain = final
    for mw in reversed(middlewares):
        outer_chain = chain

        async def wrapper(event: Any, data: Dict[str, Any], _mw: Any = mw, _inner: Callable = outer_chain) -> Any:
            return await _mw(_inner, event, data)
        chain = wrapper
    return chain


async def _call_with_middlewares(
    handler: Callable,
    event: Any,
    data: Dict[str, Any],
    middlewares: List[Tuple[Any, bool]],
) -> Any:
    outer_mws = [mw for mw, is_outer in middlewares if is_outer]
    inner_mws = [mw for mw, is_outer in middlewares if not is_outer]

    inner_chain = _make_middleware_chain(handler, inner_mws)

    async def inner_as_handler(event: Any) -> Any:
        return await inner_chain(event, data)

    outer_chain = _make_middleware_chain(inner_as_handler, outer_mws)
    return await outer_chain(event, data)


# ---------------------------------------------------------------------------
# YandexPlatform
# ---------------------------------------------------------------------------

class YandexPlatform(BasePlatform):
    """Yandex Messenger platform — polling + direct HTTP calls."""

    def __init__(self, token: str):
        self._token = token
        self._bot = YandexBot(token)
        self._router = YandexRouter()
        self._external_router: Optional[Any] = None
        self._running = False
        self._polling_task: Optional[asyncio.Task] = None
        self._handlers_setup = False
        self._middlewares: Dict[str, List[Tuple[Any, bool]]] = {t: [] for t in MIDDLEWARE_OBSERVER_TYPES}

    # --- BasePlatform interface ---

    @property
    def platform(self) -> BPlatform:
        return BPlatform.yandex

    @property
    def bot(self) -> YandexBot:
        return self._bot

    @property
    def dispatcher(self) -> "YandexPlatform":
        return self

    @property
    def router(self) -> YandexRouter:
        return self._router

    # --- Filter conversion ---

    def convert_filters_for_platform(self, filters: tuple, handler_type: str = "message") -> tuple:
        return self._convert_filters(filters)

    def _convert_filters(self, filters: tuple) -> tuple:
        from aiogram.filters import Command, CommandStart

        converted = []
        for f in filters:
            name = type(f).__name__
            if name == "CommandStart":
                converted.append(self._create_command_filter(["start"]))
            elif name == "Command":
                commands = getattr(f, "commands", [])
                if commands:
                    converted.append(self._create_command_filter(list(commands)))
            elif name == "MagicFilter":
                converted.append(f)
            elif "State" in name:
                converted.append(f)
            else:
                if callable(f):
                    converted.append(f)
        return tuple(converted)

    @staticmethod
    def _create_command_filter(commands: list) -> Callable:
        def command_filter(message: Any) -> bool:
            text = getattr(message, "text", None)
            if not text:
                return False
            for cmd in commands:
                if text == f"/{cmd}" or text.startswith(f"/{cmd} "):
                    return True
            return False
        return command_filter

    # --- Middleware ---

    def add_middleware(self, observer_type: str, middleware: Any, outer: bool = False) -> None:
        if observer_type not in self._middlewares:
            return
        self._middlewares[observer_type].append((middleware, outer))

    def get_middlewares(self, observer_type: str) -> List[Tuple[Any, bool]]:
        return self._middlewares.get(observer_type, [])

    # --- External router ---

    def set_external_router(self, router: Any) -> None:
        self._external_router = router

    # --- Handler setup ---

    def _setup_handlers(self) -> None:
        if self._handlers_setup:
            return
        if self._external_router:
            self._register_external_handlers()
        self._handlers_setup = True

    def _register_external_handlers(self) -> None:
        if not self._external_router:
            return
        for filters, kwargs, handler in getattr(self._external_router, "_message_handlers", []):
            wrapped = self.wrap_handler(handler)
            flt = filters[0] if filters else None
            self._router.message_handlers.append((wrapped, flt))
        for filters, kwargs, handler in getattr(self._external_router, "_callback_handlers", []):
            wrapped = self.wrap_handler(handler)
            flt = filters[0] if filters else None
            self._router.callback_handlers.append((wrapped, flt))

    # --- Handler wrapping ---

    def wrap_handler(self, handler: HandlerType) -> HandlerType:
        @wraps(handler)
        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            token = set_current_platform(BPlatform.yandex)
            try:
                for arg in args:
                    try:
                        object.__setattr__(arg, "platform", "yandex")
                    except (AttributeError, TypeError, ValueError):
                        pass
                for v in kwargs.values():
                    try:
                        object.__setattr__(v, "platform", "yandex")
                    except (AttributeError, TypeError, ValueError):
                        pass
                return await handler(*args, **kwargs)
            finally:
                reset_current_platform(token)
        return wrapped

    # --- Filter checking (same pattern as MaxPlatform) ---

    async def _filter_check(self, flt: Any, data: Any) -> bool:
        if flt is None:
            return True

        flt_name = type(flt).__name__

        if flt_name == "MagicFilter" or hasattr(flt, "_resolve_operation_"):
            try:
                if hasattr(flt, "resolve"):
                    result = flt.resolve(data)
                    if isinstance(result, bool):
                        return result
                    return result is not None
            except Exception:
                return False

        if flt_name in ("Command", "CommandStart", "CommandObject"):
            text = getattr(data, "text", "") or ""
            if not text.startswith("/"):
                return False
            parts = text.split()
            cmd = parts[0][1:].split("@")[0] if parts else ""
            if flt_name == "CommandStart":
                return cmd == "start"
            if hasattr(flt, "commands"):
                cmds = flt.commands
                return cmd in cmds if isinstance(cmds, (list, tuple, set, frozenset)) else cmd == cmds
            return False

        if hasattr(flt, "check") and callable(flt.check):
            result = flt.check(data)
            if asyncio.iscoroutine(result):
                result = await result
            return bool(result)

        if callable(flt):
            try:
                result = flt(data)
            except TypeError:
                try:
                    result = flt(data)
                except Exception:
                    return False
            if asyncio.iscoroutine(result):
                result = await result
            return bool(result)

        return False

    # --- Polling ---

    async def start_polling(self) -> None:
        self._setup_handlers()
        self._running = True

        offset = 0
        response = await self._bot.get_updates(offset=0, limit=100)
        updates = response.get("updates", [])
        if updates:
            offset = max(int(u.get("update_id", 0)) for u in updates) + 1

        logger.info("[Yandex] Polling started (offset=%s)", offset)

        while self._running:
            try:
                response = await self._bot.get_updates(offset=offset, limit=100)
                updates = response.get("updates", [])
                for upd in updates:
                    uid = int(upd.get("update_id", 0))
                    if uid >= offset:
                        offset = uid + 1
                    try:
                        await self._dispatch_update(upd)
                    except Exception:
                        logger.exception("[Yandex] Error dispatching update %s", uid)
            except asyncio.CancelledError:
                logger.info("[Yandex] Polling cancelled")
                break
            except Exception:
                logger.exception("[Yandex] Polling error, retrying in 5s")
                await asyncio.sleep(5)
                continue
            await asyncio.sleep(1)

        logger.info("[Yandex] Polling stopped")

    async def stop_polling(self) -> None:
        self._running = False
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
        await self._bot.close()

    # --- Update dispatch ---

    async def _dispatch_update(self, update: dict) -> Any:
        from obabot.adapters.yandex_message import YandexMessageAdapter
        from obabot.adapters.yandex_callback import YandexCallbackQuery

        is_callback = "callback_data" in update

        if is_callback:
            cb = YandexCallbackQuery(update, self._bot)
            mw_data: Dict[str, Any] = {"bot": self._bot, "event_update": update}
            cb_mws = self._middlewares.get("callback_query", [])

            for handler, flt in self._router.callback_handlers:
                if await self._filter_check(flt, cb):
                    name = getattr(handler, "__name__", str(handler))
                    logger.info("[Yandex] callback -> %s", name)
                    await _call_with_middlewares(handler, cb, mw_data, cb_mws)
                    return
            logger.debug("[Yandex] No callback handler matched")
        else:
            msg = YandexMessageAdapter(update, self._bot)
            mw_data = {"bot": self._bot, "event_update": update}
            msg_mws = self._middlewares.get("message", [])

            for handler, flt in self._router.message_handlers:
                if await self._filter_check(flt, msg):
                    name = getattr(handler, "__name__", str(handler))
                    logger.info("[Yandex] message -> %s", name)
                    await _call_with_middlewares(handler, msg, mw_data, msg_mws)
                    return
            logger.debug("[Yandex] No message handler matched")

    # --- feed_update / feed_raw_update ---

    async def feed_update(self, update: Any, **kwargs: Any) -> Any:
        self._setup_handlers()
        if isinstance(update, dict):
            return await self._dispatch_update(update)
        return None

    async def feed_raw_update(self, update: dict, **kwargs: Any) -> Any:
        self._setup_handlers()

        if isinstance(update, dict) and "updates" in update:
            for upd in update["updates"]:
                await self._dispatch_update(upd)
            return None

        return await self._dispatch_update(update)
