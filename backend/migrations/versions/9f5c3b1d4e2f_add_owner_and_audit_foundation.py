"""add_owner_and_audit_foundation

Revision ID: 9f5c3b1d4e2f
Revises: 6d8b1f2e9a0c
Create Date: 2026-04-12 16:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f5c3b1d4e2f"
down_revision: Union[str, Sequence[str], None] = "6d8b1f2e9a0c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "sessions",
        sa.Column("owner_user_id", sa.String(length=80), nullable=False, server_default="demo-user"),
    )
    op.create_index("ix_sessions_owner_created_at", "sessions", ["owner_user_id", "created_at"], unique=False)

    op.add_column(
        "documents",
        sa.Column("owner_user_id", sa.String(length=80), nullable=False, server_default="demo-user"),
    )
    op.create_index("ix_documents_owner_created_at", "documents", ["owner_user_id", "created_at"], unique=False)

    op.add_column(
        "qa_history",
        sa.Column("owner_user_id", sa.String(length=80), nullable=False, server_default="demo-user"),
    )
    op.create_index("ix_qa_history_owner_created_at", "qa_history", ["owner_user_id", "created_at"], unique=False)

    op.add_column(
        "feedback",
        sa.Column("owner_user_id", sa.String(length=80), nullable=False, server_default="demo-user"),
    )
    op.create_index("ix_feedback_owner_created_at", "feedback", ["owner_user_id", "created_at"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_user_id", sa.String(length=80), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_owner_created_at", "audit_logs", ["owner_user_id", "created_at"], unique=False)
    op.create_index("ix_audit_logs_trace_id", "audit_logs", ["trace_id"], unique=False)
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_audit_logs_event_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_trace_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_owner_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_feedback_owner_created_at", table_name="feedback")
    op.drop_column("feedback", "owner_user_id")

    op.drop_index("ix_qa_history_owner_created_at", table_name="qa_history")
    op.drop_column("qa_history", "owner_user_id")

    op.drop_index("ix_documents_owner_created_at", table_name="documents")
    op.drop_column("documents", "owner_user_id")

    op.drop_index("ix_sessions_owner_created_at", table_name="sessions")
    op.drop_column("sessions", "owner_user_id")
