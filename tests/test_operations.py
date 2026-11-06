from pathlib import Path
import sqlite3
import subprocess
import sys
import pytest
from server.app import create_app
from server import cli
from server.db import get_db
from conftest import bind, spin


def test_production_rejects_missing_secret_http_and_public_database(tmp_path, monkeypatch):
    monkeypatch.setenv('APP_ENV','production')
    configuration = {'SECRET_KEY':'test-secure-secret-'*4, 'PUBLIC_ORIGIN':'https://gifts.example.com',
                     'DATABASE':str(tmp_path/'production.sqlite3'), 'COOKIE_SECURE':True}
    with pytest.raises(RuntimeError, match='SECRET_KEY'):
        create_app({**configuration,'SECRET_KEY':''})
    with pytest.raises(RuntimeError, match='https://'):
        create_app({**configuration,'PUBLIC_ORIGIN':'http://gifts.example.com'})
    with pytest.raises(RuntimeError, match='secure cookies'):
        create_app({**configuration,'COOKIE_SECURE':False})
    with pytest.raises(RuntimeError, match='outside'):
        create_app({**configuration,'DATABASE':str(Path('dist/event.sqlite3').resolve())})
    with pytest.raises(RuntimeError, match='origin'):
        create_app({**configuration,'PUBLIC_ORIGIN':'https://gifts.example.com/wrong-path'})


def test_configuration_generates_private_secret_without_overwriting(tmp_path):
    output = tmp_path/'setup.env'
    command = [sys.executable,'scripts/configure.py','--production','--origin','https://gifts.example.com',
               '--database',str(tmp_path/'event.sqlite3'),'--output',str(output)]
    first = subprocess.run(command,capture_output=True,text=True)
    assert first.returncode == 0, first.stderr
    original = output.read_text()
    secret = next(line.split('=',1)[1] for line in original.splitlines() if line.startswith('SECRET_KEY='))
    assert len(secret) >= 48 and secret not in first.stdout
    assert 'ALLOW_INSECURE_HTTP=0' in original
    if sys.platform != 'win32': assert output.stat().st_mode & 0o777 == 0o600
    assert subprocess.run(command,capture_output=True).returncode != 0
    assert output.read_text() == original


def test_live_backup_contains_the_committed_event_and_refuses_overwrite(app, tmp_path, monkeypatch):
    client = app.test_client(); state = bind(client); saved = spin(client,state).json
    destination = tmp_path/'safe-backup.sqlite3'
    monkeypatch.setattr(cli,'create_app',lambda:app)
    monkeypatch.setattr(sys,'argv',['server.cli','backup',str(destination)])
    cli.main()
    with sqlite3.connect(destination) as copy:
        result = copy.execute('SELECT recipient_id FROM draws WHERE giver_id=?',(state['participant']['id'],)).fetchone()
        assert result[0] == saved['draw']['recipient']['id']
        assert copy.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    with pytest.raises(SystemExit): cli.main()


def test_password_setup_overrides_default_and_revokes_admin_sessions(app, monkeypatch):
    from conftest import administrator
    admin, _ = administrator(app)
    app.config['ADMIN_PASSWORD_HASH'] = None
    monkeypatch.setattr(cli,'create_app',lambda:app)
    monkeypatch.setattr(sys,'argv',['server.cli','set-admin-password'])
    monkeypatch.setattr(cli.getpass,'getpass',lambda _: 'my-new-private-test-password')
    cli.main()
    assert admin.get('/api/admin/dashboard').status_code == 401
    with app.app_context():
        hashed = get_db().execute("SELECT value FROM settings WHERE key='admin_password_hash'").fetchone()[0]
        assert hashed.startswith('scrypt:') and 'my-new-private-test-password' not in hashed
