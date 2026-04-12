"""add_qa_history_metadata_columns

Revision ID: 6d8b1f2e9a0c
Revises: 2f41c6a77d2b
Create Date: 2026-04-12 15:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6d8b1f2e9a0c"
down_revision: Union[str, Sequence[str], None] = "2f41c6a77d2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "qa_history",
        sa.Column("retrieval_confidence", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "qa_history",
        sa.Column("refusal_reason", sa.String(length=80), nullable=False, server_default=""),
    )
    op.add_column(
        "qa_history",
        sa.Column("need_human_review", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "qa_history",
        sa.Column("answer_provider", sa.String(length=80), nullable=False, server_default=""),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("qa_history", "answer_provider")
    op.drop_column("qa_history", "need_human_review")
    op.drop_column("qa_history", "refusal_reason")
    op.drop_column("qa_history", "retrieval_confidence")
