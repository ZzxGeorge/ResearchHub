"""Portable, checksummed backups. Recovery never overwrites a workspace."""
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from pathlib import Path, PurePosixPath
from sqlalchemy import select, text
from .models import Node, Revision, Attachment
from .workspace import now, uid, dumps, sha

MAX_BACKUP = 2 * 1024**3

def create_backup(ws, output_dir=None):
    output = Path(output_dir or ws.root/'backups').expanduser().resolve()
    if output == ws.root or output.is_relative_to(ws.root/'database'):
        raise ValueError('备份目录不得是数据库目录或工作空间根目录')
    output.mkdir(parents=True,exist_ok=True)
    destination = output / ('research-hub-'+now()[:10]+'-'+uid()+'.zip')
    with ws.lock, tempfile.TemporaryDirectory() as temp:
        snapshot = Path(temp)/'hub.sqlite3'
        with closing(sqlite3.connect(ws.db)) as src, closing(sqlite3.connect(snapshot)) as dst:
            src.backup(dst)
        paths = {'workspace.json'}
        with ws.Session() as s:
            paths.update(s.scalars(select(Node.note_path)).all())
            paths.update(s.scalars(select(Revision.note_path)).all())
            paths.update(s.scalars(select(Attachment.path)).all())
            # Also works before migration 0003, when the annotation tables do not exist yet.
            tables=set(s.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).scalars())
            for table in ['annotations','annotation_revisions']:
                if table in tables:
                    paths.update(s.execute(text('SELECT note_path FROM '+table)).scalars())
        manifest = {'data_format_version':'1.0','created_at':now(),'files':{}}
        temporary = destination.with_suffix('.tmp')
        try:
            with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as z:
                for relative in sorted(paths | {'database/hub.sqlite3'}):
                    path = snapshot if relative=='database/hub.sqlite3' else ws.path(relative)
                    if not path.is_file(): raise ValueError('无法备份：文件缺失 '+relative)
                    data = path.read_bytes()
                    manifest['files'][relative] = {'sha256':sha(data),'size':len(data)}
                    z.writestr(relative,data)
                z.writestr('manifest.json',dumps(manifest))
            os.replace(temporary,destination)
        finally:
            temporary.unlink(missing_ok=True)
    return destination

def restore_backup(archive, target):
    target = Path(target).expanduser().resolve()
    if target.exists(): raise ValueError('恢复目标必须是不存在的新目录；不会覆盖现有工作空间')
    target.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        if len(infos)>100000 or len(names)!=len(set(names)) or sum(i.file_size for i in infos)>MAX_BACKUP:
            raise ValueError('备份文件过大或含有重复路径')
        for i in infos:
            p = PurePosixPath(i.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in i.filename or ':' in i.filename or i.is_dir() or ((i.external_attr >> 16) & 0o170000)==0o120000:
                raise ValueError('备份含有非法路径或链接')
        if 'manifest.json' not in names: raise ValueError('缺少备份清单')
        manifest = json.loads(z.read('manifest.json'))
        if manifest.get('data_format_version')!='1.0': raise ValueError('不支持的备份版本')
        if set(manifest.get('files',{})) != set(names)-{'manifest.json'}: raise ValueError('备份清单与文件不匹配')
        if not {'database/hub.sqlite3','workspace.json'} <= set(names): raise ValueError('缺少数据库或配置')
        with tempfile.TemporaryDirectory(prefix='.hub-restore-',dir=target.parent) as temp:
            stage = Path(temp)/'workspace'
            stage.mkdir()
            for relative, check in manifest['files'].items():
                data = z.read(relative)
                if len(data)!=check['size'] or sha(data)!=check['sha256']: raise ValueError('备份校验失败: '+relative)
                path = stage/relative
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(data)
            with closing(sqlite3.connect(stage/'database/hub.sqlite3')) as db:
                if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():
                    raise ValueError('数据库完整性校验失败')
                if db.execute('SELECT version_num FROM alembic_version').fetchone()[0] not in {'0001','0002','0003'}:
                    raise ValueError('备份数据库版本暂不受支持')
                paths = [r[0] for r in db.execute('SELECT note_path FROM nodes UNION SELECT note_path FROM revisions UNION SELECT path FROM attachments')]
                tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                for table in ['annotations','annotation_revisions']:
                    if table in tables: paths.extend(r[0] for r in db.execute('SELECT note_path FROM '+table))
                for path in paths:
                    if path not in manifest['files']: raise ValueError('数据库引用了缺失的文件: '+path)
                for path, checksum in db.execute('SELECT path,sha256 FROM attachments'):
                    if manifest['files'][path]['sha256'] != checksum: raise ValueError('附件校验值与数据库不匹配')
            if target.exists(): raise ValueError('恢复目标已存在')
            # Same-filesystem rename is atomic; unlike replace it must never overwrite.
            os.rename(stage,target)
    return {'workspace':str(target),'files':len(manifest['files']),'data_format_version':'1.0'}
