import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.config import Settings
from app.services.rate_limit import RateLimiter
from app.services.upload import validate_upload


def _request(path: str, method: str = "POST") -> Request:
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    })


@pytest.mark.asyncio
async def test_login_rate_limit_blocks_after_capacity():
    limiter = RateLimiter(Settings(
        app_env="development",
        rate_limit_enabled=True,
        rate_limit_window_seconds=60,
    ))
    results = [await limiter.check(_request("/api/v1/auth/login")) for _ in range(11)]
    assert all(allowed for allowed, _ in results[:10])
    assert results[10][0] is False


def test_upload_rejects_spoofed_pdf_content():
    with pytest.raises(HTTPException) as exc:
        validate_upload("malicious.pdf", "application/pdf", b"not a real pdf")
    assert exc.value.status_code == 415


def test_upload_accepts_octet_stream_for_valid_text_extension():
    result = validate_upload("mobile-upload.txt", "application/octet-stream", b"safe text content")
    assert result.mime_type == "text/plain"
    assert result.extension == ".txt"


def test_upload_rejects_office_container_with_wrong_internal_type():
    fake_docx = b"PK\x03\x04not-a-real-office-container"
    with pytest.raises(HTTPException) as exc:
        validate_upload(
            "fake.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            fake_docx,
        )
    assert exc.value.status_code == 415


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,capacity",
    [
        ("/api/v1/search/global", 60),
        ("/api/v1/ai/table", 20),
        ("/api/v1/exports", 20),
        ("/api/v1/exports/job-1/retry", 10),
        ("/api/v1/auth/email-verification/request", 5),
    ],
)
async def test_expensive_routes_are_rate_limited(path, capacity):
    limiter = RateLimiter(Settings(
        app_env="development",
        rate_limit_enabled=True,
        rate_limit_window_seconds=60,
    ))
    results = [await limiter.check(_request(path)) for _ in range(capacity + 1)]
    assert all(allowed for allowed, _ in results[:capacity])
    assert results[-1][0] is False
