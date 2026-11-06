"""Schema metadata for Alembic. Runtime draws retain their sqlite3 transactions."""
import sqlalchemy as sa

metadata = sa.MetaData()

# SQLite's original PRIMARY KEY declarations omit an explicit NOT NULL clause.
# Keep their reflected nullability when adopting existing installations; primary
# keys themselves retain the same uniqueness and row-ID semantics.
def identity(name='id'):
    return sa.Column(name, sa.Integer, primary_key=True, nullable=True)


def token_key(name):
    return sa.Column(name, sa.Text, primary_key=True, nullable=True)


settings = sa.Table('settings', metadata, token_key('key'), sa.Column('value', sa.Text, nullable=False))
events = sa.Table('events', metadata, identity(),
    sa.Column('active', sa.Integer, nullable=False),
    sa.Column('created_at', sa.Text, nullable=False), sa.Column('started_at', sa.Text),
    sa.Column('revision', sa.Integer, nullable=False, server_default=sa.text('0')),
    sa.CheckConstraint('active IN (0,1)'))
sa.Index('one_active_event', events.c.active, unique=True,
         sqlite_where=sa.text('active=1'), postgresql_where=sa.text('active=1'))
participants = sa.Table('participants', metadata, identity(),
    sa.Column('event_id', sa.Integer, sa.ForeignKey('events.id'), nullable=False),
    sa.Column('name', sa.Text().with_variant(sa.Text(collation='NOCASE'), 'sqlite'), nullable=False),
    sa.Column('position', sa.Integer, nullable=False), sa.Column('claimed_at', sa.Text),
    sa.Column('draw_version', sa.Integer, nullable=False, server_default=sa.text('0')),
    sa.Column('replay_version', sa.Integer, nullable=False, server_default=sa.text('0')),
    sa.CheckConstraint('length(name) BETWEEN 1 AND 40'), sa.CheckConstraint('position BETWEEN 0 AND 7'),
    sa.UniqueConstraint('event_id', 'name'), sa.UniqueConstraint('event_id', 'position'),
    sa.UniqueConstraint('event_id', 'id'))
browser_sessions = sa.Table('browser_sessions', metadata, token_key('token_hash'),
    sa.Column('event_id', sa.Integer, sa.ForeignKey('events.id'), nullable=False),
    sa.Column('participant_id', sa.Integer, sa.ForeignKey('participants.id')),
    sa.Column('revoked', sa.Integer, nullable=False, server_default=sa.text('0')),
    sa.Column('created_at', sa.Text, nullable=False), sa.CheckConstraint('revoked IN (0,1)'),
    sa.ForeignKeyConstraint(['event_id', 'participant_id'], ['participants.event_id', 'participants.id']))
sa.Index('one_active_binding', browser_sessions.c.participant_id, unique=True,
    sqlite_where=sa.text('revoked=0 AND participant_id IS NOT NULL'),
    postgresql_where=sa.text('revoked=0 AND participant_id IS NOT NULL'))
draws = sa.Table('draws', metadata,
    sa.Column('event_id', sa.Integer, sa.ForeignKey('events.id'), primary_key=True, nullable=False),
    sa.Column('giver_id', sa.Integer, primary_key=True, nullable=False),
    sa.Column('recipient_id', sa.Integer, nullable=False),
    sa.Column('segments', sa.Text, nullable=False), sa.Column('created_at', sa.Text, nullable=False),
    sa.UniqueConstraint('event_id', 'recipient_id'), sa.CheckConstraint('giver_id != recipient_id'),
    sa.ForeignKeyConstraint(['event_id', 'giver_id'], ['participants.event_id', 'participants.id']),
    sa.ForeignKeyConstraint(['event_id', 'recipient_id'], ['participants.event_id', 'participants.id']))
admin_sessions = sa.Table('admin_sessions', metadata, token_key('token_hash'),
    sa.Column('expires_at', sa.REAL().with_variant(sa.Double(), 'postgresql'), nullable=False), sa.Column('created_at', sa.Text, nullable=False))
recovery_tokens = sa.Table('recovery_tokens', metadata, token_key('token_hash'),
    sa.Column('event_id', sa.Integer, sa.ForeignKey('events.id'), nullable=False),
    sa.Column('participant_id', sa.Integer, sa.ForeignKey('participants.id'), nullable=False),
    sa.Column('expires_at', sa.REAL().with_variant(sa.Double(), 'postgresql'), nullable=False), sa.Column('used_at', sa.Text),
    sa.Column('created_at', sa.Text, nullable=False))
login_limits = sa.Table('login_limits', metadata, token_key('scope'),
    sa.Column('attempts', sa.Integer, nullable=False), sa.Column('window_start', sa.REAL().with_variant(sa.Double(), 'postgresql'), nullable=False))
audit_log = sa.Table('audit_log', metadata, identity(),
    sa.Column('event_id', sa.Integer, sa.ForeignKey('events.id')),
    sa.Column('actor', sa.Text, nullable=False), sa.Column('action', sa.Text, nullable=False),
    sa.Column('participant_name', sa.Text),
    sa.Column('details', sa.Text, nullable=False, server_default=sa.text("'{}'")),
    sa.Column('created_at', sa.Text, nullable=False))
