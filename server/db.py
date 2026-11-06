from contextlib import contextmanager
from datetime import datetime, timezone
import sqlite3
from flask import current_app, g
from werkzeug.security import generate_password_hash

# Simple built-in password requested for this one-time office event.
DEFAULT_ADMIN_PASSWORD = "amanda123"

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY, active INTEGER NOT NULL CHECK(active IN (0,1)),
    created_at TEXT NOT NULL, started_at TEXT, revision INTEGER NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_event ON events(active) WHERE active=1;
CREATE TABLE IF NOT EXISTS participants (
    id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL REFERENCES events(id),
    name TEXT NOT NULL COLLATE NOCASE CHECK(length(name) BETWEEN 1 AND 40),
    position INTEGER NOT NULL CHECK(position BETWEEN 0 AND 7), claimed_at TEXT,
    draw_version INTEGER NOT NULL DEFAULT 0, replay_version INTEGER NOT NULL DEFAULT 0,
    UNIQUE(event_id, name), UNIQUE(event_id, position), UNIQUE(event_id,id)
);
CREATE TABLE IF NOT EXISTS browser_sessions (
    token_hash TEXT PRIMARY KEY, event_id INTEGER NOT NULL REFERENCES events(id),
    participant_id INTEGER REFERENCES participants(id),
    revoked INTEGER NOT NULL DEFAULT 0 CHECK(revoked IN (0,1)), created_at TEXT NOT NULL,
    FOREIGN KEY(event_id,participant_id) REFERENCES participants(event_id,id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_binding
    ON browser_sessions(participant_id) WHERE revoked=0 AND participant_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS draws (
    event_id INTEGER NOT NULL REFERENCES events(id), giver_id INTEGER NOT NULL,
    recipient_id INTEGER NOT NULL, segments TEXT NOT NULL, created_at TEXT NOT NULL,
    PRIMARY KEY(event_id,giver_id), UNIQUE(event_id,recipient_id), CHECK(giver_id != recipient_id),
    FOREIGN KEY(event_id,giver_id) REFERENCES participants(event_id,id),
    FOREIGN KEY(event_id,recipient_id) REFERENCES participants(event_id,id)
);
CREATE TABLE IF NOT EXISTS admin_sessions (
    token_hash TEXT PRIMARY KEY, expires_at REAL NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS recovery_tokens (
    token_hash TEXT PRIMARY KEY, event_id INTEGER NOT NULL REFERENCES events(id),
    participant_id INTEGER NOT NULL REFERENCES participants(id), expires_at REAL NOT NULL,
    used_at TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS login_limits (
    scope TEXT PRIMARY KEY, attempts INTEGER NOT NULL, window_start REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY, event_id INTEGER REFERENCES events(id), actor TEXT NOT NULL,
    action TEXT NOT NULL, participant_name TEXT, details TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
"""


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


def init_db():
    db = get_db()
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript(SCHEMA)
    with transaction():
        if not db.execute("SELECT 1 FROM settings WHERE key='admin_password_hash'").fetchone():
            db.execute("INSERT INTO settings(key,value) VALUES('admin_password_hash',?)",
                       (generate_password_hash(DEFAULT_ADMIN_PASSWORD, method='scrypt'),))
        if not db.execute('SELECT 1 FROM events WHERE active=1').fetchone():
            create_event(db, ['Amanda', *[f'Name {i}' for i in range(2, 9)]])
