from __future__ import annotations

from sqlalchemy.orm import Session
from ..models import AuditLog


def write_audit(db: Session, workspace_id: str, actor_id: str | None, action: str, target_type: str, target_id: str | None = None, metadata: dict | None = None) -> None:
    db.add(AuditLog(
        workspace_id=workspace_id,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata_json=metadata or {},
    ))
