"""Keyboard converter from aiogram format to umaxbot format."""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

KeyboardType = Any

# Max API documentation for URL button requirements
MAX_API_DOCS_URL = "https://dev.max.ru/docs-api/methods/POST/messages"


def _normalize_url_for_max(url: str) -> str:
    """Normalize URL for Max API - encode special characters, fix common issues."""
    from urllib.parse import urlparse, urlunparse, quote
    
    url_stripped = url.strip()
    
    try:
        parsed = urlparse(url_stripped)
        
        # Encode path if needed (handle cyrillic and special chars)
        path = parsed.path
        if path:
            # Quote only if contains non-ASCII or spaces
            if any(ord(c) > 127 or c == ' ' for c in path):
                path = quote(path, safe='/-_.~')
        
        # Encode query if needed
        query = parsed.query
        if query:
            if any(ord(c) > 127 or c == ' ' for c in query):
                query = quote(query, safe='=&-_.~')
        
        # Reconstruct URL
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc,
            path,
            parsed.params,
            query,
            ''  # Remove fragment, not needed for buttons
        ))
        
        return normalized
        
    except Exception:
        return url_stripped


def _validate_url_for_max(url: str) -> tuple[bool, str]:
    """Validate URL format for Max API.
    
    Max API requires URLs to:
    - Start with http:// or https://
    - Have a valid domain format (at least domain.tld)
    - Have a proper TLD (minimum 2 characters)
    - Not contain invalid characters
    
    Returns:
        Tuple of (is_valid, normalized_url)
    """
    if not url:
        return False, ""
    
    # Normalize URL first
    url_normalized = _normalize_url_for_max(url)
    url_lower = url_normalized.lower()
    
    # Must start with http:// or https://
    if not url_lower.startswith(('http://', 'https://')):
        logger.warning(
            "[Max keyboard] Invalid URL: '%s' - must start with http:// or https://. Docs: %s",
            url_normalized, MAX_API_DOCS_URL
        )
        return False, url_normalized
    
    # Extract domain part
    try:
        # Remove protocol
        if url_lower.startswith('https://'):
            domain_part = url_normalized[8:]
        else:
            domain_part = url_normalized[7:]
        
        # Get domain (before path/query/port)
        domain = domain_part.split('/')[0].split('?')[0].split('#')[0]
        
        # Remove port if present
        if ':' in domain:
            domain = domain.split(':')[0]
        
        # Domain must have at least one dot
        if '.' not in domain:
            logger.warning(
                "[Max keyboard] Invalid URL: '%s' - domain '%s' has no TLD",
                url_normalized, domain
            )
            return False, url_normalized
        
        # Check domain parts
        parts = domain.split('.')
        
        # Check for empty parts
        if any(not part for part in parts):
            logger.warning(
                "[Max keyboard] Invalid URL: '%s' - malformed domain (empty parts)",
                url_normalized
            )
            return False, url_normalized
        
        # TLD must be at least 2 characters (e.g., .ru, .com, .io)
        tld = parts[-1]
        if len(tld) < 2:
            logger.warning(
                "[Max keyboard] Invalid URL: '%s' - TLD '%s' too short (min 2 chars)",
                url_normalized, tld
            )
            return False, url_normalized
        
        # Check for valid characters in domain
        import re
        # Allow letters, numbers, hyphens, and dots
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-\.]*[a-zA-Z0-9]$', domain):
            # Single character domains or special cases
            if not re.match(r'^[a-zA-Z0-9]+$', domain.replace('.', '')):
                logger.warning(
                    "[Max keyboard] Invalid URL: '%s' - domain contains invalid characters",
                    url_normalized
                )
                return False, url_normalized
            
    except Exception as e:
        logger.warning(
            "[Max keyboard] Invalid URL: '%s' - parse error: %s",
            url_normalized, e
        )
        return False, url_normalized
    
    logger.debug("[Max keyboard] URL validated OK: '%s'", url_normalized)
    return True, url_normalized


def convert_keyboard_to_max(keyboard: Optional[KeyboardType]) -> Optional[Any]:
    """
    Convert aiogram keyboard markup to umaxbot format.
    
    umaxbot uses similar format to aiogram:
    - InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(...)]])
    - InlineKeyboardButton(text="...", callback_data="...")
    
    Args:
        keyboard: aiogram keyboard markup or None
        
    Returns:
        umaxbot keyboard or None
    """
    if keyboard is None:
        return None
    
    keyboard_type = type(keyboard).__name__
    
    if keyboard_type == 'InlineKeyboardMarkup':
        return _convert_inline_keyboard(keyboard)
    elif keyboard_type == 'ReplyKeyboardMarkup':
        return _convert_reply_keyboard(keyboard)
    elif keyboard_type == 'ReplyKeyboardRemove':
        return {'remove_keyboard': True}
    else:
        return keyboard


def _convert_inline_keyboard(keyboard: Any) -> Any:
    """Convert aiogram InlineKeyboardMarkup to umaxbot format."""
    try:
        from maxbot.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        buttons = []
        for row_idx, row in enumerate(keyboard.inline_keyboard):
            row_buttons = []
            for btn_idx, button in enumerate(row):
                url = getattr(button, 'url', None)
                callback_data = button.callback_data
                
                # Build kwargs dynamically - only include non-None values
                btn_kwargs = {'text': button.text}
                
                if url:
                    # Validate URL format for Max API
                    is_valid, normalized_url = _validate_url_for_max(url)
                    if is_valid:
                        btn_kwargs['url'] = normalized_url
                        btn_kwargs['type'] = 'link'
                    else:
                        # Invalid URL - skip this button
                        logger.warning(
                            "[Max keyboard] Skipping button [%d][%d] '%s' with invalid URL: %s. "
                            "See Max API docs: %s",
                            row_idx, btn_idx, button.text, url, MAX_API_DOCS_URL
                        )
                        continue
                elif callback_data:
                    btn_kwargs['callback_data'] = callback_data
                    btn_kwargs['type'] = 'callback'
                
                max_button = InlineKeyboardButton(**btn_kwargs)
                row_buttons.append(max_button)
                
                # Log button details
                logger.debug(
                    "[Max keyboard] Button [%d][%d]: text='%s', type='%s', url=%s, cb=%s",
                    row_idx, btn_idx, button.text,
                    btn_kwargs.get('type'),
                    btn_kwargs.get('url', 'N/A'),
                    btn_kwargs.get('callback_data', 'N/A')[:20] if btn_kwargs.get('callback_data') else 'N/A'
                )
                
            if row_buttons:
                buttons.append(row_buttons)
        
        result = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        # Log final JSON for debugging
        try:
            import json
            att = result.to_attachment()
            logger.debug("[Max keyboard] Final attachment JSON: %s", json.dumps(att, ensure_ascii=False))
        except Exception as log_err:
            logger.debug("[Max keyboard] Could not log attachment: %s", log_err)
        
        return result
    except ImportError:
        return _convert_inline_keyboard_generic(keyboard)


def _convert_inline_keyboard_generic(keyboard: Any) -> dict:
    """Convert inline keyboard to generic dict format (fallback)."""
    buttons = []
    for row in keyboard.inline_keyboard:
        row_buttons = []
        for button in row:
            url = getattr(button, 'url', None)
            callback_data = button.callback_data
            
            btn_dict = {'text': button.text}
            
            # Determine button type for Max API
            if url:
                is_valid, normalized_url = _validate_url_for_max(url)
                if is_valid:
                    btn_dict['url'] = normalized_url
                    btn_dict['type'] = 'link'
                else:
                    # Skip invalid URL buttons
                    continue
            elif callback_data:
                btn_dict['callback_data'] = callback_data
                btn_dict['type'] = 'callback'
            
            row_buttons.append(btn_dict)
        if row_buttons:
            buttons.append(row_buttons)
    
    return {'inline_keyboard': buttons}


def _convert_reply_keyboard(keyboard: Any) -> dict:
    """Convert aiogram ReplyKeyboardMarkup to dict format."""
    buttons = []
    for row in keyboard.keyboard:
        row_buttons = []
        for button in row:
            text = button.text if hasattr(button, 'text') else str(button)
            row_buttons.append({'text': text})
        buttons.append(row_buttons)
    
    return {
        'keyboard': buttons,
        'resize_keyboard': getattr(keyboard, 'resize_keyboard', True),
        'one_time_keyboard': getattr(keyboard, 'one_time_keyboard', False),
    }


def convert_keyboard_to_yandex(keyboard: Optional[KeyboardType]) -> Optional[list]:
    """Convert aiogram InlineKeyboardMarkup to Yandex Messenger inline_keyboard format.

    Yandex uses a flat list of button objects:
        [{"text": "Да", "callback_data": "yes"}, ...]

    Aiogram uses rows of rows:
        [[InlineKeyboardButton(text="Да", callback_data="yes")], ...]

    The conversion flattens all rows into a single list.

    Returns:
        List of button dicts for ``inline_keyboard`` field, or None.
    """
    if keyboard is None:
        return None

    keyboard_type = type(keyboard).__name__

    if keyboard_type != "InlineKeyboardMarkup":
        logger.debug("[Yandex keyboard] Unsupported keyboard type: %s", keyboard_type)
        return None

    buttons: list[dict] = []
    for row in keyboard.inline_keyboard:
        for button in row:
            btn: dict = {"text": button.text}
            url = getattr(button, "url", None)
            callback_data = getattr(button, "callback_data", None)
            if url:
                btn["url"] = url
            elif callback_data is not None:
                btn["callback_data"] = callback_data
            buttons.append(btn)

    return buttons if buttons else None


def convert_keyboard_from_max(keyboard: Optional[Any]) -> Optional[KeyboardType]:
    """Convert umaxbot keyboard to aiogram format (reverse conversion)."""
    if keyboard is None:
        return None
    
    try:
        from aiogram.types import (
            InlineKeyboardMarkup,
            InlineKeyboardButton,
            ReplyKeyboardMarkup,
            KeyboardButton,
            ReplyKeyboardRemove,
        )
        
        keyboard_type = type(keyboard).__name__
        
        if 'Inline' in keyboard_type or (isinstance(keyboard, dict) and 'inline_keyboard' in keyboard):
            buttons = []
            source = getattr(keyboard, 'inline_keyboard', None) or keyboard.get('inline_keyboard', [])
            for row in source:
                row_buttons = []
                for button in row:
                    if isinstance(button, dict):
                        row_buttons.append(InlineKeyboardButton(
                            text=button.get('text', ''),
                            callback_data=button.get('callback_data'),
                            url=button.get('url'),
                        ))
                    else:
                        row_buttons.append(InlineKeyboardButton(
                            text=getattr(button, 'text', str(button)),
                            callback_data=getattr(button, 'callback_data', None),
                            url=getattr(button, 'url', None),
                        ))
                buttons.append(row_buttons)
            return InlineKeyboardMarkup(inline_keyboard=buttons)
        
        elif 'Reply' in keyboard_type and 'Remove' not in keyboard_type:
            buttons = []
            source = getattr(keyboard, 'keyboard', [])
            for row in source:
                row_buttons = []
                for button in row:
                    text = getattr(button, 'text', str(button))
                    row_buttons.append(KeyboardButton(text=text))
                buttons.append(row_buttons)
            return ReplyKeyboardMarkup(
                keyboard=buttons,
                resize_keyboard=getattr(keyboard, 'resize_keyboard', True),
            )
        
        elif 'Remove' in keyboard_type or (isinstance(keyboard, dict) and keyboard.get('remove_keyboard')):
            return ReplyKeyboardRemove()
        
    except ImportError:
        pass
    
    return keyboard
