from __future__ import annotations

import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..dependencies import get_current_user, require_workspace_role
from ..models import ExportJob, User
from ..services.queueing import enqueue_export
from ..services.storage import get_storage

router = APIRouter(prefix="/exports", tags=["exports"])

EXPORT_KINDS = {
    "note_markdown",
    "note_pdf",
    "chat_markdown",
    "chat_pdf",
    "flashcards_csv",
    "quiz_pdf",
    "summary_pdf",
    "extraction_json",
    "extraction_csv",
}
SOURCE_REQUIRED = {
    "note_markdown",
    "note_pdf",
    "chat_markdown",
    "chat_pdf",
    "flashcards_csv",
    "quiz_pdf",
}


class ExportCreate(BaseModel):
    workspace_id: str
    kind: str = Field(min_length=1, max_length=40)
    source_id: str | None = None
    payload: dict = Field(default_factory=dict)


def _out(job: ExportJob) -> dict:
    return {
        "id": job.id,
        "workspace_id": job.workspace_id,
        "kind": job.kind,
        "source_id": job.source_id,
        "status": job.status,
        "filename": job.filename,
        "mime_type": job.mime_type,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }


def _owned_job(db: Session, job_id: str, user: User) -> ExportJob:
    job = db.get(ExportJob, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(status_code=404, detail="Export not found")
    require_workspace_role(db, job.workspace_id, user.id, "viewer")
    return job


@router.post("", status_code=202)
def create_export(
    payload: ExportCreate,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_workspace_role(db, payload.workspace_id, user.id, "viewer")
    if payload.kind not in EXPORT_KINDS:
        raise HTTPException(status_code=422, detail="Unsupported export kind")
    if payload.kind in SOURCE_REQUIRED and not payload.source_id:
        raise HTTPException(status_code=422, detail="source_id is required for this export")
    if len(json.dumps(payload.payload, ensure_ascii=False)) > 1_000_000:
        raise HTTPException(status_code=413, detail="Export payload is too large")

    job = ExportJob(
        workspace_id=payload.workspace_id,
        user_id=user.id,
        kind=payload.kind,
        source_id=payload.source_id,
        payload_json=payload.payload,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    enqueue_export(background_tasks, job.id)
    return _out(job)


@router.get("")
def list_exports(
    workspace_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    require_workspace_role(db, workspace_id, user.id, "viewer")
    rows = db.scalars(
        select(ExportJob)
        .where(
            ExportJob.workspace_id == workspace_id,
            ExportJob.user_id == user.id,
        )
        .order_by(ExportJob.created_at.desc())
        .limit(100)
    ).all()
    return [_out(job) for job in rows]


@router.get("/{job_id}")
def get_export(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return _out(_owned_job(db, job_id, user))


@router.post("/{job_id}/retry", status_code=202)
def retry_export(
    job_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    job = _owned_job(db, job_id, user)
    if job.status not in {"failed", "pending"}:
        raise HTTPException(status_code=409, detail="Only failed or pending exports can be retried")
    job.status = "pending"
    job.error_message = None
    db.commit()
    enqueue_export(background_tasks, job.id)
    return _out(job)


@router.get("/{job_id}/download-url")
def export_download_url(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    job = _owned_job(db, job_id, user)
    if job.status != "ready" or not job.object_key:
        raise HTTPException(status_code=409, detail="Export is not ready")
    if get_settings().storage_backend.lower() == "local":
        return {"url": f"/api/v1/exports/{job.id}/file"}
    return {"url": get_storage().signed_get_url(job.object_key)}


@router.get("/{job_id}/file")
def export_file(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    job = _owned_job(db, job_id, user)
    if job.status != "ready" or not job.object_key:
        raise HTTPException(status_code=409, detail="Export is not ready")
    data = get_storage().get_bytes(job.object_key)
    filename = (job.filename or "docmind-export").replace('"', "")
    return Response(
        content=data,
        media_type=job.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/{job_id}", status_code=204)
def delete_export(
    job_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    job = _owned_job(db, job_id, user)
    object_key = job.object_key
    db.delete(job)
    db.commit()
    if object_key:
        get_storage().delete(object_key)
