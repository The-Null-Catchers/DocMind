from __future__ import annotations

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy import func, or_, select
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


@router.get("/library")
def document_library(
    workspace_id: str,
    q: str = Query(default="", max_length=300),
    status: str | None = Query(default=None, max_length=30),
    mime_type: str | None = Query(default=None, max_length=150),
    folder_id: str | None = Query(default=None, max_length=36),
    sort: str = Query(default="created_at", pattern="^(created_at|title|file_size|status)$"),
    direction: str = Query(default="desc", pattern="^(asc|desc)$"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    require_workspace_role(db, workspace_id, user.id, "viewer")
    base_filters = [
        Document.workspace_id == workspace_id,
        Document.deleted_at.is_(None),
    ]
    filters = list(base_filters)
    needle = q.strip()
    if needle:
        pattern = f"%{needle}%"
        filters.append(or_(Document.title.ilike(pattern), Document.original_filename.ilike(pattern)))
    if status:
        filters.append(Document.status == status)
    if mime_type:
        filters.append(Document.mime_type == mime_type)
    if folder_id:
        filters.append(Document.folder_id == folder_id)

    sort_columns = {
        "created_at": Document.created_at,
        "title": Document.title,
        "file_size": Document.file_size,
        "status": Document.status,
    }
    sort_column = sort_columns[sort]
    ordering = sort_column.asc() if direction == "asc" else sort_column.desc()
    rows = db.scalars(
        select(Document)
        .where(*filters)
        .order_by(ordering, Document.id.asc())
        .offset(offset)
        .limit(limit)
    ).all()
    total = int(db.scalar(select(func.count(Document.id)).where(*filters)) or 0)
    statuses = [
        str(value)
        for value in db.scalars(
            select(Document.status)
            .where(*base_filters)
            .distinct()
            .order_by(Document.status.asc())
        ).all()
    ]
    mime_types = [
        str(value)
        for value in db.scalars(
            select(Document.mime_type)
            .where(*base_filters)
            .distinct()
            .order_by(Document.mime_type.asc())
        ).all()
    ]
    return {
        "items": [DocumentOut.model_validate(row).model_dump() for row in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
        "facets": {"statuses": statuses, "mime_types": mime_types},
    }


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




@router.get("/{document_id}/tables")
def get_tables(
    document_id: str,
    page: int | None = Query(default=None, ge=1),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    document = db.get(Document, document_id)
    if not document or document.deleted_at:
        raise HTTPException(status_code=404, detail="Document not found")
    require_workspace_role(db, document.workspace_id, user.id, "viewer")

    statement = select(DocumentPage).where(DocumentPage.document_id == document_id)
    if page is not None:
        statement = statement.where(DocumentPage.page_number == page)
    rows = db.scalars(statement.order_by(DocumentPage.page_number.asc())).all()

    tables: list[dict] = []
    for row in rows:
        metadata = row.metadata_json or {}
        raw_tables = metadata.get("tables", [])
        if not isinstance(raw_tables, list):
            continue
        for raw in raw_tables:
            if not isinstance(raw, dict):
                continue
            table_rows = raw.get("rows", [])
            if not isinstance(table_rows, list):
                continue
            tables.append(
                {
                    "page_number": row.page_number,
                    "table_index": int(raw.get("table_index") or len(tables) + 1),
                    "rows": table_rows,
                    "row_count": int(raw.get("row_count") or len(table_rows)),
                    "column_count": int(raw.get("column_count") or 0),
                    "truncated": bool(raw.get("truncated")),
                }
            )
    return tables

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
