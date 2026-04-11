"""add_index_job_error_code

Revision ID: 2f41c6a77d2b
Revises: f13c2be2a88c
Create Date: 2026-04-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2f41c6a77d2b"
down_revision: Union[str, Sequence[str], None] = "f13c2be2a88c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("index_jobs", sa.Column("error_code", sa.String(length=80), nullable=False, server_default=""))
    op.alter_column("index_jobs", "error_code", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("index_jobs", "error_code")
