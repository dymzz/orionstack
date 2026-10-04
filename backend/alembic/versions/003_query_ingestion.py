"""Preserved PostgreSQL revision 003_query_ingestion, managed by Alembic."""

from app.knowledge.alembic_migrations import apply_revision

revision = "003_query_ingestion"
down_revision = "002_raw_retrieval"
branch_labels = None
depends_on = None


def upgrade():
    apply_revision(revision)


def downgrade():
    raise RuntimeError("Destructive downgrades are not supported; restore a verified isolated backup")
