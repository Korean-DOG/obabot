"""Base platform interface."""

from abc import ABC, abstractmethod
from typing import Any, Callable, Coroutine, TypeVar

from obabot.types import BPlatform

T = TypeVar("T")
HandlerType = Callable[..., Coroutine[Any, Any, Any]]


class BasePlatform(ABC):
    """Abstract base class for platform implementations."""
    
    @property
    @abstractmethod
    def platform(self) -> BPlatform:
        """Return the platform type."""
        ...
    
    @property
    @abstractmethod
    def bot(self) -> Any:
        """Return the underlying bot instance."""
        ...
    
    @property
    @abstractmethod
    def dispatcher(self) -> Any:
        """Return the underlying dispatcher instance."""
        ...
    
    @property
    @abstractmethod
    def router(self) -> Any:
        """Return the underlying router instance."""
        ...
    
    @abstractmethod
    def wrap_handler(self, handler: HandlerType) -> HandlerType:
        """
        Wrap a handler to add platform-specific behavior.
        For Telegram: adds message.platform attribute
        For Max: wraps message in adapter with aiogram-compatible API
        """
        ...
    
    @abstractmethod
    async def start_polling(self) -> None:
        """Start polling for updates."""
        ...
    
    @abstractmethod
    async def stop_polling(self) -> None:
        """Stop polling for updates."""
        ...
    
    @abstractmethod
    async def feed_update(self, update: Any, **kwargs: Any) -> Any:
        """
        Process a single update.
        
        Args:
            update: Update object to process
            **kwargs: Additional arguments passed to the underlying dispatcher
            
        Returns:
            Result from the update processing (can be used as webhook response)
        """
        ...
    
    @abstractmethod
    async def feed_raw_update(self, update: dict, **kwargs: Any) -> Any:
        """
        Process a raw update dict.
        
        Args:
            update: Raw update dictionary
            **kwargs: Additional arguments passed to the underlying dispatcher
            
        Returns:
            Result from the update processing (can be used as webhook response)
        """
        ...

