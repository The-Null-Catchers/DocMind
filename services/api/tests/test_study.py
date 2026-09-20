from datetime import datetime, timezone
from app.models import Flashcard, FlashcardDeck
from app.services.study import review_sm2


def test_sm2_review_advances_due_date():
    card = Flashcard(deck_id="deck", front="Q", back="A", source_citations=[], difficulty="medium", tags=[])
    now = datetime(2026, 9, 16, tzinfo=timezone.utc)
    review_sm2(card, "good", now)
    assert card.repetition == 1
    assert card.interval_days == 1
    assert card.due_at > now


def test_flashcard_review_endpoint_is_idempotent(client, db, auth):
    headers, auth_data = auth
    workspace = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "Study", "kind": "personal"},
    ).json()
    deck = FlashcardDeck(
        workspace_id=workspace["id"],
        user_id=auth_data["user"]["id"],
        name="Idempotency",
        language="en",
    )
    db.add(deck)
    db.flush()
    card = Flashcard(
        deck_id=deck.id,
        front="Question",
        back="Answer",
        source_citations=[],
        difficulty="medium",
        tags=[],
    )
    db.add(card)
    db.commit()
    card_id = card.id

    payload = {"rating": "good", "idempotency_key": "review-test-0001"}
    first = client.post(f"/api/v1/flashcards/{card_id}/review", headers=headers, json=payload)
    second = client.post(f"/api/v1/flashcards/{card_id}/review", headers=headers, json=payload)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    db.expire_all()
    persisted = db.get(Flashcard, card_id)
    assert persisted is not None
    assert persisted.repetition == 1
    assert persisted.interval_days == 1


def test_flashcard_review_rejects_reused_key_for_different_rating(client, db, auth):
    headers, auth_data = auth
    workspace = client.post(
        "/api/v1/workspaces",
        headers=headers,
        json={"name": "Study conflict", "kind": "personal"},
    ).json()
    deck = FlashcardDeck(
        workspace_id=workspace["id"],
        user_id=auth_data["user"]["id"],
        name="Conflict",
        language="en",
    )
    db.add(deck)
    db.flush()
    card = Flashcard(
        deck_id=deck.id,
        front="Question",
        back="Answer",
        source_citations=[],
        difficulty="medium",
        tags=[],
    )
    db.add(card)
    db.commit()

    first = client.post(
        f"/api/v1/flashcards/{card.id}/review",
        headers=headers,
        json={"rating": "good", "idempotency_key": "review-test-0002"},
    )
    conflict = client.post(
        f"/api/v1/flashcards/{card.id}/review",
        headers=headers,
        json={"rating": "easy", "idempotency_key": "review-test-0002"},
    )

    assert first.status_code == 200, first.text
    assert conflict.status_code == 409
