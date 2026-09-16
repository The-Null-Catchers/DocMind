from __future__ import annotations

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..config import get_settings
from ..db import get_db
from ..dependencies import get_current_user
from ..models import AuthToken, Document, User, UserSession, Workspace
from ..schemas import AuthResponse, LoginRequest, RefreshRequest, RegisterRequest, UserOut
from ..security import create_access_token, hash_password, hash_refresh_token, new_refresh_token, verify_password
from ..services.storage import get_storage

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_session(db: Session, user: User, request: Request, device_name: str | None = None) -> AuthResponse:
    refresh = new_refresh_token()
    expires = datetime.now(timezone.utc) + timedelta(days=get_settings().refresh_token_days)
    session = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh),
        device_name=device_name,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
        expires_at=expires,
    )
    db.add(session)
    db.flush()
    access = create_access_token(user.id, session.id)
    return AuthResponse(access_token=access, refresh_token=refresh, user=UserOut.model_validate(user))


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    email = payload.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Email already registered")
    try:
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    user = User(email=email, password_hash=password_hash, display_name=payload.display_name.strip(), locale=payload.locale)
    db.add(user)
    db.flush()
    response = _issue_session(db, user, request)
    db.commit()
    return response


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower().strip()))
    if not user or not user.is_active or user.deleted_at or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    response = _issue_session(db, user, request, payload.device_name)
    db.commit()
    return response


@router.post("/refresh", response_model=AuthResponse)
def refresh(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)) -> AuthResponse:
    token_hash = hash_refresh_token(payload.refresh_token)
    session = db.scalar(select(UserSession).where(UserSession.refresh_token_hash == token_hash))
    now = datetime.now(timezone.utc)
    if not session or session.revoked_at or session.expires_at.replace(tzinfo=timezone.utc) <= now:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    user = db.get(User, session.user_id)
    if not user or not user.is_active or user.deleted_at:
        raise HTTPException(status_code=401, detail="User unavailable")
    session.revoked_at = now
    response = _issue_session(db, user, request, session.device_name)
    db.commit()
    return response


@router.post("/logout", status_code=204)
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    sessions = db.scalars(select(UserSession).where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))).all()
    now = datetime.now(timezone.utc)
    for session in sessions:
        session.revoked_at = now
    db.commit()


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user)


@router.post("/password/forgot", status_code=202)
def forgot_password(payload: dict, db: Session = Depends(get_db)) -> dict:
    email = str(payload.get("email", "")).lower().strip()
    user = db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))
    response: dict = {"message": "If the account exists, reset instructions will be sent."}
    if user:
        raw = new_refresh_token()
        db.add(AuthToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw),
            purpose="password_reset",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        ))
        db.commit()
        if get_settings().app_env != "production":
            response["dev_token"] = raw
    return response


@router.post("/password/reset", status_code=204)
def reset_password(payload: dict, db: Session = Depends(get_db)) -> None:
    raw = str(payload.get("token", ""))
    password = str(payload.get("password", ""))
    token = db.scalar(select(AuthToken).where(
        AuthToken.token_hash == hash_refresh_token(raw),
        AuthToken.purpose == "password_reset",
        AuthToken.consumed_at.is_(None),
    ))
    now = datetime.now(timezone.utc)
    if not token or token.expires_at.replace(tzinfo=timezone.utc) <= now:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    user = db.get(User, token.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    try:
        user.password_hash = hash_password(password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    token.consumed_at = now
    for session in db.scalars(select(UserSession).where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))).all():
        session.revoked_at = now
    db.commit()


@router.post("/email-verification/request", status_code=202)
def request_email_verification(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if user.is_email_verified:
        return {"message": "Email already verified"}
    raw = new_refresh_token()
    db.add(AuthToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw),
        purpose="email_verify",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    ))
    db.commit()
    response = {"message": "Verification instructions queued"}
    if get_settings().app_env != "production":
        response["dev_token"] = raw
    return response


@router.post("/email-verification/confirm", status_code=204)
def confirm_email_verification(payload: dict, db: Session = Depends(get_db)) -> None:
    token = db.scalar(select(AuthToken).where(
        AuthToken.token_hash == hash_refresh_token(str(payload.get("token", ""))),
        AuthToken.purpose == "email_verify",
        AuthToken.consumed_at.is_(None),
    ))
    now = datetime.now(timezone.utc)
    if not token or token.expires_at.replace(tzinfo=timezone.utc) <= now:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    user = db.get(User, token.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid verification token")
    user.is_email_verified = True
    token.consumed_at = now
    db.commit()


@router.get("/sessions")
def sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(UserSession).where(UserSession.user_id == user.id).order_by(UserSession.created_at.desc())).all()
    return [{
        "id": row.id,
        "device_name": row.device_name,
        "created_at": row.created_at,
        "expires_at": row.expires_at,
        "revoked": row.revoked_at is not None,
    } for row in rows]


@router.delete("/sessions/{session_id}", status_code=204)
def revoke_session(session_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    row = db.get(UserSession, session_id)
    if not row or row.user_id != user.id:
        return
    row.revoked_at = datetime.now(timezone.utc)
    db.commit()


@router.delete("/account", status_code=204)
def delete_account(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    # Object storage is not governed by SQL cascade, so remove owned-workspace files explicitly.
    owned_ids = db.scalars(select(Workspace.id).where(Workspace.owner_id == user.id)).all()
    if owned_ids:
        for key in db.scalars(select(Document.object_key).where(Document.workspace_id.in_(owned_ids))).all():
            try:
                get_storage().delete(key)
            except Exception:
                # DB deletion still proceeds; production cleanup workers retry orphan cleanup.
                pass
    db.delete(user)
    db.commit()
