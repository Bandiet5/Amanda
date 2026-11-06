from functools import wraps
import hashlib
import hmac
import secrets
import time
from flask import current_app, g, request
from .db import get_db, now

BROWSER_COOKIE = 'amanda_browser'
ADMIN_COOKIE = 'amanda_admin'


class APIError(Exception):
    def __init__(self, message, status=400, code='invalid_request'):
        self.message, self.status, self.code = message, status, code


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def new_token():
    return secrets.token_urlsafe(32)


def csrf_for(token_hash):
    return hmac.new(current_app.secret_key.encode(), ('csrf:' + token_hash).encode(), hashlib.sha256).hexdigest()


def check_csrf(token_hash):
    origin = request.headers.get('Origin')
    if origin and origin != current_app.config['PUBLIC_ORIGIN']:
        raise APIError('Please use the event website to make this change.', 403, 'csrf')
    supplied = request.headers.get('X-CSRF-Token', '')
    if not token_hash or not hmac.compare_digest(csrf_for(token_hash), supplied):
        raise APIError('Your page needs a refresh. Please reload and try again.', 403, 'csrf')
    if not request.is_json:
        raise APIError('Please send a JSON request.', 415)


def current_event(db):
    return db.execute('SELECT * FROM events WHERE active=1').fetchone()


def browser_session(db, event_id):
    token = request.cookies.get(BROWSER_COOKIE, '')
    if not token or len(token) > 128:
        return None
    return db.execute('SELECT * FROM browser_sessions WHERE token_hash=? AND event_id=?',
                      (digest(token), event_id)).fetchone()


def ensure_browser(db, event_id):
    session = browser_session(db, event_id)
    if session is None:
        token = new_token()
        db.execute('INSERT INTO browser_sessions(token_hash,event_id,created_at) VALUES(?,?,?)',
                   (digest(token), event_id, now()))
        g.new_browser_token = token
        session = db.execute('SELECT * FROM browser_sessions WHERE token_hash=?', (digest(token),)).fetchone()
    return session


def require_browser(db, event_id, bound=False, allow_revoked=False):
    session = browser_session(db, event_id)
    if session is None:
        raise APIError('The event has changed. Refresh to join the current round.', 409, 'session_changed')
    check_csrf(session['token_hash'])
    if session['revoked'] and not allow_revoked:
        raise APIError('Amanda has reset this browser link. Please use your recovery link.', 409, 'binding_reset')
    if bound and session['participant_id'] is None:
        raise APIError('Choose and confirm your name first.', 401, 'not_bound')
    return session


def admin_session():
    token = request.cookies.get(ADMIN_COOKIE, '')
    if not token or len(token) > 128:
        return None
    return get_db().execute('SELECT * FROM admin_sessions WHERE token_hash=? AND expires_at>?',
                            (digest(token), time.time())).fetchone()


def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        admin = admin_session()
        if not admin:
            raise APIError('Please sign in to Amanda’s admin area.', 401, 'admin_required')
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            check_csrf(admin['token_hash'])
        return fn(*args, **kwargs)
    return wrapped
