"""Preserved PostgreSQL revision 001_core, managed by Alembic."""

from app.knowledge.alembic_migrations import apply_revision

revision = "001_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    apply_revision(revision)


def downgrade():
    raise RuntimeError("Destructive downgrades are not supported; restore a verified isolated backup")
