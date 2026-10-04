from app.knowledge.alembic_migrations import apply_revision

revision = '011_conversation_graph'
down_revision = '010_feedback_audit'
branch_labels = None
depends_on = None


def upgrade():
    apply_revision(revision)


def downgrade():
    raise RuntimeError('Restore an isolated backup instead of destructive downgrade')
