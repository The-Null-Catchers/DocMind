from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..db import get_db
from ..dependencies import get_current_user, require_workspace_role
from ..models import Flashcard, FlashcardDeck, FlashcardReviewEvent, Quiz, QuizAttempt, QuizQuestion, User
from ..schemas import FlashcardReviewRequest
from ..services.study import review_sm2

router = APIRouter(tags=["study"])


class QuizAttemptRequest(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)


def _owned_quiz(db: Session, quiz_id: str, user: User) -> Quiz:
    quiz = db.get(Quiz, quiz_id)
    if not quiz or quiz.user_id != user.id:
        raise HTTPException(status_code=404, detail="Quiz not found")
    require_workspace_role(db, quiz.workspace_id, user.id, "viewer")
    return quiz


@router.get("/flashcards/decks")
def flashcard_decks(workspace_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    require_workspace_role(db, workspace_id, user.id, "viewer")
    decks = db.scalars(select(FlashcardDeck).where(
        FlashcardDeck.workspace_id == workspace_id,
        FlashcardDeck.user_id == user.id,
    ).order_by(FlashcardDeck.updated_at.desc()).limit(100)).all()
    return [{"id": d.id, "name": d.name, "language": d.language, "updated_at": d.updated_at} for d in decks]


@router.get("/flashcards/due")
def due_cards(workspace_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    require_workspace_role(db, workspace_id, user.id, "viewer")
    now = datetime.now(timezone.utc)
    cards = db.scalars(
        select(Flashcard)
        .join(FlashcardDeck, FlashcardDeck.id == Flashcard.deck_id)
        .where(FlashcardDeck.workspace_id == workspace_id, FlashcardDeck.user_id == user.id, (Flashcard.due_at.is_(None)) | (Flashcard.due_at <= now))
        .limit(100)
    ).all()
    return [{"id": c.id, "deck_id": c.deck_id, "front": c.front, "back": c.back, "due_at": c.due_at, "sources": c.source_citations} for c in cards]


def _review_out(card: Flashcard) -> dict:
    return {
        "id": card.id,
        "due_at": card.due_at,
        "interval_days": card.interval_days,
        "ease_factor": card.ease_factor,
        "repetition": card.repetition,
    }


@router.post("/flashcards/{card_id}/review")
def review_card(card_id: str, payload: FlashcardReviewRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    card = db.scalar(select(Flashcard).where(Flashcard.id == card_id).with_for_update())
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    deck = db.get(FlashcardDeck, card.deck_id)
    if not deck or deck.user_id != user.id:
        raise HTTPException(status_code=404, detail="Card not found")
    require_workspace_role(db, deck.workspace_id, user.id, "viewer")

    if payload.idempotency_key:
        existing = db.scalar(
            select(FlashcardReviewEvent).where(
                FlashcardReviewEvent.user_id == user.id,
                FlashcardReviewEvent.idempotency_key == payload.idempotency_key,
            )
        )
        if existing:
            if existing.card_id != card.id or existing.rating != payload.rating:
                raise HTTPException(status_code=409, detail="Idempotency key was already used for a different review")
            return _review_out(card)

    review_sm2(card, payload.rating)
    if payload.idempotency_key:
        db.add(
            FlashcardReviewEvent(
                card_id=card.id,
                user_id=user.id,
                idempotency_key=payload.idempotency_key,
                rating=payload.rating,
            )
        )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if not payload.idempotency_key:
            raise
        existing = db.scalar(
            select(FlashcardReviewEvent).where(
                FlashcardReviewEvent.user_id == user.id,
                FlashcardReviewEvent.idempotency_key == payload.idempotency_key,
            )
        )
        if not existing or existing.card_id != card_id or existing.rating != payload.rating:
            raise HTTPException(status_code=409, detail="Idempotency key conflict")
        card = db.get(Flashcard, card_id)
        if not card:
            raise HTTPException(status_code=404, detail="Card not found")
    return _review_out(card)


@router.get("/quizzes")
def list_quizzes(workspace_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    require_workspace_role(db, workspace_id, user.id, "viewer")
    rows = db.scalars(select(Quiz).where(
        Quiz.workspace_id == workspace_id,
        Quiz.user_id == user.id,
    ).order_by(Quiz.updated_at.desc()).limit(100)).all()
    return [{"id": q.id, "title": q.title, "language": q.language, "difficulty": q.difficulty, "updated_at": q.updated_at} for q in rows]


@router.get("/quizzes/{quiz_id}")
def get_quiz(quiz_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    quiz = _owned_quiz(db, quiz_id, user)
    questions = db.scalars(select(QuizQuestion).where(QuizQuestion.quiz_id == quiz.id).order_by(QuizQuestion.created_at.asc())).all()
    return {
        "id": quiz.id,
        "title": quiz.title,
        "language": quiz.language,
        "difficulty": quiz.difficulty,
        "questions": [{
            "id": q.id,
            "question_type": q.question_type,
            "question": q.question,
            "options": q.options,
            "sources": q.source_citations,
        } for q in questions],
    }


@router.post("/quizzes/{quiz_id}/attempts", status_code=201)
def submit_quiz_attempt(quiz_id: str, payload: QuizAttemptRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    quiz = _owned_quiz(db, quiz_id, user)
    questions = db.scalars(select(QuizQuestion).where(QuizQuestion.quiz_id == quiz.id)).all()
    if not questions:
        raise HTTPException(status_code=409, detail="Quiz has no questions")

    results = []
    correct = 0
    for question in questions:
        supplied = str(payload.answers.get(question.id, "")).strip()
        expected = question.answer.strip()
        is_correct = supplied.casefold() == expected.casefold()
        if is_correct:
            correct += 1
        results.append({
            "question_id": question.id,
            "correct": is_correct,
            "answer": expected,
            "explanation": question.explanation,
            "sources": question.source_citations,
        })
    score = correct / len(questions) * 100.0
    attempt = QuizAttempt(quiz_id=quiz.id, user_id=user.id, score=score, answers=payload.answers)
    db.add(attempt)
    db.commit()
    return {"attempt_id": attempt.id, "score": score, "correct": correct, "total": len(questions), "results": results}


@router.get("/quizzes/{quiz_id}/attempts")
def quiz_attempts(quiz_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    quiz = _owned_quiz(db, quiz_id, user)
    rows = db.scalars(select(QuizAttempt).where(
        QuizAttempt.quiz_id == quiz.id,
        QuizAttempt.user_id == user.id,
    ).order_by(QuizAttempt.created_at.desc()).limit(50)).all()
    return [{"id": row.id, "score": row.score, "created_at": row.created_at} for row in rows]
