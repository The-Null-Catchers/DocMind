from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..dependencies import get_current_user, require_workspace_role
from ..models import Document, DocumentChunk, Flashcard, FlashcardDeck, Quiz, QuizQuestion, User
from ..services.extraction import StructuredExtractionService
from ..services.rag import RAGService

router = APIRouter(tags=["ai-tools"])


class DocumentsRequest(BaseModel):
    workspace_id: str
    document_ids: list[str] = Field(min_length=1, max_length=20)
    language: str = Field(default="auto", pattern="^(auto|en|ar)$")


class SummaryRequest(DocumentsRequest):
    style: str = Field(default="detailed", pattern="^(short|detailed|executive|bullet|study)$")


class CompareRequest(DocumentsRequest):
    focus: str | None = Field(default=None, max_length=2000)


class ExtractionRequest(DocumentsRequest):
    schema_definition: dict


class StudyGenerateRequest(DocumentsRequest):
    count: int = Field(default=10, ge=1, le=50)
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")


@router.post("/summaries/generate")
async def summary(payload: SummaryRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_workspace_role(db, payload.workspace_id, user.id, "viewer")
    result = await RAGService(db).answer(workspace_id=payload.workspace_id, document_ids=payload.document_ids, question=f"Create a {payload.style} summary of the selected documents. Include the important findings and cite every document-derived claim.")
    return {"content": result.answer, "citations": [c.__dict__ for c in result.citations]}


@router.post("/compare")
async def compare(payload: CompareRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_workspace_role(db, payload.workspace_id, user.id, "viewer")
    question = "Compare these documents: identify similarities, differences, contradictions, shared topics, key metrics, and timeline differences."
    if payload.focus:
        question += f" Focus especially on: {payload.focus}."
    result = await RAGService(db).answer(workspace_id=payload.workspace_id, document_ids=payload.document_ids, question=question)
    return {"content": result.answer, "citations": [c.__dict__ for c in result.citations]}


@router.post("/extract")
async def extract(payload: ExtractionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_workspace_role(db, payload.workspace_id, user.id, "viewer")
    return await StructuredExtractionService(db).extract(workspace_id=payload.workspace_id, document_ids=payload.document_ids, schema=payload.schema_definition)


@router.post("/flashcards/generate", status_code=201)
def generate_flashcards(payload: StudyGenerateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_workspace_role(db, payload.workspace_id, user.id, "viewer")
    chunks = db.scalars(select(DocumentChunk).where(DocumentChunk.workspace_id == payload.workspace_id, DocumentChunk.document_id.in_(payload.document_ids)).order_by(DocumentChunk.document_id, DocumentChunk.chunk_index).limit(payload.count)).all()
    deck = FlashcardDeck(workspace_id=payload.workspace_id, user_id=user.id, name="Generated study deck", language="ar" if payload.language == "ar" else "en")
    db.add(deck); db.flush()
    cards=[]
    for chunk in chunks:
        sentence = chunk.text.split(".")[0].strip()[:300] or chunk.text[:300]
        front = ("اشرح: " if payload.language == "ar" else "Explain: ") + sentence
        card = Flashcard(deck_id=deck.id, front=front, back=chunk.text[:900], source_citations=[{"chunk_id": chunk.id, "document_id": chunk.document_id, "page_number": chunk.page_start}], difficulty=payload.difficulty, tags=[])
        db.add(card); cards.append(card)
    db.commit()
    return {"deck_id": deck.id, "count": len(cards)}


@router.post("/quizzes/generate", status_code=201)
def generate_quiz(payload: StudyGenerateRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    require_workspace_role(db, payload.workspace_id, user.id, "viewer")
    chunks = db.scalars(select(DocumentChunk).where(DocumentChunk.workspace_id == payload.workspace_id, DocumentChunk.document_id.in_(payload.document_ids)).order_by(DocumentChunk.document_id, DocumentChunk.chunk_index).limit(payload.count)).all()
    quiz = Quiz(workspace_id=payload.workspace_id, user_id=user.id, title="Generated document quiz", language="ar" if payload.language == "ar" else "en", difficulty=payload.difficulty)
    db.add(quiz); db.flush()
    count=0
    for chunk in chunks:
        prompt = ("ما الفكرة الرئيسية في هذا الجزء؟" if payload.language == "ar" else "What is the main idea of this source section?")
        question = QuizQuestion(quiz_id=quiz.id, question_type="short_answer", question=prompt, options=[], answer=chunk.text[:350], explanation=chunk.text[:700], source_citations=[{"chunk_id": chunk.id, "document_id": chunk.document_id, "page_number": chunk.page_start}])
        db.add(question); count += 1
    db.commit(); return {"quiz_id": quiz.id, "count": count}
