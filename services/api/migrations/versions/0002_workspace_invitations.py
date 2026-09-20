"""Workspace invitations.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("workspace_invitations"):
        return
    op.create_table(
        "workspace_invitations",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("workspace_id", sa.String(36), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("invited_by_id", sa.String(36), nullable=True),
        sa.Column("accepted_by_id", sa.String(36), nullable=True),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["accepted_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    for column in [
        "workspace_id",
        "email",
        "role",
        "invited_by_id",
        "accepted_by_id",
        "token_hash",
        "status",
        "expires_at",
        "last_sent_at",
    ]:
        op.create_index(
            f"ix_workspace_invitations_{column}",
            "workspace_invitations",
            [column],
            unique=column == "token_hash",
        )


def downgrade() -> None:
    op.drop_table("workspace_invitations")
