"""add_chunk_and_embedding_tables

Revision ID: 8d4e6a72e4c1
Revises: cced19f99863
Create Date: 2026-04-11 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8d4e6a72e4c1"
down_revision: Union[str, Sequence[str], None] = "cced19f99863"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "document_chunks",
        sa.Column("chunk_id", sa.String(length=64), nullable=False),
        sa.Column("document_id", sa.String(length=64), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("snippet", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("chunk_id"),
    )
    op.create_index(
        "ix_document_chunks_document_id_ordinal",
        "document_chunks",
        ["document_id", "ordinal"],
        unique=False,
    )

    op.create_table(
        "chunk_embeddings",
        sa.Column("embedding_id", sa.String(length=64), nullable=False),
        sa.Column("chunk_id", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=120), nullable=False),
        sa.Column("embedding_dim", sa.Integer(), nullable=False),
        sa.Column("storage_backend", sa.String(length=40), nullable=False),
        sa.Column("storage_ref", sa.String(length=255), nullable=True),
        sa.Column("vector_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.chunk_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("embedding_id"),
        sa.UniqueConstraint("chunk_id", "embedding_model", name="uq_chunk_embeddings_chunk_model"),
    )
    op.create_index("ix_chunk_embeddings_chunk_id", "chunk_embeddings", ["chunk_id"], unique=False)
    op.create_index(
        "ix_chunk_embeddings_embedding_model",
        "chunk_embeddings",
        ["embedding_model"],
        unique=False,
    )
    op.create_index(
        "ix_chunk_embeddings_storage_backend",
        "chunk_embeddings",
        ["storage_backend"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_chunk_embeddings_storage_backend", table_name="chunk_embeddings")
    op.drop_index("ix_chunk_embeddings_embedding_model", table_name="chunk_embeddings")
    op.drop_index("ix_chunk_embeddings_chunk_id", table_name="chunk_embeddings")
    op.drop_table("chunk_embeddings")

    op.drop_index("ix_document_chunks_document_id_ordinal", table_name="document_chunks")
    op.drop_table("document_chunks")
