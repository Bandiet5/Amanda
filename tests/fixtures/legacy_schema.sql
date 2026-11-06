-- Frozen schema from release 25db2d3, before Alembic. Tests only.
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
