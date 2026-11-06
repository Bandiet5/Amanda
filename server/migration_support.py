"""Register migration commands without connecting to or creating the database."""
from pathlib import Path

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
import sqlalchemy as sa
from sqlalchemy.engine import URL, make_url
from sqlalchemy.pool import NullPool

from .schema import metadata

MIGRATIONS = Path(__file__).resolve().parent.parent / 'migrations'
schema_db = SQLAlchemy(metadata=metadata)
migrate = Migrate()


def database_path(config, explicit_test_config=None):
    """DATABASE_URL is the PaaS contract; DATABASE remains a path internally."""
    configured_url = config.get('DATABASE_URL')
    # An explicit test/embedding path must not accidentally use the host's URL.
    if explicit_test_config and 'DATABASE' in explicit_test_config and 'DATABASE_URL' not in explicit_test_config:
        configured_url = None
    if configured_url:
        try:
            url = make_url(configured_url)
        except (sa.exc.ArgumentError, ValueError) as error:
            raise RuntimeError('DATABASE_URL must be a SQLite URL for a persistent file.') from error
        if url.drivername not in ('sqlite', 'sqlite+pysqlite') or not url.database or url.database == ':memory:' or url.query:
            raise RuntimeError('This app uses SQLite. Set DATABASE_URL to sqlite:////absolute/path/amanda.sqlite3.')
        return Path(url.database).expanduser().resolve()
    return Path(config['DATABASE']).expanduser().resolve()


def _sqlite_connect(connection, _record):
    # Migration DDL must roll back with its data/version stamp on failure.
    # Disable sqlite3's implicit/legacy transaction handling; SQLAlchemy's begin
    # event below acquires the same write lock as the participant API.
    connection.isolation_level = None
    cursor = connection.cursor()
    try:
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.execute('PRAGMA busy_timeout=15000')
        cursor.execute('PRAGMA journal_mode=WAL')
        cursor.execute('PRAGMA synchronous=FULL')
    finally:
        cursor.close()


def _sqlite_begin(connection):
    connection.exec_driver_sql('BEGIN IMMEDIATE')


def configure_migrations(app, path):
    app.config['SQLALCHEMY_DATABASE_URI'] = URL.create('sqlite', database=str(path))
    app.config['DATABASE_URL'] = app.config['SQLALCHEMY_DATABASE_URI'].render_as_string(hide_password=False)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'poolclass': NullPool, 'connect_args': {'timeout': 15}}
    schema_db.init_app(app)
    migrate.init_app(app, schema_db, directory=str(MIGRATIONS), compare_type=True, render_as_batch=True)
    with app.app_context():
        # Accessing the engine configures it; no connection or DDL occurs here.
        engine = schema_db.engine
        sa.event.listen(engine, 'connect', _sqlite_connect)
        sa.event.listen(engine, 'begin', _sqlite_begin)
