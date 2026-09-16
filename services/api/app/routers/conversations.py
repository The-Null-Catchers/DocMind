from __future__ import annotations

import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..dependencies import get_current_user, require_workspace_role
from ..models import Conversation, ConversationDocument, Message, MessageCitation, User
from ..schemas import ChatRequest, ConversationCreate
from ..services.rag import RAGService

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("", status_code=201)
def create_conversation(payload: ConversationCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_workspace_role(db, payload.workspace_id, user.id, "viewer")
    conversation = Conversation(workspace_id=payload.workspace_id, user_id=user.id, title=payload.title)
    db.add(conversation)
    db.flush()
    for document_id in payload.document_ids:
        db.add(ConversationDocument(conversation_id=conversation.id, document_id=document_id))
    db.commit()
    return {"id": conversation.id, "title": conversation.title, "workspace_id": conversation.workspace_id}


@router.get("")
def list_conversations(workspace_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    require_workspace_role(db, workspace_id, user.id, "viewer")
    rows = db.scalars(select(Conversation).where(Conversation.workspace_id == workspace_id, Conversation.user_id == user.id).order_by(Conversation.updated_at.desc()).limit(100)).all()
    return [{"id": c.id, "title": c.title, "pinned": c.pinned, "updated_at": c.updated_at} for c in rows]


@router.post("/{conversation_id}/messages/stream")
async def stream_message(conversation_id: str, payload: ChatRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> StreamingResponse:
    conversation = db.get(Conversation, conversation_id)
    if not conversation or conversation.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    require_workspace_role(db, conversation.workspace_id, user.id, "viewer")
    existing_doc_ids = db.scalars(select(ConversationDocument.document_id).where(ConversationDocument.conversation_id == conversation_id)).all()
    doc_ids = payload.document_ids or list(existing_doc_ids)
    history_rows = db.scalars(select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.desc()).limit(12)).all()
    history = [{"role": m.role, "content": m.content} for m in reversed(history_rows) if m.role in {"user", "assistant"}]
    user_message = Message(conversation_id=conversation_id, role="user", content=payload.message)
    db.add(user_message)
    db.commit()

    async def events():
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

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
