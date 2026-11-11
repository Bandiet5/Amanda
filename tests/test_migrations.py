"""Exercise the committed baseline, not a substitute create_all() schema."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import uuid

from alembic import command
from flask_migrate import upgrade, check
import pytest
import sqlalchemy as sa
from werkzeug.security import generate_password_hash, check_password_hash

from server.app import create_app
from server.db import get_db
from server.migration_support import MIGRATIONS, schema_db
from server.security import BROWSER_COOKIE, digest
from conftest import bootstrap, post

ROOT = Path(__file__).resolve().parent.parent
LEGACY_SCHEMA = Path(__file__).parent / 'fixtures' / 'legacy_schema.sql'
REVISION = '0002_seven_participants'
TABLES = ('settings', 'events', 'participants', 'browser_sessions', 'draws',
          'admin_sessions', 'recovery_tokens', 'login_limits', 'audit_log')


def application(path, **overrides):
    config = {'TESTING': True, 'SECRET_KEY': 'isolated-migration-secret-' * 3,
              'DATABASE': str(path), 'PUBLIC_ORIGIN': 'http://localhost',
              'COOKIE_SECURE': False, 'TRUSTED_HOSTS': ['localhost'],
              'ADMIN_PASSWORD_HASH': None}
    config.update(overrides)
    return create_app(config)


def snapshot(path):
    with sqlite3.connect(path) as db:
        return {table: db.execute(f'SELECT * FROM {table} ORDER BY 1,2').fetchall() for table in TABLES}


def legacy_database(path):
    timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    names = ['Amanda', 'Ben', 'Carla', 'Danie', 'Elsa', 'Freddie', 'Gerda', 'Hennie']
    with sqlite3.connect(path) as db:
        db.execute('PRAGMA foreign_keys=ON')
        db.executescript(LEGACY_SCHEMA.read_text())
        db.execute('INSERT INTO settings VALUES(?,?)', ('admin_password_hash', generate_password_hash('existing-private-password')))
        db.execute('INSERT INTO settings VALUES(?,?)', ('custom_setting', 'keep-me'))
        db.execute('INSERT INTO events VALUES(1,1,?,?,10)', (timestamp,timestamp))
        db.executemany('INSERT INTO participants(id,event_id,name,position,claimed_at,draw_version,replay_version) VALUES(?,1,?,?,?,0,0)',
                       [(i+1,name,i,timestamp if i < 2 else None) for i,name in enumerate(names)])
        db.execute('INSERT INTO browser_sessions VALUES(?,1,1,0,?)', (digest('existing-browser-token'),timestamp))
        db.execute('INSERT INTO browser_sessions VALUES(?,1,2,0,?)', (digest('second-browser-token'),timestamp))
        for giver, recipient in [(1,2), (2,3)]:
            segments = [{'id': i+1,'name': name} for i,name in enumerate(names) if i+1 != giver and (giver == 1 or i+1 != 2)]
            db.execute('INSERT INTO draws VALUES(1,?,?,?,?)',(giver,recipient,json.dumps(segments),timestamp))
        db.execute('INSERT INTO admin_sessions VALUES(?,?,?)',(digest('existing-admin-token'),time.time()+3600,timestamp))
        db.execute('INSERT INTO recovery_tokens VALUES(?,1,2,?,NULL,?)',(digest('existing-recovery-token'),time.time()+3600,timestamp))
        db.execute('INSERT INTO login_limits VALUES(?,2,?)',('existing-limit',time.time()))
        db.execute("INSERT INTO audit_log VALUES(1,1,'Amanda (administrator)','existing-action','Amanda','{}',?)", (timestamp,))


def test_startup_never_creates_schema_or_seeds_data(tmp_path):
    path = tmp_path / 'no-startup.sqlite3'
    app = application(path)
    assert not path.exists()
    restarted = create_app(dict(app.config))
    assert restarted.config['DATABASE'] == app.config['DATABASE']
    assert not path.exists()
    runner = app.test_cli_runner()
    assert 'db' in runner.invoke(args=['--help']).output
    assert not path.exists()
    assert app.test_client().get('/api/health').status_code == 503
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []


def test_fresh_upgrade_is_idempotent_and_matches_metadata(tmp_path):
    path = tmp_path / 'fresh.sqlite3'
    app = application(path)
    with app.app_context():
        upgrade()
        assert get_db().execute('SELECT version_num FROM alembic_version').fetchone()[0] == REVISION
        assert get_db().execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
        password = get_db().execute("SELECT value FROM settings WHERE key='admin_password_hash'").fetchone()[0]
        assert check_password_hash(password,'amanda123')
        assert get_db().execute('SELECT count(*) FROM participants').fetchone()[0] == 15
        assert get_db().execute('PRAGMA foreign_key_check').fetchall() == []
        before = snapshot(path)
        upgrade()
        check()
        assert snapshot(path) == before
    assert app.test_client().get('/api/health').status_code == 200


def test_existing_database_adoption_preserves_every_row_and_saved_session(tmp_path):
    path = tmp_path / 'existing.sqlite3'
    legacy_database(path)
    before = snapshot(path)
    app = application(path)
    assert snapshot(path) == before  # Constructing the WSGI app cannot migrate.
    with app.app_context():
        upgrade(revision='0001_gift_exchange')
        assert snapshot(path) == before
        assert get_db().execute('PRAGMA foreign_key_check').fetchall() == []
        upgrade(revision='0001_gift_exchange')
        assert snapshot(path) == before
    client = app.test_client()
    client.set_cookie(BROWSER_COOKIE,'existing-browser-token')
    state = bootstrap(client)
    assert state['participant']['name'] == 'Amanda'
    assert state['draw']['recipient']['name'] == 'Ben'
    assert state['completed_count'] == 2
    recovery_browser = app.test_client()
    response = post(recovery_browser,'/recover',bootstrap(recovery_browser),{'token':'existing-recovery-token'})
    assert response.status_code == 200
    assert response.json['draw']['recipient']['name'] == 'Carla'
    returning = application(path)
    assert bootstrap(client)['draw']['recipient']['name'] == 'Ben'
    assert returning.test_client().get('/api/health').status_code == 200


def test_incomplete_legacy_schema_fails_without_stamping_or_changing_data(tmp_path):
    path = tmp_path / 'partial.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        db.execute("INSERT INTO settings VALUES('keep','original')")
    app = application(path)
    result = app.test_cli_runner().invoke(args=['db','upgrade'])
    assert result.exit_code != 0
    assert 'not a complete supported legacy schema' in result.output
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT * FROM settings').fetchall() == [('keep','original')]
        assert db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == [('settings',)]


def test_missing_uniqueness_protection_is_rejected_without_data_changes(tmp_path):
    path = tmp_path / 'missing-index.sqlite3'
    legacy_database(path)
    with sqlite3.connect(path) as db:
        db.execute('DROP INDEX one_active_binding')
    before = snapshot(path)
    app = application(path)
    result = app.test_cli_runner().invoke(args=['db','upgrade'])
    assert result.exit_code != 0
    assert 'one_active_binding' in result.output
    assert snapshot(path) == before
    with sqlite3.connect(path) as db:
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='alembic_version'").fetchone()


def test_empty_legacy_schema_gets_only_initial_setup(tmp_path):
    path = tmp_path / 'empty-legacy.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript(LEGACY_SCHEMA.read_text())
    app = application(path)
    with app.app_context():
        upgrade()
        assert get_db().execute('SELECT count(*) FROM events WHERE active=1').fetchone()[0] == 1
        assert get_db().execute('SELECT count(*) FROM participants').fetchone()[0] == 15
        assert get_db().execute('SELECT count(*) FROM draws').fetchone()[0] == 0


def test_paas_database_url_selects_same_file_for_migration_and_runtime(tmp_path, monkeypatch):
    # Include a space and % so URL handling cannot silently select a different file.
    path = tmp_path / 'persistent % data' / 'event.sqlite3'
    ignored = tmp_path / 'do-not-create.sqlite3'
    monkeypatch.setenv('DATABASE_URL', sa.URL.create('sqlite',database=str(path)).render_as_string(hide_password=False))
    monkeypatch.setenv('DATABASE_PATH', str(ignored))
    app = create_app({'TESTING':True,'SECRET_KEY':'isolated-paas-env-'*4,'PUBLIC_ORIGIN':'http://localhost',
                      'COOKIE_SECURE':False,'TRUSTED_HOSTS':['localhost']})
    assert Path(app.config['DATABASE']) == path
    assert not ignored.exists() and not path.exists()
    with app.app_context():
        upgrade()
    assert path.exists() and not ignored.exists()
    assert bootstrap(app.test_client())['total'] == 7


@pytest.mark.parametrize('url',['sqlite:///:memory:','sqlite://','postgresql://example/app'])
def test_runtime_stays_on_persistent_sqlite(tmp_path,url):
    with pytest.raises(RuntimeError,match='SQLite'):
        application(tmp_path/'unused.sqlite3',DATABASE_URL=url)


def test_exact_paas_entry_point_upgrades_from_another_working_directory(tmp_path):
    path = tmp_path / 'cli.sqlite3'
    env = {**os.environ, 'APP_ENV':'development','SECRET_KEY':'isolated-cli-check-'*4,
           'PUBLIC_ORIGIN':'http://localhost','ALLOW_INSECURE_HTTP':'1',
           'DATABASE_URL':sa.URL.create('sqlite',database=str(path)).render_as_string(hide_password=False),
           'PYTHONPATH':str(ROOT)}
    imported = subprocess.run([sys.executable,'-c','from server.wsgi import app; assert app.name == "server.app"'],
                              cwd=tmp_path,env=env,capture_output=True,text=True)
    assert imported.returncode == 0, imported.stderr
    assert not path.exists()
    result = subprocess.run([sys.executable,'-m','flask','--app','server.wsgi:app','db','upgrade'],
                            cwd=tmp_path,env=env,capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == REVISION
        assert db.execute('SELECT count(*) FROM participants').fetchone()[0] == 15


def test_compatibility_init_db_command_applies_committed_revision(tmp_path,monkeypatch):
    from server import cli
    path=tmp_path/'legacy-command.sqlite3'
    app=application(path)
    monkeypatch.setattr(cli,'create_app',lambda:app)
    monkeypatch.setattr(sys,'argv',['server.cli','init-db'])
    cli.main()
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT version_num FROM alembic_version').fetchone()[0] == REVISION


def test_postgres_initial_revision_with_real_foreign_keys_and_data(tmp_path):
    url=os.environ.get('AMANDA_TEST_POSTGRES_URL')
    if not url:
        pytest.skip('Run with pg_virtualenv and tests/run_postgres_migrations.py for the PostgreSQL contract check.')
    engine=sa.create_engine(url)
    schema='amanda_migration_'+uuid.uuid4().hex
    app=application(tmp_path/'unused.sqlite3')
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
            with app.app_context():
                config=app.extensions['migrate'].migrate.get_config()
                config.attributes['connection']=connection
                command.upgrade(config,'head')
            assert connection.execute(sa.text('SELECT count(*) FROM participants')).scalar_one() == 15
            ids=connection.execute(sa.text('SELECT id FROM participants WHERE event_id=(SELECT id FROM events WHERE active=1) ORDER BY position')).scalars().all()
            event=connection.execute(sa.text('SELECT id FROM events WHERE active=1')).scalar_one()
            connection.execute(sa.text("INSERT INTO browser_sessions(token_hash,event_id,participant_id,created_at) VALUES('test-token',:event,:person,'now')"),{'event':event,'person':ids[0]})
            connection.execute(sa.text("INSERT INTO draws(event_id,giver_id,recipient_id,segments,created_at) VALUES(:event,:giver,:recipient,'[]','now')"),{'event':event,'giver':ids[0],'recipient':ids[1]})
            for statement, values in [
                ("INSERT INTO draws VALUES(:event,:giver,:giver,'[]','now')",{'event':event,'giver':ids[2]}),
                ("INSERT INTO draws VALUES(:event,:giver,:recipient,'[]','now')",{'event':event,'giver':ids[2],'recipient':ids[1]}),
                ("INSERT INTO draws VALUES(:event,:giver,999999,'[]','now')",{'event':event,'giver':ids[3]}),
                ("INSERT INTO browser_sessions(token_hash,event_id,participant_id,created_at) VALUES('duplicate',:event,:person,'now')",{'event':event,'person':ids[0]}),
            ]:
                with pytest.raises(sa.exc.IntegrityError):
                    with connection.begin_nested():
                        connection.execute(sa.text(statement),values)
            with app.app_context():
                command.upgrade(config,'head')
            assert connection.execute(sa.text('SELECT count(*) FROM draws')).scalar_one() == 1
            assert connection.execute(sa.text('SELECT version_num FROM alembic_version')).scalar_one() == REVISION
    finally:
        with engine.begin() as connection:
            connection.exec_driver_sql(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        engine.dispose()
