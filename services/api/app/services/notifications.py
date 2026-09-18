from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Notification, UserSetting


DEFAULT_PREFERENCES = {
    "in_app": True,
    "email": False,
    "web_push": False,
    "mobile_push": False,
    "document_processing": True,
    "workspace_invitations": True,
    "exports": True,
    "flashcards_due": True,
    "usage_limits": True,
}


def notification_preferences(db: Session, user_id: str) -> dict:
    settings = db.scalar(select(UserSetting).where(UserSetting.user_id == user_id))
    values = dict(DEFAULT_PREFERENCES)
    if settings and settings.notifications_json:
        values.update(settings.notifications_json)
    return values


def notify_user(
    db: Session,
    *,
    user_id: str | None,
    kind: str,
    title: str,
    body: str,
    data: dict | None = None,
    preference_key: str | None = None,
) -> Notification | None:
    if not user_id:
        return None
    preferences = notification_preferences(db, user_id)
    if not preferences.get("in_app", True):
        return None
    if preference_key and not preferences.get(preference_key, True):
        return None
    row = Notification(
        user_id=user_id,
        kind=kind,
        title=title,
        body=body,
        data_json=data or {},
    )
    db.add(row)
    return row
