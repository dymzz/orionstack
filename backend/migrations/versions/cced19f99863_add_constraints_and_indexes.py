"""add_constraints_and_indexes

Revision ID: cced19f99863
Revises: 43ed9acf80bc
Create Date: 2026-04-11 15:42:01.972036

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cced19f99863'
down_revision: Union[str, Sequence[str], None] = '43ed9acf80bc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index("ix_sessions_created_at", "sessions", ["created_at"], unique=False)
    op.create_index("ix_documents_created_at", "documents", ["created_at"], unique=False)
    op.create_index("ix_documents_status", "documents", ["status"], unique=False)
    op.create_index(
        "ix_qa_history_session_created_at",
        "qa_history",
        ["session_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_feedback_session_created_at",
        "feedback",
        ["session_id", "created_at"],
        unique=False,
    )
    op.create_index("ix_feedback_trace_id", "feedback", ["trace_id"], unique=False)

    op.create_check_constraint(
        "ck_qa_history_latency_non_negative",
        "qa_history",
        "latency_ms >= 0",
    )
    op.create_check_constraint(
        "ck_feedback_rating_allowed",
        "feedback",
        "rating IN ('up', 'down', 'neutral')",
    )

    op.create_foreign_key(
        "fk_feedback_session_id_sessions",
        "feedback",
        "sessions",
        ["session_id"],
        ["session_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("fk_feedback_session_id_sessions", "feedback", type_="foreignkey")
    op.drop_constraint("ck_feedback_rating_allowed", "feedback", type_="check")
    op.drop_constraint("ck_qa_history_latency_non_negative", "qa_history", type_="check")

    op.drop_index("ix_feedback_trace_id", table_name="feedback")
    op.drop_index("ix_feedback_session_created_at", table_name="feedback")
    op.drop_index("ix_qa_history_session_created_at", table_name="qa_history")
    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_index("ix_documents_created_at", table_name="documents")
    op.drop_index("ix_sessions_created_at", table_name="sessions")
