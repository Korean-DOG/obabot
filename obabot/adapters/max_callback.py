"""Max CallbackQuery wrapper with aiogram/python-telegram-bot compatibility methods.

This module provides MaxCallbackQuery - an extended umaxbot Callback
that adds convenience methods like edit_message_text() for cross-platform compatibility.
"""

import asyncio
import logging
from typing import Any, Optional, TYPE_CHECKING

from obabot.mixins import PlatformAwareMixin

if TYPE_CHECKING:
    from maxbot.bot import Bot
    from maxbot.types import Message

logger = logging.getLogger(__name__)

# Default timeout for API calls (seconds)
DEFAULT_TIMEOUT = 30.0


def _raise_for_max_response(result: Any, context: str) -> None:
    """Raise RuntimeError on Max HTTP 4xx/5xx responses returned by umaxbot bot methods."""
    if result is None or not hasattr(result, "status_code"):
        return

    status = getattr(result, "status_code", None)
    body = getattr(result, "text", "") or ""
    if status is not None and status >= 400:
        logger.error(
            "[Max callback] %s: API error status=%s body=%s",
            context,
            status,
            body[:200],
            extra={"max_status": status, "max_body": body[:200]},
        )
        raise RuntimeError(f"Max API error {context}: status={status} body={body[:200]!r}")


def _get_callback_base_class():
    """Import Callback class dynamically to avoid import errors if umaxbot not installed."""
    try:
        from maxbot.types import Callback
        return Callback
    except ImportError:
        # Fallback to a dummy base if umaxbot not installed
        return object


# Create the base class dynamically
_CallbackBase = _get_callback_base_class()


class MaxCallbackQuery(PlatformAwareMixin, _CallbackBase):
    """Extended umaxbot Callback with convenience methods like aiogram/python-telegram-bot.
    
    Guaranteed (safe without getattr): .data (str | None, alias for payload), .message (Message adapter with .edit_text).
    
    This class inherits from umaxbot's Callback and adds shortcut methods
    for cross-platform compatibility.
    
    Benefits:
    - isinstance(cb, Callback) returns True (backward compatible)
    - All original attributes work (payload, user, message, FSM methods)
    - Same interface as TelegramCallbackQuery
    - Clean implementation without monkey-patching
    - get_platform() method for platform identification
    
    Usage:
        # Instead of:
        await bot.update_message(message_id, text)
        
        # You can use:
        await callback.edit_message_text("New text")
        
        # Platform check:
        if callback.is_max():
            ...
    """
    
    # Store bot reference for API calls
    _bot: Optional["Bot"] = None
    
    def get_platform(self) -> str:
        """Get the platform identifier."""
        return "max"
    
    def is_telegram(self) -> bool:
        """Check if this is a Telegram platform object."""
        return False
    
    def is_max(self) -> bool:
        """Check if this is a Max platform object."""
        return True
    
    def _get_bot(self) -> Optional["Bot"]:
        """Get bot instance for API calls."""
        if self._bot:
            return self._bot
        # Try to get from dispatcher
        if hasattr(self, 'dispatcher') and self.dispatcher:
            return getattr(self.dispatcher, 'bot', None)
        return None
    
    async def edit_message_text(
        self,
        text: str,
        reply_markup: Any = None,
        parse_mode: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """Edit message text via bot.update_message().
        
        Shortcut compatible with aiogram/python-telegram-bot API.
        
        Args:
            text: New message text
            reply_markup: Optional keyboard markup
            parse_mode: Text parse mode (note: Max has limited formatting support)
            **kwargs: Additional arguments
            
        Returns:
            API response
        """
        from obabot.adapters.keyboard import convert_keyboard_to_max
        from obabot.utils.text_format import format_text_for_platform
        
        bot = self._get_bot()
        if not bot:
            logger.warning("[Max callback] edit_message_text: no bot available")
            return None
        
        # Format text for Max platform
        formatted_text = format_text_for_platform(text, parse_mode, "max")
        
        # Convert keyboard if provided
        keyboard = convert_keyboard_to_max(reply_markup) if reply_markup else None
        
        # Get message_id
        msg_id = None
        if self.message:
            msg_id = getattr(self.message, 'id', None) or getattr(self.message, 'mid', None)
            if not msg_id:
                body = getattr(self.message, 'body', None)
                if body:
                    msg_id = getattr(body, 'mid', None)
        
        if not msg_id:
            logger.warning("[Max callback] edit_message_text: no message_id")
            return None
        
        try:
            if hasattr(bot, 'update_message'):
                result = await asyncio.wait_for(
                    bot.update_message(
                        message_id=str(msg_id),
                        text=formatted_text,
                        reply_markup=keyboard
                    ),
                    timeout=DEFAULT_TIMEOUT
                )
                _raise_for_max_response(result, "edit_message_text")
                return result
        except asyncio.TimeoutError:
            logger.warning("[Max callback] edit_message_text timeout")
            return None
        except Exception as e:
            if "message is not modified" in str(e).lower():
                logger.debug("[Max callback] edit_message_text: message not modified")
                return None
            logger.exception("[Max callback] edit_message_text failed")
            raise
        
        return None
    
    async def edit_message_reply_markup(
        self,
        reply_markup: Any = None,
        **kwargs: Any
    ) -> Any:
        """Edit message reply markup.
        
        Shortcut compatible with aiogram/python-telegram-bot API.
        
        Args:
            reply_markup: New keyboard markup
            **kwargs: Additional arguments
            
        Returns:
            API response
        """
        from obabot.adapters.keyboard import convert_keyboard_to_max
        
        bot = self._get_bot()
        if not bot:
            logger.warning("[Max callback] edit_message_reply_markup: no bot available")
            return None
        
        keyboard = convert_keyboard_to_max(reply_markup) if reply_markup else None
        
        msg_id = None
        if self.message:
            msg_id = getattr(self.message, 'id', None) or getattr(self.message, 'mid', None)
        
        if not msg_id:
            logger.warning("[Max callback] edit_message_reply_markup: no message_id")
            return None
        
        try:
            if hasattr(bot, 'update_message'):
                # Max API requires text when updating, get current text
                current_text = getattr(self.message, 'text', '') or ''
                result = await asyncio.wait_for(
                    bot.update_message(
                        message_id=str(msg_id),
                        text=current_text,
                        reply_markup=keyboard
                    ),
                    timeout=DEFAULT_TIMEOUT
                )
                _raise_for_max_response(result, "edit_message_reply_markup")
                return result
        except asyncio.TimeoutError:
            logger.warning("[Max callback] edit_message_reply_markup timeout")
            return None
        except Exception as e:
            if "message is not modified" in str(e).lower():
                return None
            raise
        
        return None
    
    async def edit_message_caption(
        self,
        caption: Optional[str] = None,
        reply_markup: Any = None,
        parse_mode: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """Edit message caption.
        
        Note: Max doesn't have separate caption concept, this edits message text.
        
        Args:
            caption: New caption text
            reply_markup: Optional keyboard markup
            parse_mode: Text parse mode
            **kwargs: Additional arguments
            
        Returns:
            API response
        """
        # Max treats caption as regular text
        return await self.edit_message_text(
            text=caption or '',
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            **kwargs
        )
    
    async def delete_message(self, **kwargs: Any) -> bool:
        """Delete the message.
        
        Shortcut compatible with aiogram/python-telegram-bot API.
        
        Args:
            **kwargs: Additional arguments
            
        Returns:
            True on success
        """
        bot = self._get_bot()
        if not bot:
            logger.warning("[Max callback] delete_message: no bot available")
            return False
        
        msg_id = None
        if self.message:
            msg_id = getattr(self.message, 'id', None) or getattr(self.message, 'mid', None)
        
        if not msg_id:
            logger.warning("[Max callback] delete_message: no message_id")
            return False
        
        try:
            if hasattr(bot, 'delete_message'):
                result = await asyncio.wait_for(
                    bot.delete_message(message_id=str(msg_id)),
                    timeout=DEFAULT_TIMEOUT
                )
                _raise_for_max_response(result, "delete_message")
                return True
        except asyncio.TimeoutError:
            logger.warning("[Max callback] delete_message timeout")
            return False
        except Exception:
            logger.exception("[Max callback] delete_message failed")
            raise
        
        return False
    
    async def answer(
        self,
        text: Optional[str] = None,
        show_alert: bool = False,
        **kwargs: Any
    ) -> Any:
        """Answer callback query (acknowledge the button press).
        
        Note: Max API does not support showing notification text like Telegram.
        The 'text' and 'show_alert' parameters are accepted for API compatibility
        but are ignored.
        
        Args:
            text: Notification text (ignored for Max)
            show_alert: Show as alert (ignored for Max)
            **kwargs: Additional arguments
            
        Returns:
            API response
        """
        if text:
            logger.debug(
                "[Max callback] answer() text=%r ignored (Max API doesn't support callback notifications)",
                text[:50] if len(text) > 50 else text
            )
        
        bot = self._get_bot()
        
        try:
            # Try umaxbot's callback.answer() first (inherited)
            if hasattr(super(), 'answer'):
                return await asyncio.wait_for(super().answer(), timeout=DEFAULT_TIMEOUT)
            
            # Fallback to bot.answer_callback
            if bot and hasattr(bot, 'answer_callback'):
                callback_id = getattr(self, 'callback_id', '') or getattr(self, 'id', '')
                return await asyncio.wait_for(
                    bot.answer_callback(callback_id, ""),
                    timeout=DEFAULT_TIMEOUT
                )
        except asyncio.TimeoutError:
            logger.warning("[Max callback] answer() timeout")
            return None
        except asyncio.CancelledError:
            return None
        except TypeError as e:
            logger.debug("[Max callback] answer() signature mismatch: %s", e)
            return None
        
        return None
    
    # message is replaced in from_callback with MaxMessageAdapter so callback.message.edit_text() works
    
    # Compatibility properties
    
    @property
    def data(self) -> Optional[str]:
        """Callback data (alias for payload, aiogram compatibility)."""
        return getattr(self, 'payload', None)
    
    @property
    def from_user(self) -> Any:
        """User who pressed the button (aiogram API). Returns adapter with .id so callback.from_user.id works."""
        raw = getattr(self, 'user', None)
        if raw is None:
            return None
        from obabot.adapters.user import MaxUserAdapter
        return MaxUserAdapter(raw)
    
    @classmethod
    def from_callback(cls, callback: Any, bot: "Bot") -> "MaxCallbackQuery":
        """Create MaxCallbackQuery from a regular umaxbot Callback.
        
        Replaces callback.message with MaxMessageAdapter so callback.message.edit_text() works
        (raw maxbot Message has no edit_text).
        """
        from obabot.adapters.message import MaxMessageAdapter
        
        extended = cls.model_validate(callback.model_dump())
        extended._bot = bot
        raw_msg = extended.__dict__.get("message")
        if raw_msg is not None and bot is not None:
            extended.__dict__["message"] = MaxMessageAdapter(raw_msg, bot)
        return extended
