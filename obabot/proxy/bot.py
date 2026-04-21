"""Proxy bot that manages multiple platform bots."""

import io
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING, Protocol, runtime_checkable

import httpx

from obabot.config import log_outgoing_message
from obabot.context import get_current_platform
from obabot.types import BPlatform
from obabot.utils.max_api import delete_max_message

if TYPE_CHECKING:
    from aiogram.types import File as TelegramFile

logger = logging.getLogger(__name__)


@runtime_checkable
class DownloadableFile(Protocol):
    """Protocol for file objects that can be downloaded (aiogram-style).
    
    ProxyFile and aiogram.types.File implement this interface.
    
    Usage:
        content = await f.download()                    # bytes
        await f.download(destination=buffer)            # write to buffer
        await f.download(destination="path.txt")        # save to disk
    """
    
    file_id: Optional[str]
    file_path: Optional[str]
    file_size: Optional[int]
    
    async def download(
        self,
        destination: Optional[Union[io.IOBase, str, Path]] = None,
        **kwargs: Any
    ) -> Optional[bytes]:
        """Download: None/bytes if destination is None; write to destination and return None otherwise."""
        ...


class ProxyFile:
    """Unified file object for both Telegram and Max (aiogram-style API).
    
    For Telegram: wraps aiogram File (accessible via .native).
    For Max: wraps attachment URL.
    
    Usage (same as aiogram.types.File):
        f = await bot.get_file(file_id)
        content = await f.download()                      # returns bytes
        await f.download(destination=buffer)              # write to BytesIO/buffer
        await f.download(destination="path.txt")          # save to disk (str or Path)
    """
    
    def __init__(
        self,
        platform: BPlatform,
        file_id: Optional[str] = None,
        file_url: Optional[str] = None,
        file_path: Optional[str] = None,
        file_size: Optional[int] = None,
        bot: Any = None,
        _telegram_file: Any = None,
        suggested_filename: Optional[str] = None,
    ):
        self.platform = platform
        self.file_id = file_id
        self.file_url = file_url
        self.file_path = file_path
        self.file_size = file_size
        self._bot = bot
        self._telegram_file = _telegram_file
        self._suggested_filename = suggested_filename
    
    def get_platform(self) -> str:
        """Get the platform identifier as string."""
        if isinstance(self.platform, BPlatform):
            return self.platform.value
        return str(self.platform) if self.platform else ''
    
    def is_telegram(self) -> bool:
        """Check if this is a Telegram platform object."""
        return self.platform == BPlatform.telegram
    
    def is_max(self) -> bool:
        """Check if this is a Max platform object."""
        return self.platform == BPlatform.max
    
    @property
    def native(self) -> Optional["TelegramFile"]:
        """Access the native platform file object.
        
        For Telegram: Returns aiogram.types.File
        For Max: Returns None (Max uses URLs directly)
        
        Use this when you need platform-specific functionality
        that ProxyFile doesn't expose.
        """
        return self._telegram_file
    
    @property
    def file_name(self) -> str:
        """Suggested filename. Telegram: from file_path; Max: from server headers or URL path."""
        if getattr(self, "_suggested_filename", None):
            return self._suggested_filename
        if self.platform == BPlatform.telegram and self.file_path:
            return Path(self.file_path).name
        from obabot.adapters.max_file import _url_basename_is_getfile, fetch_filename_from_max_url_sync, filename_from_max_url
        if self.file_url and _url_basename_is_getfile(self.file_url):
            name = fetch_filename_from_max_url_sync(self.file_url)
            if name:
                return name
            return "file.bin"
        return filename_from_max_url(self.file_url)
    
    async def download(
        self,
        destination: Optional[Union[io.IOBase, str, Path]] = None,
        timeout: float = 60.0
    ) -> Optional[bytes]:
        """Download file (aiogram-style).
        
        Args:
            destination: None (return bytes), path (str/Path) to save to disk, or BinaryIO to write to.
            timeout: Download timeout in seconds.

        Returns:
            bytes if destination is None, else None.
        """
        if destination is not None and not isinstance(destination, io.IOBase):
            # Path or str -> save to file (fetch first so Max gets filename from Content-Disposition)
            content = await self._download_raw(None, timeout)
            if content is None:
                raise ValueError("Cannot download file: no content")
            path = Path(destination)
            if path.is_dir():
                path = path / self.file_name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            return None
        return await self._download_raw(destination, timeout)
    
    async def _download_raw(
        self,
        destination: Optional[io.IOBase],
        timeout: float
    ) -> Optional[bytes]:
        """Internal: download to buffer or return bytes."""
        if self.platform == BPlatform.telegram:
            return await self._download_telegram(destination, timeout)
        return await self._download_max(destination, timeout)
    
    async def _download_telegram(
        self,
        destination: Optional[io.IOBase],
        timeout: float
    ) -> Optional[bytes]:
        """Download file from Telegram."""
        if self._telegram_file and hasattr(self._telegram_file, 'download'):
            # Use aiogram's download method
            if destination:
                await self._telegram_file.download(destination=destination)
                return None
            else:
                buffer = io.BytesIO()
                await self._telegram_file.download(destination=buffer)
                return buffer.getvalue()
        
        # Fallback: download via bot
        if self._bot and self.file_path:
            file_url = f"https://api.telegram.org/file/bot{self._bot.token}/{self.file_path}"
            return await self._download_from_url(file_url, destination, timeout)
        
        raise ValueError("Cannot download Telegram file: no file object or path available")
    
    async def _download_max(
        self,
        destination: Optional[io.IOBase],
        timeout: float
    ) -> Optional[bytes]:
        """Download file from Max (delegates to adapters.max_file)."""
        if not self.file_url:
            raise ValueError("Cannot download Max file: no URL available")
        from obabot.adapters.max_file import download_max_file
        content, cd_filename = await download_max_file(self.file_url, destination, timeout)
        if cd_filename:
            self._suggested_filename = cd_filename
        return content
    
    async def _download_from_url(
        self,
        url: str,
        destination: Optional[io.IOBase],
        timeout: float
    ) -> Optional[bytes]:
        """Download file from URL (Telegram fallback)."""
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.content
            if destination:
                destination.write(content)
                return None
            return content
    
    def __repr__(self) -> str:
        return (
            f"ProxyFile(platform={self.platform}, file_id={self.file_id}, "
            f"file_url={self.file_url[:50] + '...' if self.file_url and len(self.file_url) > 50 else self.file_url})"
        )


def _convert_to_input_file(file: Any) -> Any:
    """Convert file to InputFile if needed for aiogram compatibility.
    
    Accepts:
    - str (file path, URL, or file_id) - passed through
    - BufferedReader/BytesIO - wrapped in InputFile
    - InputFile - passed through
    """
    # Check if already InputFile or string
    if isinstance(file, str):
        return file
    
    # Check if it's a file-like object (BufferedReader, BytesIO, etc.)
    if isinstance(file, (io.BufferedReader, io.BytesIO, io.BufferedIOBase)):
        try:
            from aiogram.types import BufferedInputFile, FSInputFile
            
            # Read content and create BufferedInputFile
            if hasattr(file, 'name'):
                filename = getattr(file, 'name', 'file')
                if isinstance(filename, str):
                    filename = filename.split('/')[-1].split('\\')[-1]
                else:
                    filename = 'file'
            else:
                filename = 'file'
            
            content = file.read()
            # Reset position if possible
            if hasattr(file, 'seek'):
                file.seek(0)
            
            return BufferedInputFile(content, filename=filename)
        except ImportError:
            # aiogram not available, return as-is
            return file
    
    # Return as-is for other types (InputFile, etc.)
    return file


def _get_file_path(file: Any) -> str:
    """Extract file path from various file types for Max API.
    
    Max API requires a file path string.
    """
    if isinstance(file, str):
        return file
    
    # BufferedReader has .name attribute with file path
    if hasattr(file, 'name'):
        name = getattr(file, 'name', None)
        if isinstance(name, str):
            return name
    
    # aiogram InputFile types
    if hasattr(file, 'path'):
        return str(getattr(file, 'path'))
    
    raise ValueError(f"Cannot extract file path from {type(file).__name__}. Max API requires file path.")

if TYPE_CHECKING:
    from obabot.platforms.base import BasePlatform


class ProxyBot:
    """
    Bot proxy that manages bots for multiple platforms.
    
    Provides a unified interface for sending messages across platforms.
    For platform-specific operations, use get_bot(platform) to access
    the underlying bot instance.
    
    Usage:
        # Send to specific chat (works on single-platform setup)
        await bot.send_message(chat_id, "Hello!")
        
        # Get platform-specific bot
        tg_bot = bot.get_bot(BPlatform.telegram)
        await tg_bot.send_photo(chat_id, photo)
    """
    
    def __init__(self, platforms: List["BasePlatform"]):
        """
        Initialize proxy bot.
        
        Args:
            platforms: List of platform instances
        """
        self._platforms = platforms
        self._platform_map: Dict[BPlatform, "BasePlatform"] = {
            p.platform: p for p in platforms
        }
    
    def get_bot(self, platform: Union[BPlatform, str]) -> Any:
        """
        Get the underlying bot for a specific platform.
        
        Args:
            platform: Platform type or string ("telegram", "max")
            
        Returns:
            The platform's native bot instance
        """
        if isinstance(platform, str):
            platform = BPlatform(platform)
        
        if platform not in self._platform_map:
            available = list(self._platform_map.keys())
            raise ValueError(
                f"Platform {platform} not configured. Available: {available}"
            )
        
        return self._platform_map[platform].bot
    
    @property
    def platforms(self) -> List[BPlatform]:
        """List of configured platforms."""
        return list(self._platform_map.keys())
    
    @property
    def is_multi_platform(self) -> bool:
        """Whether multiple platforms are configured."""
        return len(self._platforms) > 1
    
    # Proxy methods for single-platform compatibility
    
    async def send_message(
        self,
        chat_id: int,
        text: str,
        platform: Optional[Union[BPlatform, str]] = None,
        **kwargs: Any
    ) -> Any:
        """
        Send a text message.
        
        Args:
            chat_id: Target chat ID
            text: Message text
            platform: Target platform (optional if single platform)
            **kwargs: Additional arguments passed to platform bot
        """
        log_outgoing_message(
            platform=str(platform) if platform else None,
            chat_id=chat_id,
            text=text,
            method="send_message",
            has_keyboard="reply_markup" in kwargs,
            parse_mode=kwargs.get("parse_mode"),
        )
        bot = self._get_bot_for_operation(platform)
        return await bot.send_message(chat_id=chat_id, text=text, **kwargs)
    
    async def send_photo(
        self,
        chat_id: int,
        photo: Any,
        platform: Optional[Union[BPlatform, str]] = None,
        caption: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """Send a photo.
        
        Accepts file path, URL, file_id, BufferedReader, or InputFile.
        Works on both Telegram (send_photo) and Max (send_file with media_type="image").
        """
        resolved_platform = self._resolve_platform_for_operation(platform)
        bot = self._get_bot_for_operation(platform)
        
        if resolved_platform == BPlatform.max:
            # Max uses send_file with media_type
            file_path = _get_file_path(photo)
            return await bot.send_file(
                file_path=file_path,
                media_type="image",
                chat_id=chat_id,
                text=caption or "",
                reply_markup=kwargs.get("reply_markup"),
            )
        else:
            # Telegram uses send_photo
            photo = _convert_to_input_file(photo)
            return await bot.send_photo(chat_id=chat_id, photo=photo, caption=caption, **kwargs)
    
    async def send_document(
        self,
        chat_id: int,
        document: Any,
        platform: Optional[Union[BPlatform, str]] = None,
        caption: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """Send a document.
        
        Accepts file path, URL, file_id, BufferedReader, or InputFile.
        Works on both Telegram (send_document) and Max (send_file with media_type="file").
        """
        resolved_platform = self._resolve_platform_for_operation(platform)
        bot = self._get_bot_for_operation(platform)
        
        if resolved_platform == BPlatform.max:
            file_path = _get_file_path(document)
            return await bot.send_file(
                file_path=file_path,
                media_type="file",
                chat_id=chat_id,
                text=caption or "",
                reply_markup=kwargs.get("reply_markup"),
            )
        else:
            document = _convert_to_input_file(document)
            return await bot.send_document(chat_id=chat_id, document=document, caption=caption, **kwargs)
    
    async def send_video(
        self,
        chat_id: int,
        video: Any,
        platform: Optional[Union[BPlatform, str]] = None,
        caption: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """Send a video."""
        resolved_platform = self._resolve_platform_for_operation(platform)
        bot = self._get_bot_for_operation(platform)
        
        if resolved_platform == BPlatform.max:
            file_path = _get_file_path(video)
            return await bot.send_file(
                file_path=file_path,
                media_type="video",
                chat_id=chat_id,
                text=caption or "",
                reply_markup=kwargs.get("reply_markup"),
            )
        else:
            video = _convert_to_input_file(video)
            return await bot.send_video(chat_id=chat_id, video=video, caption=caption, **kwargs)
    
    async def send_audio(
        self,
        chat_id: int,
        audio: Any,
        platform: Optional[Union[BPlatform, str]] = None,
        caption: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """Send an audio file."""
        resolved_platform = self._resolve_platform_for_operation(platform)
        bot = self._get_bot_for_operation(platform)
        
        if resolved_platform == BPlatform.max:
            file_path = _get_file_path(audio)
            return await bot.send_file(
                file_path=file_path,
                media_type="audio",
                chat_id=chat_id,
                text=caption or "",
                reply_markup=kwargs.get("reply_markup"),
            )
        else:
            audio = _convert_to_input_file(audio)
            return await bot.send_audio(chat_id=chat_id, audio=audio, caption=caption, **kwargs)
    
    async def send_sticker(
        self,
        chat_id: int,
        sticker: Any,
        platform: Optional[Union[BPlatform, str]] = None,
        **kwargs: Any
    ) -> Any:
        """Send a sticker."""
        resolved_platform = self._resolve_platform_for_operation(platform)
        bot = self._get_bot_for_operation(platform)
        
        if resolved_platform == BPlatform.max:
            # Max may not support stickers, use as file
            file_path = _get_file_path(sticker)
            return await bot.send_file(
                file_path=file_path,
                media_type="file",
                chat_id=chat_id,
                reply_markup=kwargs.get("reply_markup"),
            )
        else:
            sticker = _convert_to_input_file(sticker)
            return await bot.send_sticker(chat_id=chat_id, sticker=sticker, **kwargs)
    
    async def send_voice(
        self,
        chat_id: int,
        voice: Any,
        platform: Optional[Union[BPlatform, str]] = None,
        caption: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """Send a voice message."""
        resolved_platform = self._resolve_platform_for_operation(platform)
        bot = self._get_bot_for_operation(platform)
        
        if resolved_platform == BPlatform.max:
            file_path = _get_file_path(voice)
            return await bot.send_file(
                file_path=file_path,
                media_type="audio",
                chat_id=chat_id,
                text=caption or "",
                reply_markup=kwargs.get("reply_markup"),
            )
        else:
            voice = _convert_to_input_file(voice)
            return await bot.send_voice(chat_id=chat_id, voice=voice, caption=caption, **kwargs)
    
    async def send_video_note(
        self,
        chat_id: int,
        video_note: Any,
        platform: Optional[Union[BPlatform, str]] = None,
        **kwargs: Any
    ) -> Any:
        """Send a video note (circular video)."""
        resolved_platform = self._resolve_platform_for_operation(platform)
        bot = self._get_bot_for_operation(platform)
        
        if resolved_platform == BPlatform.max:
            file_path = _get_file_path(video_note)
            return await bot.send_file(
                file_path=file_path,
                media_type="video",
                chat_id=chat_id,
                reply_markup=kwargs.get("reply_markup"),
            )
        else:
            video_note = _convert_to_input_file(video_note)
            return await bot.send_video_note(chat_id=chat_id, video_note=video_note, **kwargs)
    
    async def send_animation(
        self,
        chat_id: int,
        animation: Any,
        platform: Optional[Union[BPlatform, str]] = None,
        caption: Optional[str] = None,
        **kwargs: Any
    ) -> Any:
        """Send an animation (GIF)."""
        resolved_platform = self._resolve_platform_for_operation(platform)
        bot = self._get_bot_for_operation(platform)
        
        if resolved_platform == BPlatform.max:
            file_path = _get_file_path(animation)
            return await bot.send_file(
                file_path=file_path,
                media_type="video",  # GIF is sent as video
                chat_id=chat_id,
                text=caption or "",
                reply_markup=kwargs.get("reply_markup"),
            )
        else:
            animation = _convert_to_input_file(animation)
            return await bot.send_animation(chat_id=chat_id, animation=animation, caption=caption, **kwargs)
    
    async def send_location(
        self,
        chat_id: int,
        latitude: float,
        longitude: float,
        platform: Optional[Union[BPlatform, str]] = None,
        **kwargs: Any
    ) -> Any:
        """Send a location."""
        bot = self._get_bot_for_operation(platform)
        return await bot.send_location(
            chat_id=chat_id,
            latitude=latitude,
            longitude=longitude,
            **kwargs
        )
    
    async def send_contact(
        self,
        chat_id: int,
        phone_number: str,
        first_name: str,
        platform: Optional[Union[BPlatform, str]] = None,
        **kwargs: Any
    ) -> Any:
        """Send a contact."""
        bot = self._get_bot_for_operation(platform)
        return await bot.send_contact(
            chat_id=chat_id,
            phone_number=phone_number,
            first_name=first_name,
            **kwargs
        )
    
    async def send_poll(
        self,
        chat_id: int,
        question: str,
        options: list[str],
        platform: Optional[Union[BPlatform, str]] = None,
        **kwargs: Any
    ) -> Any:
        """Send a poll."""
        bot = self._get_bot_for_operation(platform)
        return await bot.send_poll(
            chat_id=chat_id,
            question=question,
            options=options,
            **kwargs
        )
    
    async def forward_message(
        self,
        chat_id: int,
        from_chat_id: int,
        message_id: int,
        platform: Optional[Union[BPlatform, str]] = None,
        **kwargs: Any
    ) -> Any:
        """Forward a message."""
        bot = self._get_bot_for_operation(platform)
        return await bot.forward_message(
            chat_id=chat_id,
            from_chat_id=from_chat_id,
            message_id=message_id,
            **kwargs
        )
    
    async def copy_message(
        self,
        chat_id: int,
        from_chat_id: int,
        message_id: int,
        platform: Optional[Union[BPlatform, str]] = None,
        **kwargs: Any
    ) -> Any:
        """Copy a message."""
        bot = self._get_bot_for_operation(platform)
        return await bot.copy_message(
            chat_id=chat_id,
            from_chat_id=from_chat_id,
            message_id=message_id,
            **kwargs
        )
    
    async def pin_message(
        self,
        chat_id: int,
        message_id: int,
        platform: Optional[Union[BPlatform, str]] = None,
        **kwargs: Any
    ) -> bool:
        """Pin a message."""
        bot = self._get_bot_for_operation(platform)
        return await bot.pin_chat_message(
            chat_id=chat_id,
            message_id=message_id,
            **kwargs
        )
    
    async def unpin_message(
        self,
        chat_id: int,
        message_id: Optional[int] = None,
        platform: Optional[Union[BPlatform, str]] = None,
        **kwargs: Any
    ) -> bool:
        """Unpin a message (or all messages if message_id is None)."""
        bot = self._get_bot_for_operation(platform)
        if message_id is None:
            return await bot.unpin_all_chat_messages(chat_id=chat_id, **kwargs)
        return await bot.unpin_chat_message(chat_id=chat_id, message_id=message_id, **kwargs)
    
    async def get_chat(
        self,
        chat_id: int,
        platform: Optional[Union[BPlatform, str]] = None
    ) -> Any:
        """Get information about a chat."""
        bot = self._get_bot_for_operation(platform)
        return await bot.get_chat(chat_id=chat_id)
    
    async def get_chat_member(
        self,
        chat_id: int,
        user_id: int,
        platform: Optional[Union[BPlatform, str]] = None
    ) -> Any:
        """Get information about a member of a chat."""
        bot = self._get_bot_for_operation(platform)
        return await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
    
    async def get_chat_members_count(
        self,
        chat_id: int,
        platform: Optional[Union[BPlatform, str]] = None
    ) -> int:
        """Get the number of members in a chat."""
        bot = self._get_bot_for_operation(platform)
        # Try get_chat_members_count first, fallback to get_chat
        try:
            return await bot.get_chat_members_count(chat_id=chat_id)
        except AttributeError:
            chat = await bot.get_chat(chat_id=chat_id)
            return getattr(chat, 'members_count', 0)
    
    async def send_dice(
        self,
        chat_id: int,
        emoji: Optional[str] = None,
        platform: Optional[Union[BPlatform, str]] = None,
        **kwargs: Any
    ) -> Any:
        """Send a dice (random value)."""
        bot = self._get_bot_for_operation(platform)
        if emoji:
            return await bot.send_dice(chat_id=chat_id, emoji=emoji, **kwargs)
        return await bot.send_dice(chat_id=chat_id, **kwargs)
    
    async def send_venue(
        self,
        chat_id: int,
        latitude: float,
        longitude: float,
        title: str,
        address: str,
        platform: Optional[Union[BPlatform, str]] = None,
        **kwargs: Any
    ) -> Any:
        """Send a venue (location with name and address)."""
        bot = self._get_bot_for_operation(platform)
        return await bot.send_venue(
            chat_id=chat_id,
            latitude=latitude,
            longitude=longitude,
            title=title,
            address=address,
            **kwargs
        )
    
    async def unpin_all_chat_messages(
        self,
        chat_id: int,
        platform: Optional[Union[BPlatform, str]] = None,
        **kwargs: Any
    ) -> bool:
        """Unpin all messages in a chat."""
        bot = self._get_bot_for_operation(platform)
        return await bot.unpin_all_chat_messages(chat_id=chat_id, **kwargs)
    
    async def get_chat_administrators(
        self,
        chat_id: int,
        platform: Optional[Union[BPlatform, str]] = None
    ) -> list:
        """Get a list of administrators in a chat."""
        bot = self._get_bot_for_operation(platform)
        return await bot.get_chat_administrators(chat_id=chat_id)
    
    async def leave_chat(
        self,
        chat_id: int,
        platform: Optional[Union[BPlatform, str]] = None,
        **kwargs: Any
    ) -> bool:
        """Leave a group, supergroup or channel."""
        bot = self._get_bot_for_operation(platform)
        return await bot.leave_chat(chat_id=chat_id, **kwargs)
    
    async def get_chat_member_count(
        self,
        chat_id: int,
        platform: Optional[Union[BPlatform, str]] = None
    ) -> int:
        """Get the number of members in a chat (alias for get_chat_members_count)."""
        return await self.get_chat_members_count(chat_id=chat_id, platform=platform)
    
    async def edit_message_text(
        self,
        text: str,
        chat_id: Optional[int] = None,
        message_id: Optional[int] = None,
        platform: Optional[Union[BPlatform, str]] = None,
        **kwargs: Any
    ) -> Any:
        """Edit message text.
        
        Automatically ignores "message is not modified" error from Telegram.
        """
        log_outgoing_message(
            platform=str(platform) if platform else None,
            chat_id=chat_id,
            text=text,
            method="edit_text",
            has_keyboard="reply_markup" in kwargs,
            parse_mode=kwargs.get("parse_mode"),
        )
        bot = self._get_bot_for_operation(platform)
        try:
            return await bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=message_id,
                **kwargs
            )
        except Exception as e:
            if "message is not modified" in str(e).lower():
                logger.debug("edit_message_text: message not modified, ignoring")
                return None
            raise
    
    async def edit_message_caption(
        self,
        caption: Optional[str] = None,
        chat_id: Optional[int] = None,
        message_id: Optional[int] = None,
        platform: Optional[Union[BPlatform, str]] = None,
        **kwargs: Any
    ) -> Any:
        """Edit message caption.
        
        Automatically ignores "message is not modified" error from Telegram.
        """
        bot = self._get_bot_for_operation(platform)
        try:
            return await bot.edit_message_caption(
                caption=caption,
                chat_id=chat_id,
                message_id=message_id,
                **kwargs
            )
        except Exception as e:
            if "message is not modified" in str(e).lower():
                logger.debug("edit_message_caption: message not modified, ignoring")
                return None
            raise
    
    async def edit_message_media(
        self,
        media: Any,
        chat_id: Optional[int] = None,
        message_id: Optional[int] = None,
        platform: Optional[Union[BPlatform, str]] = None,
        **kwargs: Any
    ) -> Any:
        """Edit message media.
        
        Automatically ignores "message is not modified" error from Telegram.
        """
        bot = self._get_bot_for_operation(platform)
        try:
            return await bot.edit_message_media(
                media=media,
                chat_id=chat_id,
                message_id=message_id,
                **kwargs
            )
        except Exception as e:
            if "message is not modified" in str(e).lower():
                logger.debug("edit_message_media: message not modified, ignoring")
                return None
            raise
    
    async def edit_message_reply_markup(
        self,
        reply_markup: Optional[Any] = None,
        chat_id: Optional[int] = None,
        message_id: Optional[int] = None,
        platform: Optional[Union[BPlatform, str]] = None,
        **kwargs: Any
    ) -> Any:
        """Edit message reply markup (keyboard).
        
        Automatically ignores "message is not modified" error from Telegram.
        """
        bot = self._get_bot_for_operation(platform)
        try:
            return await bot.edit_message_reply_markup(
                reply_markup=reply_markup,
                chat_id=chat_id,
                message_id=message_id,
                **kwargs
            )
        except Exception as e:
            if "message is not modified" in str(e).lower():
                logger.debug("edit_message_reply_markup: message not modified, ignoring")
                return None
            raise
    
    async def delete_message(
        self,
        chat_id: int,
        message_id: int,
        platform: Optional[Union[BPlatform, str]] = None,
    ) -> bool:
        """Delete a message."""
        resolved_platform = self._resolve_platform_for_operation(platform)
        bot = self._get_bot_for_operation(platform)
        if resolved_platform == BPlatform.max:
            await delete_max_message(bot, message_id)
            return True
        return await bot.delete_message(chat_id=chat_id, message_id=message_id)
    
    async def get_me(
        self,
        platform: Optional[Union[BPlatform, str]] = None
    ) -> Any:
        """Get bot information."""
        bot = self._get_bot_for_operation(platform)
        return await bot.get_me()
    
    async def get_file(
        self,
        file_id: str,
        platform: Optional[Union[BPlatform, str]] = None,
        suggested_filename: Optional[str] = None,
    ) -> ProxyFile:
        """Get file information and download link.
        
        Returns a unified ProxyFile object with download() method that works
        for both Telegram and Max platforms.
        
        Args:
            file_id: For Telegram - file_id from message
                    For Max - direct URL to the file (from attachment.url)
            platform: Target platform (optional, auto-detected from context)
            suggested_filename: For Max, use this as .file_name until server sends Content-Disposition (e.g. message.document.file_name)
            
        Returns:
            ProxyFile object with .file_name and download() method
            
        Usage:
            # Max: pass attachment file_name so saved file has correct name (not "getfile")
            doc = message.document
            f = await bot.get_file(doc.file_id, platform="max", suggested_filename=doc.file_name)
            await f.download(destination="downloads/")
        """
        resolved_platform = self._resolve_platform_for_operation(platform)
        bot = self._get_bot_for_operation(platform)
        
        if resolved_platform == BPlatform.max:
            from obabot.adapters.max_file import MaxFileFilenameError, fetch_filename_from_max_url
            head_filename = await fetch_filename_from_max_url(file_id)
            name = suggested_filename or head_filename
            if name is None:
                raise MaxFileFilenameError(
                    file_id,
                    "Max file filename unknown (server sent no Content-Disposition/Content-Type). "
                    "Pass suggested_filename= to get_file(), e.g. get_file(url, platform='max', suggested_filename='document.pdf')."
                )
            return ProxyFile(
                platform=BPlatform.max,
                file_id=file_id,
                file_url=file_id,
                bot=bot,
                suggested_filename=name,
            )
        
        # Telegram: get file info from API
        tg_file = await bot.get_file(file_id)
        return ProxyFile(
            platform=BPlatform.telegram,
            file_id=file_id,
            file_path=tg_file.file_path,
            file_size=tg_file.file_size,
            bot=bot,
            _telegram_file=tg_file,
        )
    
    async def download_file(
        self,
        file_id: str,
        destination: Optional[Union[io.IOBase, str, Path]] = None,
        platform: Optional[Union[BPlatform, str]] = None,
        timeout: float = 60.0
    ) -> Optional[bytes]:
        """Download file directly (aiogram-style: get_file + download in one call).
        
        Args:
            file_id: Telegram file_id or Max attachment URL.
            destination: None (return bytes), path (str/Path), or BinaryIO.
            platform: Target platform (optional, auto-detected from context).
            timeout: Download timeout in seconds.
            
        Returns:
            bytes if destination is None, else None.
            
        Usage:
            content = await bot.download_file(file_id)
            await bot.download_file(file_id, destination=buffer)
            await bot.download_file(file_id, destination="path.txt")
        """
        proxy_file = await self.get_file(file_id, platform=platform)
        return await proxy_file.download(destination=destination, timeout=timeout)
    
    async def download(
        self,
        file: Union[str, Any],
        destination: Optional[Union[io.IOBase, str, Path]] = None,
        platform: Optional[Union[BPlatform, str]] = None,
        timeout: float = 30.0,
        chunk_size: Optional[int] = None,
        seek: bool = True
    ) -> Optional[Union[io.BytesIO, bytes]]:
        """Aiogram-compatible: download by file_id or Downloadable object.
        
        Mirrors aiogram Bot.download() so code like await bot.download(file_id)
        or await bot.download(message.document) works.
        
        Args:
            file: file_id (str) or Downloadable (object with file_id attr, e.g. message.document).
            destination: None (return BytesIO), path (str/Path), or BinaryIO.
            platform: Target platform (optional).
            timeout: Timeout in seconds (chunk_size/seek accepted for API compatibility, not used).
            
        Returns:
            io.BytesIO when destination is None (aiogram style), else None.
        """
        file_id = getattr(file, "file_id", file) if not isinstance(file, str) else file
        result = await self.download_file(
            file_id,
            destination=destination,
            platform=platform,
            timeout=timeout
        )
        if destination is None and result is not None:
            buf = io.BytesIO(result)
            if seek:
                buf.seek(0)
            return buf
        return result
    
    def _get_bot_for_operation(
        self, 
        platform: Optional[Union[BPlatform, str]] = None
    ) -> Any:
        """Get the appropriate bot for an operation.
        
        Resolution order:
        1. Explicit platform parameter
        2. Current platform from context (set by handler)
        3. Single platform (if only one configured)
        """
        if platform:
            return self.get_bot(platform)
        
        # Try to get platform from context (set when handler is called)
        ctx_platform = get_current_platform()
        if ctx_platform and ctx_platform in self._platform_map:
            return self._platform_map[ctx_platform].bot
        
        if len(self._platforms) == 1:
            return self._platforms[0].bot
        
        raise ValueError(
            "Multiple platforms configured. "
            "Specify 'platform' parameter or use get_bot(platform)."
        )
    
    def _resolve_platform_for_operation(
        self,
        platform: Optional[Union[BPlatform, str]] = None
    ) -> BPlatform:
        """Resolve platform type for an operation.
        
        Same resolution order as _get_bot_for_operation but returns BPlatform.
        """
        if platform:
            if isinstance(platform, str):
                return BPlatform(platform)
            return platform
        
        ctx_platform = get_current_platform()
        if ctx_platform and ctx_platform in self._platform_map:
            return ctx_platform
        
        if len(self._platforms) == 1:
            return self._platforms[0].platform
        
        raise ValueError(
            "Multiple platforms configured. "
            "Specify 'platform' parameter or use get_bot(platform)."
        )
    
    # Properties for aiogram compatibility
    
    @property
    def id(self) -> Optional[int]:
        """
        Bot ID (from first platform for compatibility).
        
        For multi-platform bots, use get_bot(platform).id to get specific platform ID.
        """
        if self._platforms:
            bot = self._platforms[0].bot
            return getattr(bot, 'id', None)
        return None
    
    def get_ids(self) -> Dict[BPlatform, Optional[int]]:
        """Get bot IDs for all platforms."""
        return {
            platform.platform: getattr(platform.bot, 'id', None)
            for platform in self._platforms
        }
    
    @property
    def token(self) -> Optional[str]:
        """
        Bot token for current platform (from context) or first platform.
        Returns raw token for API use. Always present when at least one platform is configured.
        """
        try:
            bot = self._get_bot_for_operation(None)
            return getattr(bot, 'token', None)
        except ValueError:
            if self._platforms:
                return getattr(self._platforms[0].bot, 'token', None)
            return None
    
    def get_token(self, platform: Optional[Union[BPlatform, str]] = None) -> Optional[str]:
        """Unified way to get raw token: for current platform (from context) or specified platform."""
        try:
            bot = self._get_bot_for_operation(platform)
            return getattr(bot, 'token', None)
        except ValueError:
            return None
    
    @property
    def token_masked(self) -> Optional[str]:
        """Partially masked token (for logging). Prefer .token for API, .token_masked for logs."""
        if self._platforms:
            bot = self._platforms[0].bot
            token = getattr(bot, 'token', None)
            if token:
                return f"{token[:8]}...{token[-4:]}"
        return None
    
    def get_tokens(self) -> Dict[BPlatform, Optional[str]]:
        """Get bot tokens for all platforms (partially masked)."""
        result = {}
        for platform in self._platforms:
            bot = platform.bot
            token = getattr(bot, 'token', None)
            if token:
                result[platform.platform] = f"{token[:8]}...{token[-4:]}"
            else:
                result[platform.platform] = None
        return result
    
    async def close(self) -> None:
        """Close all bot sessions (only for initialized platforms)."""
        from obabot.platforms.lazy import LazyPlatform
        
        for platform in self._platforms:
            # Skip lazy platforms that were never initialized
            if isinstance(platform, LazyPlatform) and platform._real is None:
                continue
            
            try:
                bot = platform.bot
                if hasattr(bot, 'session') and hasattr(bot.session, 'close'):
                    await bot.session.close()
                elif hasattr(bot, 'close'):
                    await bot.close()
            except Exception:
                pass

