# Verification — 2026-10-30

Passed locally:

- Python source compilation and JavaScript syntax check with Node.
- 11 parser/API unit tests: checkbox round-trip, invalid URLs, mismatched form IDs, empty prefilled links, duplicate IDs, login/auth, CSRF, import, invalid counts/mode/ownership, job overlap, page rendering and CSV export.
- Real headless Chromium UI checks against the locally served Flask app: sign-in, import, checkbox editor, 390px mobile viewport overflow check, ownership validation, and no JavaScript errors.
- Real headless Chromium runner checks with every request intercepted and fulfilled in memory: two sections, final POST acknowledgement, success confirmation/counting, and blocking a form without TEST ONLY in its title. No external Google Forms request was made by these fixtures.

Not verified:

- Live Google Forms submission, optional-field completeness, advanced question types, Google layout variations or custom form branching.
- Render deployment, Docker image build on Render, available memory for Chromium, or sustained batch throughput.

A first browser download mirror returned a corrupted archive; Playwright's fallback successfully installed Chromium and the browser checks then passed.

Reproduce from the project folder:

```sh
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m unittest discover -s tests -v
python tests/browser_smoke.py
node --check static/app.js
```

The browser checks use local/mocked content only. Node is optional and is only needed for the syntax check, not for running the app.
