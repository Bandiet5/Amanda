from contextlib import contextmanager
from datetime import datetime, timezone
import sqlite3
from flask import current_app, g


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def get_db():
    if 'db' not in g:
        db = sqlite3.connect(current_app.config['DATABASE'], timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA busy_timeout=15000')
        db.execute('PRAGMA synchronous=FULL')
        g.db = db
    return g.db


def close_db(_=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


@contextmanager
def transaction(write=True):
    db = get_db()
    db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
    try:
        yield db
        db.execute('COMMIT')
    except BaseException:
        db.execute('ROLLBACK')
        raise


def create_event(db, names):
    event_id = db.execute('INSERT INTO events(active,created_at) VALUES(1,?)', (now(),)).lastrowid
    db.executemany('INSERT INTO participants(event_id,name,position) VALUES(?,?,?)',
                   [(event_id, name, i) for i, name in enumerate(names)])
    return event_id
