from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from ..db import get_db
from ..dependencies import get_current_user, require_workspace_role
from ..models import Collection, CollectionDocument, Document, Folder, Note, SavedPrompt, Tag, User

router = APIRouter(tags=["library"])


class NamePayload(BaseModel):
    workspace_id: str
    name: str = Field(min_length=1, max_length=180)


class CollectionPayload(NamePayload):
    description: str | None = Field(default=None, max_length=2000)
    document_ids: list[str] = Field(default_factory=list, max_length=200)


class NotePayload(BaseModel):
    workspace_id: str
    title: str = Field(min_length=1, max_length=300)
    content_markdown: str = Field(default="", max_length=200000)
    source_links: list[dict] = Field(default_factory=list, max_length=100)


class PromptPayload(BaseModel):
    workspace_id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    prompt: str = Field(min_length=1, max_length=12000)


def _validate_collection_documents(db: Session, workspace_id: str, document_ids: list[str]) -> list[str]:
    if not document_ids:
        return []
    unique_ids = list(dict.fromkeys(document_ids))
    valid_ids = set(db.scalars(select(Document.id).where(
        Document.id.in_(unique_ids),
        Document.workspace_id == workspace_id,
        Document.deleted_at.is_(None),
    )).all())
    if valid_ids != set(unique_ids):
        raise HTTPException(status_code=400, detail="One or more documents are not available in this workspace")
    return unique_ids


@router.post("/folders", status_code=201)
def create_folder(payload: NamePayload, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_workspace_role(db, payload.workspace_id, user.id, "editor")
    folder = Folder(workspace_id=payload.workspace_id, name=payload.name.strip())
    db.add(folder)
    db.commit()
    return {"id": folder.id, "name": folder.name, "parent_id": folder.parent_id}


@router.get("/folders")
def folders(workspace_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    require_workspace_role(db, workspace_id, user.id, "viewer")
    rows = db.scalars(select(Folder).where(Folder.workspace_id == workspace_id).order_by(Folder.name.asc()).limit(500)).all()
    return [{"id": row.id, "name": row.name, "parent_id": row.parent_id} for row in rows]


@router.post("/tags", status_code=201)
def create_tag(payload: NamePayload, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_workspace_role(db, payload.workspace_id, user.id, "editor")
    tag = Tag(workspace_id=payload.workspace_id, name=payload.name.strip())
    db.add(tag)
    db.commit()
    return {"id": tag.id, "name": tag.name}


@router.get("/tags")
def tags(workspace_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    require_workspace_role(db, workspace_id, user.id, "viewer")
    rows = db.scalars(select(Tag).where(Tag.workspace_id == workspace_id).order_by(Tag.name.asc()).limit(500)).all()
    return [{"id": row.id, "name": row.name} for row in rows]


@router.post("/collections", status_code=201)
def create_collection(payload: CollectionPayload, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_workspace_role(db, payload.workspace_id, user.id, "editor")
    document_ids = _validate_collection_documents(db, payload.workspace_id, payload.document_ids)
    collection = Collection(
        workspace_id=payload.workspace_id,
        created_by_id=user.id,
        name=payload.name.strip(),
        description=payload.description,
    )
    db.add(collection)
    db.flush()
    for document_id in document_ids:
        db.add(CollectionDocument(collection_id=collection.id, document_id=document_id))
    db.commit()
    return {"id": collection.id, "name": collection.name, "description": collection.description, "document_ids": document_ids}


@router.get("/collections")
def collections(workspace_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    require_workspace_role(db, workspace_id, user.id, "viewer")
    rows = db.scalars(select(Collection).where(Collection.workspace_id == workspace_id).order_by(Collection.updated_at.desc()).limit(200)).all()
    collection_ids = [row.id for row in rows]
    documents_by_collection: dict[str, list[str]] = {collection_id: [] for collection_id in collection_ids}
    if collection_ids:
        links = db.scalars(select(CollectionDocument).where(CollectionDocument.collection_id.in_(collection_ids))).all()
        for link in links:
            documents_by_collection[link.collection_id].append(link.document_id)
    return [{
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "document_ids": documents_by_collection.get(row.id, []),
    } for row in rows]


@router.post("/notes", status_code=201)
def create_note(payload: NotePayload, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_workspace_role(db, payload.workspace_id, user.id, "editor")
    note = Note(
        workspace_id=payload.workspace_id,
        user_id=user.id,
        title=payload.title,
        content_markdown=payload.content_markdown,
        source_links=payload.source_links,
    )
    db.add(note)
    db.commit()
    return {"id": note.id, "title": note.title, "content_markdown": note.content_markdown, "source_links": note.source_links}


@router.get("/notes")
def notes(workspace_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    require_workspace_role(db, workspace_id, user.id, "viewer")
    rows = db.scalars(select(Note).where(
        Note.workspace_id == workspace_id,
        Note.user_id == user.id,
    ).order_by(Note.updated_at.desc()).limit(500)).all()
    return [{"id": n.id, "title": n.title, "content_markdown": n.content_markdown, "source_links": n.source_links, "updated_at": n.updated_at} for n in rows]


@router.post("/saved-prompts", status_code=201)
def create_prompt(payload: PromptPayload, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if payload.workspace_id:
        require_workspace_role(db, payload.workspace_id, user.id, "viewer")
    row = SavedPrompt(
        user_id=user.id,
        workspace_id=payload.workspace_id,
        name=payload.name.strip(),
        prompt=payload.prompt,
    )
    db.add(row)
    db.commit()
    return {"id": row.id, "workspace_id": row.workspace_id, "name": row.name, "prompt": row.prompt}


@router.get("/saved-prompts")
def saved_prompts(workspace_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    if workspace_id:
        require_workspace_role(db, workspace_id, user.id, "viewer")
        scope = or_(SavedPrompt.workspace_id == workspace_id, SavedPrompt.workspace_id.is_(None))
    else:
        scope = SavedPrompt.workspace_id.is_(None)
    rows = db.scalars(select(SavedPrompt).where(
        SavedPrompt.user_id == user.id,
        scope,
    ).order_by(SavedPrompt.updated_at.desc()).limit(200)).all()
    return [{"id": row.id, "workspace_id": row.workspace_id, "name": row.name, "prompt": row.prompt} for row in rows]
