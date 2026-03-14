"""Text formatting utilities for cross-platform compatibility."""

import re
from html import unescape
from typing import Optional


# HTML tag to plain text/markdown mapping
HTML_TO_PLAIN = {
    # Bold: <b>, <strong>
    r'<b>(.*?)</b>': r'\1',
    r'<strong>(.*?)</strong>': r'\1',
    # Italic: <i>, <em>
    r'<i>(.*?)</i>': r'\1',
    r'<em>(.*?)</em>': r'\1',
    # Underline: <u>, <ins>
    r'<u>(.*?)</u>': r'\1',
    r'<ins>(.*?)</ins>': r'\1',
    # Strikethrough: <s>, <strike>, <del>
    r'<s>(.*?)</s>': r'\1',
    r'<strike>(.*?)</strike>': r'\1',
    r'<del>(.*?)</del>': r'\1',
    # Code: <code>, <pre>
    r'<code>(.*?)</code>': r'`\1`',
    r'<pre>(.*?)</pre>': r'\1',
    # Links: <a href="url">text</a>
    r'<a\s+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>': r'\2 (\1)',
    # Line breaks
    r'<br\s*/?>': '\n',
    # Spoiler (Telegram specific)
    r'<tg-spoiler>(.*?)</tg-spoiler>': r'\1',
    r'<span\s+class=["\']tg-spoiler["\'][^>]*>(.*?)</span>': r'\1',
}


def strip_html(text: str) -> str:
    """
    Remove all HTML tags from text, preserving content.
    
    Args:
        text: Text with HTML tags
        
    Returns:
        Plain text without HTML tags
    """
    if not text:
        return text
    
    # Apply specific conversions first (preserve links, code formatting)
    result = text
    for pattern, replacement in HTML_TO_PLAIN.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove any remaining HTML tags
    result = re.sub(r'<[^>]+>', '', result)
    
    # Decode HTML entities
    result = unescape(result)
    
    # Normalize whitespace but preserve newlines
    lines = result.split('\n')
    lines = [' '.join(line.split()) for line in lines]
    result = '\n'.join(lines)
    
    return result.strip()


def convert_html_to_max(text: str) -> str:
    """
    Convert HTML formatted text to Max-compatible format.
    
    Max doesn't support HTML formatting in regular messages,
    so we strip tags while preserving readability.
    
    Args:
        text: Text with HTML formatting (Telegram style)
        
    Returns:
        Plain text suitable for Max
    """
    return strip_html(text)


def convert_markdown_to_plain(text: str) -> str:
    """
    Convert Markdown formatted text to plain text.
    
    Args:
        text: Text with Markdown formatting
        
    Returns:
        Plain text without Markdown formatting
    """
    if not text:
        return text
    
    result = text
    
    # Bold: **text** or __text__
    result = re.sub(r'\*\*(.+?)\*\*', r'\1', result)
    result = re.sub(r'__(.+?)__', r'\1', result)
    
    # Italic: *text* or _text_
    result = re.sub(r'\*(.+?)\*', r'\1', result)
    result = re.sub(r'_(.+?)_', r'\1', result)
    
    # Strikethrough: ~~text~~
    result = re.sub(r'~~(.+?)~~', r'\1', result)
    
    # Code: `text`
    result = re.sub(r'`(.+?)`', r'\1', result)
    
    # Links: [text](url)
    result = re.sub(r'\[(.+?)\]\((.+?)\)', r'\1 (\2)', result)
    
    return result


def format_text_for_platform(
    text: str,
    parse_mode: Optional[str] = None,
    target_platform: str = "max"
) -> str:
    """
    Format text for target platform based on parse_mode.
    
    Args:
        text: Original text
        parse_mode: Source format ("HTML", "Markdown", "MarkdownV2", or None)
        target_platform: Target platform ("max", "telegram")
        
    Returns:
        Text formatted for target platform
    """
    if not text:
        return text
    
    if not parse_mode:
        return text
    
    mode = parse_mode.upper()
    
    if target_platform == "max":
        # Max doesn't support rich formatting, convert to plain text
        if mode == "HTML":
            return convert_html_to_max(text)
        elif mode in ("MARKDOWN", "MARKDOWNV2"):
            return convert_markdown_to_plain(text)
    
    # For Telegram, pass through as-is (it supports HTML/Markdown)
    return text
