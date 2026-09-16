from __future__ import annotations

import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from ..db import get_db
from ..dependencies import get_current_user, require_workspace_role
from ..models import User, Workspace, WorkspaceMember
from ..schemas import WorkspaceCreate, WorkspaceOut
from ..services.audit import write_audit

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def _slug(name: str) -> str:
    value = re.sub(r"[^a-z0-9\u0600-\u06ff]+", "-", name.lower()).strip("-")
    return value[:120] or "workspace"


@router.get("", response_model=list[WorkspaceOut])
def list_workspaces(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[WorkspaceOut]:
    rows = db.scalars(
        select(Workspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user.id, Workspace.deleted_at.is_(None))
        .order_by(Workspace.updated_at.desc())
    ).all()
    return [WorkspaceOut.model_validate(row) for row in rows]


@router.post("", response_model=WorkspaceOut, status_code=201)
def create_workspace(payload: WorkspaceCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> WorkspaceOut:
    base = _slug(payload.name)
    slug = base
    i = 2
    while db.scalar(select(Workspace.id).where(Workspace.owner_id == user.id, Workspace.slug == slug)):
        slug = f"{base}-{i}"
        i += 1
    workspace = Workspace(owner_id=user.id, name=payload.name.strip(), slug=slug, description=payload.description, kind=payload.kind)
    db.add(workspace)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    write_audit(db, workspace.id, user.id, "workspace.created", "workspace", workspace.id)
    db.commit()
    db.refresh(workspace)
    return WorkspaceOut.model_validate(workspace)


@router.get("/{workspace_id}", response_model=WorkspaceOut)
def get_workspace(workspace_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> WorkspaceOut:
    require_workspace_role(db, workspace_id, user.id, "viewer")
    workspace = db.get(Workspace, workspace_id)
    if not workspace or workspace.deleted_at:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceOut.model_validate(workspace)
