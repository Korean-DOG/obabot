"""Message adapter for Max platform.

Note: With umaxbot, the Message class already has aiogram-compatible interface.
This module provides a thin wrapper only if needed for compatibility.
"""

import asyncio
import logging
from typing import Any, Optional, TYPE_CHECKING

from obabot.config import log_outgoing_message
from obabot.utils.max_api import delete_max_message
from obabot.utils.text_format import format_text_for_platform

if TYPE_CHECKING:
    from obabot.adapters.keyboard import KeyboardType

logger = logging.getLogger(__name__)

# Default timeout for API calls (seconds)
DEFAULT_TIMEOUT = 30.0


def _filename_from_url(url: Optional[str]) -> str:
    """Get filename from URL (Max). For getfile URLs fetches from server (HEAD/GET); else basename from path."""
    from obabot.adapters.max_file import (
        _url_basename_is_getfile,
        fetch_filename_from_max_url_sync,
        filename_from_max_url,
    )
    if url and _url_basename_is_getfile(url):
        name = fetch_filename_from_max_url_sync(url)
        if name:
            return name
        return "file.bin"
    return filename_from_max_url(url)


class MaxFileAttachmentAdapter:
    """Wraps Max Attachment so message.document / .audio etc. have aiogram-like .file_name and .file_id.
    
    Max Attachment has: type, url, token, id (no file_name).
    Aiogram Document has: file_id, file_name, file_unique_id, ...
    This adapter provides .file_name (from url basename or fallback) and .file_id (= url for get_file).
    """
    
    def __init__(self, attachment: Any):
        self._att = attachment
    
    @property
    def file_name(self) -> str:
        return (
            getattr(self._att, "file_name", None)
            or getattr(self._att, "filename", None)
            or _filename_from_url(getattr(self._att, "url", None))
        )
    
    @property
    def file_id(self) -> str:
        """For Max, file_id is the URL (used with get_file(attachment.url, platform='max'))."""
        return getattr(self._att, "url", "") or getattr(self._att, "id", "") or ""
    
    @property
    def url(self) -> Optional[str]:
        return getattr(self._att, "url", None)
    
    def __getattr__(self, name: str) -> Any:
        return getattr(self._att, name)


class MaxMessageAdapter:
    """
    Max message adapter with guaranteed aiogram-style attributes.
    
    Guaranteed (safe to use without getattr):
    - .text: str (empty string when no text)
    - .photo: list (empty when no photos)
    - .document, .video, .voice, .sticker, .location, .contact: present, None when absent
    - .content_type: str ("photo" | "document" | "text" | "unknown" | ...)
    
    Also: .from_user, .chat, .message_id, .get_attachment(), .edit_text(), .reply(), etc.
    """
    
    _platform_id: str = "max"
    
    def __init__(self, msg: Any, bot: Any = None, event: Any = None):
        self._msg = msg
        self._bot = bot
        self._event = event
    
    def get_platform(self) -> str:
        """Get the platform identifier."""
        return self._platform_id
    
    def is_telegram(self) -> bool:
        """Check if this is a Telegram platform object."""
        return False
    
    def is_max(self) -> bool:
        """Check if this is a Max platform object."""
        return True
    
    @property
    def platform(self) -> str:
        return self._platform_id
    
    @property
    def text(self) -> str:
        """Message text. Always present: str (empty string when no text)."""
        return getattr(self._msg, 'text', None) or ""
    
    @property
    def message_id(self) -> int:
        """Message ID."""
        return getattr(self._msg, 'id', 0) or getattr(self._msg, 'message_id', 0)
    
    @property
    def id(self) -> Any:
        """Message id (alias for message_id, for callback.message.id)."""
        return getattr(self._msg, 'id', None) or getattr(self._msg, 'mid', None) or self.message_id
    
    @property
    def mid(self) -> Any:
        """Message mid (Max API)."""
        return getattr(self._msg, 'mid', None) or getattr(self._msg, 'id', None) or self.message_id
    
    @property
    def from_user(self) -> Any:
        """Message sender (aiogram API). Wrapped so .username, .id, .first_name exist (maxbot User has no username)."""
        sender = getattr(self._msg, 'sender', None)
        if sender is None:
            return None
        from obabot.adapters.user import MaxUserAdapter
        return MaxUserAdapter(sender)
    
    @property
    def sender(self) -> Any:
        """Message sender (umaxbot API, for filters)."""
        return getattr(self._msg, 'sender', None)
    
    @property
    def chat(self) -> Any:
        """Chat object (aiogram API). Wrapped for consistent .id, .type."""
        raw = getattr(self._msg, 'chat', None) or getattr(self._msg, 'sender', None)
        if raw is None:
            return None
        from obabot.adapters.user import MaxChatAdapter
        return MaxChatAdapter(raw)
    
    # --- Attachment properties for F.photo, F.document, etc. compatibility ---
    
    def _get_attachments(self, attachment_type: str) -> list:
        """Get attachments of specific type from Max message."""
        if hasattr(self._msg, 'get_attachments'):
            return list(self._msg.get_attachments(attachment_type))
        if hasattr(self._msg, 'attachments'):
            attachments = getattr(self._msg, 'attachments', []) or []
            return [a for a in attachments if getattr(a, 'type', None) == attachment_type]
        return []
    
    def _get_attachment(self, attachment_type: str) -> Optional[Any]:
        """Get single attachment of specific type from Max message."""
        if hasattr(self._msg, 'get_attachment'):
            return self._msg.get_attachment(attachment_type)
        attachments = self._get_attachments(attachment_type)
        return attachments[0] if attachments else None
    
    def _wrap_file_attachment(self, att: Any) -> Optional[MaxFileAttachmentAdapter]:
        """Wrap attachment so .file_name and .file_id work (aiogram compatibility)."""
        if att is None:
            return None
        return MaxFileAttachmentAdapter(att)
    
    _FILE_ATTACHMENT_TYPES = frozenset({"file", "document", "audio", "video", "voice", "video_note", "animation", "gif"})
    
    def get_attachment(self, attachment_type: str) -> Optional[Any]:
        """Get attachment by type. For file-like types returns wrapper with .file_name, .file_id (url)."""
        att = self._get_attachment(attachment_type)
        if att is None:
            return None
        if attachment_type in self._FILE_ATTACHMENT_TYPES:
            return MaxFileAttachmentAdapter(att)
        return att
    
    @property
    def photo(self) -> list:
        """Photo attachments. Always present: list (empty when no photos)."""
        return self._get_attachments("image")
    
    @property
    def document(self) -> Optional[Any]:
        """Document attachment (for F.document filter). Returns wrapper with .file_name, .file_id (url)."""
        att = self._get_attachment("file") or self._get_attachment("document")
        return self._wrap_file_attachment(att)
    
    @property
    def audio(self) -> Optional[Any]:
        """Audio attachment (for F.audio filter). Returns wrapper with .file_name, .file_id (url)."""
        return self._wrap_file_attachment(self._get_attachment("audio"))
    
    @property
    def video(self) -> Optional[Any]:
        """Video attachment (for F.video filter). Returns wrapper with .file_name, .file_id (url)."""
        return self._wrap_file_attachment(self._get_attachment("video"))
    
    @property
    def voice(self) -> Optional[Any]:
        """Voice attachment (for F.voice filter). Returns wrapper with .file_name, .file_id (url)."""
        return self._wrap_file_attachment(self._get_attachment("voice"))
    
    @property
    def video_note(self) -> Optional[Any]:
        """Video note attachment. Returns wrapper with .file_name, .file_id (url)."""
        return self._wrap_file_attachment(self._get_attachment("video_note"))
    
    @property
    def sticker(self) -> Optional[Any]:
        """Sticker attachment (for F.sticker filter compatibility)."""
        return self._get_attachment("sticker")
    
    @property
    def animation(self) -> Optional[Any]:
        """Animation/GIF attachment. Returns wrapper with .file_name, .file_id (url)."""
        att = self._get_attachment("animation") or self._get_attachment("gif")
        return self._wrap_file_attachment(att)
    
    @property
    def contact(self) -> Optional[Any]:
        """Contact attachment (for F.contact filter compatibility)."""
        return self._get_attachment("contact")
    
    @property
    def location(self) -> Optional[Any]:
        """Location attachment (for F.location filter compatibility)."""
        return self._get_attachment("location")
    
    @property
    def successful_payment(self) -> Optional[Any]:
        """Successful payment info (for F.successful_payment filter compatibility).
        
        Note: Max may not support payments. Returns None.
        """
        # Max doesn't have Telegram-style payments, always return None
        return None
    
    @property
    def content_type(self) -> str:
        """Content type of the message (for content_type filters)."""
        if self.photo:
            return "photo"
        if self.document:
            return "document"
        if self.audio:
            return "audio"
        if self.video:
            return "video"
        if self.voice:
            return "voice"
        if self.video_note:
            return "video_note"
        if self.sticker:
            return "sticker"
        if self.animation:
            return "animation"
        if self.contact:
            return "contact"
        if self.location:
            return "location"
        if self.text:
            return "text"
        return "unknown"
    
    def _chat_id_for_send(self) -> Optional[Any]:
        """Resolve chat_id for sending (Max API uses chat_id or user_id)."""
        chat = self.chat
        if chat is None:
            return None
        if hasattr(chat, 'id'):
            return getattr(chat, 'id', None)
        return chat
    
    def _log_max_response(self, result: Any, context: str = "answer") -> None:
        """Log Max API response; treat 4xx/5xx as error and raise."""
        if result is None:
            logger.warning("[Max send] %s: response is None", context)
            return
        status = None
        body_preview = ""
        if hasattr(result, 'status_code'):
            status = getattr(result, 'status_code', None)
            if hasattr(result, 'text'):
                body_preview = (result.text or "")[:200]
        if status is not None:
            if status >= 400:
                logger.error(
                    "[Max send] %s: API error status=%s body=%s",
                    context, status, body_preview,
                    extra={"max_status": status, "max_body": body_preview}
                )
                raise RuntimeError(
                    f"Max API error {context}: status={status} body={body_preview!r}"
                )
            logger.info(
                "[Max send] %s: Max API response status=%s body=%s",
                context, status, body_preview or "(empty)",
                extra={"max_status": status}
            )
        else:
            logger.info("[Max send] %s: Max API response (no status): %s", context, type(result).__name__)
    
    async def answer(
        self,
        text: str,
        reply_markup: Optional["KeyboardType"] = None,
        parse_mode: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """Send message to the same chat.
        
        Args:
            text: Message text
            reply_markup: Optional keyboard
            parse_mode: Text format ("HTML", "Markdown", etc.). 
                       Max doesn't support HTML/Markdown, so tags are stripped.
            **kwargs: Additional arguments (ignored for Max compatibility)
        """
        from obabot.adapters.keyboard import convert_keyboard_to_max
        
        # Convert HTML/Markdown to plain text for Max
        formatted_text = format_text_for_platform(text, parse_mode, "max")
        
        keyboard = convert_keyboard_to_max(reply_markup) if reply_markup else None
        chat_id = self._chat_id_for_send()
        
        # Log outgoing message (platform auto-detected from context)
        log_outgoing_message(
            chat_id=chat_id,
            text=formatted_text,
            method="answer",
            has_keyboard=keyboard is not None,
            parse_mode=parse_mode,
        )
        
        if not self._bot or not hasattr(self._bot, 'send_message'):
            logger.error("[Max send] answer: bot.send_message not available")
            raise NotImplementedError("Cannot send message: bot.send_message not available")
        
        if not chat_id:
            logger.error("[Max send] answer: chat_id is missing")
            raise ValueError("Cannot send: chat_id is missing")
        
        try:
            logger.info("[Max send] answer via bot.send_message: chat_id=%s", chat_id)
            coro = self._bot.send_message(chat_id=chat_id, text=formatted_text, reply_markup=keyboard)
            result = await asyncio.wait_for(coro, timeout=DEFAULT_TIMEOUT)
            self._log_max_response(result, "answer")
            return result
        except asyncio.TimeoutError:
            logger.warning("[Max send] answer() timeout after %.1fs: chat_id=%s", DEFAULT_TIMEOUT, chat_id)
            return None
        except asyncio.CancelledError:
            logger.debug("[Max send] answer() cancelled: chat_id=%s", chat_id)
            return None
        except Exception:
            logger.exception("[Max send] answer() failed: chat_id=%s", chat_id)
            raise
    
    async def reply(
        self,
        text: str,
        reply_markup: Optional["KeyboardType"] = None,
        parse_mode: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """Reply to message.
        
        Args:
            text: Message text
            reply_markup: Optional keyboard
            parse_mode: Text format ("HTML", "Markdown", etc.).
                       Max doesn't support HTML/Markdown, so tags are stripped.
            **kwargs: Additional arguments (ignored for Max compatibility)
        """
        from obabot.adapters.keyboard import convert_keyboard_to_max
        
        # Convert HTML/Markdown to plain text for Max
        formatted_text = format_text_for_platform(text, parse_mode, "max")
        
        keyboard = convert_keyboard_to_max(reply_markup) if reply_markup else None
        chat_id = self._chat_id_for_send()
        
        # Log outgoing message (platform auto-detected from context)
        log_outgoing_message(
            chat_id=chat_id,
            text=formatted_text,
            method="reply",
            has_keyboard=keyboard is not None,
            parse_mode=parse_mode,
        )
        
        # Max doesn't have native reply-to-message, just send to same chat
        # Use answer() which calls bot.send_message()
        return await self.answer(text, reply_markup=reply_markup, parse_mode=parse_mode, **kwargs)
    
    async def edit_text(
        self,
        text: str,
        reply_markup: Optional["KeyboardType"] = None,
        parse_mode: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """Edit message text (aiogram API compatibility).
        
        Args:
            text: New message text
            reply_markup: Optional keyboard
            parse_mode: Text format ("HTML", "Markdown", etc.).
                       Max doesn't support HTML/Markdown, so tags are stripped.
            **kwargs: Additional arguments
        """
        from obabot.adapters.keyboard import convert_keyboard_to_max
        
        formatted_text = format_text_for_platform(text, parse_mode, "max")
        keyboard = convert_keyboard_to_max(reply_markup) if reply_markup else None
        chat_id = self._chat_id_for_send()
        
        # Log outgoing message (platform auto-detected from context)
        log_outgoing_message(
            chat_id=chat_id,
            text=formatted_text,
            method="edit_text",
            has_keyboard=keyboard is not None,
            parse_mode=parse_mode,
        )
        
        msg_id = self.message_id
        
        try:
            # maxbot Bot uses update_message(message_id, text, reply_markup, ...)
            if self._bot and hasattr(self._bot, 'update_message'):
                logger.info("[Max send] edit_text via update_message: msg_id=%s", msg_id)
                
                # Log keyboard JSON for debugging
                if keyboard and hasattr(keyboard, 'to_attachment'):
                    try:
                        import json
                        att = keyboard.to_attachment()
                        logger.debug("[Max send] edit_text keyboard attachment: %s", json.dumps(att, ensure_ascii=False))
                    except Exception as log_err:
                        logger.debug("[Max send] edit_text keyboard log error: %s", log_err)
                
                coro = self._bot.update_message(
                    message_id=str(msg_id),
                    text=formatted_text,
                    reply_markup=keyboard
                )
                result = await asyncio.wait_for(coro, timeout=DEFAULT_TIMEOUT)
                
                # Check response status and raise on error (e.g., invalid URL in buttons)
                self._log_max_response(result, "edit_text")
                
                return result
            
            # Fallback: try Message.edit() if available
            if hasattr(self._msg, 'edit'):
                coro = self._msg.edit(formatted_text, reply_markup=keyboard) if keyboard else self._msg.edit(formatted_text)
                return await asyncio.wait_for(coro, timeout=DEFAULT_TIMEOUT)
            
            logger.warning("[Max send] edit_text: no update_message or edit method available, msg_id=%s", msg_id)
            return None
        except asyncio.TimeoutError:
            logger.warning("[Max send] edit_text() timeout after %.1fs: chat_id=%s", DEFAULT_TIMEOUT, chat_id)
            return None
        except asyncio.CancelledError:
            return None
        except Exception as e:
            if "message is not modified" in str(e).lower():
                logger.debug("[Max send] edit_text: message not modified, ignoring")
                return None
            logger.exception("[Max send] edit_text() failed: chat_id=%s", chat_id)
            raise
    
    async def edit_reply_markup(
        self,
        reply_markup: Optional["KeyboardType"] = None,
        **kwargs: Any
    ) -> Any:
        """Edit message reply markup only (aiogram API compatibility).
        
        Args:
            reply_markup: New keyboard or None to remove
            **kwargs: Additional arguments
        """
        from obabot.adapters.keyboard import convert_keyboard_to_max
        
        keyboard = convert_keyboard_to_max(reply_markup) if reply_markup else None
        chat_id = self._chat_id_for_send()
        msg_id = self.message_id
        
        log_outgoing_message(
            chat_id=chat_id,
            text="[edit_reply_markup]",
            method="edit_reply_markup",
            has_keyboard=keyboard is not None,
        )
        
        try:
            if self._bot and hasattr(self._bot, 'update_message') and msg_id:
                logger.info("[Max send] edit_reply_markup via update_message: msg_id=%s", msg_id)
                # Max API requires text for update_message, use existing text
                existing_text = self.text or ""
                coro = self._bot.update_message(
                    message_id=str(msg_id),
                    text=existing_text,
                    reply_markup=keyboard
                )
                result = await asyncio.wait_for(coro, timeout=DEFAULT_TIMEOUT)
                self._log_max_response(result, "edit_reply_markup")
                return result
            
            logger.warning("[Max send] edit_reply_markup: no update_message available")
            return None
        except asyncio.TimeoutError:
            logger.warning("[Max send] edit_reply_markup() timeout")
            return None
        except asyncio.CancelledError:
            return None
        except Exception as e:
            if "message is not modified" in str(e).lower():
                logger.debug("[Max send] edit_reply_markup: not modified, ignoring")
                return None
            logger.exception("[Max send] edit_reply_markup() failed")
            raise
    
    async def edit_caption(
        self,
        caption: Optional[str] = None,
        reply_markup: Optional["KeyboardType"] = None,
        parse_mode: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """Edit media caption (aiogram API compatibility).
        
        Note: Max API may not support editing captions separately.
        This is a best-effort implementation.
        
        Args:
            caption: New caption text
            reply_markup: Optional keyboard
            parse_mode: Text format
            **kwargs: Additional arguments
        """
        # Max doesn't have separate caption editing, treat as edit_text
        formatted_caption = format_text_for_platform(caption, parse_mode, "max") if caption else ""
        return await self.edit_text(
            text=formatted_caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            **kwargs
        )
    
    async def edit_media(
        self,
        media: Any,
        reply_markup: Optional["KeyboardType"] = None,
        **kwargs: Any
    ) -> Any:
        """Edit media content (aiogram API compatibility).
        
        Note: Max API may not support editing media. This logs a warning.
        
        Args:
            media: New media
            reply_markup: Optional keyboard
            **kwargs: Additional arguments
        """
        logger.warning(
            "[Max send] edit_media: Max API doesn't support editing media content. "
            "Consider sending a new message instead."
        )
        return None
    
    async def delete(self, **kwargs: Any) -> Any:
        """Delete this message (aiogram API compatibility).
        
        Args:
            **kwargs: Additional arguments
        """
        msg_id = self.message_id
        chat_id = self._chat_id_for_send()
        
        log_outgoing_message(
            chat_id=chat_id,
            text="[DELETE]",
            method="delete",
        )
        
        try:
            if self._bot and msg_id:
                logger.info("[Max send] delete via bot.delete_message: msg_id=%s", msg_id)
                coro = delete_max_message(self._bot, msg_id)
                result = await asyncio.wait_for(coro, timeout=DEFAULT_TIMEOUT)
                self._log_max_response(result, "delete")
                return result
            
            if hasattr(self._msg, 'delete'):
                logger.info("[Max send] delete via msg.delete()")
                result = await asyncio.wait_for(self._msg.delete(), timeout=DEFAULT_TIMEOUT)
                self._log_max_response(result, "delete")
                return result
            
            logger.warning("[Max send] delete: no delete method available")
            return None
        except asyncio.TimeoutError:
            logger.warning("[Max send] delete() timeout")
            return None
        except asyncio.CancelledError:
            return None
        except Exception:
            logger.exception("[Max send] delete() failed")
            raise
    
    async def answer_photo(
        self,
        photo: Any,
        caption: Optional[str] = None,
        reply_markup: Optional["KeyboardType"] = None,
        parse_mode: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """Send photo to the same chat (aiogram API compatibility).
        
        Args:
            photo: Photo file path, URL, or file_id
            caption: Optional caption text
            reply_markup: Optional keyboard
            parse_mode: Text format for caption
            **kwargs: Additional arguments
        """
        from obabot.adapters.keyboard import convert_keyboard_to_max
        
        formatted_caption = format_text_for_platform(caption, parse_mode, "max") if caption else ""
        keyboard = convert_keyboard_to_max(reply_markup) if reply_markup else None
        chat_id = self._chat_id_for_send()
        
        log_outgoing_message(
            chat_id=chat_id,
            text=f"[PHOTO] {formatted_caption}" if formatted_caption else "[PHOTO]",
            method="answer_photo",
            has_keyboard=keyboard is not None,
            parse_mode=parse_mode,
        )
        
        if not self._bot or not hasattr(self._bot, 'send_file'):
            logger.error("[Max send] answer_photo: bot.send_file not available")
            raise NotImplementedError("Cannot send photo: bot.send_file not available")
        
        if not chat_id:
            logger.error("[Max send] answer_photo: chat_id is missing")
            raise ValueError("Cannot send photo: chat_id is missing")
        
        try:
            logger.info("[Max send] answer_photo via bot.send_file: chat_id=%s", chat_id)
            coro = self._bot.send_file(
                file_path=str(photo),
                media_type="image",
                chat_id=chat_id,
                text=formatted_caption,
                reply_markup=keyboard
            )
            result = await asyncio.wait_for(coro, timeout=DEFAULT_TIMEOUT)
            self._log_max_response(result, "answer_photo")
            return result
        except asyncio.TimeoutError:
            logger.warning("[Max send] answer_photo() timeout: chat_id=%s", chat_id)
            return None
        except asyncio.CancelledError:
            return None
        except Exception:
            logger.exception("[Max send] answer_photo() failed: chat_id=%s", chat_id)
            raise
    
    async def answer_document(
        self,
        document: Any,
        caption: Optional[str] = None,
        reply_markup: Optional["KeyboardType"] = None,
        parse_mode: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """Send document to the same chat (aiogram API compatibility).
        
        Args:
            document: Document file path, URL, or file_id
            caption: Optional caption text
            reply_markup: Optional keyboard
            parse_mode: Text format for caption
            **kwargs: Additional arguments
        """
        from obabot.adapters.keyboard import convert_keyboard_to_max
        
        formatted_caption = format_text_for_platform(caption, parse_mode, "max") if caption else ""
        keyboard = convert_keyboard_to_max(reply_markup) if reply_markup else None
        chat_id = self._chat_id_for_send()
        
        log_outgoing_message(
            chat_id=chat_id,
            text=f"[DOCUMENT] {formatted_caption}" if formatted_caption else "[DOCUMENT]",
            method="answer_document",
            has_keyboard=keyboard is not None,
            parse_mode=parse_mode,
        )
        
        if not self._bot or not hasattr(self._bot, 'send_file'):
            logger.error("[Max send] answer_document: bot.send_file not available")
            raise NotImplementedError("Cannot send document: bot.send_file not available")
        
        if not chat_id:
            logger.error("[Max send] answer_document: chat_id is missing")
            raise ValueError("Cannot send document: chat_id is missing")
        
        try:
            logger.info("[Max send] answer_document via bot.send_file: chat_id=%s", chat_id)
            coro = self._bot.send_file(
                file_path=str(document),
                media_type="file",
                chat_id=chat_id,
                text=formatted_caption,
                reply_markup=keyboard
            )
            result = await asyncio.wait_for(coro, timeout=DEFAULT_TIMEOUT)
            self._log_max_response(result, "answer_document")
            return result
        except asyncio.TimeoutError:
            logger.warning("[Max send] answer_document() timeout: chat_id=%s", chat_id)
            return None
        except asyncio.CancelledError:
            return None
        except Exception:
            logger.exception("[Max send] answer_document() failed: chat_id=%s", chat_id)
            raise
    
    async def answer_video(
        self,
        video: Any,
        caption: Optional[str] = None,
        reply_markup: Optional["KeyboardType"] = None,
        parse_mode: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """Send video to the same chat (aiogram API compatibility).
        
        Args:
            video: Video file path, URL, or file_id
            caption: Optional caption text
            reply_markup: Optional keyboard
            parse_mode: Text format for caption
            **kwargs: Additional arguments
        """
        from obabot.adapters.keyboard import convert_keyboard_to_max
        
        formatted_caption = format_text_for_platform(caption, parse_mode, "max") if caption else ""
        keyboard = convert_keyboard_to_max(reply_markup) if reply_markup else None
        chat_id = self._chat_id_for_send()
        
        log_outgoing_message(
            chat_id=chat_id,
            text=f"[VIDEO] {formatted_caption}" if formatted_caption else "[VIDEO]",
            method="answer_video",
            has_keyboard=keyboard is not None,
            parse_mode=parse_mode,
        )
        
        if not self._bot or not hasattr(self._bot, 'send_file'):
            logger.error("[Max send] answer_video: bot.send_file not available")
            raise NotImplementedError("Cannot send video: bot.send_file not available")
        
        if not chat_id:
            logger.error("[Max send] answer_video: chat_id is missing")
            raise ValueError("Cannot send video: chat_id is missing")
        
        try:
            logger.info("[Max send] answer_video via bot.send_file: chat_id=%s", chat_id)
            coro = self._bot.send_file(
                file_path=str(video),
                media_type="video",
                chat_id=chat_id,
                text=formatted_caption,
                reply_markup=keyboard
            )
            result = await asyncio.wait_for(coro, timeout=DEFAULT_TIMEOUT)
            self._log_max_response(result, "answer_video")
            return result
        except asyncio.TimeoutError:
            logger.warning("[Max send] answer_video() timeout: chat_id=%s", chat_id)
            return None
        except asyncio.CancelledError:
            return None
        except Exception:
            logger.exception("[Max send] answer_video() failed: chat_id=%s", chat_id)
            raise
    
    async def answer_audio(
        self,
        audio: Any,
        caption: Optional[str] = None,
        reply_markup: Optional["KeyboardType"] = None,
        parse_mode: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """Send audio to the same chat (aiogram API compatibility).
        
        Args:
            audio: Audio file path, URL, or file_id
            caption: Optional caption text
            reply_markup: Optional keyboard
            parse_mode: Text format for caption
            **kwargs: Additional arguments
        """
        from obabot.adapters.keyboard import convert_keyboard_to_max
        
        formatted_caption = format_text_for_platform(caption, parse_mode, "max") if caption else ""
        keyboard = convert_keyboard_to_max(reply_markup) if reply_markup else None
        chat_id = self._chat_id_for_send()
        
        log_outgoing_message(
            chat_id=chat_id,
            text=f"[AUDIO] {formatted_caption}" if formatted_caption else "[AUDIO]",
            method="answer_audio",
            has_keyboard=keyboard is not None,
            parse_mode=parse_mode,
        )
        
        if not self._bot or not hasattr(self._bot, 'send_file'):
            logger.error("[Max send] answer_audio: bot.send_file not available")
            raise NotImplementedError("Cannot send audio: bot.send_file not available")
        
        if not chat_id:
            logger.error("[Max send] answer_audio: chat_id is missing")
            raise ValueError("Cannot send audio: chat_id is missing")
        
        try:
            logger.info("[Max send] answer_audio via bot.send_file: chat_id=%s", chat_id)
            coro = self._bot.send_file(
                file_path=str(audio),
                media_type="audio",
                chat_id=chat_id,
                text=formatted_caption,
                reply_markup=keyboard
            )
            result = await asyncio.wait_for(coro, timeout=DEFAULT_TIMEOUT)
            self._log_max_response(result, "answer_audio")
            return result
        except asyncio.TimeoutError:
            logger.warning("[Max send] answer_audio() timeout: chat_id=%s", chat_id)
            return None
        except asyncio.CancelledError:
            return None
        except Exception:
            logger.exception("[Max send] answer_audio() failed: chat_id=%s", chat_id)
            raise
    
    async def answer_voice(
        self,
        voice: Any,
        caption: Optional[str] = None,
        reply_markup: Optional["KeyboardType"] = None,
        parse_mode: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """Send voice message to the same chat (aiogram API compatibility).
        
        Args:
            voice: Voice file path, URL, or file_id
            caption: Optional caption text
            reply_markup: Optional keyboard
            parse_mode: Text format for caption
            **kwargs: Additional arguments
        """
        from obabot.adapters.keyboard import convert_keyboard_to_max
        
        formatted_caption = format_text_for_platform(caption, parse_mode, "max") if caption else ""
        keyboard = convert_keyboard_to_max(reply_markup) if reply_markup else None
        chat_id = self._chat_id_for_send()
        
        log_outgoing_message(
            chat_id=chat_id,
            text=f"[VOICE] {formatted_caption}" if formatted_caption else "[VOICE]",
            method="answer_voice",
            has_keyboard=keyboard is not None,
            parse_mode=parse_mode,
        )
        
        if not self._bot or not hasattr(self._bot, 'send_file'):
            logger.error("[Max send] answer_voice: bot.send_file not available")
            raise NotImplementedError("Cannot send voice: bot.send_file not available")
        
        if not chat_id:
            logger.error("[Max send] answer_voice: chat_id is missing")
            raise ValueError("Cannot send voice: chat_id is missing")
        
        try:
            logger.info("[Max send] answer_voice via bot.send_file: chat_id=%s", chat_id)
            coro = self._bot.send_file(
                file_path=str(voice),
                media_type="voice",
                chat_id=chat_id,
                text=formatted_caption,
                reply_markup=keyboard
            )
            result = await asyncio.wait_for(coro, timeout=DEFAULT_TIMEOUT)
            self._log_max_response(result, "answer_voice")
            return result
        except asyncio.TimeoutError:
            logger.warning("[Max send] answer_voice() timeout: chat_id=%s", chat_id)
            return None
        except asyncio.CancelledError:
            return None
        except Exception:
            logger.exception("[Max send] answer_voice() failed: chat_id=%s", chat_id)
            raise
    
    async def answer_sticker(
        self,
        sticker: Any,
        reply_markup: Optional["KeyboardType"] = None,
        **kwargs: Any
    ) -> Any:
        """Send sticker to the same chat (aiogram API compatibility).
        
        Args:
            sticker: Sticker file path, URL, or file_id
            reply_markup: Optional keyboard
            **kwargs: Additional arguments
        """
        from obabot.adapters.keyboard import convert_keyboard_to_max
        
        keyboard = convert_keyboard_to_max(reply_markup) if reply_markup else None
        chat_id = self._chat_id_for_send()
        
        log_outgoing_message(
            chat_id=chat_id,
            text="[STICKER]",
            method="answer_sticker",
            has_keyboard=keyboard is not None,
        )
        
        if not self._bot or not hasattr(self._bot, 'send_file'):
            logger.error("[Max send] answer_sticker: bot.send_file not available")
            raise NotImplementedError("Cannot send sticker: bot.send_file not available")
        
        if not chat_id:
            logger.error("[Max send] answer_sticker: chat_id is missing")
            raise ValueError("Cannot send sticker: chat_id is missing")
        
        try:
            logger.info("[Max send] answer_sticker via bot.send_file: chat_id=%s", chat_id)
            coro = self._bot.send_file(
                file_path=str(sticker),
                media_type="sticker",
                chat_id=chat_id,
                reply_markup=keyboard
            )
            result = await asyncio.wait_for(coro, timeout=DEFAULT_TIMEOUT)
            self._log_max_response(result, "answer_sticker")
            return result
        except asyncio.TimeoutError:
            logger.warning("[Max send] answer_sticker() timeout: chat_id=%s", chat_id)
            return None
        except asyncio.CancelledError:
            return None
        except Exception:
            logger.exception("[Max send] answer_sticker() failed: chat_id=%s", chat_id)
            raise
    
    async def answer_animation(
        self,
        animation: Any,
        caption: Optional[str] = None,
        reply_markup: Optional["KeyboardType"] = None,
        parse_mode: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """Send animation/GIF to the same chat (aiogram API compatibility).
        
        Args:
            animation: Animation file path, URL, or file_id
            caption: Optional caption text
            reply_markup: Optional keyboard
            parse_mode: Text format for caption
            **kwargs: Additional arguments
        """
        from obabot.adapters.keyboard import convert_keyboard_to_max
        
        formatted_caption = format_text_for_platform(caption, parse_mode, "max") if caption else ""
        keyboard = convert_keyboard_to_max(reply_markup) if reply_markup else None
        chat_id = self._chat_id_for_send()
        
        log_outgoing_message(
            chat_id=chat_id,
            text=f"[ANIMATION] {formatted_caption}" if formatted_caption else "[ANIMATION]",
            method="answer_animation",
            has_keyboard=keyboard is not None,
            parse_mode=parse_mode,
        )
        
        if not self._bot or not hasattr(self._bot, 'send_file'):
            logger.error("[Max send] answer_animation: bot.send_file not available")
            raise NotImplementedError("Cannot send animation: bot.send_file not available")
        
        if not chat_id:
            logger.error("[Max send] answer_animation: chat_id is missing")
            raise ValueError("Cannot send animation: chat_id is missing")
        
        try:
            logger.info("[Max send] answer_animation via bot.send_file: chat_id=%s", chat_id)
            # Max may use "video" or "gif" for animations
            coro = self._bot.send_file(
                file_path=str(animation),
                media_type="video",  # Max uses video for GIFs
                chat_id=chat_id,
                text=formatted_caption,
                reply_markup=keyboard
            )
            result = await asyncio.wait_for(coro, timeout=DEFAULT_TIMEOUT)
            self._log_max_response(result, "answer_animation")
            return result
        except asyncio.TimeoutError:
            logger.warning("[Max send] answer_animation() timeout: chat_id=%s", chat_id)
            return None
        except asyncio.CancelledError:
            return None
        except Exception:
            logger.exception("[Max send] answer_animation() failed: chat_id=%s", chat_id)
            raise
    
    async def forward(
        self,
        chat_id: Any,
        **kwargs: Any
    ) -> Any:
        """Forward this message to another chat (aiogram API compatibility).
        
        Note: Max API may not support message forwarding directly.
        This is a best-effort implementation.
        
        Args:
            chat_id: Target chat ID
            **kwargs: Additional arguments
        """
        msg_id = self.message_id
        
        log_outgoing_message(
            chat_id=chat_id,
            text=f"[FORWARD from {self._chat_id_for_send()}]",
            method="forward",
        )
        
        try:
            if self._bot and hasattr(self._bot, 'forward_message') and msg_id:
                logger.info("[Max send] forward via bot.forward_message: msg_id=%s -> chat_id=%s", msg_id, chat_id)
                coro = self._bot.forward_message(
                    chat_id=chat_id,
                    from_chat_id=self._chat_id_for_send(),
                    message_id=str(msg_id)
                )
                result = await asyncio.wait_for(coro, timeout=DEFAULT_TIMEOUT)
                self._log_max_response(result, "forward")
                return result
            
            # Fallback: copy message content
            logger.warning(
                "[Max send] forward: bot.forward_message not available, "
                "consider using copy_to() instead"
            )
            return None
        except asyncio.TimeoutError:
            logger.warning("[Max send] forward() timeout")
            return None
        except asyncio.CancelledError:
            return None
        except Exception:
            logger.exception("[Max send] forward() failed")
            raise
    
    async def set_state(self, state: Any) -> None:
        """Set FSM state."""
        if hasattr(self._msg, 'set_state'):
            await self._msg.set_state(state)
    
    async def get_state(self) -> Any:
        """Get FSM state."""
        if hasattr(self._msg, 'get_state'):
            return await self._msg.get_state()
        return None
    
    async def reset_state(self) -> None:
        """Reset FSM state."""
        if hasattr(self._msg, 'reset_state'):
            await self._msg.reset_state()
    
    async def update_data(self, **data: Any) -> None:
        """Update FSM data."""
        if hasattr(self._msg, 'update_data'):
            await self._msg.update_data(**data)
    
    async def get_data(self) -> dict:
        """Get FSM data."""
        if hasattr(self._msg, 'get_data'):
            return await self._msg.get_data()
        return {}
    
    def __getattr__(self, name: str) -> Any:
        """Proxy any other attribute to the underlying message."""
        return getattr(self._msg, name)
