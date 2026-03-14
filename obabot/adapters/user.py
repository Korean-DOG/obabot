"""User and Chat adapters for Max platform.

Note: With umaxbot, user/chat objects already have aiogram-compatible attributes.
These adapters exist for backward compatibility only.
"""

from typing import Any, Optional


class MaxUserAdapter:
    """Thin wrapper for umaxbot user object.
    
    Guaranteed: .first_name is always present (str, at least "").
    """
    
    def __init__(self, user: Any):
        self._user = user
    
    @property
    def id(self) -> int:
        return getattr(self._user, 'id', 0) or getattr(self._user, 'user_id', 0)
    
    @property
    def first_name(self) -> str:
        """Always present: str (empty string when none)."""
        return getattr(self._user, 'first_name', '') or getattr(self._user, 'name', None) or ""
    
    @property
    def last_name(self) -> Optional[str]:
        return getattr(self._user, 'last_name', None)
    
    @property
    def username(self) -> Optional[str]:
        return getattr(self._user, 'username', None)
    
    @property
    def language_code(self) -> Optional[str]:
        return getattr(self._user, 'language_code', None)
    
    @property
    def is_bot(self) -> bool:
        return getattr(self._user, 'is_bot', False)
    
    @property
    def full_name(self) -> str:
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name
    
    def __getattr__(self, name: str) -> Any:
        return getattr(self._user, name)
    
    def __repr__(self) -> str:
        return f"MaxUserAdapter(id={self.id}, name={self.full_name})"


class MaxChatAdapter:
    """Thin wrapper for umaxbot chat object."""
    
    def __init__(self, chat: Any):
        self._chat = chat
    
    @property
    def id(self) -> int:
        return getattr(self._chat, 'id', 0) or getattr(self._chat, 'chat_id', 0)
    
    @property
    def type(self) -> str:
        chat_type = getattr(self._chat, 'type', 'private') or getattr(self._chat, 'chat_type', 'private')
        type_mapping = {'dialog': 'private', 'chat': 'group', 'channel': 'channel'}
        return type_mapping.get(str(chat_type).lower(), str(chat_type))
    
    @property
    def title(self) -> Optional[str]:
        return getattr(self._chat, 'title', None) or getattr(self._chat, 'name', None)
    
    @property
    def username(self) -> Optional[str]:
        return getattr(self._chat, 'username', None)
    
    @property
    def first_name(self) -> Optional[str]:
        return getattr(self._chat, 'first_name', None)
    
    @property
    def last_name(self) -> Optional[str]:
        return getattr(self._chat, 'last_name', None)
    
    def __getattr__(self, name: str) -> Any:
        return getattr(self._chat, name)
    
    def __repr__(self) -> str:
        return f"MaxChatAdapter(id={self.id}, type={self.type})"
