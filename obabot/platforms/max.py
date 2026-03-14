"""Max platform implementation using umaxbot with aiogram-compatible API."""

from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING
import asyncio
import logging

from obabot.config import get_update_context
from obabot.context import set_current_platform, reset_current_platform
from obabot.platforms.base import BasePlatform, HandlerType
from obabot.types import BPlatform

if TYPE_CHECKING:
    from maxbot.bot import Bot
    from maxbot.dispatcher import Dispatcher
    from maxbot.router import Router
    from maxbot.types import Message, Callback

logger = logging.getLogger(__name__)

# Observer types that support middleware for Max
MIDDLEWARE_OBSERVER_TYPES = ("message", "callback_query", "edited_message")


def _make_middleware_chain(
    handler: Callable,
    middlewares: List[Any],
) -> Callable:
    """
    Build middleware chain for handler.
    
    Middlewares follow aiogram pattern: async def __call__(self, handler, event, data).
    First registered middleware is outermost (called first).
    
    Args:
        handler: The actual handler function (event) -> result
        middlewares: List of middleware objects with __call__(handler, event, data)
    
    Returns:
        Wrapped handler: (event, data) -> result
    """
    if not middlewares:
        async def no_middleware_handler(event: Any, data: Dict[str, Any]) -> Any:
            return await handler(event)
        return no_middleware_handler
    
    # Final handler converts (event, data) -> handler(event)
    async def final_handler(event: Any, data: Dict[str, Any]) -> Any:
        return await handler(event)
    
    # Build chain from inside out
    chain = final_handler
    for mw in reversed(middlewares):
        outer_chain = chain
        # Capture mw and outer_chain in closure via default args
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
    """
    Call handler with middleware chain.
    
    Args:
        handler: The actual handler function
        event: Message/Callback event object
        data: Additional data dict (bot, state, etc.)
        middlewares: List of (middleware, is_outer) tuples
    
    Returns:
        Handler result
    """
    # Separate outer and inner middlewares
    outer_mws = [mw for mw, is_outer in middlewares if is_outer]
    inner_mws = [mw for mw, is_outer in middlewares if not is_outer]
    
    # Build inner chain first (handler + inner middlewares)
    inner_chain = _make_middleware_chain(handler, inner_mws)
    
    # Wrap inner chain as a handler for outer middlewares
    async def inner_as_handler(event: Any) -> Any:
        return await inner_chain(event, data)
    
    # Build outer chain
    outer_chain = _make_middleware_chain(inner_as_handler, outer_mws)
    
    return await outer_chain(event, data)


class MaxPlatform(BasePlatform):
    """
    Max platform using umaxbot library.
    
    umaxbot has aiogram-style API:
    - Bot, Dispatcher, Router classes
    - dp.include_router(router)
    - Filters: F.text == "hello", StateFilter, etc.
    - FSM with set_state, get_state, reset_state
    - InlineKeyboardMarkup, InlineKeyboardButton
    
    Since umaxbot is already aiogram-compatible, minimal adaptation is needed.
    """
    
    def __init__(self, token: str):
        self._token = token
        self._bot: Optional["Bot"] = None
        self._dispatcher: Optional["Dispatcher"] = None
        self._router: Optional["Router"] = None
        self._external_router: Optional[Any] = None
        self._running = False
        self._polling_task: Optional[asyncio.Task] = None
        self._handlers_setup = False
        # Middleware storage: {observer_type: [(middleware, is_outer), ...]}
        self._middlewares: Dict[str, List[Tuple[Any, bool]]] = {t: [] for t in MIDDLEWARE_OBSERVER_TYPES}
        
        self._init_umaxbot()
    
    def _init_umaxbot(self) -> None:
        """Initialize umaxbot components."""
        try:
            from maxbot.bot import Bot
            from maxbot.dispatcher import Dispatcher
            from maxbot.router import Router
            
            self._bot = Bot(self._token)
            self._dispatcher = Dispatcher(self._bot)
            self._router = Router()
            self._dispatcher.include_router(self._router)  # Include immediately (like TelegramPlatform)
            
            logger.info("umaxbot initialized successfully")
        except ImportError as e:
            logger.warning(f"umaxbot not installed: {e}. Max platform will not work. Install with: pip install umaxbot")
            self._bot = None
            self._dispatcher = None
            self._router = None
    
    @property
    def platform(self) -> BPlatform:
        return BPlatform.max
    
    @property
    def bot(self) -> Optional["Bot"]:
        return self._bot
    
    @property
    def dispatcher(self) -> Optional["Dispatcher"]:
        return self._dispatcher
    
    @property
    def router(self) -> Optional["Router"]:
        """Return the internal router for handler registration."""
        return self._router
    
    def convert_filters_for_platform(self, filters: tuple, handler_type: str = "message") -> tuple:
        """
        Convert aiogram filters to Max-compatible filters so handlers
        (e.g. CommandStart()) work without needing aiogram Bot in the filter.
        Called by ProxyRouter when registering handlers for this platform.
        """
        return self._convert_filters(filters)
    
    def set_external_router(self, router: Any) -> None:
        """Set external router (from ProxyRouter) to be included in dispatcher."""
        self._external_router = router
    
    def add_middleware(self, observer_type: str, middleware: Any, outer: bool = False) -> None:
        """Add middleware for a specific observer type (message, callback_query, edited_message)."""
        if observer_type not in self._middlewares:
            logger.warning("[Max] Unknown observer type for middleware: %s", observer_type)
            return
        self._middlewares[observer_type].append((middleware, outer))
        logger.debug("[Max] Added %s middleware: %s (outer=%s)", observer_type, type(middleware).__name__, outer)
    
    def get_middlewares(self, observer_type: str) -> List[Tuple[Any, bool]]:
        """Get list of (middleware, is_outer) for a given observer type."""
        return self._middlewares.get(observer_type, [])
    
    def wrap_handler(self, handler: HandlerType) -> HandlerType:
        """
        Wrap handler to add platform attribute to messages.
        
        umaxbot Message/Callback are Pydantic models and may not allow
        extra fields; use object.__setattr__ to bypass validation.
        """
        @wraps(handler)
        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            # Set platform context for bot.send_* auto-detection
            token = set_current_platform(BPlatform.max)
            try:
                def set_platform(obj: Any) -> None:
                    if obj is None:
                        return
                    try:
                        object.__setattr__(obj, 'platform', 'max')
                    except (AttributeError, TypeError, ValueError):
                        pass
                for arg in args:
                    set_platform(arg)
                for v in kwargs.values():
                    set_platform(v)
                return await handler(*args, **kwargs)
            finally:
                reset_current_platform(token)
        return wrapped
    
    def _setup_handlers(self) -> None:
        """Setup handlers with umaxbot dispatcher."""
        if self._handlers_setup:
            logger.debug("[Max] Handlers already setup, skip")
            return
        
        if not self._dispatcher or not self._router:
            logger.error("[Max] Cannot setup handlers: umaxbot not initialized")
            return
        
        # Router already included in _init_umaxbot, just setup external handlers
        if self._external_router:
            n_msg = len(getattr(self._external_router, '_message_handlers', []))
            n_cb = len(getattr(self._external_router, '_callback_handlers', []))
            logger.info("[Max] Registering external handlers: %s message, %s callback", n_msg, n_cb)
            self._register_external_handlers()
        
        try:
            n_msg = len(self._dispatcher.message_handlers) + sum(len(r.message_handlers) for r in self._dispatcher.routers)
            n_cb = len(self._dispatcher.callback_handlers) + sum(len(r.callback_handlers) for r in self._dispatcher.routers)
            logger.info("[Max] Handlers setup complete: %s message handlers, %s callback handlers total", n_msg, n_cb)
        except (TypeError, AttributeError):
            logger.info("[Max] Handlers setup complete")
        self._handlers_setup = True
    
    def _register_external_handlers(self) -> None:
        """Register handlers from external ProxyRouter."""
        if not self._external_router:
            return
        
        message_handlers = getattr(self._external_router, '_message_handlers', [])
        callback_handlers = getattr(self._external_router, '_callback_handlers', [])
        
        for filters, kwargs, handler in message_handlers:
            wrapped = self.wrap_handler(handler)
            self._register_message_handler(wrapped, filters, kwargs)
        
        for filters, kwargs, handler in callback_handlers:
            wrapped = self.wrap_handler(handler)
            self._register_callback_handler(wrapped, filters, kwargs)
    
    def _register_message_handler(
        self, 
        handler: HandlerType, 
        filters: tuple, 
        kwargs: dict
    ) -> None:
        """Register message handler with umaxbot router."""
        if not self._router:
            return
        name = getattr(handler, "__name__", str(handler))
        converted_filters = self._convert_filters(filters)
        self._router.message(*converted_filters)(handler)
        logger.info("[Max] Registered message handler: %s (filters: %s -> %s)", name, [type(f).__name__ for f in filters], len(converted_filters))
    
    def _register_callback_handler(
        self, 
        handler: HandlerType, 
        filters: tuple, 
        kwargs: dict
    ) -> None:
        """Register callback handler with umaxbot router."""
        if not self._router:
            return
        name = getattr(handler, "__name__", str(handler))
        converted_filters = self._convert_filters(filters)
        self._router.callback(*converted_filters)(handler)
        logger.info("[Max] Registered callback handler: %s", name)
    
    def _convert_filters(self, filters: tuple) -> tuple:
        """
        Convert aiogram filters to Max-compatible filters.
        
        Note: maxbot's TextStartsFilter checks update.payload (callbacks), not message.text.
        So for Command/CommandStart we use _create_command_filter (checks message.text).
        """
        from aiogram.filters import Command, CommandStart
        
        converted = []
        for f in filters:
            filter_name = type(f).__name__
            
            if filter_name == 'CommandStart':
                converted.append(self._create_command_filter(['start']))
            
            elif filter_name == 'Command':
                commands = getattr(f, 'commands', [])
                if commands:
                    converted.append(self._create_command_filter(list(commands)))
            
            elif filter_name == 'MagicFilter':
                converted.append(f)
            
            elif 'State' in filter_name:
                try:
                    from maxbot.filters import StateFilter
                    state = getattr(f, 'state', None)
                    if state:
                        converted.append(StateFilter(state))
                except ImportError:
                    converted.append(f)
            
            else:
                if callable(f):
                    converted.append(f)
        
        return tuple(converted)
    
    def _create_command_filter(self, commands: list) -> Callable:
        """Create command filter for umaxbot."""
        def command_filter(message: Any) -> bool:
            text = getattr(message, 'text', None)
            if not text:
                return False
            for cmd in commands:
                if text == f'/{cmd}' or text.startswith(f'/{cmd} '):
                    return True
            return False
        return command_filter
    
    async def start_polling(self) -> None:
        """Start polling using umaxbot dispatcher."""
        if not self._dispatcher:
            logger.error("umaxbot not initialized, cannot start polling")
            return
        
        self._setup_handlers()
        self._running = True
        
        try:
            await self._dispatcher.start_polling()
        except asyncio.CancelledError:
            logger.info("Max polling cancelled")
        except Exception as e:
            logger.error(f"Max polling error: {e}")
            raise
    
    async def stop_polling(self) -> None:
        """Stop polling."""
        self._running = False
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
    
    async def feed_update(self, update: Any, **kwargs: Any) -> Any:
        """Process a single update."""
        if not self._dispatcher:
            logger.error("umaxbot not initialized")
            return None
        
        self._setup_handlers()
        
        update_dict = update if isinstance(update, dict) else (getattr(update, '__dict__', None) or {})
        return await self._dispatch_raw_update(update_dict)
    
    async def feed_raw_update(self, update: dict, **kwargs: Any) -> Any:
        """Process a raw update dict (webhook payload).
        
        umaxbot Dispatcher has no feed_update; we replicate its _polling
        dispatch logic for a single update.
        """
        if not self._dispatcher:
            logger.error("[max:?] feed_raw_update: umaxbot not initialized")
            return None
        
        # Support nested body (e.g. Yandex Cloud: event has body with the actual payload)
        if isinstance(update, dict) and "body" in update and isinstance(update.get("body"), dict):
            update = update["body"]
        
        ctx = get_update_context(update, "max")
        update_type = update.get("update_type") or update.get("type")
        keys = list(update.keys()) if isinstance(update, dict) else []
        logger.info("%s feed_raw_update: keys=%s update_type=%s", ctx, keys, update_type)
        
        self._setup_handlers()
        result = await self._dispatch_raw_update(update)
        logger.info("%s feed_raw_update: dispatch done", ctx)
        return result
    
    async def _filter_check(self, flt: Any, data: Any) -> bool:
        """
        Return True if filter passes. Supports:
        - aiogram MagicFilter (F.photo, F.text, F.data, etc.) via resolve()
        - aiogram Command/CommandStart filters
        - umaxbot filters with .check(data)
        - callable filters (message) -> bool
        Always returns bool (never a filter object).
        """
        if flt is None:
            return True
        
        flt_name = type(flt).__name__
        
        # Handle aiogram MagicFilter (F.photo, F.text, F.data, etc.)
        if flt_name == 'MagicFilter' or hasattr(flt, '_resolve_operation_'):
            try:
                # MagicFilter uses resolve() to check the value
                if hasattr(flt, 'resolve'):
                    result = flt.resolve(data)
                    # resolve() returns the value if it exists, or raises
                    # For boolean comparisons (F.data == "value"), result is True/False
                    # For attribute access (F.photo), result is the value or raises
                    if isinstance(result, bool):
                        return result
                    return result is not None
            except (AttributeError, LookupError, TypeError, KeyError, ValueError):
                # Filter didn't match (attribute doesn't exist or comparison failed)
                return False
            except Exception as e:
                logger.debug("[Max] MagicFilter resolve failed: %s", e)
                return False
        
        # Handle aiogram Command/CommandStart filters
        if flt_name in ('Command', 'CommandStart', 'CommandObject'):
            text = getattr(data, 'text', '') or ''
            if not text.startswith('/'):
                return False
            # Extract command from text
            parts = text.split()
            command_part = parts[0][1:] if parts else ''  # Remove '/'
            # Handle command@botname format
            if '@' in command_part:
                command_part = command_part.split('@')[0]
            # CommandStart matches /start
            if flt_name == 'CommandStart':
                return command_part == 'start'
            # Command matches specified commands
            if hasattr(flt, 'commands'):
                commands = flt.commands
                if isinstance(commands, (list, tuple, set, frozenset)):
                    return command_part in commands
                return command_part == commands
            return False
        
        # Handle umaxbot filters with .check() method
        if hasattr(flt, 'check') and callable(getattr(flt, 'check')):
            data_for_check = getattr(data, '_msg', data)
            result = flt.check(data_for_check)
            if asyncio.iscoroutine(result):
                result = await result
            return bool(result)
        
        # Handle callable filters
        if not callable(flt):
            return False
        
        try:
            # Try calling with (data, bot) first (aiogram style)
            result = flt(data, self._bot) if self._bot else flt(data)
        except TypeError:
            try:
                result = flt(data)
            except Exception as e:
                logger.debug("[Max] filter %s call failed: %s", flt_name, e)
                return False
        
        try:
            if asyncio.iscoroutine(result):
                result = await result
            return bool(result)
        except Exception as e:
            logger.debug("[Max] filter %s result check failed: %s", flt_name, e)
            return False
    
    async def _dispatch_raw_update(self, update: dict) -> Any:
        """
        Dispatch a single raw update to umaxbot handlers.
        
        Passes extended types to handlers so message.from_user / callback.from_user
        work (umaxbot uses .sender / .user). Uses MaxCallbackQuery for inheritance-based
        compatibility (isinstance(cb, Callback) = True).
        """
        from maxbot.types import Message, Callback
        from maxbot.dispatcher import set_current_dispatcher
        from obabot.adapters.message import MaxMessageAdapter
        from obabot.adapters.max_callback import MaxCallbackQuery
        
        set_current_dispatcher(self._dispatcher)
        ctx = get_update_context(update, "max")
        update_type = update.get("update_type") or update.get("type")
        # Infer message_created if we have "message" but no update_type (some gateways)
        if not update_type and update.get("message"):
            update_type = "message_created"
        
        n_disp = len(getattr(self._dispatcher, "message_handlers", []))
        n_routers = len(getattr(self._dispatcher, "routers", []))
        n_router_handlers = sum(len(getattr(r, "message_handlers", [])) for r in getattr(self._dispatcher, "routers", []))
        logger.info("%s dispatch: update_type=%s handlers=%s/%s", ctx, update_type, n_disp, n_router_handlers)
        
        try:
            if update_type == "message_created":
                raw_message = update.get("message")
                if not raw_message:
                    logger.warning("%s message_created but no 'message' key", ctx)
                    return None
                msg = Message.from_raw(raw_message)
                msg_adapter = MaxMessageAdapter(msg, self._bot)
                msg_text = getattr(msg, "text", "") or ""
                chat_id = getattr(getattr(msg, 'chat', None), 'id', None) or getattr(getattr(msg, 'sender', None), 'id', None)
                logger.info("%s message: chat=%s text=%r", ctx, chat_id, msg_text[:80])
                
                # Prepare middleware data dict (aiogram-style)
                mw_data: Dict[str, Any] = {"bot": self._bot, "event_update": update}
                msg_middlewares = self._middlewares.get("message", [])
                
                # Check dispatcher handlers first, stop after first match (like aiogram)
                handled = False
                for i, h_item in enumerate(getattr(self._dispatcher, "message_handlers", [])):
                    try:
                        func, flt = (h_item[0], h_item[1]) if len(h_item) >= 2 else (h_item, None)
                    except (TypeError, ValueError, IndexError):
                        logger.debug("%s handler[%s] unexpected format", ctx, i)
                        continue
                    passed = await self._filter_check(flt, msg_adapter)
                    name = getattr(func, '__name__', str(func))
                    logger.debug("%s handler %s filter=%s", ctx, name, passed)
                    if passed:
                        logger.info("%s -> %s", ctx, name)
                        try:
                            await _call_with_middlewares(func, msg_adapter, mw_data, msg_middlewares)
                            logger.debug("%s handler %s done", ctx, name)
                            handled = True
                            break  # Stop after first matching handler
                        except Exception:
                            logger.exception("%s handler %s failed", ctx, name)
                            raise
                
                # Check router handlers if not yet handled
                if not handled:
                    for ri, router in enumerate(getattr(self._dispatcher, "routers", [])):
                        if handled:
                            break
                        handlers = getattr(router, "message_handlers", [])
                        for i, h_item in enumerate(handlers):
                            try:
                                func, flt = (h_item[0], h_item[1]) if len(h_item) >= 2 else (h_item, None)
                            except (TypeError, ValueError, IndexError):
                                logger.debug("%s router[%s] handler[%s] unexpected format", ctx, ri, i)
                                continue
                            passed = await self._filter_check(flt, msg_adapter)
                            name = getattr(func, '__name__', str(func))
                            logger.debug("%s router handler %s filter=%s", ctx, name, passed)
                            if passed:
                                logger.info("%s -> %s", ctx, name)
                                try:
                                    await _call_with_middlewares(func, msg_adapter, mw_data, msg_middlewares)
                                    logger.debug("%s handler %s done", ctx, name)
                                    handled = True
                                    break  # Stop after first matching handler
                                except Exception:
                                    logger.exception("%s handler %s failed", ctx, name)
                                    raise
                
                logger.debug("%s message_created done, handled=%s", ctx, handled)
                return None
            
            elif update_type == "message_callback":
                raw_callback = update.get("callback")
                raw_message = update.get("message")
                if not raw_callback or not raw_message:
                    logger.warning("%s callback missing 'callback' or 'message'", ctx)
                    return None
                msg = Message.from_raw(raw_message)
                cb = Callback(**raw_callback, message=msg)
                # Use MaxCallbackQuery (inheritance) instead of adapter for isinstance() compatibility
                cb_extended = MaxCallbackQuery.from_callback(cb, self._bot)
                payload = raw_callback.get("payload", "?")
                logger.info("%s callback: payload=%s", ctx, payload)
                
                # Prepare middleware data dict
                cb_mw_data: Dict[str, Any] = {"bot": self._bot, "event_update": update}
                cb_middlewares = self._middlewares.get("callback_query", [])
                
                # Check dispatcher callback handlers, stop after first match
                handled = False
                for func, flt in self._dispatcher.callback_handlers:
                    if await self._filter_check(flt, cb_extended):
                        name = getattr(func, '__name__', str(func))
                        logger.info("%s -> %s", ctx, name)
                        await _call_with_middlewares(func, cb_extended, cb_mw_data, cb_middlewares)
                        logger.debug("%s handler %s done", ctx, name)
                        handled = True
                        break  # Stop after first matching handler
                
                # Check router callback handlers if not yet handled
                if not handled:
                    for router in self._dispatcher.routers:
                        if handled:
                            break
                        for func, flt in router.callback_handlers:
                            if await self._filter_check(flt, cb_extended):
                                name = getattr(func, '__name__', str(func))
                                logger.info("%s -> %s", ctx, name)
                                await _call_with_middlewares(func, cb_extended, cb_mw_data, cb_middlewares)
                                logger.debug("%s handler %s done", ctx, name)
                                handled = True
                                break  # Stop after first matching handler
                
                logger.debug("%s callback done, handled=%s", ctx, handled)
                return None
            
            elif update_type == "bot_started":
                logger.info("%s bot_started", ctx)
                for func in self._dispatcher.bot_started_handlers:
                    await func(update)
                for router in self._dispatcher.routers:
                    for func in getattr(router, 'bot_started_handlers', []):
                        await func(update)
                return None
            
            else:
                logger.debug("%s unhandled update_type: %s", ctx, update_type)
                return None
        except Exception as e:
            logger.exception("%s error: %s", ctx, e)
            raise
