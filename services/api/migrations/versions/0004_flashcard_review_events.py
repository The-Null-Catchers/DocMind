"""Idempotent flashcard review events.

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "flashcard_review_events",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("card_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("rating", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["card_id"], ["flashcards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_flashcard_review_user_key"),
    )
    op.create_index("ix_flashcard_review_events_card_id", "flashcard_review_events", ["card_id"])
    op.create_index("ix_flashcard_review_events_user_id", "flashcard_review_events", ["user_id"])
    op.create_index("ix_flashcard_review_events_idempotency_key", "flashcard_review_events", ["idempotency_key"])


def downgrade() -> None:
    op.drop_table("flashcard_review_events")
