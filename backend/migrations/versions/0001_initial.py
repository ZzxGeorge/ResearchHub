"""Initial version. Frozen SQL ensures future models cannot alter this migration."""
from alembic import op
revision = '0001'
down_revision = None

def upgrade():
    statements = [
        '''CREATE TABLE nodes (id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL, normalized_title TEXT NOT NULL, status TEXT NOT NULL, tags_json TEXT NOT NULL, metadata_json TEXT NOT NULL, note_path TEXT NOT NULL, version INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted BOOLEAN NOT NULL)''',
        '''CREATE TABLE revisions (id TEXT PRIMARY KEY, node_id TEXT NOT NULL REFERENCES nodes(id), version INTEGER NOT NULL, note_path TEXT NOT NULL, snapshot TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(node_id,version))''',
        '''CREATE TABLE relations (id TEXT PRIMARY KEY, source TEXT NOT NULL REFERENCES nodes(id), target TEXT NOT NULL REFERENCES nodes(id), type TEXT NOT NULL, description TEXT NOT NULL, evidence TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(source,target,type))''',
        '''CREATE TABLE attachments (id TEXT PRIMARY KEY, node_id TEXT NOT NULL REFERENCES nodes(id), name TEXT NOT NULL, path TEXT NOT NULL, media_type TEXT NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL, created_at TEXT NOT NULL)''',
        '''CREATE TABLE review_states (node_id TEXT PRIMARY KEY REFERENCES nodes(id), repetitions INTEGER NOT NULL, interval_days INTEGER NOT NULL, ease TEXT NOT NULL, due_at TEXT NOT NULL, last_review TEXT, lapses INTEGER NOT NULL, version INTEGER NOT NULL)''',
        '''CREATE TABLE review_logs (id TEXT PRIMARY KEY, node_id TEXT NOT NULL REFERENCES nodes(id), rating TEXT NOT NULL, reviewed_at TEXT NOT NULL, before_json TEXT NOT NULL, after_json TEXT NOT NULL, algorithm TEXT NOT NULL)''',
        '''CREATE TABLE import_receipts (digest TEXT PRIMARY KEY, report_json TEXT NOT NULL, created_at TEXT NOT NULL)''',
        '''CREATE TABLE categories (id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL, parent_id TEXT REFERENCES categories(id))''',
        '''CREATE VIRTUAL TABLE search_index USING fts5(node_id UNINDEXED, text, tokenize='unicode61')''',
        'CREATE INDEX ix_nodes_kind ON nodes(kind)', 'CREATE INDEX ix_nodes_title ON nodes(normalized_title)', 'CREATE INDEX ix_rel_source ON relations(source)', 'CREATE INDEX ix_rel_target ON relations(target)', 'CREATE INDEX ix_revisions_node ON revisions(node_id)',
    ]
    for sql in statements:
        op.execute(sql)

def downgrade():
    raise RuntimeError('Refusing destructive downgrade; restore an earlier backup into a new workspace.')
