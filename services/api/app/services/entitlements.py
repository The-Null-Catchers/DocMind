from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Document, Subscription, UsageRecord, WorkspaceMember


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


class EntitlementExceeded(RuntimeError):
    def __init__(self, *, metric: str, current: float, limit: float, requested: float = 0):
        self.metric = metric
        self.current = current
        self.limit = limit
        self.requested = requested
        super().__init__(
            f"{metric} limit exceeded: current={current:g}, requested={requested:g}, limit={limit:g}"
        )


def entitlements_for(plan: str) -> PlanEntitlements:
    return PLANS.get(plan, PLANS["free"])


def workspace_plan(db: Session, workspace_id: str) -> tuple[str, PlanEntitlements]:
    plan = db.scalar(
        select(Subscription.plan).where(
            Subscription.workspace_id == workspace_id,
            Subscription.status == "active",
        )
    ) or "free"
    return plan, entitlements_for(plan)


def _month_start() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc)


def monthly_usage(db: Session, workspace_id: str, metric: str) -> float:
    value = db.scalar(
        select(func.coalesce(func.sum(UsageRecord.quantity), 0.0)).where(
            UsageRecord.workspace_id == workspace_id,
            UsageRecord.metric == metric,
            UsageRecord.created_at >= _month_start(),
        )
    )
    return float(value or 0.0)


def require_monthly_capacity(
    db: Session,
    workspace_id: str,
    metric: str,
    *,
    quantity: float = 1,
) -> None:
    _plan, limits = workspace_plan(db, workspace_id)
    limit_by_metric = {
        "processed_pages": limits.max_pages_month,
        "ai_messages": limits.max_ai_messages_month,
        "ocr_pages": limits.max_ocr_pages_month,
    }
    if metric not in limit_by_metric:
        raise ValueError(f"Unsupported entitlement metric: {metric}")
    limit = float(limit_by_metric[metric])
    current = monthly_usage(db, workspace_id, metric)
    if current + quantity > limit:
        raise EntitlementExceeded(
            metric=metric,
            current=current,
            requested=quantity,
            limit=limit,
        )


def require_document_capacity(
    db: Session,
    workspace_id: str,
    *,
    incoming_bytes: int,
) -> None:
    _plan, limits = workspace_plan(db, workspace_id)
    filters = (
        Document.workspace_id == workspace_id,
        Document.deleted_at.is_(None),
    )
    document_count = int(
        db.scalar(select(func.count(Document.id)).where(*filters)) or 0
    )
    if document_count + 1 > limits.max_documents:
        raise EntitlementExceeded(
            metric="documents",
            current=document_count,
            requested=1,
            limit=limits.max_documents,
        )
    storage_bytes = int(
        db.scalar(select(func.coalesce(func.sum(Document.file_size), 0)).where(*filters))
        or 0
    )
    if storage_bytes + incoming_bytes > limits.max_storage_bytes:
        raise EntitlementExceeded(
            metric="storage_bytes",
            current=storage_bytes,
            requested=incoming_bytes,
            limit=limits.max_storage_bytes,
        )


def require_member_capacity(
    db: Session,
    workspace_id: str,
    *,
    additional_members: int = 1,
) -> None:
    _plan, limits = workspace_plan(db, workspace_id)
    current = int(
        db.scalar(
            select(func.count(WorkspaceMember.id)).where(
                WorkspaceMember.workspace_id == workspace_id
            )
        )
        or 0
    )
    if current + additional_members > limits.max_members:
        raise EntitlementExceeded(
            metric="workspace_members",
            current=current,
            requested=additional_members,
            limit=limits.max_members,
        )


def record_document_processing_usage(
    db: Session,
    *,
    workspace_id: str,
    document_id: str,
    processed_pages: int,
    ocr_pages: int,
) -> None:
    """Record processing usage once per document/version in the current month.

    Reprocessing replaces this month's prior per-document usage records so retries
    do not double-charge page or OCR quotas.
    """

    start = _month_start()
    existing = db.scalars(
        select(UsageRecord).where(
            UsageRecord.workspace_id == workspace_id,
            UsageRecord.metric.in_(["processed_pages", "ocr_pages"]),
            UsageRecord.created_at >= start,
        )
    ).all()
    for row in existing:
        if (row.metadata_json or {}).get("document_id") == document_id:
            db.delete(row)

    db.add_all(
        [
            UsageRecord(
                workspace_id=workspace_id,
                user_id=None,
                metric="processed_pages",
                quantity=float(processed_pages),
                metadata_json={"document_id": document_id, "source": "document_processing"},
            ),
            UsageRecord(
                workspace_id=workspace_id,
                user_id=None,
                metric="ocr_pages",
                quantity=float(ocr_pages),
                metadata_json={"document_id": document_id, "source": "document_processing"},
            ),
        ]
    )
