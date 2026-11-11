import pytest
from flask_migrate import upgrade
from werkzeug.security import generate_password_hash
from server.app import create_app

PASSWORD = 'a-test-password-only-2026'


@pytest.fixture(scope='session')
def password_hash():
    return generate_password_hash(PASSWORD, method='scrypt')


@pytest.fixture
def app(tmp_path, password_hash):
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test-secret-' * 5,
                       'DATABASE': str(tmp_path / 'event.sqlite3'), 'PUBLIC_ORIGIN': 'http://localhost',
                       'COOKIE_SECURE': False, 'ADMIN_PASSWORD_HASH': password_hash,
                       'TRUSTED_HOSTS': ['localhost']})
    with app.app_context():
        upgrade(revision='0001_gift_exchange')  # Exercise the original eight-person fixture.
    return app


def bootstrap(client):
    response = client.get('/api/state')
    assert response.status_code == 200
    return response.json


def post(client, path, state, body=None):
    return client.post('/api' + path, json=body or {}, headers={'X-CSRF-Token': state['csrf'], 'Origin': 'http://localhost'})


def bind(client, person_id=None):
    state = bootstrap(client)
    if person_id is None:
        person_id = next(p['id'] for p in state['participants'] if not p['claimed'])
    response = post(client, '/claim', state, {'event_id': state['event_id'], 'participant_id': person_id})
    assert response.status_code == 200, response.json
    return response.json


def spin(client, state):
    return post(client, '/draw', state, {'event_id': state['event_id'], 'draw_version': state['participant']['draw_version']})


def administrator(app):
    client = app.test_client()
    state = client.get('/api/admin/session').json
    response = post(client, '/admin/login', state, {'password': PASSWORD})
    assert response.status_code == 200
    return client, response.json
