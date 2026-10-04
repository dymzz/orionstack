"""Preserved PostgreSQL revision 005_account_sessions, managed by Alembic."""

from app.knowledge.alembic_migrations import apply_revision

revision = "005_account_sessions"
down_revision = "004_dataset_snapshots"
branch_labels = None
depends_on = None


def upgrade():
    apply_revision(revision)


def downgrade():
    raise RuntimeError("Destructive downgrades are not supported; restore a verified isolated backup")
