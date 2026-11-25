"""Persistent, per-attachment PDF reading positions; no changes to interchange v1."""
from alembic import op
revision='0002'
down_revision='0001'
def upgrade():
    op.execute('CREATE TABLE reading_positions (attachment_id TEXT PRIMARY KEY REFERENCES attachments(id), data_json TEXT NOT NULL, updated_at TEXT NOT NULL)')
def downgrade():
    raise RuntimeError('Restore a pre-migration backup into a new workspace instead of dropping reading state.')
