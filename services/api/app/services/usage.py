from __future__ import annotations

from sqlalchemy.orm import Session
from ..models import UsageRecord


def record_usage(db: Session, *, workspace_id: str, user_id: str | None, metric: str, quantity: float, provider: str | None = None, model: str | None = None, metadata: dict | None = None) -> None:
    db.add(UsageRecord(
        workspace_id=workspace_id,
        user_id=user_id,
        metric=metric,
        quantity=quantity,
        provider=provider,
        model=model,
        metadata_json=metadata or {},
    ))
