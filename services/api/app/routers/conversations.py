from __future__ import annotations

import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from ..db import get_db
from ..dependencies import get_current_user, require_workspace_role
from ..models import Conversation, ConversationDocument, Document, Message, MessageCitation, User
from ..schemas import ChatRequest, ConversationCreate
from ..services.rag import RAGResult, RAGService
from ..services.usage import record_usage

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
    return {"id": conversation.id, "title": conversation.title, "workspace_id": conversation.workspace_id, "pinned": conversation.pinned, "document_ids": document_ids}


@router.get("")
def list_conversations(workspace_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    require_workspace_role(db, workspace_id, user.id, "viewer")
    rows = db.scalars(select(Conversation).where(Conversation.workspace_id == workspace_id, Conversation.user_id == user.id).order_by(Conversation.pinned.desc(), Conversation.updated_at.desc()).limit(100)).all()
    conversation_ids = [row.id for row in rows]
    documents_by_conversation: dict[str, list[str]] = {conversation_id: [] for conversation_id in conversation_ids}
    if conversation_ids:
        links = db.execute(
            select(ConversationDocument.conversation_id, ConversationDocument.document_id).where(
                ConversationDocument.conversation_id.in_(conversation_ids)
            )
        ).all()
        for conversation_id, document_id in links:
            documents_by_conversation[conversation_id].append(document_id)
    return [{
        "id": row.id,
        "title": row.title,
        "pinned": row.pinned,
        "updated_at": row.updated_at,
        "document_ids": documents_by_conversation.get(row.id, []),
    } for row in rows]


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
    if "document_ids" in payload:
        raw_document_ids = payload["document_ids"]
        if not isinstance(raw_document_ids, list) or not all(isinstance(value, str) for value in raw_document_ids):
            raise HTTPException(status_code=422, detail="document_ids must be a list of document IDs")
        document_ids = _validate_documents(db, conversation.workspace_id, raw_document_ids)
        db.execute(delete(ConversationDocument).where(ConversationDocument.conversation_id == conversation.id))
        for document_id in document_ids:
            db.add(ConversationDocument(conversation_id=conversation.id, document_id=document_id))
    else:
        document_ids = list(db.scalars(select(ConversationDocument.document_id).where(
            ConversationDocument.conversation_id == conversation.id
        )).all())
    db.commit()
    return {
        "id": conversation.id,
        "title": conversation.title,
        "pinned": conversation.pinned,
        "updated_at": conversation.updated_at,
        "document_ids": document_ids,
    }


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    conversation = _owned_conversation(db, conversation_id, user)
    db.delete(conversation)
    db.commit()


@router.post("/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: str,
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    conversation = _owned_conversation(db, conversation_id, user)
    existing_doc_ids = db.scalars(
        select(ConversationDocument.document_id).where(
            ConversationDocument.conversation_id == conversation_id
        )
    ).all()
    requested_doc_ids = payload.document_ids or list(existing_doc_ids)
    doc_ids = _validate_documents(db, conversation.workspace_id, requested_doc_ids)
    history_rows = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(12)
    ).all()
    history = [
        {"role": message.role, "content": message.content}
        for message in reversed(history_rows)
        if message.role in {"user", "assistant"} and message.status == "complete"
    ]

    rag = RAGService(db)
    user_message = Message(
        conversation_id=conversation_id,
        role="user",
        content=payload.message,
    )
    assistant_message = Message(
        conversation_id=conversation_id,
        role="assistant",
        content="",
        model=rag.llm.model,
        status="streaming",
    )
    db.add_all([user_message, assistant_message])
    db.commit()

    async def events():
        final_result: RAGResult | None = None
        partial_content = ""
        try:
            yield f"event: status\ndata: {json.dumps({'status': 'retrieving'})}\n\n"
            async for event_type, data in rag.stream_answer(
                workspace_id=conversation.workspace_id,
                question=payload.message,
                document_ids=doc_ids,
                history=history,
            ):
                if event_type == "final":
                    final_result = data if isinstance(data, RAGResult) else None
                    continue
                if (
                    event_type == "token"
                    and isinstance(data, dict)
                    and isinstance(data.get("text"), str)
                ):
                    partial_content += data["text"]
                yield (
                    f"event: {event_type}\n"
                    f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                )

            if final_result is None:
                raise RuntimeError("RAG stream completed without final result")

            assistant_message.content = final_result.answer
            assistant_message.status = "complete"
            assistant_message.model = rag.llm.model
            for citation in final_result.citations:
                db.add(
                    MessageCitation(
                        message_id=assistant_message.id,
                        chunk_id=citation.chunk_id,
                        document_id=citation.document_id,
                        page_number=citation.page_number,
                        source_excerpt=citation.source_excerpt,
                        ordinal=citation.ordinal,
                    )
                )
            record_usage(
                db,
                workspace_id=conversation.workspace_id,
                user_id=user.id,
                metric="ai_messages",
                quantity=1,
                provider=rag.llm.name,
                model=rag.llm.model,
                metadata={"conversation_id": conversation_id},
            )
            db.commit()

            yield (
                "event: citations\n"
                f"data: {json.dumps([citation.__dict__ for citation in final_result.citations], ensure_ascii=False)}\n\n"
            )
            yield (
                "event: done\n"
                f"data: {json.dumps({'message_id': assistant_message.id, 'model': rag.llm.model, 'provider': rag.llm.name})}\n\n"
            )
        except asyncio.CancelledError:
            db.rollback()
            persisted = db.get(Message, assistant_message.id)
            if persisted:
                persisted.content = partial_content.strip()
                persisted.status = "cancelled"
                db.commit()
            return
        except Exception:
            db.rollback()
            persisted = db.get(Message, assistant_message.id)
            if persisted:
                persisted.content = partial_content.strip()
                persisted.status = "failed"
                db.commit()
            yield (
                "event: error\n"
                f"data: {json.dumps({'message': 'Generation failed'}, ensure_ascii=False)}\n\n"
            )

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )

