"""Mixins for cross-platform compatibility.

Provides reusable functionality that can be added to any class
via multiple inheritance.
"""

from typing import Optional

from obabot.types import BPlatform


class PlatformAwareMixin:
    """Mixin that provides platform identification.
    
    Add this mixin to any class to give it a consistent get_platform() method.
    Classes should set _platform_id in __init__ or as class attribute.
    
    Usage:
        class MyClass(PlatformAwareMixin, SomeBase):
            _platform_id: str = "telegram"
        
        obj = MyClass()
        platform = obj.get_platform()  # "telegram"
        platform_enum = obj.get_platform_enum()  # BPlatform.telegram
    """
    
    # Subclasses should set this
    _platform_id: str = ""
    
    def get_platform(self) -> str:
        """Get the platform identifier as string.
        
        Returns:
            Platform string: "telegram", "max", or empty string if unknown
        """
        # Try _platform_id first (set by mixin)
        if hasattr(self, '_platform_id') and self._platform_id:
            return self._platform_id
        
        # Fallback to 'platform' attribute (might be set dynamically)
        if hasattr(self, 'platform'):
            val = getattr(self, 'platform', '')
            if isinstance(val, BPlatform):
                return val.value
            return str(val) if val else ''
        
        return ''
    
    def get_platform_enum(self) -> Optional[BPlatform]:
        """Get the platform as BPlatform enum.
        
        Returns:
            BPlatform enum value or None if unknown
        """
        platform_str = self.get_platform()
        if not platform_str:
            return None
        
        try:
            return BPlatform(platform_str)
        except ValueError:
            return None
    
    def is_telegram(self) -> bool:
        """Check if this is a Telegram platform object."""
        return self.get_platform() == "telegram"
    
    def is_max(self) -> bool:
        """Check if this is a Max platform object."""
        return self.get_platform() == "max"
