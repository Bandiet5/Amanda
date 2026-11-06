"""Use Flask's configured migration engine; do not create a runtime schema."""
from logging.config import fileConfig

from alembic import context
from flask import current_app

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

extension = current_app.extensions['migrate']
target_metadata = extension.db.metadata


def configure(connection=None):
    options = dict(extension.configure_args)
    options.update(target_metadata=target_metadata, transactional_ddl=True)
    if connection is None:
        options.update(url=extension.db.engine.url, literal_binds=True, dialect_opts={'paramstyle': 'named'})
    else:
        options.update(connection=connection, render_as_batch=connection.dialect.name == 'sqlite')
    context.configure(**options)


def run_migrations_offline():
    configure()
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    # A supplied connection supports isolated integration tests of the committed
    # DDL on PostgreSQL. The deployed app itself deliberately remains SQLite.
    supplied = config.attributes.get('connection')
    if supplied is not None:
        configure(supplied)
        with context.begin_transaction():
            context.run_migrations()
    else:
        with extension.db.engine.connect() as connection:
            configure(connection)
            with context.begin_transaction():
                context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
