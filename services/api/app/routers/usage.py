from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..db import get_db
from ..dependencies import get_current_user, require_workspace_role
from ..models import Subscription, UsageRecord, User
from ..services.entitlements import entitlements_for

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("")
def usage(workspace_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_workspace_role(db, workspace_id, user.id, "viewer")
    plan = db.scalar(select(Subscription.plan).where(Subscription.workspace_id == workspace_id)) or "free"
    grouped = db.execute(select(UsageRecord.metric, func.sum(UsageRecord.quantity)).where(UsageRecord.workspace_id == workspace_id).group_by(UsageRecord.metric)).all()
    limits = entitlements_for(plan)
    return {"plan": plan, "usage": {metric: total for metric, total in grouped}, "limits": limits.__dict__}
