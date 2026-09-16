from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..dependencies import get_current_user, require_workspace_role
from ..models import Collection, CollectionDocument, Folder, Note, SavedPrompt, Tag, User

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


@router.post("/folders", status_code=201)
def create_folder(payload: NamePayload, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_workspace_role(db, payload.workspace_id, user.id, "editor")
    folder = Folder(workspace_id=payload.workspace_id, name=payload.name)
    db.add(folder); db.commit(); return {"id": folder.id, "name": folder.name}


@router.post("/tags", status_code=201)
def create_tag(payload: NamePayload, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_workspace_role(db, payload.workspace_id, user.id, "editor")
    tag = Tag(workspace_id=payload.workspace_id, name=payload.name)
    db.add(tag); db.commit(); return {"id": tag.id, "name": tag.name}


@router.post("/collections", status_code=201)
def create_collection(payload: CollectionPayload, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_workspace_role(db, payload.workspace_id, user.id, "editor")
    collection = Collection(workspace_id=payload.workspace_id, created_by_id=user.id, name=payload.name, description=payload.description)
    db.add(collection); db.flush()
    for document_id in payload.document_ids:
        db.add(CollectionDocument(collection_id=collection.id, document_id=document_id))
    db.commit(); return {"id": collection.id, "name": collection.name, "document_ids": payload.document_ids}


@router.get("/collections")
def collections(workspace_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    require_workspace_role(db, workspace_id, user.id, "viewer")
    rows = db.scalars(select(Collection).where(Collection.workspace_id == workspace_id).order_by(Collection.updated_at.desc())).all()
    return [{"id": c.id, "name": c.name, "description": c.description} for c in rows]


@router.post("/notes", status_code=201)
def create_note(payload: NotePayload, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_workspace_role(db, payload.workspace_id, user.id, "editor")
    note = Note(workspace_id=payload.workspace_id, user_id=user.id, title=payload.title, content_markdown=payload.content_markdown, source_links=payload.source_links)
    db.add(note); db.commit(); return {"id": note.id, "title": note.title, "content_markdown": note.content_markdown, "source_links": note.source_links}


@router.get("/notes")
def notes(workspace_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    require_workspace_role(db, workspace_id, user.id, "viewer")
    rows = db.scalars(select(Note).where(Note.workspace_id == workspace_id, Note.user_id == user.id).order_by(Note.updated_at.desc())).all()
    return [{"id": n.id, "title": n.title, "content_markdown": n.content_markdown, "source_links": n.source_links, "updated_at": n.updated_at} for n in rows]


@router.post("/saved-prompts", status_code=201)
def create_prompt(payload: PromptPayload, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    if payload.workspace_id:
        require_workspace_role(db, payload.workspace_id, user.id, "viewer")
    row = SavedPrompt(user_id=user.id, workspace_id=payload.workspace_id, name=payload.name, prompt=payload.prompt)
    db.add(row); db.commit(); return {"id": row.id, "name": row.name, "prompt": row.prompt}
