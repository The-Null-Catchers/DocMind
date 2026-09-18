from __future__ import annotations

import time
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .config import get_settings
from .services.rate_limit import RateLimiter
from .routers import admin, ai_tools, auth, conversations, documents, health, library, notifications, search, study, usage, workspaces

settings = get_settings()
rate_limiter = RateLimiter(settings)
app = FastAPI(
    title="DocMind API",
    version="0.1.0",
    description="Private, citation-grounded AI document workspace API",
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin] if settings.web_origin != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    started = time.perf_counter()
    allowed, retry_after = await rate_limiter.check(request)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"error": {"code": "rate_limited", "message": "Too many requests"}},
            headers={"Retry-After": str(retry_after), "x-request-id": request_id},
        )
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    response.headers["x-response-time-ms"] = f"{(time.perf_counter() - started) * 1000:.1f}"
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["x-frame-options"] = "DENY"
    response.headers["referrer-policy"] = "strict-origin-when-cross-origin"
    return response


@app.exception_handler(ValueError)
async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"error": {"code": "validation_error", "message": str(exc)}})


app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(workspaces.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(conversations.router, prefix="/api/v1")
app.include_router(study.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(ai_tools.router, prefix="/api/v1")
app.include_router(library.router, prefix="/api/v1")
app.include_router(usage.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
