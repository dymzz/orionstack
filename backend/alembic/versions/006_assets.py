"""Tenant-scoped Assets and append-only DataOps audit."""
from app.knowledge.alembic_migrations import apply_revision
revision = '006_assets'
down_revision = '005_account_sessions'
branch_labels = None
depends_on = None
def upgrade(): apply_revision(revision)
def downgrade(): raise RuntimeError('Restore a verified isolated backup instead of destructive downgrade')
