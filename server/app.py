import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
from urllib.parse import urlsplit

from dotenv import load_dotenv
from flask import Flask, g, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash

from .db import close_db, create_event, get_db, now, transaction
from .matching import valid_candidates
from .migration_support import configure_migrations, database_path
from .security import (ADMIN_COOKIE, BROWSER_COOKIE, APIError, admin_required, admin_session,
                       browser_session, check_csrf, csrf_for, current_event, digest,
                       ensure_browser, new_token, require_browser)

ROOT = Path(__file__).resolve().parent.parent


def participants(db, event_id):
    return db.execute('SELECT * FROM participants WHERE event_id=? ORDER BY position', (event_id,)).fetchall()


def candidates(db, event_id, giver_id):
    people = participants(db, event_id)
    allocations = db.execute('SELECT giver_id,recipient_id FROM draws WHERE event_id=?', (event_id,)).fetchall()
    givers = {p['id'] for p in people} - {d['giver_id'] for d in allocations}
    recipients = [p['id'] for p in people if p['id'] not in {d['recipient_id'] for d in allocations}]
    ids = valid_candidates(giver_id, givers, recipients)
    return [{'id': p['id'], 'name': p['name']} for p in people if p['id'] in ids]


def saved_draw(db, event_id, giver_id):
    row = db.execute('SELECT d.*,p.name FROM draws d JOIN participants p ON p.id=d.recipient_id '
                     'WHERE d.event_id=? AND d.giver_id=?', (event_id, giver_id)).fetchone()
    if not row:
        return None
    return {'recipient': {'id': row['recipient_id'], 'name': row['name']},
            'segments': json.loads(row['segments']), 'drawn_at': row['created_at']}


def state_payload(db, event, session):
    people = participants(db, event['id'])
    person = next((p for p in people if p['id'] == session['participant_id']), None) if not session['revoked'] else None
    draw = saved_draw(db, event['id'], person['id']) if person else None
    completed = db.execute('SELECT count(*) FROM draws WHERE event_id=?', (event['id'],)).fetchone()[0]
    return {
        'event_id': event['id'], 'revision': event['revision'],
        'csrf': csrf_for(session['token_hash']), 'binding_lost': bool(session['revoked']),
        'participants': [{'id': p['id'], 'name': p['name'], 'claimed': p['claimed_at'] is not None} for p in people],
        'participant': {'id': person['id'], 'name': person['name'], 'draw_version': person['draw_version'],
                        'replay_version': person['replay_version']} if person else None,
        'draw': draw, 'segments': draw['segments'] if draw else candidates(db, event['id'], person['id']) if person else [],
        'completed_count': completed, 'total': len(people),
    }


def audit(db, event_id, action, name=None, details=None):
    db.execute('INSERT INTO audit_log(event_id,actor,action,participant_name,details,created_at) VALUES(?,?,?,?,?,?)',
               (event_id, 'Amanda (administrator)', action, name, json.dumps(details or {}), now()))


def json_body():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise APIError('Please check the information and try again.')
    return body


def person_or_404(db, event_id, person_id):
    if type(person_id) is not int:
        raise APIError('Please choose a valid participant name.')
    person = db.execute('SELECT * FROM participants WHERE event_id=? AND id=?', (event_id, person_id)).fetchone()
    if not person:
        raise APIError('This person is no longer part of the current round.', 404)
    return person


def create_app(test_config=None):
    load_dotenv(ROOT / '.env.local')
    load_dotenv(ROOT / '.env')
    app = Flask(__name__, static_folder=None)
    environment = os.environ.get('APP_ENV', 'production')
    if environment not in ('production', 'development'):
        raise RuntimeError('APP_ENV must be production or development.')
    production = environment == 'production'
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY'),
        DATABASE=os.environ.get('DATABASE_PATH', str(ROOT / 'instance' / 'amanda.sqlite3')),
        DATABASE_URL=os.environ.get('DATABASE_URL'),
        PUBLIC_ORIGIN=os.environ.get('PUBLIC_ORIGIN', 'http://localhost:5173' if not production else ''),
        COOKIE_SECURE=os.environ.get('ALLOW_INSECURE_HTTP') != '1',
        ADMIN_PASSWORD_HASH=os.environ.get('ADMIN_PASSWORD_HASH'),
        MAX_CONTENT_LENGTH=16384, DEBUG=False, TESTING=False,
    )
    if test_config:
        app.config.update(test_config)
    if not app.secret_key or len(app.secret_key) < 32:
        raise RuntimeError('Set SECRET_KEY to at least 32 random characters. See README.md.')
    origin = urlsplit(app.config['PUBLIC_ORIGIN'])
    if origin.scheme not in ('http', 'https') or not origin.hostname or origin.path not in ('', '/') or origin.query or origin.fragment or origin.username or origin.password:
        raise RuntimeError('PUBLIC_ORIGIN must be the exact website origin, without a path.')
    app.config['PUBLIC_ORIGIN'] = app.config['PUBLIC_ORIGIN'].rstrip('/')
    if production and not app.testing and (origin.scheme != 'https' or not app.config['COOKIE_SECURE']):
        raise RuntimeError('Production requires an https:// PUBLIC_ORIGIN and secure cookies.')
    app.config['TRUSTED_HOSTS'] = [origin.hostname] if production else ['localhost', '127.0.0.1', '[::1]']
    if test_config and 'TRUSTED_HOSTS' in test_config:
        app.config['TRUSTED_HOSTS'] = test_config['TRUSTED_HOSTS']
    db_path = database_path(app.config, test_config)
    if any(db_path.is_relative_to(path) for path in (ROOT / 'dist', ROOT / 'frontend')):
        raise RuntimeError('The database must be outside frontend/publicly served directories.')
    db_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    app.config['DATABASE'] = str(db_path)
    app.teardown_appcontext(close_db)
    configure_migrations(app, db_path)
    try:
        db_path.chmod(0o600)
    except OSError:
        pass  # Windows ACLs should be configured by the operator.

    @app.after_request
    def headers(response):
        if getattr(g, 'new_browser_token', None):
            response.set_cookie(BROWSER_COOKIE, g.new_browser_token, max_age=180 * 86400,
                                secure=app.config['COOKIE_SECURE'], httponly=True, samesite='Lax', path='/')
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        if app.config['COOKIE_SECURE']:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        if request.path.startswith('/api/') or request.path in ('/', '/admin'):
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(APIError)
    def api_error(error):
        response = jsonify(error=error.message, code=error.code)
        response.status_code = error.status
        if error.status == 429:
            response.headers['Retry-After'] = '900'
        return response

    @app.errorhandler(sqlite3.OperationalError)
    def sqlite_error(error):
        if 'locked' in str(error).lower() or 'busy' in str(error).lower():
            return jsonify(error='A few Christmas elves are busy. Please try again in a moment.', code='busy'), 503
        app.logger.exception('Database operation failed')
        return jsonify(error='We could not save that change. Please try again.', code='database_error'), 500

    @app.errorhandler(Exception)
    def unexpected_error(error):
        if isinstance(error, HTTPException):
            if request.path.startswith('/api/'):
                return jsonify(error=error.description, code='http_error'), error.code
            return error
        app.logger.exception('Unhandled request error')
        return jsonify(error='Something went wrong. Your saved draw is safe; please refresh.', code='server_error'), 500

    @app.get('/api/health')
    def health():
        try:
            db = get_db()
            version = db.execute('SELECT version_num FROM alembic_version').fetchone()
            active = db.execute('SELECT 1 FROM events WHERE active=1').fetchone()
        except sqlite3.OperationalError as error:
            if 'no such table' not in str(error).lower():
                raise
            version = active = None
        if version is None or active is None:
            return jsonify(ok=False, code='migration_required', error='Apply the committed database migrations before starting the event.'), 503
        return jsonify(ok=True)

    @app.get('/api/state')
    def state():
        # A short write transaction also covers anonymous session issuance.
        with transaction() as db:
            event = current_event(db)
            session = ensure_browser(db, event['id'])
            payload = state_payload(db, event, session)
        return jsonify(payload)

    @app.post('/api/claim')
    def claim():
        body = json_body()
        with transaction() as db:
            event = current_event(db)
            session = require_browser(db, event['id'])
            if body.get('event_id') != event['id']:
                raise APIError('A new round has started. Refresh to join it.', 409, 'session_changed')
            if session['participant_id'] is not None:
                if session['participant_id'] == body.get('participant_id'):
                    return jsonify(state_payload(db, event, session))
                raise APIError('This browser already has a name. Ask Amanda for help if it is incorrect.', 409, 'already_bound')
            person = person_or_404(db, event['id'], body.get('participant_id'))
            if person['claimed_at']:
                raise APIError('Someone just selected that name. Please choose your own name from the updated list.', 409, 'name_claimed')
            db.execute('UPDATE browser_sessions SET participant_id=? WHERE token_hash=?', (person['id'], session['token_hash']))
            db.execute('UPDATE participants SET claimed_at=? WHERE id=?', (now(), person['id']))
            db.execute('UPDATE events SET revision=revision+1 WHERE id=?', (event['id'],))
            return jsonify(state_payload(db, current_event(db), browser_session(db, event['id'])))

    @app.post('/api/draw')
    def draw():
        body = json_body()
        with transaction() as db:
            event = current_event(db)
            session = require_browser(db, event['id'], bound=True)
            person = person_or_404(db, event['id'], session['participant_id'])
            if body.get('event_id') != event['id'] or body.get('draw_version') != person['draw_version']:
                raise APIError('Amanda has updated this draw. Refresh to see its current state.', 409, 'draw_changed')
            if not saved_draw(db, event['id'], person['id']):
                segments = candidates(db, event['id'], person['id'])
                if not segments:
                    raise APIError('There is no valid draw available. Please ask Amanda for help.', 409, 'no_candidates')
                winner = secrets.choice(segments)
                timestamp = now()
                db.execute('INSERT INTO draws(event_id,giver_id,recipient_id,segments,created_at) VALUES(?,?,?,?,?)',
                           (event['id'], person['id'], winner['id'], json.dumps(segments), timestamp))
                db.execute('UPDATE events SET started_at=COALESCE(started_at,?),revision=revision+1 WHERE id=?',
                           (timestamp, event['id']))
            return jsonify(state_payload(db, current_event(db), session))

    @app.post('/api/recover')
    def recover():
        body = json_body()
        with transaction() as db:
            event = current_event(db)
            session = require_browser(db, event['id'], allow_revoked=True)
            token = body.get('token', '')
            if not isinstance(token, str) or len(token) > 128:
                raise APIError('This recovery link is not valid.', 400)
            recovery = db.execute('SELECT * FROM recovery_tokens WHERE token_hash=? AND event_id=? '
                                  'AND used_at IS NULL AND expires_at>?', (digest(token), event['id'], time.time())).fetchone()
            if not recovery:
                raise APIError('This recovery link has expired or was already used. Ask Amanda for a fresh one.', 410, 'link_expired')
            if session['participant_id'] is not None and not session['revoked'] and session['participant_id'] != recovery['participant_id']:
                raise APIError('This browser already belongs to someone else. Open the recovery link on your own phone.', 409, 'already_bound')
            db.execute('UPDATE browser_sessions SET revoked=1 WHERE participant_id=? AND revoked=0', (recovery['participant_id'],))
            db.execute('UPDATE browser_sessions SET participant_id=?,revoked=0 WHERE token_hash=?',
                       (recovery['participant_id'], session['token_hash']))
            db.execute('UPDATE recovery_tokens SET used_at=? WHERE token_hash=?', (now(), digest(token)))
            db.execute('UPDATE participants SET claimed_at=COALESCE(claimed_at,?) WHERE id=?', (now(), recovery['participant_id']))
            db.execute('UPDATE events SET revision=revision+1 WHERE id=?', (event['id'],))
            person = person_or_404(db, event['id'], recovery['participant_id'])
            audit(db, event['id'], 'recovery_link_used', person['name'])
            return jsonify(state_payload(db, current_event(db), browser_session(db, event['id'])))

    @app.get('/api/admin/session')
    def admin_status():
        with transaction() as db:
            admin = admin_session()
            browser = ensure_browser(db, current_event(db)['id'])
            return jsonify(authenticated=admin is not None, csrf=csrf_for(admin['token_hash'] if admin else browser['token_hash']))

    @app.post('/api/admin/login')
    def login():
        body = json_body()
        password = body.get('password', '')
        with transaction() as db:
            event = current_event(db)
            require_browser(db, event['id'], allow_revoked=True)
            scopes = [('ip:' + digest(request.remote_addr or 'unknown'), 5), ('global', 30)]
            timestamp = time.time()
            for scope, limit in scopes:
                row = db.execute('SELECT * FROM login_limits WHERE scope=?', (scope,)).fetchone()
                if row and timestamp - row['window_start'] < 900 and row['attempts'] >= limit:
                    raise APIError('Too many sign-in attempts. Please wait 15 minutes and try again.', 429, 'rate_limited')
            stored = db.execute("SELECT value FROM settings WHERE key='admin_password_hash'").fetchone()
            password_hash = app.config['ADMIN_PASSWORD_HASH'] or (stored['value'] if stored else None)
            if not password_hash:
                raise APIError('Admin access needs setup. Run the set-admin-password command on the server.', 503, 'admin_not_configured')
            valid = isinstance(password, str) and len(password) <= 1024 and check_password_hash(password_hash, password)
            if not valid:
                for scope, _ in scopes:
                    db.execute('INSERT INTO login_limits(scope,attempts,window_start) VALUES(?,1,?) '
                               'ON CONFLICT(scope) DO UPDATE SET attempts=CASE WHEN ?-window_start>=900 THEN 1 ELSE attempts+1 END, '
                               'window_start=CASE WHEN ?-window_start>=900 THEN ? ELSE window_start END',
                               (scope, timestamp, timestamp, timestamp, timestamp))
                audit(db, event['id'], 'admin_login_failed')
            else:
                db.execute('DELETE FROM login_limits WHERE scope=?', (scopes[0][0],))
                db.execute('DELETE FROM admin_sessions WHERE expires_at<=?', (timestamp,))
                token = new_token()
                db.execute('INSERT INTO admin_sessions(token_hash,expires_at,created_at) VALUES(?,?,?)',
                           (digest(token), timestamp + 12 * 3600, now()))
                previous = request.cookies.get(ADMIN_COOKIE)
                if previous:
                    db.execute('DELETE FROM admin_sessions WHERE token_hash=?', (digest(previous),))
                audit(db, event['id'], 'admin_login')
        # Failed attempt counters must commit, rather than rolling back with an exception.
        if not valid:
            raise APIError('That password does not match. Please try again.', 401, 'invalid_password')
        response = jsonify(authenticated=True, csrf=csrf_for(digest(token)))
        response.set_cookie(ADMIN_COOKIE, token, max_age=12 * 3600, secure=app.config['COOKIE_SECURE'],
                            httponly=True, samesite='Strict', path='/api/admin')
        return response

    @app.post('/api/admin/logout')
    @admin_required
    def logout():
        with transaction() as db:
            db.execute('DELETE FROM admin_sessions WHERE token_hash=?', (admin_session()['token_hash'],))
            audit(db, current_event(db)['id'], 'admin_logout')
        response = jsonify(ok=True)
        response.delete_cookie(ADMIN_COOKIE, path='/api/admin', secure=app.config['COOKIE_SECURE'], httponly=True, samesite='Strict')
        return response

    @app.get('/api/admin/dashboard')
    @admin_required
    def dashboard():
        with transaction(write=False) as db:
            event = current_event(db)
            rows = db.execute('SELECT p.*,d.created_at AS drawn_at FROM participants p LEFT JOIN draws d '
                              'ON d.event_id=p.event_id AND d.giver_id=p.id WHERE p.event_id=? ORDER BY p.position', (event['id'],)).fetchall()
            log = db.execute('SELECT * FROM audit_log ORDER BY id DESC LIMIT 60').fetchall()
            return jsonify(event_id=event['id'], started=event['started_at'] is not None, revision=event['revision'],
                           participants=[{'id': p['id'], 'name': p['name'], 'claimed': p['claimed_at'] is not None,
                                          'claimed_at': p['claimed_at'], 'drawn_at': p['drawn_at'], 'completed': p['drawn_at'] is not None, 'draw_version': p['draw_version']} for p in rows],
                           audit=[dict(row) for row in log])

    @app.post('/api/admin/reveal')
    @admin_required
    def reveal():
        if json_body().get('confirmation') != 'REVEAL ASSIGNMENTS':
            raise APIError('Confirm that you want to reveal the secret assignments.')
        with transaction() as db:
            event = current_event(db)
            rows = db.execute('SELECT d.giver_id,p.name AS recipient FROM draws d JOIN participants p ON p.id=d.recipient_id '
                              'WHERE d.event_id=?', (event['id'],)).fetchall()
            audit(db, event['id'], 'assignments_revealed')
            return jsonify(revision=event['revision'], assignments=[dict(row) for row in rows])

    @app.post('/api/admin/names')
    @admin_required
    def rename():
        body = json_body()
        names = body.get('names')
        if not isinstance(names, list) or len(names) != 8 or any(not isinstance(n, str) or not 1 <= len(n.strip()) <= 40 or any(ord(c)<32 for c in n) for n in names):
            raise APIError('Enter exactly eight names, each between 1 and 40 characters.')
        names = [n.strip() for n in names]
        if len({n.casefold() for n in names}) != 8:
            raise APIError('Each person needs a different name.')
        with transaction() as db:
            event = current_event(db)
            if body.get('event_id') != event['id']:
                raise APIError('A new round has started. Reload the dashboard before editing names.', 409, 'event_changed')
            rows = participants(db, event['id'])
            original_names = body.get('original_names')
            if original_names is not None:
                if original_names != [p['name'] for p in rows]:
                    raise APIError('The saved names changed in another admin tab. Use the saved names, then edit again.', 409, 'names_changed')
            elif body.get('revision') != event['revision']:
                raise APIError('The event has changed. Reload the dashboard before editing names.', 409, 'event_changed')
            temporary_prefix = secrets.token_hex(10)
            for p in rows:
                db.execute('UPDATE participants SET name=? WHERE id=?', (temporary_prefix + str(p['id']), p['id']))
            for p, name in zip(rows, names):
                db.execute('UPDATE participants SET name=? WHERE id=?', (name, p['id']))
            # Keep every assignment and segment ID intact; only the display names change.
            names_by_id = {p['id']: name for p, name in zip(rows, names)}
            saved = db.execute('SELECT giver_id,segments FROM draws WHERE event_id=?', (event['id'],)).fetchall()
            for allocation in saved:
                segments = json.loads(allocation['segments'])
                for segment in segments:
                    segment['name'] = names_by_id[segment['id']]
                db.execute('UPDATE draws SET segments=? WHERE event_id=? AND giver_id=?',
                           (json.dumps(segments), event['id'], allocation['giver_id']))
            db.execute('UPDATE events SET revision=revision+1 WHERE id=?', (event['id'],))
            audit(db, event['id'], 'participant_names_updated', details={'names': names})
        return jsonify(ok=True)

    def admin_person_action(person_id, action):
        body = json_body()
        with transaction() as db:
            event = current_event(db)
            if body.get('event_id') != event['id']:
                raise APIError('The event has changed. Reload the dashboard.', 409, 'event_changed')
            person = person_or_404(db, event['id'], person_id)
            if action == 'replay':
                if not saved_draw(db, event['id'], person_id):
                    raise APIError('This person has not drawn yet.', 409)
                db.execute('UPDATE participants SET replay_version=replay_version+1 WHERE id=?', (person_id,))
                audit(db, event['id'], 'animation_replayed', person['name'])
            elif action == 'new-draw':
                if body.get('confirmation') != 'NEW DRAW':
                    raise APIError('Type NEW DRAW to invalidate this person’s previous recipient.')
                if body.get('draw_version') != person['draw_version']:
                    raise APIError('This person’s draw has changed. Close this dialog and review their current draw before confirming again.', 409, 'draw_changed')
                if not saved_draw(db, event['id'], person_id):
                    raise APIError('This person already has an unused draw. Refresh the dashboard.', 409)
                db.execute('DELETE FROM draws WHERE event_id=? AND giver_id=?', (event['id'], person_id))
                db.execute('UPDATE participants SET draw_version=draw_version+1,replay_version=replay_version+1 WHERE id=?', (person_id,))
                audit(db, event['id'], 'new_draw_granted', person['name'], {'previous_recipient_invalidated': True})
            elif action == 'recovery':
                if body.get('confirmation') != 'RESET BROWSER LINK':
                    raise APIError('Confirm that you want to reset this person’s browser link.')
                db.execute('UPDATE participants SET claimed_at=COALESCE(claimed_at,?) WHERE id=?', (now(), person_id))
                db.execute('UPDATE browser_sessions SET revoked=1 WHERE participant_id=?', (person_id,))
                db.execute('DELETE FROM recovery_tokens WHERE participant_id=?', (person_id,))
                token = new_token()
                db.execute('INSERT INTO recovery_tokens(token_hash,event_id,participant_id,expires_at,created_at) VALUES(?,?,?,?,?)',
                           (digest(token), event['id'], person_id, time.time() + 86400, now()))
                audit(db, event['id'], 'browser_binding_reset', person['name'])
            db.execute('UPDATE events SET revision=revision+1 WHERE id=?', (event['id'],))
            if action == 'recovery':
                return jsonify(ok=True, recovery_url=app.config['PUBLIC_ORIGIN'] + '/#recover=' + token, expires_in=86400)
            return jsonify(ok=True)

    @app.post('/api/admin/participants/<int:person_id>/replay')
    @admin_required
    def replay(person_id):
        return admin_person_action(person_id, 'replay')

    @app.post('/api/admin/participants/<int:person_id>/new-draw')
    @admin_required
    def new_draw(person_id):
        return admin_person_action(person_id, 'new-draw')

    @app.post('/api/admin/participants/<int:person_id>/recovery')
    @admin_required
    def recovery(person_id):
        return admin_person_action(person_id, 'recovery')

    @app.post('/api/admin/reset')
    @admin_required
    def reset():
        body = json_body()
        if body.get('confirmation') != 'RESET ENTIRE EVENT':
            raise APIError('Type RESET ENTIRE EVENT to start a new round.')
        with transaction() as db:
            event = current_event(db)
            if body.get('event_id') != event['id']:
                raise APIError('A new round already exists. Refresh the dashboard.', 409)
            names = [p['name'] for p in participants(db, event['id'])]
            db.execute('DELETE FROM draws WHERE event_id=?', (event['id'],))
            db.execute('DELETE FROM recovery_tokens WHERE event_id=?', (event['id'],))
            db.execute('DELETE FROM browser_sessions WHERE event_id=?', (event['id'],))
            db.execute('UPDATE participants SET claimed_at=NULL WHERE event_id=?', (event['id'],))
            db.execute('UPDATE events SET active=0 WHERE id=?', (event['id'],))
            new_id = create_event(db, names)
            audit(db, new_id, 'entire_event_reset', details={'previous_event_id': event['id']})
        return jsonify(ok=True, event_id=new_id)

    @app.get('/')
    @app.get('/admin')
    def frontend():
        if not (ROOT / 'dist' / 'index.html').exists():
            return 'Build the frontend with npm run build, or use the Vite development server.', 503
        return send_from_directory(ROOT / 'dist', 'index.html')

    @app.get('/assets/<path:filename>')
    def assets(filename):
        return send_from_directory(ROOT / 'dist' / 'assets', filename, max_age=31536000)

    @app.get('/favicon.svg')
    def favicon():
        return send_from_directory(ROOT / 'dist', 'favicon.svg')

    return app
