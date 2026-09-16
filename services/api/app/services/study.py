from __future__ import annotations

from datetime import datetime, timedelta, timezone
from ..models import Flashcard

RATING_QUALITY = {"again": 1, "hard": 3, "good": 4, "easy": 5}


def review_sm2(card: Flashcard, rating: str, now: datetime | None = None) -> None:
    if rating not in RATING_QUALITY:
        raise ValueError("Unknown flashcard rating")
    now = now or datetime.now(timezone.utc)
    quality = RATING_QUALITY[rating]
    card.repetition = card.repetition or 0
    card.interval_days = card.interval_days or 0
    card.ease_factor = card.ease_factor or 2.5
    if quality < 3:
        card.repetition = 0
        card.interval_days = 1
    else:
        if card.repetition == 0:
            card.interval_days = 1
        elif card.repetition == 1:
            card.interval_days = 6
        else:
            card.interval_days = max(1, round(card.interval_days * card.ease_factor))
        card.repetition += 1
    card.ease_factor = max(1.3, card.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    if rating == "easy":
        card.interval_days = max(card.interval_days, round(card.interval_days * 1.3))
    elif rating == "hard":
        card.interval_days = max(1, round(card.interval_days * 0.75))
    card.due_at = now + timedelta(days=card.interval_days)
