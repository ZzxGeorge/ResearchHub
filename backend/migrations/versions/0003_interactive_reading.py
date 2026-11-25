"""Separate original locations, many-to-many provenance, annotations and UI drafts."""
from alembic import op

revision = '0003'
down_revision = '0002'

def upgrade():
    op.execute('''CREATE TABLE source_anchors (
        id TEXT PRIMARY KEY, paper_id TEXT NOT NULL REFERENCES nodes(id),
        attachment_id TEXT NOT NULL REFERENCES attachments(id), pdf_sha256 TEXT NOT NULL,
        page INTEGER NOT NULL CHECK(page >= 1), printed_page TEXT NOT NULL,
        raw_text TEXT NOT NULL, cleaned_text TEXT NOT NULL, context TEXT NOT NULL,
        section TEXT NOT NULL, rects_json TEXT NOT NULL, notes TEXT NOT NULL,
        version INTEGER NOT NULL, deleted BOOLEAN NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')
    op.execute('CREATE INDEX ix_source_anchors_paper_id ON source_anchors(paper_id)')
    op.execute('CREATE INDEX ix_source_anchors_attachment_id ON source_anchors(attachment_id)')
    op.execute('''CREATE TABLE source_links (
        anchor_id TEXT NOT NULL REFERENCES source_anchors(id), node_id TEXT NOT NULL REFERENCES nodes(id),
        created_at TEXT NOT NULL, PRIMARY KEY(anchor_id, node_id))''')
    op.execute('CREATE INDEX ix_source_links_node_id ON source_links(node_id)')
    op.execute('''CREATE TABLE annotations (
        id TEXT PRIMARY KEY, anchor_id TEXT NOT NULL UNIQUE REFERENCES source_anchors(id),
        color TEXT NOT NULL, label TEXT NOT NULL, note_path TEXT NOT NULL,
        version INTEGER NOT NULL, deleted BOOLEAN NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')
    op.execute('''CREATE TABLE annotation_revisions (
        id TEXT PRIMARY KEY, annotation_id TEXT NOT NULL REFERENCES annotations(id),
        version INTEGER NOT NULL, note_path TEXT NOT NULL, snapshot TEXT NOT NULL,
        created_at TEXT NOT NULL, UNIQUE(annotation_id, version))''')
    op.execute('CREATE INDEX ix_annotation_revisions_annotation_id ON annotation_revisions(annotation_id)')
    op.execute('''CREATE TABLE paper_reading_states (
        paper_id TEXT PRIMARY KEY REFERENCES nodes(id), data_json TEXT NOT NULL, updated_at TEXT NOT NULL)''')

def downgrade():
    raise RuntimeError('Restore a pre-upgrade backup to a new workspace; do not drop research provenance.')
