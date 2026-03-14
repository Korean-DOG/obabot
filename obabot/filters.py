"""
Re-export aiogram filters for convenience.

This module re-exports all commonly used aiogram filters,
allowing users to import them from obabot directly:

    from obabot.filters import Command, F, StateFilter

Instead of:

    from aiogram.filters import Command
    from aiogram import F
"""

try:
    # Core filters
    from aiogram.filters import (
        Command,
        CommandStart,
        CommandObject,
        StateFilter,
        ExceptionTypeFilter,
        MagicData,
    )
    
    # Magic filter F
    from aiogram import F
    
    # Filter base classes (for custom filters)
    from aiogram.filters.base import Filter
    
    # Text filters
    try:
        from aiogram.filters import Text
    except ImportError:
        # Text filter was removed in newer aiogram versions
        Text = None
    
    # Callback data filters
    try:
        from aiogram.filters.callback_data import CallbackData
    except ImportError:
        from aiogram.filters import CallbackData
    
    __all__ = [
        "Command",
        "CommandStart", 
        "CommandObject",
        "StateFilter",
        "ExceptionTypeFilter",
        "MagicData",
        "F",
        "Filter",
        "Text",
        "CallbackData",
    ]

except ImportError as e:
    # aiogram not installed - provide stubs for type checking
    import warnings
    warnings.warn(
        f"aiogram not installed, filters will not work: {e}",
        ImportWarning
    )
    
    # Stub classes for when aiogram is not available
    class Command:
        def __init__(self, *commands, **kwargs): pass
    
    class CommandStart(Command):
        pass
    
    class CommandObject:
        pass
    
    class StateFilter:
        def __init__(self, *states): pass
    
    class ExceptionTypeFilter:
        def __init__(self, *types): pass
    
    class MagicData:
        pass
    
    class Filter:
        pass
    
    class CallbackData:
        pass
    
    # Dummy F object
    class _MagicFilter:
        def __getattr__(self, name):
            return self
        def __call__(self, *args, **kwargs):
            return self
        def __eq__(self, other):
            return self
        def __ne__(self, other):
            return self
        def __and__(self, other):
            return self
        def __or__(self, other):
            return self
        def __invert__(self):
            return self
    
    F = _MagicFilter()
    Text = None
    
    __all__ = [
        "Command",
        "CommandStart",
        "CommandObject", 
        "StateFilter",
        "ExceptionTypeFilter",
        "MagicData",
        "F",
        "Filter",
        "Text",
        "CallbackData",
    ]

