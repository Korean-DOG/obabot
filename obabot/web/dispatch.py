"""Web dispatch engine — routes web requests through obabot handlers.

Reads pending handlers from ProxyRouter (normal mode) or aiogram Router
(test mode), checks filters against web emulators, injects FSMContext
when handlers expect it, and runs the middleware chain.
"""

import asyncio
import inspect
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Handler collection — works with ProxyDispatcher *and* aiogram Dispatcher
# ---------------------------------------------------------------------------

HandlerRecord = Tuple[str, tuple, dict, Callable]


def _collect_handlers(dp: Any) -> List[HandlerRecord]:
    """Build a flat list of ``(handler_type, filters, kwargs, callback)``
    that the web dispatch can iterate over.

    Supports two dispatcher flavours:
    * **ProxyDispatcher** — reads ``dp._router._pending_handlers``.
    * **aiogram Dispatcher** (test mode) — introspects sub-routers and
      their ``TelegramEventObserver`` handler lists.
    """
    # 1. ProxyRouter (normal mode)
    proxy_router = getattr(dp, "_router", None)
    if proxy_router is not None:
        pending = getattr(proxy_router, "_pending_handlers", None)
        if pending:
            return list(pending)

    # 2. aiogram Dispatcher / Router (test mode)
    records: List[HandlerRecord] = []
    routers: list = []

    sub = getattr(dp, "sub_routers", None)
    if sub:
        routers.extend(sub)
    routers.append(dp)

    for router in routers:
        _extract_aiogram_handlers(router, records)

    return records


def _extract_aiogram_handlers(router: Any, out: List[HandlerRecord]) -> None:
    """Extract handlers from an aiogram Router into *out*."""
    for event_name, handler_type in (
        ("message", "message"),
        ("callback_query", "callback_query"),
        ("edited_message", "edited_message"),
    ):
        observer = getattr(router, event_name, None)
        if observer is None:
            continue
        handler_objects = getattr(observer, "handlers", [])
        for ho in handler_objects:
            callback = getattr(ho, "callback", None)
            if callback is None:
                continue
            raw_filters = _unwrap_aiogram_filters(getattr(ho, "filters", None))
            out.append((handler_type, raw_filters, {}, callback))


def _unwrap_aiogram_filters(filter_objects: Any) -> tuple:
    """Convert aiogram ``FilterObject`` wrappers to raw filter instances.

    Aiogram stores filters as ``FilterObject(callback=<real_filter>, ...)``
    in ``HandlerObject.filters``.  We extract the inner ``.callback`` so
    our ``_check_filter`` can work with the original ``CommandStart``,
    ``MagicFilter``, ``StateFilter`` etc.
    """
    if not filter_objects:
        return ()
    result: list = []
    for fo in filter_objects:
        inner = getattr(fo, "callback", fo)
        result.append(inner)
    return tuple(result)


# ---------------------------------------------------------------------------
# WebFSMContext — lightweight wrapper over aiogram's BaseStorage
# ---------------------------------------------------------------------------

class WebFSMContext:
    """FSMContext-compatible object that works with aiogram's storage backends.

    Handlers that declare ``state: FSMContext`` receive this object.
    """

    def __init__(self, storage: Any, user_id: int, chat_id: int, bot_id: int = 0):
        self._storage = storage
        self._user_id = user_id
        self._chat_id = chat_id
        self._bot_id = bot_id
        self._key = self._make_key()

    def _make_key(self) -> Any:
        try:
            from aiogram.fsm.storage.base import StorageKey
            return StorageKey(
                bot_id=self._bot_id, chat_id=self._chat_id,
                user_id=self._user_id,
            )
        except ImportError:
            return None

    async def get_state(self) -> Optional[str]:
        if self._storage is None or self._key is None:
            return None
        return await self._storage.get_state(key=self._key)

    async def set_state(self, state: Any = None) -> None:
        if self._storage is None or self._key is None:
            return
        if state is None:
            state_str = None
        elif hasattr(state, "state"):
            state_str = state.state
        else:
            state_str = str(state)
        await self._storage.set_state(key=self._key, state=state_str)

    async def get_data(self) -> Dict[str, Any]:
        if self._storage is None or self._key is None:
            return {}
        return await self._storage.get_data(key=self._key)

    async def update_data(self, data: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
        if self._storage is None or self._key is None:
            return {}
        merged = dict(data or {}, **kwargs)
        return await self._storage.update_data(key=self._key, data=merged)

    async def set_data(self, data: Dict[str, Any]) -> None:
        if self._storage is None or self._key is None:
            return
        await self._storage.set_data(key=self._key, data=data)

    async def clear(self) -> None:
        await self.set_state(None)
        await self.set_data({})


# ---------------------------------------------------------------------------
# Filter checking
# ---------------------------------------------------------------------------

async def _check_filter(
    flt: Any,
    event: Any,
    fsm_ctx: Optional[WebFSMContext] = None,
) -> bool:
    """Check a single filter against a web event.

    Handles: MagicFilter, Command/CommandStart, State/StateFilter, callables.
    """
    if flt is None:
        return True

    flt_name = type(flt).__name__

    # --- MagicFilter (F.text, F.data, F.photo, …) -------------------------
    if flt_name == "MagicFilter" or hasattr(flt, "_resolve_operation_"):
        try:
            result = flt.resolve(event) if hasattr(flt, "resolve") else None
            return bool(result) if isinstance(result, bool) else result is not None
        except (AttributeError, LookupError, TypeError, KeyError, ValueError):
            return False
        except Exception:
            return False

    # --- Command / CommandStart --------------------------------------------
    if flt_name in ("Command", "CommandStart", "CommandObject"):
        text = getattr(event, "text", "") or ""
        if not text.startswith("/"):
            return False
        parts = text.split()
        cmd = parts[0][1:].split("@")[0] if parts else ""
        if flt_name == "CommandStart":
            return cmd == "start"
        commands = getattr(flt, "commands", None)
        if commands is not None:
            if isinstance(commands, (list, tuple, set, frozenset)):
                return cmd in commands
            return cmd == commands
        return False

    # --- StateFilter (aiogram wraps State objects into StateFilter) --------
    if flt_name == "StateFilter":
        if fsm_ctx is None:
            return False
        current = await fsm_ctx.get_state()
        states = getattr(flt, "states", [])
        for s in states:
            target_str = getattr(s, "state", None)
            if target_str is None and s is not None:
                target_str = str(s) if str(s) != "*" else None
            if target_str is None and current is None:
                return True
            if current == target_str:
                return True
        return False

    # --- Raw State object (from StatesGroup) / other State-like filters ---
    if "State" in flt_name or (hasattr(flt, "state") and hasattr(flt, "group")):
        if fsm_ctx is None:
            return False
        current = await fsm_ctx.get_state()
        target = getattr(flt, "state", flt)
        target_str = getattr(target, "state", None) or str(target) if target is not None else None
        if target_str is None:
            return current is None
        return current == target_str

    # --- umaxbot-style .check() -------------------------------------------
    if hasattr(flt, "check") and callable(getattr(flt, "check")):
        try:
            result = flt.check(event)
            if asyncio.iscoroutine(result):
                result = await result
            return bool(result)
        except Exception:
            return False

    # --- Callable ----------------------------------------------------------
    if callable(flt):
        try:
            result = flt(event)
            if asyncio.iscoroutine(result):
                result = await result
            return bool(result)
        except Exception:
            return False

    return False


# ---------------------------------------------------------------------------
# Handler argument injection
# ---------------------------------------------------------------------------

def _resolve_extra_args(
    handler: Callable,
    fsm_ctx: Optional[WebFSMContext],
    bot: Any,
) -> list:
    """Inspect handler signature and build extra positional args after *event*."""
    try:
        sig = inspect.signature(handler)
    except (ValueError, TypeError):
        return []

    params = list(sig.parameters.values())
    extras: list = []

    for param in params[1:]:  # skip first (event)
        ann = param.annotation
        ann_name = getattr(ann, "__name__", "") if ann != inspect.Parameter.empty else ""

        if "FSMContext" in ann_name or param.name == "state":
            extras.append(fsm_ctx)
        elif param.name == "bot":
            extras.append(bot)
        elif param.name == "command" and ann_name == "CommandObject":
            extras.append(None)
        else:
            if param.default is not inspect.Parameter.empty:
                break
            extras.append(None)

    return extras


# ---------------------------------------------------------------------------
# Middleware chain (reusable from MaxPlatform pattern)
# ---------------------------------------------------------------------------

async def _call_with_middleware(
    handler: Callable,
    event: Any,
    extra_args: list,
    middlewares: List[Tuple[Any, bool]],
    mw_data: Dict[str, Any],
) -> Any:
    """Run handler through middleware chain (outer → inner → handler)."""

    async def final_handler(ev: Any, data: Dict[str, Any]) -> Any:
        return await handler(ev, *extra_args)

    if not middlewares:
        return await final_handler(event, mw_data)

    outer_mws = [mw for mw, is_outer in middlewares if is_outer]
    inner_mws = [mw for mw, is_outer in middlewares if not is_outer]

    chain = final_handler
    for mw in reversed(inner_mws):
        prev = chain

        async def _inner(ev: Any, data: Dict[str, Any], _m: Any = mw, _p: Any = prev) -> Any:
            return await _m(_p, ev, data)
        chain = _inner

    inner_chain = chain

    async def inner_entry(ev: Any) -> Any:
        return await inner_chain(ev, mw_data)

    outer_fn: Callable = inner_entry
    for mw in reversed(outer_mws):
        prev_fn = outer_fn

        async def _outer(ev: Any, _m: Any = mw, _prev: Any = prev_fn) -> Any:
            async def _prev_handler(ev2: Any, data: Dict[str, Any]) -> Any:
                return await _prev(ev2)
            return await _m(_prev_handler, ev, mw_data)
        outer_fn = _outer

    return await outer_fn(event)


# ---------------------------------------------------------------------------
# Public dispatch helpers
# ---------------------------------------------------------------------------

async def dispatch_message(
    dp: Any,
    web_bot: Any,
    message: Any,
    *,
    bot_id: int = 0,
) -> None:
    """Dispatch a WebMessage through the registered handlers."""
    handlers = _collect_handlers(dp)
    if not handlers:
        logger.warning("[web] dispatch_message: no handlers found")
        return

    fsm_storage = getattr(dp, "_fsm_storage", None) or getattr(dp, "fsm_storage", None)

    fsm_ctx: Optional[WebFSMContext] = None
    if fsm_storage and hasattr(message, "from_user") and message.from_user:
        uid = message.from_user.id
        cid = message.chat.id if hasattr(message, "chat") and message.chat else uid
        fsm_ctx = WebFSMContext(fsm_storage, uid, cid, bot_id)
        message._fsm_storage = fsm_storage
        message._fsm_bot_id = bot_id

    proxy_router = getattr(dp, "_router", None)
    middlewares = (
        proxy_router.get_middlewares("message")
        if proxy_router and hasattr(proxy_router, "get_middlewares")
        else []
    )
    mw_data: Dict[str, Any] = {"bot": web_bot, "state": fsm_ctx, "event_update": None}

    for handler_type, filters, _kwargs, handler in handlers:
        if handler_type not in ("message", "edited_message"):
            continue

        all_pass = True
        for flt in filters:
            if not await _check_filter(flt, message, fsm_ctx):
                all_pass = False
                break

        if all_pass:
            extra = _resolve_extra_args(handler, fsm_ctx, web_bot)
            name = getattr(handler, "__name__", str(handler))
            logger.info("[web] message -> %s", name)
            try:
                await _call_with_middleware(handler, message, extra, middlewares, mw_data)
            except Exception:
                logger.exception("[web] handler %s failed", name)
                raise
            return  # first match wins (aiogram behaviour)

    logger.debug("[web] no matching message handler")


async def dispatch_callback(
    dp: Any,
    web_bot: Any,
    callback: Any,
    *,
    bot_id: int = 0,
) -> None:
    """Dispatch a WebCallbackQuery through the registered handlers."""
    handlers = _collect_handlers(dp)
    if not handlers:
        logger.warning("[web] dispatch_callback: no handlers found")
        return

    fsm_storage = getattr(dp, "_fsm_storage", None) or getattr(dp, "fsm_storage", None)

    fsm_ctx: Optional[WebFSMContext] = None
    if fsm_storage and hasattr(callback, "from_user") and callback.from_user:
        uid = callback.from_user.id
        cid = callback._chat_id if hasattr(callback, "_chat_id") else uid
        fsm_ctx = WebFSMContext(fsm_storage, uid, cid, bot_id)
        callback._fsm_storage = fsm_storage
        callback._fsm_bot_id = bot_id

    proxy_router = getattr(dp, "_router", None)
    middlewares = (
        proxy_router.get_middlewares("callback_query")
        if proxy_router and hasattr(proxy_router, "get_middlewares")
        else []
    )
    mw_data: Dict[str, Any] = {"bot": web_bot, "state": fsm_ctx, "event_update": None}

    for handler_type, filters, _kwargs, handler in handlers:
        if handler_type != "callback_query":
            continue

        all_pass = True
        for flt in filters:
            if not await _check_filter(flt, callback, fsm_ctx):
                all_pass = False
                break

        if all_pass:
            extra = _resolve_extra_args(handler, fsm_ctx, web_bot)
            name = getattr(handler, "__name__", str(handler))
            logger.info("[web] callback -> %s", name)
            try:
                await _call_with_middleware(handler, callback, extra, middlewares, mw_data)
            except Exception:
                logger.exception("[web] handler %s failed", name)
                raise
            return

    logger.debug("[web] no matching callback handler")
