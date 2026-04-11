"""add_pgvector_backend_table

Revision ID: b9c7f4d2a301
Revises: 8d4e6a72e4c1
Create Date: 2026-04-11 19:10:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b9c7f4d2a301"
down_revision: Union[str, Sequence[str], None] = "8d4e6a72e4c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pgvector_chunk_embeddings (
            embedding_id VARCHAR(64) PRIMARY KEY
                REFERENCES chunk_embeddings (embedding_id) ON DELETE CASCADE,
            embedding vector NOT NULL
        )
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("DROP TABLE IF EXISTS pgvector_chunk_embeddings")
