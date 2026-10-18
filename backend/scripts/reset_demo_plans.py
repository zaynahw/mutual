"""Back up and clear generated demo plans; retain profiles, friends and windows.

Run from the repository root: python -m backend.scripts.reset_demo_plans
Refuses real accounts, in-flight calendar writes, and non-demo runtime modes.
"""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from backend import settings
from backend.database import connect
from backend.models import User

TABLES = ('calendar_event_keys','calendar_events','approvals','proposals',
          'creation_receipts','hangout_intents','hangout_requests')


def reset_demo_plans() -> tuple[Path,dict[str,int]]:
    if settings.mode()!='demo':raise ValueError('Reset is available only in demo mode')
    with connect() as connection:
        connection.execute('BEGIN IMMEDIATE')
        if connection.execute('SELECT COUNT(*) FROM google_accounts').fetchone()[0]:
            raise ValueError('This database contains Google accounts; no data was removed')
        if any(not User.model_validate_json(row['data']).is_demo for row in connection.execute('SELECT data FROM users')):
            raise ValueError('This database contains real users; no data was removed')
        if connection.execute("SELECT COUNT(*) FROM calendar_events WHERE status='creating'").fetchone()[0]:
            raise ValueError('A calendar write is in progress; stop activity and retry later')
        path=Path(connection.execute('PRAGMA database_list').fetchone()['file'])
        folder=path.parent/'backups';folder.mkdir(exist_ok=True)
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup=folder/f'{path.stem}-before-reset-{stamp}-{uuid4().hex[:8]}.db'
        descriptor=os.open(backup,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(descriptor)
        # A separate reader can back up the last committed state while the main
        # connection holds a reserved write lock, preventing concurrent changes.
        with sqlite3.connect(path) as source, sqlite3.connect(backup) as target:
            source.backup(target)
        counts={}
        for table in TABLES:
            counts[table]=connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
            connection.execute(f'DELETE FROM {table}')
    return backup,counts


if __name__=='__main__':
    backup,counts=reset_demo_plans()
    print('Backup:',backup)
    print('Cleared:',counts)
    print('Preserved user profiles, friendships, and social windows.')
