from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..dependencies import get_current_user
from ..models import Notification, User, UserSetting

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationPreferences(BaseModel):
    in_app: bool = True
    email: bool = False
    web_push: bool = False
    mobile_push: bool = False
    document_processing: bool = True
    workspace_invitations: bool = True
    exports: bool = True
    flashcards_due: bool = True
    usage_limits: bool = True


def _settings(db: Session, user: User) -> UserSetting:
    row = db.scalar(select(UserSetting).where(UserSetting.user_id == user.id))
    if not row:
        row = UserSetting(
            user_id=user.id,
            theme="system",
            locale=user.locale,
            notifications_json={},
        )
        db.add(row)
        db.flush()
    return row


def _notification_out(row: Notification) -> dict:
    return {
        "id": row.id,
        "kind": row.kind,
        "title": row.title,
        "body": row.body,
        "data": row.data_json,
        "read": row.read,
        "created_at": row.created_at,
    }


@router.get("")
def list_notifications(
    unread_only: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    statement = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        statement = statement.where(Notification.read.is_(False))
    rows = db.scalars(
        statement.order_by(Notification.created_at.desc()).limit(limit)
    ).all()
    unread = len(
        db.scalars(
            select(Notification.id).where(
                Notification.user_id == user.id,
                Notification.read.is_(False),
            )
        ).all()
    )
    return {
        "items": [_notification_out(row) for row in rows],
        "unread": unread,
    }


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    row = db.get(Notification, notification_id)
    if not row or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    row.read = True
    db.commit()
    return _notification_out(row)


@router.post("/read-all", status_code=204)
def mark_all_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    rows = db.scalars(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.read.is_(False),
        )
    ).all()
    for row in rows:
        row.read = True
    db.commit()


@router.get("/preferences")
def get_preferences(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    row = _settings(db, user)
    defaults = NotificationPreferences().model_dump()
    defaults.update(row.notifications_json or {})
    db.commit()
    return defaults


@router.patch("/preferences")
def update_preferences(
    payload: NotificationPreferences,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    row = _settings(db, user)
    row.notifications_json = payload.model_dump()
    db.commit()
    return row.notifications_json
