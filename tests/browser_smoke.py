"""Optional integration checks with local/mocked pages. Never contacts Google Forms."""
import os
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server
from app import app
from core import build_url
import runner

URL = 'https://docs.google.com/forms/d/e/example123/viewform'

def main():
    os.environ['APP_PASSWORD'] = 'browser-test-password-123'
    server = make_server('127.0.0.1', 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f'http://127.0.0.1:{server.server_port}'
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(origin)
            page.locator('#password').fill(os.environ['APP_PASSWORD'])
            page.locator('#login').click()
            page.locator('#url').wait_for()
            page.locator('#url').fill(URL)
            page.locator('#prefill').fill(URL + '?entry.123=Maps&entry.123=Social&entry.456=Good')
            page.locator('#import').click()
            page.locator('.entry').nth(1).wait_for()
            assert page.locator('.entry').count() == 2
            assert page.locator('.kind').first.input_value() == 'multi'
            page.locator('.question').first.fill('Methods used')
            assert page.locator('.answer').first.input_value() == 'Maps\nSocial'
            page.set_viewport_size({'width': 390, 'height': 844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.locator('#preview').click()
            page.get_by_role('alert').filter(has_text='Confirm this is your disposable test form.').wait_for()
            assert not errors, errors
            browser.close()
        print('PASS: browser login, import, checkbox editor, mobile overflow, ownership error, no JavaScript errors')
    finally:
        server.shutdown()

    # The runner sees a Google-shaped URL, but every request is fulfilled in memory.
    for title, expected in [('TEST ONLY fixture', 'finished'), ('Real survey', 'blocked')]:
        with sync_playwright() as p:
            real = p.chromium.launch(headless=True)
            def route_handler(route):
                request = route.request
                if request.method == 'POST':
                    html = '<p>Your response has been recorded.</p>'
                elif 'section=2' in request.url:
                    html = f'<h1>{title}</h1><form method="post" action="/formResponse"><button>Submit</button></form>'
                else:
                    html = f'<h1>{title}</h1><button onclick="location.href=\'?section=2\'">Next</button>'
                route.fulfill(status=200, content_type='text/html', body=html)
            class BrowserProxy:
                def new_context(self, **kw):
                    c = real.new_context(**kw)
                    c.route('**/*', route_handler)
                    return c
                def close(self):
                    pass
            class ChromiumProxy:
                def launch(self, **kw):
                    return BrowserProxy()
            class PlaywrightProxy:
                chromium = ChromiumProxy()
            @contextmanager
            def fake_playwright():
                yield PlaywrightProxy()
            logs = []
            def log(s, completed=False):
                logs.append((s, completed))
            try:
                with patch.object(runner, 'sync_playwright', fake_playwright):
                    result = runner.run_browser([build_url(URL, [{'id':'entry.123','answers':['Maps']}])], True, 'Your response has been recorded.', log, threading.Event())
                assert expected == 'finished' and result == 'finished'
                assert sum(done for _, done in logs) == 1
            except RuntimeError as e:
                assert expected == 'blocked' and 'TEST ONLY' in str(e), str(e)
            finally:
                real.close()
    print('PASS: two-section runner, POST acknowledgement, confirmation counting, test-title enforcement (mocked network only)')

if __name__ == '__main__':
    main()
