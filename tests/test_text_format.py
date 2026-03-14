"""Tests for text formatting utilities."""

import pytest
from obabot.utils.text_format import (
    strip_html,
    convert_html_to_max,
    convert_markdown_to_plain,
    format_text_for_platform,
)


class TestStripHtml:
    """Test HTML stripping functionality."""
    
    def test_simple_bold(self):
        assert strip_html("<b>bold</b>") == "bold"
        assert strip_html("<strong>bold</strong>") == "bold"
    
    def test_simple_italic(self):
        assert strip_html("<i>italic</i>") == "italic"
        assert strip_html("<em>italic</em>") == "italic"
    
    def test_code_preserved(self):
        assert strip_html("<code>code</code>") == "`code`"
    
    def test_link_with_url(self):
        result = strip_html('<a href="https://example.com">link</a>')
        assert "link" in result
        assert "example.com" in result
    
    def test_nested_tags(self):
        assert strip_html("<b><i>bold italic</i></b>") == "bold italic"
    
    def test_line_breaks(self):
        result = strip_html("line1<br>line2<br/>line3")
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result
    
    def test_html_entities(self):
        assert strip_html("&amp; &lt; &gt;") == "& < >"
    
    def test_none_text(self):
        assert strip_html(None) is None
        assert strip_html("") == ""
    
    def test_plain_text_unchanged(self):
        assert strip_html("plain text") == "plain text"
    
    def test_telegram_spoiler(self):
        assert strip_html("<tg-spoiler>secret</tg-spoiler>") == "secret"
    
    def test_complex_message(self):
        html = """<b>Hello</b> <i>world</i>!
<code>code here</code>
<a href="https://example.com">Click me</a>"""
        result = strip_html(html)
        assert "Hello" in result
        assert "world" in result
        assert "`code here`" in result
        assert "Click me" in result
        assert "<b>" not in result
        assert "<i>" not in result


class TestMarkdownStrip:
    """Test Markdown stripping functionality."""
    
    def test_bold(self):
        assert convert_markdown_to_plain("**bold**") == "bold"
        assert convert_markdown_to_plain("__bold__") == "bold"
    
    def test_italic(self):
        assert convert_markdown_to_plain("*italic*") == "italic"
        assert convert_markdown_to_plain("_italic_") == "italic"
    
    def test_strikethrough(self):
        assert convert_markdown_to_plain("~~strikethrough~~") == "strikethrough"
    
    def test_code(self):
        assert convert_markdown_to_plain("`code`") == "code"
    
    def test_link(self):
        result = convert_markdown_to_plain("[link](https://example.com)")
        assert "link" in result
        assert "example.com" in result


class TestFormatTextForPlatform:
    """Test platform-specific formatting."""
    
    def test_max_html(self):
        result = format_text_for_platform("<b>bold</b>", "HTML", "max")
        assert result == "bold"
        assert "<b>" not in result
    
    def test_max_markdown(self):
        result = format_text_for_platform("**bold**", "Markdown", "max")
        assert result == "bold"
        assert "**" not in result
    
    def test_max_no_parse_mode(self):
        result = format_text_for_platform("<b>bold</b>", None, "max")
        assert result == "<b>bold</b>"  # No stripping without parse_mode
    
    def test_telegram_html_passthrough(self):
        result = format_text_for_platform("<b>bold</b>", "HTML", "telegram")
        assert result == "<b>bold</b>"  # Telegram supports HTML
    
    def test_case_insensitive_parse_mode(self):
        assert format_text_for_platform("<b>b</b>", "html", "max") == "b"
        assert format_text_for_platform("<b>b</b>", "HTML", "max") == "b"
        assert format_text_for_platform("<b>b</b>", "Html", "max") == "b"


class TestRealWorldExamples:
    """Test with real-world message examples."""
    
    def test_welcome_message(self):
        html = """<b>Добро пожаловать!</b>

Вы зарегистрированы как <code>user123</code>.

<i>Используйте /help для списка команд.</i>"""
        
        result = format_text_for_platform(html, "HTML", "max")
        
        assert "Добро пожаловать!" in result
        assert "`user123`" in result
        assert "Используйте /help" in result
        assert "<b>" not in result
        assert "<i>" not in result
    
    def test_error_message(self):
        html = "<b>Ошибка!</b> Неверный формат: <code>&lt;date&gt;</code>"
        result = format_text_for_platform(html, "HTML", "max")
        
        assert "Ошибка!" in result
        assert "`<date>`" in result
        assert "<b>" not in result
    
    def test_link_message(self):
        html = 'Подробнее: <a href="https://docs.example.com/guide">документация</a>'
        result = format_text_for_platform(html, "HTML", "max")
        
        assert "документация" in result
        assert "docs.example.com" in result
        assert "<a" not in result
