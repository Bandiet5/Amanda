from concurrent.futures import ThreadPoolExecutor
import random
import sqlite3
import threading
import pytest
from server.db import get_db, transaction
from server.security import BROWSER_COOKIE, digest
from conftest import administrator, bind, bootstrap, post, spin


def allocations(app):
    with app.app_context():
        return dict(get_db().execute('SELECT giver_id,recipient_id FROM draws').fetchall())


def test_all_eight_draw_once_without_duplicate_or_self(app):
    clients = [app.test_client() for _ in range(8)]
    states = [bind(client) for client in clients]
    assert len(states[0]['segments']) == 7
    results = []
    for client, state in zip(clients, states):
        response = spin(client, state)
        assert response.status_code == 200
        result = response.json
        draw = result['draw']
        assert draw['recipient']['id'] != result['participant']['id']
        assert draw['recipient'] in draw['segments']
        assert bootstrap(client)['draw'] == draw
        assert spin(client, state).json['draw'] == draw
        results.append(draw['recipient']['id'])
    assert len(set(results)) == 8
    assert bootstrap(clients[-1])['completed_count'] == 8
    assert len(response.json['draw']['segments']) == 1


@pytest.mark.parametrize('seed', range(24))
def test_varied_draw_orders_never_dead_end(app, monkeypatch, seed):
    rng = random.Random(seed)
    monkeypatch.setattr('server.app.secrets.choice', rng.choice)
    clients = [app.test_client() for _ in range(8)]
    states = [bind(client) for client in clients]
    order = list(range(8)); rng.shuffle(order)
    for index in order:
        response = spin(clients[index], states[index])
        assert response.status_code == 200, response.json
    saved = allocations(app)
    assert len(saved) == len(set(saved.values())) == 8
    assert all(giver != recipient for giver, recipient in saved.items())


def test_atomic_concurrent_claims_only_one_succeeds(app):
    clients = [app.test_client() for _ in range(6)]
    states = [bootstrap(c) for c in clients]
    person_id = states[0]['participants'][0]['id']
    barrier = threading.Barrier(6)
    def compete(index):
        barrier.wait()
        return post(clients[index], '/claim', states[index], {'event_id': states[index]['event_id'], 'participant_id': person_id})
    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(compete, range(6)))
    assert sorted(r.status_code for r in responses) == [200, 409, 409, 409, 409, 409]
    assert all(r.json.get('code') == 'name_claimed' for r in responses if r.status_code == 409)


def test_concurrent_spins_and_duplicate_requests_are_consistent(app):
    originals = [app.test_client() for _ in range(8)]
    states = [bind(c) for c in originals]
    # Two simultaneous requests for each browser plus all eight givers at once.
    jobs = []
    for client, state in zip(originals, states):
        for _ in range(2):
            duplicate = app.test_client()
            duplicate.set_cookie(BROWSER_COOKIE, client.get_cookie(BROWSER_COOKIE).value)
            jobs.append((duplicate, state))
    barrier = threading.Barrier(16)
    def draw(job):
        barrier.wait()
        return spin(*job)
    with ThreadPoolExecutor(max_workers=16) as pool:
        responses = list(pool.map(draw, jobs))
    assert all(r.status_code == 200 for r in responses), [r.json for r in responses]
    for i in range(0, 16, 2):
        assert responses[i].json['draw'] == responses[i + 1].json['draw']
    assert len(allocations(app)) == len(set(allocations(app).values())) == 8


def test_browser_cannot_change_names_or_supply_result(app):
    client = app.test_client(); state = bind(client)
    response = post(client, '/claim', state, {'event_id': state['event_id'], 'participant_id': state['participants'][1]['id']})
    assert response.status_code == 409
    forged = post(client, '/draw', state, {'event_id': state['event_id'], 'draw_version': 0,
                                         'participant_id': state['participants'][1]['id'], 'recipient_id': state['participant']['id']})
    assert forged.status_code == 200
    assert forged.json['participant']['id'] == state['participant']['id']
    assert forged.json['draw']['recipient']['id'] != state['participant']['id']
    assert 'assignments' not in forged.json


def test_tokens_are_hashes_and_results_are_not_in_cookies(app):
    client = app.test_client(); state = bind(client); result = spin(client, state).json
    raw = client.get_cookie(BROWSER_COOKIE).value
    assert len(raw) >= 40
    with app.app_context():
        session = get_db().execute('SELECT * FROM browser_sessions').fetchone()
        assert session['token_hash'] == digest(raw)
        assert raw not in str(dict(session))
    assert result['draw']['recipient']['name'] not in raw


def test_database_constraints_prevent_duplicate_and_self_assignments(app):
    client = app.test_client(); state = bind(client); spin(client, state)
    ids = [p['id'] for p in state['participants']]
    recipient = allocations(app)[ids[0]]
    with app.app_context():
        with pytest.raises(sqlite3.IntegrityError), transaction() as db:
            db.execute('INSERT INTO draws VALUES(?,?,?,?,?)', (state['event_id'], ids[1], recipient, '[]', 'now'))
        with pytest.raises(sqlite3.IntegrityError), transaction() as db:
            db.execute('INSERT INTO draws VALUES(?,?,?,?,?)', (state['event_id'], ids[2], ids[2], '[]', 'now'))


def test_lost_response_and_server_restart_preserve_draw(app):
    from server.app import create_app
    client = app.test_client(); state = bind(client)
    spin(client, state)  # Discard the response, as if the network connection were lost.
    stored = allocations(app)
    restarted = create_app(dict(app.config))
    returning = restarted.test_client(); returning.set_cookie(BROWSER_COOKIE, client.get_cookie(BROWSER_COOKIE).value)
    assert bootstrap(returning)['draw']['recipient']['id'] == stored[state['participant']['id']]
    assert spin(returning, state).json['draw']['recipient']['id'] == stored[state['participant']['id']]
    assert allocations(app) == stored


def test_csrf_origin_and_malformed_identity_are_rejected(app):
    client = app.test_client(); state = bootstrap(client)
    body = {'participant_id': state['participants'][0]['id'], 'event_id': state['event_id']}
    assert client.post('/api/claim', json=body).status_code == 403
    assert client.post('/api/claim', json=body, headers={'X-CSRF-Token': state['csrf'], 'Origin': 'https://evil.example'}).status_code == 403
    assert post(client, '/claim', state, {**body, 'participant_id': []}).status_code == 400
    assert not allocations(app)


def test_secure_cookie_defaults_and_api_cache_headers(app):
    app.config['COOKIE_SECURE'] = True
    response = app.test_client().get('/api/state')
    cookie = response.headers['Set-Cookie']
    assert 'Secure' in cookie and 'HttpOnly' in cookie and 'SameSite=Lax' in cookie and 'Max-Age=' in cookie
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'frame-ancestors' in response.headers['Content-Security-Policy']
    assert response.headers['Strict-Transport-Security']
