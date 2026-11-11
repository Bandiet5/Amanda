from flask_migrate import upgrade
from conftest import bind, bootstrap, spin, post
from server.db import get_db


def test_six_person_restart_invalidates_old_draws_and_has_unique_recipients(app):
    with app.app_context():
        upgrade(revision='0002_seven_participants')
    old = app.test_client()
    previous = spin(old, bind(old)).json
    marlene = app.test_client()
    marlene_state = bind(marlene, previous['participants'][-1]['id'])
    with app.app_context():
        upgrade()
        assert get_db().execute('SELECT count(*) FROM draws WHERE event_id=?', (previous['event_id'],)).fetchone()[0] == 1
    fresh = bootstrap(old)
    names = ['Amanda', 'Elsa', 'Linda', 'Karin', 'Christine', 'Chanson']
    assert [p['name'] for p in fresh['participants']] == names
    assert fresh['participant'] is None and fresh['draw'] is None
    assert fresh['completed_count'] == 0 and fresh['total'] == 6
    assert spin(marlene, marlene_state).status_code == 409
    assert bootstrap(marlene)['participant'] is None
    assert post(marlene, '/claim', bootstrap(marlene), {'event_id': fresh['event_id'], 'participant_id': marlene_state['participant']['id']}).status_code == 404
    results = []
    for _ in names:
        client = app.test_client()
        state = bind(client)
        result = spin(client, state).json
        assert result['draw']['recipient']['id'] != state['participant']['id']
        results.append(result['draw']['recipient']['id'])
    assert len(set(results)) == 6
    with app.app_context():
        upgrade()
    assert bootstrap(old)['event_id'] == fresh['event_id']
    assert bootstrap(old)['completed_count'] == 6
