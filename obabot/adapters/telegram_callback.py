"""Telegram CallbackQuery wrapper with python-telegram-bot compatibility methods.

This module provides TelegramCallbackQuery - an extended aiogram CallbackQuery
that adds convenience methods like edit_message_text() for easier migration
from python-telegram-bot.
"""

from typing import Any, Optional, TYPE_CHECKING

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from obabot.mixins import PlatformAwareMixin

if TYPE_CHECKING:
    from aiogram import Bot
    from aiogram.types import Message


class TelegramCallbackQuery(PlatformAwareMixin, CallbackQuery):
    """Extended CallbackQuery with convenience methods like python-telegram-bot.
    
    Guaranteed (safe without getattr): .data (str | None), .message (Message | None).
    
    Benefits:
    - isinstance(cb, CallbackQuery) returns True (backward compatible)
    - All original attributes work
    - Type hints compatible
    - Clean implementation without monkey-patching
    - get_platform() method for platform identification
    
    Usage:
        # Instead of:
        await callback.message.edit_text("New text")
        
        # You can use:
        await callback.edit_message_text("New text")
        
        # Platform check:
        if callback.is_telegram():
            ...
    """
    
    def get_platform(self) -> str:
        """Get the platform identifier."""
        return "telegram"
    
    def is_telegram(self) -> bool:
        """Check if this is a Telegram platform object."""
        return True
    
    def is_max(self) -> bool:
        """Check if this is a Max platform object."""
        return False
    
    async def edit_message_text(
        self,
        text: str,
        reply_markup: Any = None,
        parse_mode: Optional[str] = None,
        **kwargs: Any
    ) -> "Message":
        """Edit message text via callback.message.edit_text().
        
        Shortcut for callback.message.edit_text() - compatible with python-telegram-bot API.
        
        Args:
            text: New message text
            reply_markup: Optional keyboard markup
            parse_mode: Text parse mode ("HTML", "Markdown", etc.)
            **kwargs: Additional arguments passed to edit_text()
            
        Returns:
            Edited Message object
        """
        return await self.message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            **kwargs
        )
    
    async def edit_message_reply_markup(
        self,
        reply_markup: Any = None,
        **kwargs: Any
    ) -> "Message":
        """Edit message reply markup via callback.message.edit_reply_markup().
        
        Shortcut for callback.message.edit_reply_markup() - compatible with python-telegram-bot API.
        
        Args:
            reply_markup: New keyboard markup
            **kwargs: Additional arguments passed to edit_reply_markup()
            
        Returns:
            Edited Message object
        """
        return await self.message.edit_reply_markup(
            reply_markup=reply_markup,
            **kwargs
        )
    
    async def edit_message_caption(
        self,
        caption: Optional[str] = None,
        reply_markup: Any = None,
        parse_mode: Optional[str] = None,
        **kwargs: Any
    ) -> "Message":
        """Edit message caption via callback.message.edit_caption().
        
        Shortcut for callback.message.edit_caption() - compatible with python-telegram-bot API.
        
        Args:
            caption: New caption text
            reply_markup: Optional keyboard markup
            parse_mode: Text parse mode
            **kwargs: Additional arguments passed to edit_caption()
            
        Returns:
            Edited Message object
        """
        return await self.message.edit_caption(
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            **kwargs
        )
    
    async def edit_message_media(
        self,
        media: Any,
        reply_markup: Any = None,
        **kwargs: Any
    ) -> "Message":
        """Edit message media via callback.message.edit_media().
        
        Shortcut for callback.message.edit_media() - compatible with python-telegram-bot API.
        
        Args:
            media: New media object
            reply_markup: Optional keyboard markup
            **kwargs: Additional arguments passed to edit_media()
            
        Returns:
            Edited Message object
        """
        return await self.message.edit_media(
            media=media,
            reply_markup=reply_markup,
            **kwargs
        )
    
    async def delete_message(self, **kwargs: Any) -> bool:
        """Delete the message via callback.message.delete().
        
        Shortcut for callback.message.delete() - compatible with python-telegram-bot API.
        
        Args:
            **kwargs: Additional arguments passed to delete()
            
        Returns:
            True on success
        """
        return await self.message.delete(**kwargs)
    
    async def answer(
        self,
        text: Optional[str] = None,
        show_alert: Optional[bool] = None,
        **kwargs: Any
    ) -> bool:
        """Answer callback query with graceful handling of timeout errors.
        
        If Telegram returns "query is too old" error (callback wasn't answered
        within 30 seconds), the error is silently ignored since there's nothing
        useful we can do at that point.
        
        Args:
            text: Text to show in notification
            show_alert: Show as alert popup instead of notification
            **kwargs: Additional arguments passed to parent answer()
            
        Returns:
            True on success, False if query expired
        """
        try:
            return await super().answer(text=text, show_alert=show_alert, **kwargs)
        except TelegramBadRequest as e:
            if "query is too old" in e.message or "query id is invalid" in e.message.lower():
                return False
            raise
    
    @classmethod
    def from_callback(cls, callback: CallbackQuery, bot: "Bot") -> "TelegramCallbackQuery":
        """Create TelegramCallbackQuery from a regular CallbackQuery.
        
        Args:
            callback: Original aiogram CallbackQuery
            bot: Bot instance to bind to (required for edit/delete methods)
            
        Returns:
            TelegramCallbackQuery with all original data and bot binding preserved
        """
        extended = cls.model_validate(callback.model_dump())
        # Restore bot binding lost during model_dump/validate
        extended.as_(bot)
        if extended.message:
            extended.message.as_(bot)
        return extended
