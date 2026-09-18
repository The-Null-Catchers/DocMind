from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..dependencies import get_current_user, require_workspace_role
from ..models import Notification, User, Workspace, WorkspaceInvitation, WorkspaceMember
from ..schemas import WorkspaceCreate, WorkspaceOut
from ..security import hash_refresh_token, new_refresh_token
from ..services.audit import write_audit

router = APIRouter(tags=["workspaces"])

INVITABLE_ROLES = {"admin", "editor", "viewer"}


class InvitationCreate(BaseModel):
    email: EmailStr
    role: str = Field(default="viewer", pattern="^(admin|editor|viewer)$")


class InvitationTokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=500)


class MemberRoleUpdate(BaseModel):
    role: str = Field(pattern="^(admin|editor|viewer)$")


def _slug(name: str) -> str:
    value = re.sub(r"[^a-z0-9\u0600-\u06ff]+", "-", name.lower()).strip("-")
    return value[:120] or "workspace"


def _workspace_out(workspace: Workspace, role: str) -> WorkspaceOut:
    return WorkspaceOut(
        id=workspace.id,
        owner_id=workspace.owner_id,
        name=workspace.name,
        slug=workspace.slug,
        description=workspace.description,
        kind=workspace.kind,
        created_at=workspace.created_at,
        role=role,
    )


def _admin_member(db: Session, workspace_id: str, user: User) -> WorkspaceMember:
    return require_workspace_role(db, workspace_id, user.id, "admin")


def _invitation_payload(invitation: WorkspaceInvitation, workspace: Workspace | None = None) -> dict:
    return {
        "id": invitation.id,
        "workspace_id": invitation.workspace_id,
        "workspace_name": workspace.name if workspace else None,
        "email": invitation.email,
        "role": invitation.role,
        "status": invitation.status,
        "expires_at": invitation.expires_at,
        "last_sent_at": invitation.last_sent_at,
        "created_at": invitation.created_at,
    }


def _active_invitation(db: Session, raw_token: str) -> WorkspaceInvitation:
    invitation = db.scalar(
        select(WorkspaceInvitation).where(
            WorkspaceInvitation.token_hash == hash_refresh_token(raw_token),
            WorkspaceInvitation.status == "pending",
        )
    )
    now = datetime.now(timezone.utc)
    if not invitation:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invitation.expires_at.replace(tzinfo=timezone.utc) <= now:
        invitation.status = "expired"
        invitation.responded_at = now
        db.commit()
        raise HTTPException(status_code=410, detail="Invitation expired")
    return invitation


@router.get("/workspaces", response_model=list[WorkspaceOut])
def list_workspaces(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WorkspaceOut]:
    rows = db.execute(
        select(Workspace, WorkspaceMember.role)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .where(
            WorkspaceMember.user_id == user.id,
            Workspace.deleted_at.is_(None),
        )
        .order_by(Workspace.updated_at.desc())
    ).all()
    return [_workspace_out(workspace, role) for workspace, role in rows]


@router.post("/workspaces", response_model=WorkspaceOut, status_code=201)
def create_workspace(
    payload: WorkspaceCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceOut:
    base = _slug(payload.name)
    slug = base
    suffix = 2
    while db.scalar(
        select(Workspace.id).where(
            Workspace.owner_id == user.id,
            Workspace.slug == slug,
        )
    ):
        slug = f"{base}-{suffix}"
        suffix += 1

    workspace = Workspace(
        owner_id=user.id,
        name=payload.name.strip(),
        slug=slug,
        description=payload.description,
        kind=payload.kind,
    )
    db.add(workspace)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner"))
    write_audit(db, workspace.id, user.id, "workspace.created", "workspace", workspace.id)
    db.commit()
    db.refresh(workspace)
    return _workspace_out(workspace, "owner")


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceOut)
def get_workspace(
    workspace_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceOut:
    member = require_workspace_role(db, workspace_id, user.id, "viewer")
    workspace = db.get(Workspace, workspace_id)
    if not workspace or workspace.deleted_at:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return _workspace_out(workspace, member.role)


@router.get("/workspaces/{workspace_id}/members")
def list_members(
    workspace_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    require_workspace_role(db, workspace_id, user.id, "viewer")
    rows = db.execute(
        select(WorkspaceMember, User)
        .join(User, User.id == WorkspaceMember.user_id)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.created_at.asc())
    ).all()
    return [
        {
            "user_id": member.user_id,
            "email": member_user.email,
            "display_name": member_user.display_name,
            "role": member.role,
            "created_at": member.created_at,
        }
        for member, member_user in rows
    ]


@router.patch("/workspaces/{workspace_id}/members/{member_user_id}")
def update_member_role(
    workspace_id: str,
    member_user_id: str,
    payload: MemberRoleUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    actor = _admin_member(db, workspace_id, user)
    target = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == member_user_id,
        )
    )
    if not target:
        raise HTTPException(status_code=404, detail="Workspace member not found")
    if target.role == "owner":
        raise HTTPException(status_code=409, detail="Workspace owner role cannot be changed")
    if actor.role != "owner" and (target.role == "admin" or payload.role == "admin"):
        raise HTTPException(status_code=403, detail="Only the workspace owner can manage admins")
    target.role = payload.role
    write_audit(
        db,
        workspace_id,
        user.id,
        "workspace.member_role_changed",
        "user",
        member_user_id,
        {"role": payload.role},
    )
    db.commit()
    return {"user_id": target.user_id, "role": target.role}


@router.delete("/workspaces/{workspace_id}/members/{member_user_id}", status_code=204)
def remove_member(
    workspace_id: str,
    member_user_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    actor = _admin_member(db, workspace_id, user)
    target = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == member_user_id,
        )
    )
    if not target:
        return
    if target.role == "owner":
        raise HTTPException(status_code=409, detail="Workspace owner cannot be removed")
    if actor.role != "owner" and target.role == "admin":
        raise HTTPException(status_code=403, detail="Only the workspace owner can remove admins")
    db.delete(target)
    write_audit(db, workspace_id, user.id, "workspace.member_removed", "user", member_user_id)
    db.commit()


@router.get("/workspaces/{workspace_id}/invitations")
def list_invitations(
    workspace_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    _admin_member(db, workspace_id, user)
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(WorkspaceInvitation)
        .where(WorkspaceInvitation.workspace_id == workspace_id)
        .order_by(WorkspaceInvitation.created_at.desc())
        .limit(200)
    ).all()
    changed = False
    for invitation in rows:
        if (
            invitation.status == "pending"
            and invitation.expires_at.replace(tzinfo=timezone.utc) <= now
        ):
            invitation.status = "expired"
            invitation.responded_at = now
            changed = True
    if changed:
        db.commit()
    return [_invitation_payload(invitation) for invitation in rows]


@router.post("/workspaces/{workspace_id}/invitations", status_code=201)
def create_invitation(
    workspace_id: str,
    payload: InvitationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    actor = _admin_member(db, workspace_id, user)
    if actor.role != "owner" and payload.role == "admin":
        raise HTTPException(status_code=403, detail="Only the workspace owner can invite admins")

    email = str(payload.email).lower().strip()
    existing_user = db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    if existing_user and db.scalar(
        select(WorkspaceMember.id).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == existing_user.id,
        )
    ):
        raise HTTPException(status_code=409, detail="User is already a workspace member")

    now = datetime.now(timezone.utc)
    pending = db.scalars(
        select(WorkspaceInvitation).where(
            WorkspaceInvitation.workspace_id == workspace_id,
            WorkspaceInvitation.email == email,
            WorkspaceInvitation.status == "pending",
        )
    ).all()
    for invitation in pending:
        invitation.status = "revoked"
        invitation.responded_at = now

    raw_token = new_refresh_token()
    invitation = WorkspaceInvitation(
        workspace_id=workspace_id,
        email=email,
        role=payload.role,
        invited_by_id=user.id,
        token_hash=hash_refresh_token(raw_token),
        status="pending",
        expires_at=now + timedelta(days=7),
        last_sent_at=now,
    )
    db.add(invitation)
    if existing_user:
        workspace = db.get(Workspace, workspace_id)
        db.add(
            Notification(
                user_id=existing_user.id,
                kind="workspace_invitation",
                title="Workspace invitation",
                body=f"You were invited to {workspace.name if workspace else 'a DocMind workspace'}.",
                data_json={"workspace_id": workspace_id, "invitation_id": invitation.id},
            )
        )
    write_audit(
        db,
        workspace_id,
        user.id,
        "workspace.invitation_created",
        "invitation",
        invitation.id,
        {"email": email, "role": payload.role},
    )
    db.commit()

    response = _invitation_payload(invitation, db.get(Workspace, workspace_id))
    if get_settings().app_env != "production":
        response["dev_token"] = raw_token
    return response


@router.post("/workspaces/{workspace_id}/invitations/{invitation_id}/resend")
def resend_invitation(
    workspace_id: str,
    invitation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    actor = _admin_member(db, workspace_id, user)
    invitation = db.get(WorkspaceInvitation, invitation_id)
    if not invitation or invitation.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Invitation not found")
    if invitation.status != "pending":
        raise HTTPException(status_code=409, detail="Only pending invitations can be resent")
    if actor.role != "owner" and invitation.role == "admin":
        raise HTTPException(status_code=403, detail="Only the workspace owner can manage admin invitations")

    now = datetime.now(timezone.utc)
    raw_token = new_refresh_token()
    invitation.token_hash = hash_refresh_token(raw_token)
    invitation.expires_at = now + timedelta(days=7)
    invitation.last_sent_at = now
    db.commit()
    response = _invitation_payload(invitation, db.get(Workspace, workspace_id))
    if get_settings().app_env != "production":
        response["dev_token"] = raw_token
    return response


@router.delete("/workspaces/{workspace_id}/invitations/{invitation_id}", status_code=204)
def revoke_invitation(
    workspace_id: str,
    invitation_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    actor = _admin_member(db, workspace_id, user)
    invitation = db.get(WorkspaceInvitation, invitation_id)
    if not invitation or invitation.workspace_id != workspace_id:
        return
    if actor.role != "owner" and invitation.role == "admin":
        raise HTTPException(status_code=403, detail="Only the workspace owner can manage admin invitations")
    if invitation.status == "pending":
        invitation.status = "revoked"
        invitation.responded_at = datetime.now(timezone.utc)
        db.commit()


@router.post("/workspace-invitations/accept")
def accept_invitation(
    payload: InvitationTokenRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    invitation = _active_invitation(db, payload.token)
    if invitation.email != user.email.lower().strip():
        raise HTTPException(status_code=403, detail="Invitation belongs to a different email address")

    member = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == invitation.workspace_id,
            WorkspaceMember.user_id == user.id,
        )
    )
    if not member:
        member = WorkspaceMember(
            workspace_id=invitation.workspace_id,
            user_id=user.id,
            role=invitation.role,
        )
        db.add(member)
    elif member.role != "owner":
        member.role = invitation.role

    now = datetime.now(timezone.utc)
    invitation.status = "accepted"
    invitation.accepted_by_id = user.id
    invitation.responded_at = now
    write_audit(
        db,
        invitation.workspace_id,
        user.id,
        "workspace.invitation_accepted",
        "invitation",
        invitation.id,
    )
    db.commit()
    workspace = db.get(Workspace, invitation.workspace_id)
    return {
        "workspace": _workspace_out(workspace, member.role).model_dump(mode="json") if workspace else None,
        "invitation": _invitation_payload(invitation, workspace),
    }


@router.post("/workspace-invitations/reject", status_code=204)
def reject_invitation(
    payload: InvitationTokenRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    invitation = _active_invitation(db, payload.token)
    if invitation.email != user.email.lower().strip():
        raise HTTPException(status_code=403, detail="Invitation belongs to a different email address")
    invitation.status = "rejected"
    invitation.responded_at = datetime.now(timezone.utc)
    db.commit()
