"""
FSM Coverage Logging Middleware for obabot.

This middleware logs FSM state transitions to CSV files for use with fsm-voyager.

Activated by environment variables:
- COVERAGE_LOG: Path to a single log file (appends to it)
- COVERAGE_LOG_DIR: Directory for log files (creates coverage-<timestamp>.log)
- COVERAGE_EXTENDED: If "1", use extended format with depth tracking

If neither COVERAGE_LOG nor COVERAGE_LOG_DIR is set, the middleware does nothing.

Simple CSV format:
    from_state,to_state,action
    start,waiting_name,callback:register

Extended CSV format (COVERAGE_EXTENDED=1):
    timestamp,user_id,session_id,from_state,to_state,trigger_type,trigger_data,depth,is_back
    2024-01-01T12:00:00,123,sess_abc,start,catalog,callback,catalog,1,false
"""

from __future__ import annotations

import csv
import logging
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from aiogram.types import Message, CallbackQuery

logger = logging.getLogger(__name__)

_coverage_lock = threading.Lock()
_coverage_file: Optional[Path] = None
_logged_transitions: Set[Tuple[str, str, str]] = set()
_session_start: Optional[str] = None
_user_sessions: Dict[str, str] = {}
_user_depths: Dict[str, int] = {}


def is_coverage_enabled() -> bool:
    """Check if FSM coverage logging is enabled via environment variables."""
    return bool(os.environ.get("COVERAGE_LOG") or os.environ.get("COVERAGE_LOG_DIR"))


def is_extended_format() -> bool:
    """Check if extended format is enabled."""
    return os.environ.get("COVERAGE_EXTENDED", "").lower() in ("1", "true", "yes")


def get_or_create_session(user_id: str) -> str:
    """Get or create a session ID for a user."""
    global _user_sessions
    if user_id not in _user_sessions:
        _user_sessions[user_id] = f"sess_{uuid.uuid4().hex[:8]}"
    return _user_sessions[user_id]


def get_user_depth(user_id: str) -> int:
    """Get current navigation depth for a user."""
    return _user_depths.get(user_id, 0)


def set_user_depth(user_id: str, depth: int) -> None:
    """Set navigation depth for a user."""
    _user_depths[user_id] = max(0, depth)


def get_coverage_log_path() -> Optional[Path]:
    """Get the path for the coverage log file based on environment variables."""
    global _coverage_file, _session_start
    
    if _coverage_file is not None:
        return _coverage_file
    
    coverage_log = os.environ.get("COVERAGE_LOG")
    coverage_log_dir = os.environ.get("COVERAGE_LOG_DIR")
    
    if coverage_log:
        _coverage_file = Path(coverage_log)
        _coverage_file.parent.mkdir(parents=True, exist_ok=True)
        return _coverage_file
    
    if coverage_log_dir:
        log_dir = Path(coverage_log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        if _session_start is None:
            _session_start = datetime.now().strftime("%Y%m%d-%H%M%S")
        
        _coverage_file = log_dir / f"coverage-{_session_start}.log"
        return _coverage_file
    
    return None


def get_coverage_logger() -> Optional["CoverageLogger"]:
    """Get a CoverageLogger instance if coverage is enabled."""
    path = get_coverage_log_path()
    if path is None:
        return None
    return CoverageLogger(path, extended=is_extended_format())


def reset_coverage_state() -> None:
    """Reset coverage state (for testing purposes)."""
    global _coverage_file, _logged_transitions, _session_start, _user_sessions, _user_depths
    with _coverage_lock:
        _coverage_file = None
        _logged_transitions.clear()
        _session_start = None
        _user_sessions.clear()
        _user_depths.clear()


class CoverageLogger:
    """Handles writing coverage data to CSV files."""
    
    SIMPLE_HEADER = ["from_state", "to_state", "action"]
    EXTENDED_HEADER = [
        "timestamp", "user_id", "session_id", "from_state", "to_state",
        "trigger_type", "trigger_data", "depth", "is_back"
    ]
    
    def __init__(self, path: Path, extended: bool = False):
        self.path = path
        self.extended = extended
        self._initialized = False
    
    def _ensure_header(self) -> None:
        """Write CSV header if file doesn't exist or is empty."""
        if self._initialized:
            return
        
        with _coverage_lock:
            if self._initialized:
                return
            
            write_header = not self.path.exists() or self.path.stat().st_size == 0
            
            if write_header:
                with open(self.path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    header = self.EXTENDED_HEADER if self.extended else self.SIMPLE_HEADER
                    writer.writerow(header)
            
            self._initialized = True
    
    def log_transition(
        self,
        from_state: Optional[str],
        to_state: Optional[str],
        action: str,
    ) -> None:
        """Log a state transition to the CSV file (simple format)."""
        if from_state is None and to_state is None:
            return
        
        from_str = from_state or ""
        to_str = to_state or ""
        
        transition = (from_str, to_str, action)
        
        with _coverage_lock:
            if transition in _logged_transitions:
                return
            _logged_transitions.add(transition)
        
        self._ensure_header()
        
        with _coverage_lock:
            with open(self.path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([from_str, to_str, action])
        
        logger.debug("FSM transition logged: %s -> %s (%s)", from_str, to_str, action)
    
    def log_transition_extended(
        self,
        from_state: Optional[str],
        to_state: Optional[str],
        trigger_type: str,
        trigger_data: str,
        user_id: str,
        session_id: str,
        depth: int,
        is_back: bool,
    ) -> None:
        """Log a state transition with extended information."""
        if from_state is None and to_state is None:
            return
        
        from_str = from_state or ""
        to_str = to_state or ""
        
        self._ensure_header()
        
        timestamp = datetime.now().isoformat()
        
        with _coverage_lock:
            with open(self.path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    timestamp,
                    user_id,
                    session_id,
                    from_str,
                    to_str,
                    trigger_type,
                    trigger_data,
                    depth,
                    str(is_back).lower(),
                ])
        
        logger.debug(
            "FSM transition logged (extended): %s -> %s (%s:%s) depth=%d back=%s",
            from_str, to_str, trigger_type, trigger_data, depth, is_back
        )


def extract_action_from_event(event: Any) -> str:
    """
    Extract action string from an event (Message or CallbackQuery).
    
    Returns:
        Action in format: callback:<data>, command:<cmd>, or text:*
    """
    from aiogram.types import Message, CallbackQuery
    
    if isinstance(event, CallbackQuery):
        data = event.data or ""
        return f"callback:{data}"
    
    if isinstance(event, Message):
        text = event.text or ""
        
        if text.startswith("/"):
            parts = text.split(maxsplit=1)
            cmd = parts[0]
            return f"command:{cmd}"
        
        return "text:*"
    
    return "unknown:*"


def extract_trigger_parts(event: Any) -> Tuple[str, str]:
    """
    Extract trigger type and data separately from an event.
    
    Returns:
        Tuple of (trigger_type, trigger_data)
    """
    from aiogram.types import Message, CallbackQuery
    
    if isinstance(event, CallbackQuery):
        return ("callback", event.data or "")
    
    if isinstance(event, Message):
        text = event.text or ""
        if text.startswith("/"):
            parts = text.split(maxsplit=1)
            return ("command", parts[0])
        return ("text", "*")
    
    return ("unknown", "*")


def extract_user_id(event: Any) -> str:
    """Extract user ID from an event."""
    from aiogram.types import Message, CallbackQuery
    
    if isinstance(event, CallbackQuery):
        if event.from_user:
            return str(event.from_user.id)
    
    if isinstance(event, Message):
        if event.from_user:
            return str(event.from_user.id)
    
    return ""


def is_back_navigation(callback_data: str) -> bool:
    """Check if callback data indicates back navigation."""
    back_patterns = ["nav:back", ":back:", "back:", "nav:main", "nv:main"]
    return any(p in callback_data for p in back_patterns)


def calculate_depth(current_depth: int, callback_data: str) -> int:
    """Calculate new navigation depth based on callback data."""
    main_menu_patterns = ["nav:main", "nv:main", "employee:menu"]
    if callback_data in main_menu_patterns:
        return 0
    
    back_patterns = ["nav:back", ":back:", "back:"]
    if any(p in callback_data for p in back_patterns):
        return max(0, current_depth - 1)
    
    role_prefixes = ["cr:", "choose_role:"]
    if any(callback_data.startswith(p) for p in role_prefixes):
        return 1
    
    return current_depth + 1


def get_state_name(state: Any) -> Optional[str]:
    """Extract state name from FSMContext state value."""
    if state is None:
        return None
    
    state_str = str(state)
    
    if ":" in state_str:
        parts = state_str.split(":")
        return parts[-1]
    
    return state_str


class FSMCoverageMiddleware:
    """
    Middleware that logs FSM state transitions for coverage analysis.
    
    This middleware:
    1. Captures the current FSM state before handler execution
    2. Captures the FSM state after handler execution
    3. If state changed, logs the transition to CSV
    
    Supports two formats:
    - Simple: from_state,to_state,action
    - Extended (COVERAGE_EXTENDED=1): timestamp,user_id,session_id,from_state,to_state,trigger_type,trigger_data,depth,is_back
    
    Usage:
        # Auto-registered when COVERAGE_LOG or COVERAGE_LOG_DIR is set
        bot, dp, router = create_bot(tg_token="...")
        
        # Or register manually:
        from obabot.middleware import FSMCoverageMiddleware
        router.message.middleware(FSMCoverageMiddleware())
        router.callback_query.middleware(FSMCoverageMiddleware())
    """
    
    def __init__(self):
        self._logger: Optional[CoverageLogger] = None
    
    @property
    def coverage_logger(self) -> Optional[CoverageLogger]:
        """Lazy-init coverage logger."""
        if self._logger is None:
            self._logger = get_coverage_logger()
        return self._logger
    
    async def __call__(
        self,
        handler: Callable,
        event: Any,
        data: dict,
    ) -> Any:
        """
        Middleware entry point.
        
        Args:
            handler: The next handler in the chain
            event: The event (Message, CallbackQuery, etc.)
            data: Handler data dict (contains 'state' FSMContext if available)
        """
        coverage_logger = self.coverage_logger
        if coverage_logger is None:
            return await handler(event, data)
        
        state_ctx = data.get("state")
        
        state_before: Optional[str] = None
        if state_ctx is not None:
            try:
                raw_state = await state_ctx.get_state()
                state_before = get_state_name(raw_state)
            except Exception:
                pass
        
        result = await handler(event, data)
        
        state_after: Optional[str] = None
        if state_ctx is not None:
            try:
                raw_state = await state_ctx.get_state()
                state_after = get_state_name(raw_state)
            except Exception:
                pass
        
        if state_before != state_after:
            if coverage_logger.extended:
                self._log_extended(coverage_logger, event, state_before, state_after)
            else:
                action = extract_action_from_event(event)
                coverage_logger.log_transition(state_before, state_after, action)
        
        return result
    
    def _log_extended(
        self,
        coverage_logger: CoverageLogger,
        event: Any,
        state_before: Optional[str],
        state_after: Optional[str],
    ) -> None:
        """Log transition with extended information."""
        user_id = extract_user_id(event)
        session_id = get_or_create_session(user_id) if user_id else "unknown"
        trigger_type, trigger_data = extract_trigger_parts(event)
        
        current_depth = get_user_depth(user_id)
        callback_data = f"{trigger_type}:{trigger_data}"
        new_depth = calculate_depth(current_depth, callback_data)
        is_back = is_back_navigation(callback_data) or new_depth < current_depth
        
        coverage_logger.log_transition_extended(
            from_state=state_before,
            to_state=state_after,
            trigger_type=trigger_type,
            trigger_data=trigger_data,
            user_id=user_id,
            session_id=session_id,
            depth=new_depth,
            is_back=is_back,
        )
        
        set_user_depth(user_id, new_depth)
