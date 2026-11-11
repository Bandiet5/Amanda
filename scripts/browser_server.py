"""Isolated browser-test server. Never reads or changes the real event database."""
from pathlib import Path
import tempfile
from waitress import serve
from flask_migrate import upgrade
from werkzeug.security import generate_password_hash
from server.app import create_app

if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='amanda-browser-tests-') as directory:
        app = create_app({
            'TESTING': True, 'SECRET_KEY': 'isolated-browser-test-secret-' * 3,
            'DATABASE': str(Path(directory) / 'test.sqlite3'),
            'PUBLIC_ORIGIN': 'http://127.0.0.1:5055', 'COOKIE_SECURE': False,
            'ADMIN_PASSWORD_HASH': generate_password_hash('browser-tests-only-password', method='scrypt'),
            'TRUSTED_HOSTS': ['127.0.0.1', 'localhost'],
        })
        with app.app_context():
            upgrade(revision='0001_gift_exchange')  # Exercise the original eight-person fixture.
        serve(app, host='127.0.0.1', port=5055, threads=8)
