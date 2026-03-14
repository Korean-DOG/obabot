"""Proxy router that registers handlers across multiple platforms."""

import inspect
import logging
from functools import partial, wraps
from typing import Any, Callable, Dict, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from obabot.platforms.base import BasePlatform

logger = logging.getLogger(__name__)

# Observer types that support middleware
MIDDLEWARE_OBSERVER_TYPES = ("message", "callback_query", "edited_message")


def _get_handler_name(handler: Callable) -> str:
    """Extract meaningful handler name, unwrapping decorators if needed."""
    # Try direct __name__
    name = getattr(handler, "__name__", None)
    
    # If it's a wrapper, try to find the original function
    if name in ("wrapper", "wrapped", "inner", "decorator", None) or "<locals>" in str(name or ""):
        # Try __wrapped__ (set by functools.wraps)
        wrapped = getattr(handler, "__wrapped__", None)
        if wrapped:
            return _get_handler_name(wrapped)
        
        # Try __func__ (for bound methods)
        func = getattr(handler, "__func__", None)
        if func:
            return _get_handler_name(func)
        
        # Try func attribute (some decorators use this)
        func = getattr(handler, "func", None)
        if func:
            return _get_handler_name(func)
        
        # Try to get from closure
        if hasattr(handler, "__closure__") and handler.__closure__:
            for cell in handler.__closure__:
                try:
                    cell_contents = cell.cell_contents
                    if callable(cell_contents) and cell_contents is not handler:
                        inner_name = getattr(cell_contents, "__name__", None)
                        if inner_name and inner_name not in ("wrapper", "wrapped", "inner", "decorator"):
                            if "<locals>" not in str(inner_name):
                                return inner_name
                except (ValueError, AttributeError):
                    continue
        
        # Fallback: try qualname
        qualname = getattr(handler, "__qualname__", None)
        if qualname and ".<locals>." in qualname:
            # Extract function name from qualname like "with_context.<locals>.wrapper"
            parts = qualname.split(".<locals>.")
            if len(parts) > 1:
                # Return the outer function name
                return parts[0]
        
        # Last resort
        return name or "handler"
    
    return name or "handler"


def _wrap_error_handler(handler: Callable) -> Callable:
    """Wrap error handler to adapt aiogram 3.x ErrorEvent to (event, exc) signature.
    
    Aiogram 3.x error handlers receive ErrorEvent with .exception attribute,
    but user handlers may expect (event, exc) signature.
    """
    @wraps(handler)
    async def wrapper(error_event: Any, *args: Any, **kwargs: Any) -> Any:
        # Extract exception from ErrorEvent
        exc = getattr(error_event, 'exception', None)
        if exc is None and args:
            exc = args[0]
        
        # Get original event/update
        event = getattr(error_event, 'update', error_event)
        
        # Determine handler signature and call appropriately
        try:
            sig = inspect.signature(handler)
            params = list(sig.parameters.keys())
            num_params = len(params)
        except (ValueError, TypeError):
            num_params = 2  # Default assumption
        
        if num_params >= 2:
            return await handler(event, exc)
        elif num_params == 1:
            return await handler(error_event)
        else:
            return await handler()
    
    return wrapper


def _format_filter(flt: Any) -> str:
    """Format a filter for readable logging."""
    flt_name = type(flt).__name__
    
    # CommandStart / Command - show commands
    if flt_name == "CommandStart":
        return "CommandStart()"
    if flt_name == "Command":
        commands = getattr(flt, "commands", None)
        if commands:
            cmds = ", ".join(f'"{c}"' for c in commands)
            return f"Command({cmds})"
        return "Command()"
    
    # MagicFilter - build full representation from operations
    if flt_name == "MagicFilter":
        try:
            ops = getattr(flt, '_operations', ())
            if not ops:
                return "MagicFilter"
            
            parts = ["F"]
            for op in ops:
                op_name = type(op).__name__
                
                if 'GetAttribute' in op_name:
                    attr = getattr(op, 'name', None)
                    if attr:
                        parts.append(f".{attr}")
                        
                elif 'Call' in op_name:
                    args = getattr(op, 'args', ())
                    if args:
                        arg_str = ", ".join(repr(a) for a in args)
                        parts.append(f"({arg_str})")
                    else:
                        parts.append("()")
                        
                elif 'Function' in op_name:
                    # in_(), contains(), etc.
                    args = getattr(op, 'args', ())
                    if args:
                        arg_str = ", ".join(repr(a) for a in args)
                        parts.append(f".in_({arg_str})")
                    else:
                        parts.append(".in_()")
                        
                elif 'Comparator' in op_name:
                    right = getattr(op, 'right', None)
                    if right is not None:
                        parts.append(f" == {repr(right)}")
                    else:
                        parts.append(" == ...")
                        
                elif 'Combination' in op_name:
                    # Complex filter - just note it
                    parts.append(" & ...")
                    break
                    
                elif 'Invert' in op_name:
                    parts.insert(0, "~")
            
            result = "".join(parts)
            if len(result) > 50:
                return result[:47] + "..."
            return result
        except Exception:
            return "MagicFilter"
    
    # StateFilter - show state
    if "State" in flt_name:
        state = getattr(flt, "state", None)
        if state:
            return f"State({state})"
        return flt_name
    
    # Default - just class name
    return flt_name


class _ObserverProxy:
    """Proxy for router.message / router.callback_query / router.edited_message with aiogram-style middleware() support."""

    def __init__(self, router: "ProxyRouter", observer_type: str):
        self._router = router
        self._type = observer_type

    def __call__(self, *filters: Any, **kwargs: Any) -> Callable:
        return self._router._register_handler(self._type, *filters, **kwargs)

    def middleware(self, middleware: Any) -> Any:
        """Register middleware (aiogram-style: router.message.middleware(Middleware()))."""
        return self._router._register_middleware(self._type, middleware)

    def outer_middleware(self, middleware: Any) -> Any:
        """Register outer middleware (runs before filters)."""
        return self._router._register_middleware(self._type, middleware, outer=True)


def _format_filters(filters: tuple) -> str:
    """Format multiple filters for logging."""
    if not filters:
        return "none"
    return ", ".join(_format_filter(f) for f in filters)


class ProxyRouter:
    """
    Router proxy that registers handlers across all platforms.
    
    Provides the same decorator API as aiogram.Router,
    but internally registers handlers to all configured platforms.
    
    Usage:
        @router.message(Command("start"))
        async def start(message):
            await message.answer("Hello!")
    
    This single decorator will register the handler for both
    Telegram and Max if both are configured.
    """
    
    def __init__(self, platforms: List["BasePlatform"]):
        """
        Initialize proxy router.
        
        Args:
            platforms: List of platform instances to register handlers to
        """
        self._platforms = platforms
        self._pending_handlers: List[Tuple[str, tuple, dict, Callable]] = []
        # Middleware storage: {observer_type: [(middleware, is_outer), ...]}
        self._middlewares: Dict[str, List[Tuple[Any, bool]]] = {t: [] for t in MIDDLEWARE_OBSERVER_TYPES}
        self._applied_to_platforms: set = set()
        # Observer proxies for aiogram-style router.message(...) / router.message.middleware(...)
        self.message = _ObserverProxy(self, "message")
        self.callback_query = _ObserverProxy(self, "callback_query")
        self.edited_message = _ObserverProxy(self, "edited_message")
    
    def _use_lazy_registration(self) -> bool:
        """True if all platforms are lazy (defer registration until first use)."""
        return all(getattr(p, "_ensure_inited", None) is not None for p in self._platforms)
    
    def _add_pending(self, handler_type: str, filters: tuple, kwargs: dict, handler: Callable) -> None:
        self._pending_handlers.append((handler_type, filters, kwargs, handler))
    
    def apply_pending_handlers(self, platform: "BasePlatform") -> None:
        """Apply all pending handlers to a real platform (called when platform is first inited)."""
        # Prevent duplicate registration
        platform_id = id(platform)
        if platform_id in self._applied_to_platforms:
            logger.debug("[Router] Handlers already applied to %s, skipping", platform.platform)
            return
        
        platform_name = str(platform.platform)
        
        for handler_type, filters, kwargs, handler in self._pending_handlers:
            # Get original function name
            name = _get_handler_name(handler)
            
            wrapped = platform.wrap_handler(handler)
            use_filters = filters
            if hasattr(platform, "convert_filters_for_platform"):
                conv = "message" if handler_type in ("message", "edited_message") else "callback"
                use_filters = platform.convert_filters_for_platform(filters, conv)
            
            filters_str = _format_filters(filters)
            
            if handler_type == "message":
                platform.router.message(*use_filters, **kwargs)(wrapped)
                logger.info("[%s] @message(%s) -> %s", platform_name, filters_str, name)
            elif handler_type == "callback_query":
                register = getattr(platform.router, "callback_query", None) or getattr(platform.router, "callback", None)
                if register:
                    register(*use_filters, **kwargs)(wrapped)
                    logger.info("[%s] @callback_query(%s) -> %s", platform_name, filters_str, name)
            elif handler_type == "edited_message":
                if hasattr(platform.router, "edited_message"):
                    platform.router.edited_message(*use_filters, **kwargs)(wrapped)
                else:
                    platform.router.message(*use_filters, **kwargs)(wrapped)
                logger.info("[%s] @edited_message(%s) -> %s", platform_name, filters_str, name)
            elif handler_type == "channel_post" and hasattr(platform.router, "channel_post"):
                platform.router.channel_post(*use_filters, **kwargs)(wrapped)
                logger.info("[%s] @channel_post(%s) -> %s", platform_name, filters_str, name)
            elif handler_type == "inline_query" and hasattr(platform.router, "inline_query"):
                platform.router.inline_query(*use_filters, **kwargs)(wrapped)
                logger.info("[%s] @inline_query(%s) -> %s", platform_name, filters_str, name)
            elif handler_type == "error":
                # Error handlers need special wrapping for aiogram 3.x
                # aiogram passes ErrorEvent with .exception attribute
                error_wrapped = _wrap_error_handler(handler)
                if hasattr(platform.router, "error"):
                    platform.router.error(*filters, **kwargs)(error_wrapped)
                elif hasattr(platform.router, "errors"):
                    platform.router.errors(*filters, **kwargs)(error_wrapped)
                logger.info("[%s] @error(%s) -> %s", platform_name, filters_str, name)
        
        for obs_type, mw_list in self._middlewares.items():
            for mw, outer in mw_list:
                self._apply_middleware_to_platform(platform, obs_type, mw, outer)
        self._applied_to_platforms.add(platform_id)
        logger.info("[%s] Applied %d handlers", platform_name, len(self._pending_handlers))

    def _apply_middleware_to_platform(self, platform: "BasePlatform", observer_type: str, middleware: Any, outer: bool = False) -> None:
        """Register middleware on a single platform's router (Telegram) or store for Max."""
        from obabot.types import BPlatform
        
        # For Max platform, store in platform's middleware list (applied in dispatch)
        if getattr(platform, "platform", None) == BPlatform.max:
            if hasattr(platform, "add_middleware"):
                platform.add_middleware(observer_type, middleware, outer=outer)
                logger.debug("[%s] %s middleware %s stored", platform.platform, observer_type, type(middleware).__name__)
            return
        
        # For Telegram/other platforms, use native router middleware
        r = getattr(platform, "router", None)
        if r is None:
            return
        obs = getattr(r, observer_type, None)
        if obs is None and observer_type == "callback_query":
            obs = getattr(r, "callback", None)
        if obs is not None:
            if outer and hasattr(obs, "outer_middleware"):
                obs.outer_middleware(middleware)
            elif hasattr(obs, "middleware"):
                obs.middleware(middleware)
            logger.debug("[%s] %s.middleware(%s) applied", platform.platform, observer_type, type(middleware).__name__)

    def _register_middleware(self, observer_type: str, middleware: Any, outer: bool = False) -> Any:
        """Register middleware for observer type on all platforms."""
        self._middlewares[observer_type].append((middleware, outer))
        if not self._use_lazy_registration():
            for platform in self._platforms:
                self._apply_middleware_to_platform(platform, observer_type, middleware, outer)
        return middleware

    def get_middlewares(self, observer_type: str) -> List[Tuple[Any, bool]]:
        """Get list of (middleware, is_outer) for a given observer type."""
        return self._middlewares.get(observer_type, [])

    def _register_handler(self, handler_type: str, *filters: Any, **kwargs: Any) -> Callable:
        """Universal handler registration for any observer type."""
        def decorator(handler: Callable) -> Callable:
            name = _get_handler_name(handler)
            filters_str = _format_filters(filters)
            logger.info("[Router] @%s(%s) -> %s", handler_type, filters_str, name)
            
            if self._use_lazy_registration():
                self._add_pending(handler_type, filters, kwargs, handler)
                return handler
            
            for platform in self._platforms:
                wrapped = platform.wrap_handler(handler)
                conv_type = "message" if handler_type in ("message", "edited_message") else "callback"
                use_filters = platform.convert_filters_for_platform(filters, conv_type) if hasattr(platform, 'convert_filters_for_platform') else filters
                
                # Find registration method
                if handler_type == "callback_query":
                    register = getattr(platform.router, 'callback_query', None) or getattr(platform.router, 'callback', None)
                else:
                    register = getattr(platform.router, handler_type, None)
                
                if register:
                    register(*use_filters, **kwargs)(wrapped)
            return handler
        return decorator

    def _register_message(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register a message handler across all platforms."""
        return self._register_handler("message", *filters, **kwargs)

    def _register_callback_query(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register a callback query handler across all platforms."""
        return self._register_handler("callback_query", *filters, **kwargs)

    def _register_edited_message(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register edited message handler across all platforms."""
        return self._register_handler("edited_message", *filters, **kwargs)
    
    def channel_post(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register channel post handler (Telegram-specific, ignored on Max)."""
        def decorator(handler: Callable) -> Callable:
            name = _get_handler_name(handler)
            filters_str = _format_filters(filters)
            logger.info("[Router] @channel_post(%s) -> %s", filters_str, name)
            
            if self._use_lazy_registration():
                self._add_pending("channel_post", filters, kwargs, handler)
                return handler
            for platform in self._platforms:
                if hasattr(platform.router, 'channel_post'):
                    wrapped = platform.wrap_handler(handler)
                    platform.router.channel_post(*filters, **kwargs)(wrapped)
            return handler
        return decorator
    
    def inline_query(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register inline query handler (Telegram-specific)."""
        def decorator(handler: Callable) -> Callable:
            name = _get_handler_name(handler)
            filters_str = _format_filters(filters)
            logger.info("[Router] @inline_query(%s) -> %s", filters_str, name)
            
            if self._use_lazy_registration():
                self._add_pending("inline_query", filters, kwargs, handler)
                return handler
            for platform in self._platforms:
                if hasattr(platform.router, 'inline_query'):
                    wrapped = platform.wrap_handler(handler)
                    platform.router.inline_query(*filters, **kwargs)(wrapped)
            return handler
        return decorator
    
    def chosen_inline_result(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register chosen inline result handler (Telegram-specific)."""
        def decorator(handler: Callable) -> Callable:
            for platform in self._platforms:
                if hasattr(platform.router, 'chosen_inline_result'):
                    wrapped = platform.wrap_handler(handler)
                    platform.router.chosen_inline_result(*filters, **kwargs)(wrapped)
            return handler
        return decorator
    
    def shipping_query(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register shipping query handler (Telegram-specific)."""
        def decorator(handler: Callable) -> Callable:
            for platform in self._platforms:
                if hasattr(platform.router, 'shipping_query'):
                    wrapped = platform.wrap_handler(handler)
                    platform.router.shipping_query(*filters, **kwargs)(wrapped)
            return handler
        return decorator
    
    def pre_checkout_query(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register pre-checkout query handler (Telegram-specific)."""
        def decorator(handler: Callable) -> Callable:
            for platform in self._platforms:
                if hasattr(platform.router, 'pre_checkout_query'):
                    wrapped = platform.wrap_handler(handler)
                    platform.router.pre_checkout_query(*filters, **kwargs)(wrapped)
            return handler
        return decorator
    
    def my_chat_member(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register my_chat_member handler."""
        def decorator(handler: Callable) -> Callable:
            for platform in self._platforms:
                if hasattr(platform.router, 'my_chat_member'):
                    wrapped = platform.wrap_handler(handler)
                    platform.router.my_chat_member(*filters, **kwargs)(wrapped)
            return handler
        return decorator
    
    def chat_member(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register chat_member handler."""
        def decorator(handler: Callable) -> Callable:
            for platform in self._platforms:
                if hasattr(platform.router, 'chat_member'):
                    wrapped = platform.wrap_handler(handler)
                    platform.router.chat_member(*filters, **kwargs)(wrapped)
            return handler
        return decorator
    
    def error(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register error handler."""
        def decorator(handler: Callable) -> Callable:
            name = _get_handler_name(handler)
            filters_str = _format_filters(filters)
            logger.info("[Router] @error(%s) -> %s", filters_str, name)
            
            if self._use_lazy_registration():
                self._add_pending("error", filters, kwargs, handler)
                return handler
            
            # Wrap error handler to adapt aiogram 3.x ErrorEvent signature
            error_wrapped = _wrap_error_handler(handler)
            for platform in self._platforms:
                if hasattr(platform.router, 'error'):
                    platform.router.error(*filters, **kwargs)(error_wrapped)
                elif hasattr(platform.router, 'errors'):
                    platform.router.errors(*filters, **kwargs)(error_wrapped)
            return handler
        return decorator
    
    def poll(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register poll handler (Telegram-specific)."""
        def decorator(handler: Callable) -> Callable:
            for platform in self._platforms:
                if hasattr(platform.router, 'poll'):
                    wrapped = platform.wrap_handler(handler)
                    platform.router.poll(*filters, **kwargs)(wrapped)
            return handler
        return decorator
    
    def poll_answer(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register poll answer handler (Telegram-specific)."""
        def decorator(handler: Callable) -> Callable:
            for platform in self._platforms:
                if hasattr(platform.router, 'poll_answer'):
                    wrapped = platform.wrap_handler(handler)
                    platform.router.poll_answer(*filters, **kwargs)(wrapped)
            return handler
        return decorator
    
    def chat_join_request(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register chat join request handler."""
        def decorator(handler: Callable) -> Callable:
            for platform in self._platforms:
                if hasattr(platform.router, 'chat_join_request'):
                    wrapped = platform.wrap_handler(handler)
                    platform.router.chat_join_request(*filters, **kwargs)(wrapped)
            return handler
        return decorator
    
    def edited_channel_post(self, *filters: Any, **kwargs: Any) -> Callable:
        """Register edited channel post handler (Telegram-specific)."""
        def decorator(handler: Callable) -> Callable:
            for platform in self._platforms:
                if hasattr(platform.router, 'edited_channel_post'):
                    wrapped = platform.wrap_handler(handler)
                    platform.router.edited_channel_post(*filters, **kwargs)(wrapped)
            return handler
        return decorator

