"""Telegram platform implementation using aiogram."""

from functools import wraps
from typing import Any, Callable

from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, CallbackQuery

from obabot.adapters.telegram_callback import TelegramCallbackQuery
from obabot.context import set_current_platform, reset_current_platform
from obabot.platforms.base import BasePlatform, HandlerType
from obabot.types import BPlatform


class TelegramPlatform(BasePlatform):
    """
    Telegram platform - thin wrapper over aiogram.
    
    Messages are passed through without conversion,
    only adding the `platform` attribute.
    """
    
    def __init__(self, token: str):
        self._bot = Bot(token=token)
        self._dispatcher = Dispatcher()
        self._router = Router()
        self._dispatcher.include_router(self._router)
    
    @property
    def platform(self) -> BPlatform:
        return BPlatform.telegram
    
    @property
    def bot(self) -> Bot:
        return self._bot
    
    @property
    def dispatcher(self) -> Dispatcher:
        return self._dispatcher
    
    @property
    def router(self) -> Router:
        return self._router
    
    def wrap_handler(self, handler: HandlerType) -> HandlerType:
        """
        Wrap handler to:
        1. Add `platform` attribute to messages
        2. Convert CallbackQuery to TelegramCallbackQuery with python-telegram-bot shortcuts
        
        Note: aiogram models are frozen Pydantic models, so we use
        object.__setattr__ to bypass the frozen restriction.
        """
        @wraps(handler)
        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            # Set platform context for bot.send_* auto-detection
            token = set_current_platform(BPlatform.telegram)
            try:
                # Process args - convert CallbackQuery, add platform to Message
                new_args = []
                for arg in args:
                    if isinstance(arg, CallbackQuery) and not isinstance(arg, TelegramCallbackQuery):
                        # Convert to TelegramCallbackQuery with bot binding preserved
                        converted = TelegramCallbackQuery.from_callback(arg, self._bot)
                        object.__setattr__(converted, 'platform', 'telegram')
                        new_args.append(converted)
                    elif isinstance(arg, Message):
                        object.__setattr__(arg, 'platform', 'telegram')
                        new_args.append(arg)
                    else:
                        new_args.append(arg)
                
                # Process kwargs - convert CallbackQuery, add platform to Message
                new_kwargs = {}
                for key, value in kwargs.items():
                    if isinstance(value, CallbackQuery) and not isinstance(value, TelegramCallbackQuery):
                        # Convert to TelegramCallbackQuery with bot binding preserved
                        converted = TelegramCallbackQuery.from_callback(value, self._bot)
                        object.__setattr__(converted, 'platform', 'telegram')
                        new_kwargs[key] = converted
                    elif isinstance(value, Message):
                        object.__setattr__(value, 'platform', 'telegram')
                        new_kwargs[key] = value
                    else:
                        new_kwargs[key] = value
                
                return await handler(*new_args, **new_kwargs)
            finally:
                reset_current_platform(token)
        
        return wrapped
    
    async def start_polling(self) -> None:
        """Start polling using aiogram dispatcher."""
        await self._dispatcher.start_polling(self._bot)
    
    async def stop_polling(self) -> None:
        """Stop polling."""
        await self._dispatcher.stop_polling()
        await self._bot.session.close()
    
    async def feed_update(self, update: Any, **kwargs: Any) -> Any:
        """
        Process a single update using aiogram dispatcher.
        
        Args:
            update: aiogram Update object
            **kwargs: Additional arguments passed to dispatcher
            
        Returns:
            Result from dispatcher.feed_update()
        """
        return await self._dispatcher.feed_update(self._bot, update, **kwargs)
    
    async def feed_raw_update(self, update: dict, **kwargs: Any) -> Any:
        """
        Process a raw update dict using aiogram dispatcher.
        
        Args:
            update: Raw update dictionary from Telegram
            **kwargs: Additional arguments passed to dispatcher
            
        Returns:
            Result from dispatcher.feed_raw_update()
        """
        return await self._dispatcher.feed_raw_update(self._bot, update, **kwargs)

