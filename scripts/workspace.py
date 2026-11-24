"""Offline maintenance: safe backup, restore, migration and index reconstruction."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.workspace import Workspace
from app.backup import create_backup,restore_backup
from app.services import index_node
from app.models import Node
from sqlalchemy import select,text

if __name__=='__main__':
    p=argparse.ArgumentParser(description='Research Hub workspace maintenance. Stop the server before moving/restoring files.')
    sub=p.add_subparsers(dest='action',required=True)
    backup=sub.add_parser('backup');backup.add_argument('--workspace',required=True,type=Path);backup.add_argument('--output',type=Path)
    restore=sub.add_parser('restore');restore.add_argument('archive',type=Path);restore.add_argument('--target',required=True,type=Path)
    for name in ['migrate','reindex']:
        command=sub.add_parser(name);command.add_argument('--workspace',required=True,type=Path)
    args=p.parse_args()
    if args.action=='restore': print(restore_backup(args.archive,args.target))
    else:
        ws=Workspace(args.workspace)
        if args.action=='backup': print(create_backup(ws,args.output))
        elif args.action=='reindex':
            with ws.lock,ws.Session.begin() as s:
                s.execute(text('DELETE FROM search_index'))
                for n in s.scalars(select(Node)): index_node(s,ws,n)
            print('Index rebuilt')
        else: print('Migrated to latest schema')
