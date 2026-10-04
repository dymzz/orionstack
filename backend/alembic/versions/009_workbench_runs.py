from app.knowledge.alembic_migrations import apply_revision

revision = '009_workbench_runs'
down_revision = '008_asset_inspection'
branch_labels = None
depends_on = None


def upgrade():
    apply_revision(revision)


def downgrade():
    raise RuntimeError('Restore an isolated backup instead of destructive downgrade')
