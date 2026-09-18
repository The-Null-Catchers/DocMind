from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..services.storage import get_storage

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/ready")
async def ready(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    checks: dict[str, str] = {}

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    try:
        get_storage().healthcheck()
        checks["storage"] = "ok"
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Object storage unavailable") from exc

    if settings.app_env.lower() in {"production", "staging"}:
        redis = Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        try:
            await redis.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Redis unavailable") from exc
        finally:
            await redis.aclose()
    else:
        checks["redis"] = "not-required-in-local-mode"

    return {"status": "ready", **checks}
