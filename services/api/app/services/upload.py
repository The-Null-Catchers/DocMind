from __future__ import annotations

import hashlib
import re
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


@dataclass(frozen=True)
class ValidatedUpload:
    safe_name: str
    content_hash: str
    size: int
    mime_type: str
    extension: str


def validate_upload(filename: str, content_type: str, data: bytes) -> ValidatedUpload:
    settings = get_settings()
    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")
    expected_ext = ALLOWED_MIME.get(content_type)
    if expected_ext is None:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported file type")
    actual_ext = Path(filename).suffix.lower()
    aliases = {".jpeg": ".jpg", ".markdown": ".md"}
    actual_ext = aliases.get(actual_ext, actual_ext)
    if actual_ext != expected_ext:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename and MIME type disagree")
    safe_stem = re.sub(r"[^\w\-. ()\u0600-\u06FF]", "_", Path(filename).stem, flags=re.UNICODE).strip()[:180]
    safe_name = f"{safe_stem or 'document'}{expected_ext}"
    return ValidatedUpload(
        safe_name=safe_name,
        content_hash=hashlib.sha256(data).hexdigest(),
        size=len(data),
        mime_type=content_type,
        extension=expected_ext,
    )
