"""Preserved PostgreSQL revision 002_raw_retrieval, managed by Alembic."""

from app.knowledge.alembic_migrations import apply_revision

revision = "002_raw_retrieval"
down_revision = "001_core"
branch_labels = None
depends_on = None


def upgrade():
    apply_revision(revision)


def downgrade():
    raise RuntimeError("Destructive downgrades are not supported; restore a verified isolated backup")
