"""Max file: filename from server headers (Content-Disposition / Content-Type).

For URL path "getfile" we do HEAD then GET and take filename from response headers.
Optional suggested_filename in get_file() overrides. MaxFileFilenameError only when
fetch returns no name and suggested_filename not passed.
"""

import re
from typing import Any, Optional, Tuple
from urllib.parse import unquote, urlparse

import httpx

GETFILE_BASENAME = "getfile"


class MaxFileFilenameError(ValueError):
    """Raised when Max file filename could not be determined (server sent no name, no suggested_filename)."""

    def __init__(self, url: Optional[str] = None, message: Optional[str] = None):
        self.url = url
        msg = message or (
            "Max file filename could not be determined. "
            "Pass suggested_filename= to get_file(), e.g. get_file(url, platform='max', suggested_filename='doc.pdf')."
        )
        if url and message is None:
            msg += f" URL: {url}"
        super().__init__(msg)


def _url_basename_is_getfile(url: Optional[str]) -> bool:
    if not url:
        return False
    path = urlparse(url).path
    name = (path.split("/")[-1] or "").lower()
    return name == GETFILE_BASENAME


def fetch_filename_from_max_url_sync(url: str, timeout: float = 10.0) -> Optional[str]:
    """Sync: HEAD then GET to get filename from headers (for .file_name when URL path is getfile)."""
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.head(url)
            if r.status_code == 200:
                name = filename_from_headers(r.headers)
                if name:
                    return name
            r = client.get(url)
            if r.status_code == 200:
                return filename_from_headers(r.headers)
    except Exception:
        pass
    return None


def filename_from_max_url(url: Optional[str]) -> str:
    """Filename from URL path (segment after last /). For 'getfile' returns 'file.bin' (use fetch from server for real name)."""
    if not url:
        return "file.bin"
    path = urlparse(url).path
    name = unquote(path.split("/")[-1]) if path else "file.bin"
    name = name or "file.bin"
    if name.lower() == GETFILE_BASENAME:
        return "file.bin"
    return name


def parse_content_disposition_filename(headers: Any) -> Optional[str]:
    """Extract filename from Content-Disposition header if present."""
    cd = headers.get("content-disposition") or headers.get("Content-Disposition")
    if not cd:
        return None
    # filename="doc.pdf" or filename*=UTF-8''%d0%b4%d0%be%d0%ba.pdf
    m = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';\s]+)["\']?', cd, re.I)
    if m:
        return unquote(m.group(1).strip())
    m = re.search(r'filename=["\']([^"\']+)["\']', cd, re.I)
    if m:
        return m.group(1).strip()
    return None


# Fallback extension from Content-Type when no Content-Disposition
_CONTENT_TYPE_EXT: dict = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "audio/ogg": ".ogg",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "text/plain": ".txt",
    "application/zip": ".zip",
    "application/octet-stream": ".bin",
}


def filename_from_headers(headers: Any) -> Optional[str]:
    """Filename from Content-Disposition, or fallback to file.<ext> from Content-Type."""
    name = parse_content_disposition_filename(headers)
    if name:
        return name
    ct = headers.get("content-type") or headers.get("Content-Type") or ""
    # "application/pdf; charset=..." -> "application/pdf"
    ct = ct.split(";")[0].strip().lower()
    ext = _CONTENT_TYPE_EXT.get(ct)
    if ext:
        return f"file{ext}"
    return None


async def fetch_filename_from_max_url(url: str, timeout: float = 10.0) -> Optional[str]:
    """HEAD then GET; return filename from Content-Disposition or Content-Type."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.head(url)
            if response.status_code == 200:
                name = filename_from_headers(response.headers)
                if name:
                    return name
            response = await client.get(url)
            if response.status_code == 200:
                name = filename_from_headers(response.headers)
                if name:
                    return name
    except Exception:
        pass
    return None


async def download_max_file(
    url: str,
    destination: Optional[Any] = None,
    timeout: float = 60.0,
) -> Tuple[Optional[bytes], Optional[str]]:
    """Download from Max URL; return (content, filename from headers)."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        filename: Optional[str] = None
        try:
            head = await client.head(url)
            if head.status_code == 200:
                filename = filename_from_headers(head.headers)
        except Exception:
            pass

        response = await client.get(url)
        response.raise_for_status()
        content = response.content
        if not filename:
            filename = filename_from_headers(response.headers)

        if destination is not None:
            destination.write(content)
            return (None, filename)
        return (content, filename)
