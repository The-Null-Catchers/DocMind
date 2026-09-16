from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from ..db import get_db
from ..dependencies import get_current_user
from ..models import Document, DocumentProcessingJob, Embedding, User, Workspace

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview")
def overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if not user.is_platform_admin:
        raise HTTPException(status_code=403, detail="Platform admin required")
    # Privacy-conscious aggregate metrics only; no private document content is returned.
    return {
        "users": db.scalar(select(func.count()).select_from(User)) or 0,
        "workspaces": db.scalar(select(func.count()).select_from(Workspace)) or 0,
        "documents": db.scalar(select(func.count()).select_from(Document)) or 0,
        "embeddings": db.scalar(select(func.count()).select_from(Embedding)) or 0,
        "failed_jobs": db.scalar(select(func.count()).select_from(DocumentProcessingJob).where(DocumentProcessingJob.status == "failed")) or 0,
    }
