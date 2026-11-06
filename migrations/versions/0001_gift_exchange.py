"""Initial gift-exchange schema, with non-destructive adoption of release 25db2d3.

Revision ID: 0001_gift_exchange
Revises: None
"""
from datetime import datetime, timezone
import re

from alembic import context, op
import sqlalchemy as sa
from werkzeug.security import generate_password_hash

revision = '0001_gift_exchange'
down_revision = None
branch_labels = None
depends_on = None

# Frozen with this revision: future model edits must not change the baseline.
EXPECTED = {'admin_sessions': {'checks': [],
                    'columns': {'created_at': ('text', False),
                                'expires_at': ('real', False),
                                'token_hash': ('text', True)},
                    'foreign_keys': [],
                    'indexes': {},
                    'primary_key': ('token_hash',),
                    'uniques': []},
 'audit_log': {'checks': [],
               'columns': {'action': ('text', False),
                           'actor': ('text', False),
                           'created_at': ('text', False),
                           'details': ('text', False),
                           'event_id': ('integer', True),
                           'id': ('integer', True),
                           'participant_name': ('text', True)},
               'foreign_keys': [(('event_id',), 'events', ('id',))],
               'indexes': {},
               'primary_key': ('id',),
               'uniques': []},
 'browser_sessions': {'checks': ['revoked IN (0,1)'],
                      'columns': {'created_at': ('text', False),
                                  'event_id': ('integer', False),
                                  'participant_id': ('integer', True),
                                  'revoked': ('integer', False),
                                  'token_hash': ('text', True)},
                      'foreign_keys': [(('event_id',), 'events', ('id',)),
                                       (('event_id', 'participant_id'), 'participants', ('event_id', 'id')),
                                       (('participant_id',), 'participants', ('id',))],
                      'indexes': {'one_active_binding': (('participant_id',),
                                                         True,
                                                         'revoked=0 AND participant_id IS NOT NULL')},
                      'primary_key': ('token_hash',),
                      'uniques': []},
 'draws': {'checks': ['giver_id != recipient_id'],
           'columns': {'created_at': ('text', False),
                       'event_id': ('integer', False),
                       'giver_id': ('integer', False),
                       'recipient_id': ('integer', False),
                       'segments': ('text', False)},
           'foreign_keys': [(('event_id',), 'events', ('id',)),
                            (('event_id', 'giver_id'), 'participants', ('event_id', 'id')),
                            (('event_id', 'recipient_id'), 'participants', ('event_id', 'id'))],
           'indexes': {},
           'primary_key': ('event_id', 'giver_id'),
           'uniques': [('event_id', 'recipient_id')]},
 'events': {'checks': ['active IN (0,1)'],
            'columns': {'active': ('integer', False),
                        'created_at': ('text', False),
                        'id': ('integer', True),
                        'revision': ('integer', False),
                        'started_at': ('text', True)},
            'foreign_keys': [],
            'indexes': {'one_active_event': (('active',), True, 'active=1')},
            'primary_key': ('id',),
            'uniques': []},
 'login_limits': {'checks': [],
                  'columns': {'attempts': ('integer', False),
                              'scope': ('text', True),
                              'window_start': ('real', False)},
                  'foreign_keys': [],
                  'indexes': {},
                  'primary_key': ('scope',),
                  'uniques': []},
 'participants': {'checks': ['length(name) BETWEEN 1 AND 40', 'position BETWEEN 0 AND 7'],
                  'columns': {'claimed_at': ('text', True),
                              'draw_version': ('integer', False),
                              'event_id': ('integer', False),
                              'id': ('integer', True),
                              'name': ('text', False),
                              'position': ('integer', False),
                              'replay_version': ('integer', False)},
                  'foreign_keys': [(('event_id',), 'events', ('id',))],
                  'indexes': {},
                  'primary_key': ('id',),
                  'uniques': [('event_id', 'id'), ('event_id', 'name'), ('event_id', 'position')]},
 'recovery_tokens': {'checks': [],
                     'columns': {'created_at': ('text', False),
                                 'event_id': ('integer', False),
                                 'expires_at': ('real', False),
                                 'participant_id': ('integer', False),
                                 'token_hash': ('text', True),
                                 'used_at': ('text', True)},
                     'foreign_keys': [(('event_id',), 'events', ('id',)),
                                      (('participant_id',), 'participants', ('id',))],
                     'indexes': {},
                     'primary_key': ('token_hash',),
                     'uniques': []},
 'settings': {'checks': [],
              'columns': {'key': ('text', True), 'value': ('text', False)},
              'foreign_keys': [],
              'indexes': {},
              'primary_key': ('key',),
              'uniques': []}}


def normalized(value):
    return re.sub(r'[\s"`\[\]]', '', str(value)).lower()


def _validate_existing(inspector):
    for table, spec in EXPECTED.items():
        columns = {column['name']: column for column in inspector.get_columns(table)}
        for name, (family, nullable) in spec['columns'].items():
            actual = columns.get(name)
            expected_type = {'integer': sa.Integer, 'text': sa.Text, 'real': sa.Float}[family]
            if actual is None or not isinstance(actual['type'], expected_type) or (not nullable and actual['nullable']):
                raise RuntimeError(f'Existing database column {table}.{name} does not match the supported baseline. No event data was changed.')
        if tuple(inspector.get_pk_constraint(table)['constrained_columns']) != spec['primary_key']:
            raise RuntimeError(f'Existing database primary key for {table} does not match the baseline.')
        uniques = {tuple(constraint['column_names']) for constraint in inspector.get_unique_constraints(table)}
        if not set(spec['uniques']).issubset(uniques):
            raise RuntimeError(f'Existing database uniqueness constraints for {table} do not match the baseline.')
        foreign_keys = {(tuple(key['constrained_columns']), key['referred_table'], tuple(key['referred_columns'])) for key in inspector.get_foreign_keys(table)}
        if not set(spec['foreign_keys']).issubset(foreign_keys):
            raise RuntimeError(f'Existing database foreign keys for {table} do not match the baseline.')
        checks = {normalized(constraint['sqltext']) for constraint in inspector.get_check_constraints(table)}
        if not {normalized(check) for check in spec['checks']}.issubset(checks):
            raise RuntimeError(f'Existing database checks for {table} do not match the baseline.')
        indexes = {index['name']: index for index in inspector.get_indexes(table)}
        for name, (column_names, unique, predicate) in spec['indexes'].items():
            actual = indexes.get(name)
            actual_predicate = None if actual is None else actual.get('dialect_options', {}).get(inspector.bind.dialect.name + '_where')
            if actual is None or tuple(actual['column_names']) != column_names or bool(actual['unique']) != unique or normalized(actual_predicate) != normalized(predicate):
                raise RuntimeError(f'Existing database index {name} does not match the baseline.')
        if inspector.bind.dialect.name == 'sqlite' and table == 'participants':
            sql = inspector.bind.execute(sa.text("SELECT sql FROM sqlite_master WHERE type='table' AND name='participants'")).scalar_one()
            if not re.search(r'\bname\b[^,]*\bcollate\s+nocase\b', sql, re.IGNORECASE):
                raise RuntimeError('Existing participant names must retain their NOCASE collation.')


def _seed_missing_setup():
    # INSERT ... SELECT ... WHERE NOT EXISTS works on SQLite and PostgreSQL.
    # Existing credentials, events, identities, sessions and allocations stay put.
    literal = op.inline_literal
    settings = sa.table('settings', sa.column('key', sa.Text), sa.column('value', sa.Text))
    events = sa.table('events', sa.column('id', sa.Integer), sa.column('active', sa.Integer), sa.column('created_at', sa.Text))
    people = sa.table('participants', sa.column('event_id', sa.Integer), sa.column('name', sa.Text), sa.column('position', sa.Integer))
    password_exists = sa.exists(sa.select(1).select_from(settings).where(settings.c.key == literal('admin_password_hash')))
    op.execute(settings.insert().from_select(['key', 'value'],
        sa.select(literal('admin_password_hash'), literal(generate_password_hash('amanda123', method='scrypt'))).where(~password_exists)))
    active_exists = sa.exists(sa.select(1).select_from(events).where(events.c.active == 1))
    op.execute(events.insert().from_select(['active', 'created_at'],
        sa.select(literal(1), literal(datetime.now(timezone.utc).isoformat(timespec='seconds'))).where(~active_exists)))
    for position, name in enumerate(['Amanda', 'Name 2', 'Name 3', 'Name 4', 'Name 5', 'Name 6', 'Name 7', 'Name 8']):
        present = sa.exists(sa.select(1).select_from(people).where(
            people.c.event_id == events.c.id, people.c.position == position).correlate(events))
        op.execute(people.insert().from_select(['event_id', 'name', 'position'],
            sa.select(events.c.id, literal(name), literal(position)).where(events.c.active == 1, ~present)))


def upgrade():
    if not context.is_offline_mode():
        inspector = sa.inspect(op.get_bind())
        existing = set(inspector.get_table_names()) - {'alembic_version'}
        if existing:
            missing = set(EXPECTED) - existing
            if missing:
                raise RuntimeError('Existing database is not a complete supported legacy schema; missing: ' + ', '.join(sorted(missing)) + '. No event data was changed.')
            _validate_existing(inspector)
            # Fill only missing first-run setup; never rewrite existing rows.
            _seed_missing_setup()
            return
    _create_schema()
    _seed_missing_setup()


def downgrade():
    # Removing this baseline would delete a real event (including adopted data).
    # Future revisions can downgrade to this baseline; removing it is explicit.
    raise RuntimeError('The initial baseline cannot be downgraded without deleting event data. Restore a consistent database backup instead.')


def _create_schema():
    op.create_table('admin_sessions',
    sa.Column('token_hash', sa.Text(), nullable=True),
    sa.Column('expires_at', sa.REAL().with_variant(sa.Double(), 'postgresql'), nullable=False),
    sa.Column('created_at', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('token_hash')
    )
    op.create_table('events',
    sa.Column('id', sa.Integer(), nullable=True),
    sa.Column('active', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.Text(), nullable=False),
    sa.Column('started_at', sa.Text(), nullable=True),
    sa.Column('revision', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.CheckConstraint('active IN (0,1)'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('one_active_event', 'events', ['active'], unique=True, sqlite_where=sa.text('active=1'), postgresql_where=sa.text('active=1'))
    op.create_table('login_limits',
    sa.Column('scope', sa.Text(), nullable=True),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('window_start', sa.REAL().with_variant(sa.Double(), 'postgresql'), nullable=False),
    sa.PrimaryKeyConstraint('scope')
    )
    op.create_table('settings',
    sa.Column('key', sa.Text(), nullable=True),
    sa.Column('value', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('audit_log',
    sa.Column('id', sa.Integer(), nullable=True),
    sa.Column('event_id', sa.Integer(), nullable=True),
    sa.Column('actor', sa.Text(), nullable=False),
    sa.Column('action', sa.Text(), nullable=False),
    sa.Column('participant_name', sa.Text(), nullable=True),
    sa.Column('details', sa.Text(), server_default=sa.text("'{}'"), nullable=False),
    sa.Column('created_at', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('participants',
    sa.Column('id', sa.Integer(), nullable=True),
    sa.Column('event_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.Text().with_variant(sa.Text(collation='NOCASE'), 'sqlite'), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('claimed_at', sa.Text(), nullable=True),
    sa.Column('draw_version', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('replay_version', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.CheckConstraint('length(name) BETWEEN 1 AND 40'),
    sa.CheckConstraint('position BETWEEN 0 AND 7'),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('event_id', 'id'),
    sa.UniqueConstraint('event_id', 'name'),
    sa.UniqueConstraint('event_id', 'position')
    )
    op.create_table('browser_sessions',
    sa.Column('token_hash', sa.Text(), nullable=True),
    sa.Column('event_id', sa.Integer(), nullable=False),
    sa.Column('participant_id', sa.Integer(), nullable=True),
    sa.Column('revoked', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('created_at', sa.Text(), nullable=False),
    sa.CheckConstraint('revoked IN (0,1)'),
    sa.ForeignKeyConstraint(['event_id', 'participant_id'], ['participants.event_id', 'participants.id'], ),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
    sa.ForeignKeyConstraint(['participant_id'], ['participants.id'], ),
    sa.PrimaryKeyConstraint('token_hash')
    )
    op.create_index('one_active_binding', 'browser_sessions', ['participant_id'], unique=True, sqlite_where=sa.text('revoked=0 AND participant_id IS NOT NULL'), postgresql_where=sa.text('revoked=0 AND participant_id IS NOT NULL'))
    op.create_table('draws',
    sa.Column('event_id', sa.Integer(), nullable=False),
    sa.Column('giver_id', sa.Integer(), nullable=False),
    sa.Column('recipient_id', sa.Integer(), nullable=False),
    sa.Column('segments', sa.Text(), nullable=False),
    sa.Column('created_at', sa.Text(), nullable=False),
    sa.CheckConstraint('giver_id != recipient_id'),
    sa.ForeignKeyConstraint(['event_id', 'giver_id'], ['participants.event_id', 'participants.id'], ),
    sa.ForeignKeyConstraint(['event_id', 'recipient_id'], ['participants.event_id', 'participants.id'], ),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
    sa.PrimaryKeyConstraint('event_id', 'giver_id'),
    sa.UniqueConstraint('event_id', 'recipient_id')
    )
    op.create_table('recovery_tokens',
    sa.Column('token_hash', sa.Text(), nullable=True),
    sa.Column('event_id', sa.Integer(), nullable=False),
    sa.Column('participant_id', sa.Integer(), nullable=False),
    sa.Column('expires_at', sa.REAL().with_variant(sa.Double(), 'postgresql'), nullable=False),
    sa.Column('used_at', sa.Text(), nullable=True),
    sa.Column('created_at', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
    sa.ForeignKeyConstraint(['participant_id'], ['participants.id'], ),
    sa.PrimaryKeyConstraint('token_hash')
    )
