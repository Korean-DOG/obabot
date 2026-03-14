"""
Re-export aiogram FSM (Finite State Machine) components.

This module re-exports FSM classes from aiogram,
allowing users to import them from obabot directly:

    from obabot.fsm import State, StatesGroup, FSMContext

Instead of:

    from aiogram.fsm.state import State, StatesGroup
    from aiogram.fsm.context import FSMContext
"""

try:
    # FSM State and StatesGroup
    from aiogram.fsm.state import State, StatesGroup
    
    # FSM Context for handlers
    from aiogram.fsm.context import FSMContext
    
    # FSM Storage backends
    from aiogram.fsm.storage.base import BaseStorage
    from aiogram.fsm.storage.memory import MemoryStorage
    
    # Try to import Redis storage (optional)
    try:
        from aiogram.fsm.storage.redis import RedisStorage
    except ImportError:
        RedisStorage = None
    
    # FSM Strategy
    try:
        from aiogram.fsm.strategy import FSMStrategy
    except ImportError:
        FSMStrategy = None
    
    __all__ = [
        "State",
        "StatesGroup",
        "FSMContext",
        "BaseStorage",
        "MemoryStorage",
        "RedisStorage",
        "FSMStrategy",
    ]

except ImportError as e:
    # aiogram not installed - provide stubs
    import warnings
    warnings.warn(
        f"aiogram not installed, FSM will not work: {e}",
        ImportWarning
    )
    
    class State:
        """Stub State class when aiogram is not available."""
        def __init__(self, state: str = None, group_name: str = None):
            self._state = state
            self._group_name = group_name
        
        def __set_name__(self, owner, name):
            self._state = name
            self._group_name = owner.__name__
        
        @property
        def state(self) -> str:
            if self._group_name:
                return f"{self._group_name}:{self._state}"
            return self._state or ""
    
    class StatesGroupMeta(type):
        """Metaclass for StatesGroup stub."""
        def __new__(mcs, name, bases, namespace):
            cls = super().__new__(mcs, name, bases, namespace)
            # Find all State attributes
            for attr_name, attr_value in namespace.items():
                if isinstance(attr_value, State):
                    attr_value.__set_name__(cls, attr_name)
            return cls
    
    class StatesGroup(metaclass=StatesGroupMeta):
        """Stub StatesGroup class when aiogram is not available."""
        pass
    
    class FSMContext:
        """Stub FSMContext class when aiogram is not available."""
        async def set_state(self, state=None):
            pass
        
        async def get_state(self):
            return None
        
        async def set_data(self, data: dict):
            pass
        
        async def get_data(self):
            return {}
        
        async def update_data(self, **kwargs):
            pass
        
        async def clear(self):
            pass
    
    class BaseStorage:
        """Stub BaseStorage class."""
        pass
    
    class MemoryStorage(BaseStorage):
        """Stub MemoryStorage class."""
        pass
    
    RedisStorage = None
    FSMStrategy = None
    
    __all__ = [
        "State",
        "StatesGroup",
        "FSMContext",
        "BaseStorage",
        "MemoryStorage",
        "RedisStorage",
        "FSMStrategy",
    ]

