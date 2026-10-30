import csv
import io
import os
import secrets
import threading
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, jsonify, request, send_from_directory, session, Response
from core import form_url, parse_prefill, validate_rows, build_url, pick_rows

env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(env_file):
    for line in open(env_file):
        key, sep, value = line.strip().partition('=')
        if sep and not key.startswith('#'):
            os.environ.setdefault(key.strip(), value.strip().strip('"\''))

FRONTEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend')
app = Flask(__name__, static_folder=os.path.join(FRONTEND, 'static'), static_url_path='/static')
app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY') or secrets.token_hex(32), MAX_CONTENT_LENGTH=2 * 1024 * 1024,
                  SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict',
                  SESSION_COOKIE_SECURE=os.environ.get('RENDER') == 'true')
lock = threading.RLock()
cancel = threading.Event()
state = {'status': 'idle', 'completed': 0, 'total': 0, 'logs': []}


def protect(f):
    @wraps(f)
    def wrapped(*a, **kw):
        if not session.get('auth'):
            return jsonify(error='Please sign in.'), 401
        if request.method == 'POST' and not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), session.get('csrf', 'missing')):
            return jsonify(error='Session expired. Refresh and sign in.'), 403
        return f(*a, **kw)
    return wrapped


@app.after_request
def headers(r):
    r.headers['X-Content-Type-Options'] = 'nosniff'
    r.headers['X-Frame-Options'] = 'DENY'
    r.headers['Cache-Control'] = 'no-store'
    r.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'"
    return r


@app.get('/health')
def health():
    return {'ok': True, 'version': (os.environ.get('RENDER_GIT_COMMIT') or 'local')[:7], 'random_answers': True}


@app.get('/')
def home():
    return send_from_directory(FRONTEND, 'index.html')


@app.get('/api/session')
def session_info():
    session.setdefault('csrf', secrets.token_hex(32))
    return jsonify(signed_in=bool(session.get('auth')), csrf=session['csrf'])


@app.post('/login')
def login():
    configured = os.environ.get('APP_PASSWORD', '')
    if len(configured) < 16:
        return jsonify(error='Set APP_PASSWORD to at least 16 characters on the server.'), 503
    payload = request.get_json(silent=True)
    supplied = payload.get('password', '') if isinstance(payload, dict) else ''
    if not isinstance(supplied, str) or not secrets.compare_digest(supplied.encode('utf-8'), configured.encode('utf-8')):
        return jsonify(error='Incorrect password.'), 401
    session.clear()
    session.update(auth=True, csrf=secrets.token_hex(32))
    return jsonify(ok=True)


@app.post('/logout')
@protect
def logout():
    session.clear()
    return {'ok': True}


@app.post('/api/import')
@protect
def import_link():
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        return jsonify(error='Expected a JSON object.'), 400
    try:
        return jsonify(rows=parse_prefill(d.get('prefill'), d.get('url')))
    except (ValueError, TypeError, AttributeError) as e:
        return jsonify(error=str(e)), 400


def log(message, completed=False):
    with lock:
        state['logs'].append({'time': datetime.now(timezone.utc).isoformat(), 'message': message})
        if completed:
            state['completed'] += 1


def work(urls, submit, confirmation):
    try:
        from runner import run_browser
        result = run_browser(urls, submit, confirmation, log, cancel)
        with lock:
            state['status'] = result
    except Exception as e:
        log(str(e))
        with lock:
            state['status'] = 'failed'


@app.post('/api/start')
@protect
def start():
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        return jsonify(error='Expected a JSON object.'), 400
    try:
        rows = validate_rows(d.get('rows'))
        build_url(d.get('url'), rows)
        # Recheck prefilled form identity even after answer edits.
        parse_prefill(d.get('prefill'), d.get('url'))
        count = d.get('count', 1)
        if type(count) is not int or not 1 <= count <= 100:
            raise ValueError('Response count must be 1–100.')
        if d.get('owned') is not True:
            raise ValueError('Confirm this is your disposable test form.')
        mode = d.get('mode')
        if mode not in ('preview', 'submit'):
            raise ValueError('Select preview or submit.')
        urls = [build_url(d.get('url'), pick_rows(rows)) for _ in range(count if mode == 'submit' else 1)]
        confirmation = d.get('confirmation', '').strip()
        if not 5 <= len(confirmation) <= 200:
            raise ValueError('Enter the exact confirmation message (5–200 characters).')
    except (ValueError, TypeError, AttributeError) as e:
        return jsonify(error=str(e)), 400
    with lock:
        if state['status'] == 'running':
            return jsonify(error='A job is already running.'), 409
        state.update(status='running', completed=0, total=count if mode == 'submit' else 1, logs=[])
        cancel.clear()
        threading.Thread(target=work, args=(urls, mode == 'submit', confirmation), daemon=True).start()
    return jsonify(ok=True)


@app.get('/api/status')
@protect
def status():
    with lock:
        return jsonify(state)


@app.post('/api/cancel')
@protect
def stop():
    cancel.set()
    return {'ok': True}


@app.get('/api/log.csv')
@protect
def export():
    f = io.StringIO()
    writer = csv.writer(f)
    writer.writerow(['UTC time', 'Event'])
    with lock:
        for row in state['logs']:
            writer.writerow([row['time'], row['message']])
    return Response(f.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=job-log.csv'})


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
