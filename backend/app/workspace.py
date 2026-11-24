import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from filelock import FileLock
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from alembic import command
from alembic.config import Config

def now():
    return datetime.now(timezone.utc).isoformat()

def uid():
    return str(uuid4())

def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)

def sha(data: bytes):
    return hashlib.sha256(data).hexdigest()

class Workspace:
    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(str(self.root / '.workspace.lock'), timeout=30)
        for folder in ['database','literature/papers','literature/notes','vocabulary','mathematics','algorithms','research_ideas','questions','attachments','exports','backups']:
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        self.db = self.root / 'database/hub.sqlite3'
        self.engine = create_engine('sqlite:///' + self.db.as_posix(), connect_args={'check_same_thread':False,'timeout':30})
        @event.listens_for(self.engine, 'connect')
        def pragmas(conn, _):
            conn.execute('PRAGMA foreign_keys=ON')
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=FULL')
        self.Session = sessionmaker(self.engine, expire_on_commit=False)
        with self.lock:
            cfg = Config()
            cfg.set_main_option('script_location', str(Path(__file__).resolve().parents[1] / 'migrations'))
            with self.engine.begin() as connection:
                cfg.attributes['connection'] = connection
                command.upgrade(cfg, 'head')
            config = self.root / 'workspace.json'
            if not config.exists():
                self.write_bytes('workspace.json', dumps({'data_format_version':'1.0','review_algorithm':'sm2-v1'}).encode())

    def path(self, relative: str):
        p = (self.root / relative).resolve()
        if not p.is_relative_to(self.root) or p == self.root:
            raise ValueError('非法工作空间路径')
        return p

    def write_bytes(self, relative, data):
        p = self.path(relative)
        p.parent.mkdir(parents=True, exist_ok=True)
        temp = p.with_name(p.name + '.' + uid() + '.tmp')
        try:
            with temp.open('xb') as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp, p)
        finally:
            temp.unlink(missing_ok=True)
        return relative

    def write_note(self, kind, node_id, version, body):
        folders = {'paper':'literature/notes','vocabulary':'vocabulary','mathematics':'mathematics','algorithm':'algorithms','idea':'research_ideas','question':'questions'}
        relative = f'{folders[kind]}/{node_id}/v{version}-{uid()}.md'
        self.write_bytes(relative, body.encode('utf-8'))
        return relative

    def read_note(self, path):
        try:
            return self.path(path).read_text(encoding='utf-8')
        except FileNotFoundError as exc:
            raise ValueError(f'Markdown 文件缺失，请从备份恢复: {path}') from exc
