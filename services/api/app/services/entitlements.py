from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanEntitlements:
    max_documents: int
    max_storage_bytes: int
    max_pages_month: int
    max_ai_messages_month: int
    max_ocr_pages_month: int
    max_members: int
    reranking: bool


PLANS = {
    "free": PlanEntitlements(50, 1_000_000_000, 500, 300, 100, 1, False),
    "pro": PlanEntitlements(2_000, 100_000_000_000, 20_000, 10_000, 5_000, 5, True),
    "team": PlanEntitlements(20_000, 1_000_000_000_000, 200_000, 100_000, 50_000, 100, True),
}


def entitlements_for(plan: str) -> PlanEntitlements:
    return PLANS.get(plan, PLANS["free"])
