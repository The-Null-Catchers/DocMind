from __future__ import annotations

import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, status

from ..config import get_settings

ALLOWED_MIME = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/csv": ".csv",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}
EXTENSION_MIME = {extension: mime for mime, extension in ALLOWED_MIME.items()}
MIME_ALIASES = {
    "application/octet-stream",
    "binary/octet-stream",
    "",
}


@dataclass(frozen=True)
class ValidatedUpload:
    safe_name: str
    content_hash: str
    size: int
    mime_type: str
    extension: str


def _bad_type(message: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail=message,
    )


def _validate_magic(mime_type: str, data: bytes) -> None:
    if mime_type == "application/pdf":
        if not data.startswith(b"%PDF-"):
            _bad_type("File content is not a valid PDF")
        return
    if mime_type == "image/png":
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            _bad_type("File content is not a valid PNG image")
        return
    if mime_type == "image/jpeg":
        if not data.startswith(b"\xff\xd8\xff"):
            _bad_type("File content is not a valid JPEG image")
        return
    if mime_type == "image/webp":
        if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
            _bad_type("File content is not a valid WebP image")
        return
    if mime_type in {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }:
        if not data.startswith(b"PK"):
            _bad_type("Office document is not a valid ZIP container")
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = set(archive.namelist())
        except zipfile.BadZipFile:
            _bad_type("Office document is not a valid ZIP container")
            return
        required = (
            "word/document.xml"
            if mime_type.endswith("wordprocessingml.document")
            else "ppt/presentation.xml"
        )
        if required not in names:
            _bad_type("Office document content does not match its extension")
        return

    # Text formats may be UTF-8/UTF-16 but must not look like arbitrary binary payloads.
    if b"\x00" in data[:4096]:
        try:
            data[:4096].decode("utf-16")
        except UnicodeDecodeError:
            _bad_type("Text upload contains binary content")


def validate_upload(filename: str, content_type: str, data: bytes) -> ValidatedUpload:
    settings = get_settings()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large",
        )

    actual_ext = Path(filename).suffix.lower()
    aliases = {".jpeg": ".jpg", ".markdown": ".md"}
    actual_ext = aliases.get(actual_ext, actual_ext)
    canonical_mime = EXTENSION_MIME.get(actual_ext)
    if canonical_mime is None:
        _bad_type("Unsupported file extension")

    declared_mime = (content_type or "").split(";", 1)[0].strip().lower()
    if declared_mime not in MIME_ALIASES:
        declared_ext = ALLOWED_MIME.get(declared_mime)
        if declared_ext is None:
            _bad_type("Unsupported MIME type")
        declared_ext = aliases.get(declared_ext, declared_ext)
        if declared_ext != actual_ext:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename and MIME type disagree",
            )

    _validate_magic(canonical_mime, data)
    safe_stem = re.sub(
        r"[^\w\-. ()\u0600-\u06FF]",
        "_",
        Path(filename).stem,
        flags=re.UNICODE,
    ).strip()[:180]
    safe_name = f"{safe_stem or 'document'}{actual_ext}"
    return ValidatedUpload(
        safe_name=safe_name,
        content_hash=hashlib.sha256(data).hexdigest(),
        size=len(data),
        mime_type=canonical_mime,
        extension=actual_ext,
    )
