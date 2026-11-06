"""Run from the project root: python -m server.cli --help."""
import argparse
import getpass
import os
from pathlib import Path
import sqlite3
from flask_migrate import upgrade
from werkzeug.security import generate_password_hash
from .app import create_app, audit
from .db import get_db, transaction
from .security import current_event


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description='Manage Amanda se Kersfees')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init-db', help='Apply committed Alembic migrations; preserves existing event data')
    sub.add_parser('set-admin-password', help='Securely prompt for Amanda’s admin password')
    backup = sub.add_parser('backup', help='Create a consistent SQLite backup, including WAL data')
    backup.add_argument('destination', type=Path)
    args = parser.parse_args()
    app = create_app()
    with app.app_context():
        if args.command == 'init-db':
            upgrade()
            print('Database ready; existing claims and draws retained.')
        elif args.command == 'set-admin-password':
            if app.config['ADMIN_PASSWORD_HASH']:
                parser.error('Unset ADMIN_PASSWORD_HASH first; the environment overrides the database password.')
            password = getpass.getpass('New admin password (at least 12 characters): ')
            if len(password) < 12 or len(password) > 1024:
                parser.error('Use between 12 and 1024 characters.')
            if password != getpass.getpass('Confirm password: '):
                parser.error('Passwords do not match.')
            hashed = generate_password_hash(password, method='scrypt')
            with transaction() as db:
                db.execute("INSERT INTO settings(key,value) VALUES('admin_password_hash',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (hashed,))
                db.execute('DELETE FROM admin_sessions')
                audit(db, current_event(db)['id'], 'admin_password_changed')
            print('Admin password saved as a scrypt hash. Existing admin sessions were signed out.')
        elif args.command == 'backup':
            destination = args.destination.expanduser().resolve()
            root = Path(__file__).resolve().parent.parent
            if destination.is_relative_to(root / 'dist') or destination.is_relative_to(root / 'frontend'):
                parser.error('Backups must stay outside publicly served directories.')
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            try:
                fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.close(fd)
            except FileExistsError:
                parser.error('Destination exists. Choose a new backup filename.')
            with sqlite3.connect(destination) as target:
                get_db().backup(target)
            print(f'Consistent backup saved to {destination}')


if __name__ == '__main__':
    main()
