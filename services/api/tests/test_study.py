from datetime import datetime, timezone
from app.models import Flashcard
from app.services.study import review_sm2


def test_sm2_review_advances_due_date():
    card = Flashcard(deck_id="deck", front="Q", back="A", source_citations=[], difficulty="medium", tags=[])
    now = datetime(2026, 9, 16, tzinfo=timezone.utc)
    review_sm2(card, "good", now)
    assert card.repetition == 1
    assert card.interval_days == 1
    assert card.due_at > now
