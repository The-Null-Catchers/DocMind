from __future__ import annotations

import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..dependencies import get_current_user, require_workspace_role
from ..models import Conversation, ConversationDocument, Document, Message, MessageCitation, User
from ..schemas import ChatRequest, ConversationCreate
from ..services.rag import RAGService

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _owned_conversation(db: Session, conversation_id: str, user: User) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if not conversation or conversation.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    require_workspace_role(db, conversation.workspace_id, user.id, "viewer")
    return conversation


def _validate_documents(db: Session, workspace_id: str, document_ids: list[str]) -> list[str]:
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


@router.post("", status_code=201)
def create_conversation(payload: ConversationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_workspace_role(db, payload.workspace_id, user.id, "viewer")
    document_ids = _validate_documents(db, payload.workspace_id, payload.document_ids)
    conversation = Conversation(workspace_id=payload.workspace_id, user_id=user.id, title=payload.title.strip() or "New conversation")
    db.add(conversation)
    db.flush()
    for document_id in document_ids:
        db.add(ConversationDocument(conversation_id=conversation.id, document_id=document_id))
    db.commit()
    return {"id": conversation.id, "title": conversation.title, "workspace_id": conversation.workspace_id, "pinned": conversation.pinned}


@router.get("")
def list_conversations(workspace_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    require_workspace_role(db, workspace_id, user.id, "viewer")
    rows = db.scalars(select(Conversation).where(Conversation.workspace_id == workspace_id, Conversation.user_id == user.id).order_by(Conversation.pinned.desc(), Conversation.updated_at.desc()).limit(100)).all()
    return [{"id": c.id, "title": c.title, "pinned": c.pinned, "updated_at": c.updated_at} for c in rows]


@router.get("/{conversation_id}/messages")
def list_messages(conversation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    _owned_conversation(db, conversation_id, user)
    rows = db.scalars(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc()).limit(500)).all()
    message_ids = [row.id for row in rows]
    citations_by_message: dict[str, list[dict]] = {message_id: [] for message_id in message_ids}
    if message_ids:
        citations = db.scalars(select(MessageCitation).where(MessageCitation.message_id.in_(message_ids)).order_by(MessageCitation.ordinal.asc())).all()
        for citation in citations:
            citations_by_message[citation.message_id].append({
                "ordinal": citation.ordinal,
                "chunk_id": citation.chunk_id,
                "document_id": citation.document_id,
                "page_number": citation.page_number,
                "source_excerpt": citation.source_excerpt,
            })
    return [{
        "id": row.id,
        "role": row.role,
        "content": row.content,
        "status": row.status,
        "model": row.model,
        "created_at": row.created_at,
        "citations": citations_by_message.get(row.id, []),
    } for row in rows]


@router.patch("/{conversation_id}")
def update_conversation(conversation_id: str, payload: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    conversation = _owned_conversation(db, conversation_id, user)
    if "title" in payload:
        title = str(payload["title"]).strip()
        if not title or len(title) > 240:
            raise HTTPException(status_code=422, detail="Title must be between 1 and 240 characters")
        conversation.title = title
    if "pinned" in payload:
        conversation.pinned = bool(payload["pinned"])
    db.commit()
    return {"id": conversation.id, "title": conversation.title, "pinned": conversation.pinned, "updated_at": conversation.updated_at}


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    conversation = _owned_conversation(db, conversation_id, user)
    db.delete(conversation)
    db.commit()


@router.post("/{conversation_id}/messages/stream")
async def stream_message(conversation_id: str, payload: ChatRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> StreamingResponse:
    conversation = _owned_conversation(db, conversation_id, user)
    existing_doc_ids = db.scalars(select(ConversationDocument.document_id).where(ConversationDocument.conversation_id == conversation_id)).all()
    requested_doc_ids = payload.document_ids or list(existing_doc_ids)
    doc_ids = _validate_documents(db, conversation.workspace_id, requested_doc_ids)
    history_rows = db.scalars(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.desc()).limit(12)).all()
    history = [{"role": m.role, "content": m.content} for m in reversed(history_rows) if m.role in {"user", "assistant"}]
    user_message = Message(conversation_id=conversation_id, role="user", content=payload.message)
    db.add(user_message)
    db.commit()

    async def events():
        try:
            yield f"event: status\ndata: {json.dumps({'status': 'retrieving'})}\n\n"
            result = await RAGService(db).answer(workspace_id=conversation.workspace_id, question=payload.message, document_ids=doc_ids, history=history)
            assistant_message = Message(conversation_id=conversation_id, role="assistant", content=result.answer, model="configured", status="complete")
            db.add(assistant_message)
            db.flush()
            for citation in result.citations:
                db.add(MessageCitation(
                    message_id=assistant_message.id,
                    chunk_id=citation.chunk_id,
                    document_id=citation.document_id,
                    page_number=citation.page_number,
                    source_excerpt=citation.source_excerpt,
                    ordinal=citation.ordinal,
                ))
            db.commit()
            for token in result.answer.split(" "):
                yield f"event: token\ndata: {json.dumps({'text': token + ' '}, ensure_ascii=False)}\n\n"
            yield f"event: citations\ndata: {json.dumps([c.__dict__ for c in result.citations], ensure_ascii=False)}\n\n"
            yield f"event: done\ndata: {json.dumps({'message_id': assistant_message.id})}\n\n"
        except Exception as exc:
            db.rollback()
            yield f"event: error\ndata: {json.dumps({'message': 'Generation failed'}, ensure_ascii=False)}\n\n"
            raise exc

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
