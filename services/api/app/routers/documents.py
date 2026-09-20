from __future__ import annotations

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..dependencies import get_current_user, require_workspace_role
from ..models import Document, DocumentPage, User
from ..schemas import DocumentOut
from ..services.audit import write_audit
from ..config import get_settings
from ..services.storage import get_storage
from ..services.malware import get_malware_scanner
from ..services.upload import validate_upload
from ..services.queueing import enqueue_document_processing

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut])
def list_documents(workspace_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[DocumentOut]:
    require_workspace_role(db, workspace_id, user.id, "viewer")
    rows = db.scalars(select(Document).where(
        Document.workspace_id == workspace_id,
        Document.deleted_at.is_(None),
    ).order_by(Document.created_at.desc()).limit(100)).all()
    return [DocumentOut.model_validate(row) for row in rows]


@router.post("/upload", response_model=DocumentOut, status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    workspace_id: str = Form(...),
    folder_id: str | None = Form(default=None),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentOut:
    require_workspace_role(db, workspace_id, user.id, "editor")
    data = await file.read()
    validated = validate_upload(file.filename or "document", file.content_type or "application/octet-stream", data)
    get_malware_scanner().scan(data)
    existing = db.scalar(select(Document).where(
        Document.workspace_id == workspace_id,
        Document.content_hash == validated.content_hash,
        Document.deleted_at.is_(None),
    ))
    if existing:
        raise HTTPException(status_code=409, detail={"message": "Document already exists", "document_id": existing.id})
    doc_id = str(uuid.uuid4())
    key = f"workspaces/{workspace_id}/documents/{doc_id}/{validated.safe_name}"
    get_storage().put_bytes(key, data, validated.mime_type)
    document = Document(
        id=doc_id,
        workspace_id=workspace_id,
        folder_id=folder_id,
        uploaded_by_id=user.id,
        original_filename=validated.safe_name,
        title=validated.safe_name.rsplit(".", 1)[0],
        object_key=key,
        mime_type=validated.mime_type,
        file_size=validated.size,
        content_hash=validated.content_hash,
        status="pending",
        processing_progress=0,
    )
    db.add(document)
    write_audit(db, workspace_id, user.id, "document.uploaded", "document", document.id, {"filename": validated.safe_name})
    db.commit()
    enqueue_document_processing(background_tasks, document.id)
    return DocumentOut.model_validate(document)


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> DocumentOut:
    document = db.get(Document, document_id)
    if not document or document.deleted_at:
        raise HTTPException(status_code=404, detail="Document not found")
    require_workspace_role(db, document.workspace_id, user.id, "viewer")
    return DocumentOut.model_validate(document)


@router.get("/{document_id}/download-url")
def signed_download(document_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    document = db.get(Document, document_id)
    if not document or document.deleted_at:
        raise HTTPException(status_code=404, detail="Document not found")
    require_workspace_role(db, document.workspace_id, user.id, "viewer")
    if get_settings().storage_backend.lower() == "local":
        return {"url": f"/api/v1/documents/{document.id}/file"}
    return {"url": get_storage().signed_get_url(document.object_key)}


@router.get("/{document_id}/file")
def get_file(document_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    document = db.get(Document, document_id)
    if not document or document.deleted_at:
        raise HTTPException(status_code=404, detail="Document not found")
    require_workspace_role(db, document.workspace_id, user.id, "viewer")
    data = get_storage().get_bytes(document.object_key)
    return Response(content=data, media_type=document.mime_type, headers={
        "Content-Disposition": f'inline; filename="{document.original_filename.replace(chr(34), "")}"',
        "Cache-Control": "private, max-age=60",
    })


@router.get("/{document_id}/pages/{page_number}")
def get_page(document_id: str, page_number: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    document = db.get(Document, document_id)
    if not document or document.deleted_at:
        raise HTTPException(status_code=404, detail="Document not found")
    require_workspace_role(db, document.workspace_id, user.id, "viewer")
    page = db.scalar(select(DocumentPage).where(DocumentPage.document_id == document_id, DocumentPage.page_number == page_number))
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return {"page_number": page.page_number, "text": page.text, "ocr_used": page.ocr_used, "ocr_confidence": page.ocr_confidence, "metadata": page.metadata_json}


@router.post("/{document_id}/reprocess", status_code=202)
def reprocess_document(document_id: str, background_tasks: BackgroundTasks, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    document = db.get(Document, document_id)
    if not document or document.deleted_at:
        raise HTTPException(status_code=404, detail="Document not found")
    require_workspace_role(db, document.workspace_id, user.id, "editor")
    document.status = "pending"
    document.processing_progress = 0
    document.error_message = None
    db.commit()
    enqueue_document_processing(background_tasks, document.id)
    return {"id": document.id, "status": "pending"}


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    document = db.get(Document, document_id)
    if not document or document.deleted_at:
        return
    require_workspace_role(db, document.workspace_id, user.id, "editor")
    workspace_id = document.workspace_id
    key = document.object_key
    db.delete(document)
    write_audit(db, workspace_id, user.id, "document.deleted", "document", document_id)
    db.commit()
    get_storage().delete(key)
