"""Utility modules for obabot."""

from obabot.utils.text_format import (
    strip_html,
    convert_html_to_max,
    convert_markdown_to_plain,
    format_text_for_platform,
)
from obabot.utils.safe_send import (
    safe_telegram_call,
    with_timeout_handling,
)

__all__ = [
    "strip_html",
    "convert_html_to_max",
    "convert_markdown_to_plain",
    "format_text_for_platform",
    "safe_telegram_call",
    "with_timeout_handling",
]
