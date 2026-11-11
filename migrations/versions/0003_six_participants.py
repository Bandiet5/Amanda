"""Start Amanda's six-person Christmas round; retain previous rounds."""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa

revision = '0003_six_participants'
down_revision = '0002_seven_participants'
branch_labels = None
depends_on = None

NAMES = ['Amanda', 'Elsa', 'Linda', 'Karin', 'Christine', 'Chanson']


def upgrade():
    db = op.get_bind()
    db.execute(sa.text('UPDATE events SET active=0 WHERE active=1'))
    db.execute(sa.text('INSERT INTO events(active,created_at) VALUES(1,:created)'),
               {'created': datetime.now(timezone.utc).isoformat(timespec='seconds')})
    event = db.execute(sa.text('SELECT id FROM events WHERE active=1')).scalar_one()
    for position, name in enumerate(NAMES):
        db.execute(sa.text('INSERT INTO participants(event_id,name,position) VALUES(:event,:name,:position)'),
                   {'event': event, 'name': name, 'position': position})


def downgrade():
    raise RuntimeError('Keep the six-person round and its data; this data migration cannot be undone automatically.')
