from flask_migrate import upgrade
from conftest import bind, bootstrap, spin, administrator, post
from server.db import get_db


def test_seven_names_archive_old_round_and_complete_draw(app):
    old = app.test_client()
    previous = spin(old, bind(old)).json
    with app.app_context():
        upgrade(revision='0002_seven_participants')
        assert get_db().execute('SELECT count(*) FROM draws WHERE event_id=?', (previous['event_id'],)).fetchone()[0] == 1
    fresh = bootstrap(old)
    names = ['Amanda', 'Elsa', 'Linda', 'Karin', 'Christine', 'Chanson', 'Marlene']
    assert [p['name'] for p in fresh['participants']] == names
    assert fresh['participant'] is None and fresh['total'] == 7
    results = []
    for _ in names:
        client = app.test_client()
        state = bind(client)
        result = spin(client, state).json
        assert result['draw']['recipient']['id'] != state['participant']['id']
        results.append(result['draw']['recipient']['id'])
    assert len(set(results)) == 7
    admin, session = administrator(app)
    dashboard = admin.get('/api/admin/dashboard').json
    assert post(admin, '/admin/names', session, {'event_id': fresh['event_id'], 'original_names': names, 'names': names}).status_code == 200
    with app.app_context():
        upgrade(revision='0002_seven_participants')
    assert bootstrap(old)['event_id'] == fresh['event_id']
