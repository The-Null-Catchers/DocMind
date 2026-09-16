"""Initial DocMind schema.

Revision ID: 0001
Revises:
"""
from alembic import op
from app.db import Base
from app import models  # noqa: F401

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=bind)
    # Native pgvector acceleration lives beside the portable JSON embedding representation.
    # This allows SQLite deterministic CI while production can backfill/index vectors natively.
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE embeddings ADD COLUMN IF NOT EXISTS vector_native vector(384)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_embeddings_workspace_model ON embeddings (workspace_id, provider, model)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_embeddings_vector_hnsw ON embeddings USING hnsw (vector_native vector_cosine_ops)")


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
