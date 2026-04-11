"""add_index_jobs_table

Revision ID: f13c2be2a88c
Revises: b9c7f4d2a301
Create Date: 2026-04-12 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f13c2be2a88c"
down_revision: Union[str, Sequence[str], None] = "b9c7f4d2a301"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "index_jobs",
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("document_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("progress_pct", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.document_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index(
        "ix_index_jobs_document_created_at",
        "index_jobs",
        ["document_id", "created_at"],
        unique=False,
    )
    op.create_index("ix_index_jobs_status", "index_jobs", ["status"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_index_jobs_status", table_name="index_jobs")
    op.drop_index("ix_index_jobs_document_created_at", table_name="index_jobs")
    op.drop_table("index_jobs")
