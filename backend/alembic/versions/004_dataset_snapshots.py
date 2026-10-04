"""Preserved PostgreSQL revision 004_dataset_snapshots, managed by Alembic."""

from app.knowledge.alembic_migrations import apply_revision

revision = "004_dataset_snapshots"
down_revision = "003_query_ingestion"
branch_labels = None
depends_on = None


def upgrade():
    apply_revision(revision)


def downgrade():
    raise RuntimeError("Destructive downgrades are not supported; restore a verified isolated backup")
