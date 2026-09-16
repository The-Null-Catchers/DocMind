from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..dependencies import get_current_user, require_workspace_role
from ..models import Flashcard, FlashcardDeck, User
from ..schemas import FlashcardReviewRequest
from ..services.study import review_sm2

router = APIRouter(prefix="/flashcards", tags=["study"])


@router.get("/due")
def due_cards(workspace_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    require_workspace_role(db, workspace_id, user.id, "viewer")
    now = datetime.now(timezone.utc)
    cards = db.scalars(
        select(Flashcard)
        .join(FlashcardDeck, FlashcardDeck.id == Flashcard.deck_id)
        .where(FlashcardDeck.workspace_id == workspace_id, FlashcardDeck.user_id == user.id, (Flashcard.due_at.is_(None)) | (Flashcard.due_at <= now))
        .limit(100)
    ).all()
    return [{"id": c.id, "front": c.front, "back": c.back, "due_at": c.due_at, "sources": c.source_citations} for c in cards]


@router.post("/{card_id}/review")
def review_card(card_id: str, payload: FlashcardReviewRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    card = db.get(Flashcard, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    deck = db.get(FlashcardDeck, card.deck_id)
    if not deck or deck.user_id != user.id:
        raise HTTPException(status_code=404, detail="Card not found")
    require_workspace_role(db, deck.workspace_id, user.id, "viewer")
    review_sm2(card, payload.rating)
    db.commit()
    return {"id": card.id, "due_at": card.due_at, "interval_days": card.interval_days, "ease_factor": card.ease_factor}
