# FormDesk — Google Forms test workspace

A Python web app that replaces repeated terminal commands with a password-protected browser interface. Paste your published form link and prefilled link, import fields, edit question labels and answers, choose a count, then preview or submit a test batch. Includes live job events, cancellation, CSV logs, configuration save/load, Docker, and a Render Blueprint.

## Important scope

Automated submissions are for disposable forms you own. The runner verifies that the respondent-visible title contains **TEST ONLY** before proceeding. Keep generated test records separate from real participant responses. The app does not invent answers. By default, Count repeats the answer set displayed in the editor. For test data that varies, choose **Vary per response** on a question and list the options you want (one per line); each response picks one of them. This still only runs on a TEST ONLY copy, and its responses are test data, not customer feedback. For a different answer set, edit or load another configuration and start a new batch.

The attachment used to build this project contained requirements and links, not Python source. This is a fresh implementation. No submission to the supplied academic questionnaire was made during development.

## Split deploy: backend on Render, frontend on Vercel

1. Deploy the backend on Render as described below (Blueprint with `render.yaml`). Note its URL, e.g. `formdesk-qa.onrender.com`.
2. In `frontend/vercel.json`, replace every `RENDER_SERVICE_URL` with that hostname (no `https://`, no trailing slash).
3. In Vercel, import the same repo. Framework preset: **Other**. Set **Root Directory** to `frontend` and leave the build command empty.
4. Open the Vercel URL. The browser only talks to Vercel; `/api/*`, `/login` and `/logout` are proxied to Render, so login cookies stay same-origin and no CORS setup is needed.

The Render URL also serves the full app by itself, which is handy for debugging.

## Deploy on Render

1. Extract the ZIP. Create a private GitHub repository and upload the **contents of the FormDesk folder** so Dockerfile and render.yaml are at its root. Never commit your passwords, private prefilled links, or real responses.
2. In Render, create a **Blueprint** and connect this repository. Select `render.yaml`.
3. Set `APP_PASSWORD` to a unique password of at least 16 characters. The Blueprint generates `SECRET_KEY` for signed login cookies. Keep that key stable across deployments.
4. Review the service plan and deploy. The included Blueprint selects Starter; Render may charge for this service. Review current pricing in your own account.
5. When the deploy succeeds, open its Render URL and sign in. All routine work now happens in the browser; no repeated terminal commands.

Alternative: create a Web Service manually, select Docker, set APP_PASSWORD and SECRET_KEY (a long random value), and set the health check path to `/health`. Do not override the Docker start command. It binds to Render's PORT environment variable.

**Use exactly one instance and one Gunicorn worker.** Job state and cancellation live in memory. Gunicorn threads serve progress requests while a browser thread runs. Restarting, redeploying, or suspending the service interrupts work and erases its logs. Download the log before a restart. This is a single-owner tool, not a durable distributed queue. Avoid free-tier sleep for batches. Chromium may require a higher-memory service if your form is large; this has not been benchmarked on Render.

## Prepare a form once

1. Duplicate your form. Rename its respondent-visible title to include `TEST ONLY`.
2. Publish it for respondents. This release supports publicly accessible English-language forms without login, file uploads, or CAPTCHA. Configure English button labels (`Next`, `Submit`). Do not enable one-response-per-account restrictions.
3. Choose **Get pre-filled link** in Google Forms. Fill every question you want included, including optional fields and later sections; copy the resulting link. The app only imports fields present in this link. It cannot infer omitted questions from pasted descriptions.
4. Copy the published `/forms/d/e/.../viewform` responder URL from the **same copy**. Expand shortened `forms.gle` links in a browser first.
5. If you use a custom confirmation message, copy it exactly from the form's settings.

## Daily workflow

1. Sign in and paste both links. Click **Import answer fields**.
2. Optionally paste your full question list into the notes box as a reference.
3. Add a question label to each imported ID. Labels are for you; entry IDs are how Google maps answers. Do not guess an ID. Missing fields require a fresh prefilled link or a known ID from it.
4. For checkbox questions, choose the checkbox answer format and put each selected option on its own line. For paragraphs or single-choice questions use one answer. The importer preserves repeated entry parameters.
5. Match options exactly. Branching answers determine which sections Google displays. A checkbox choice such as “None” should not be combined with other choices.
6. Run **Preview without submitting**. This opens the form in headless Chromium and navigates to the final page. It reports navigation failures, but does not prove every optional question was filled or every intended branch was visited. It also does not validate required fields on the final page because it does not press Submit.
7. Choose count **1**, confirm ownership, and click **Submit test batch**. Check the actual response in Google Forms, including optional fields and sections, before running a larger batch (maximum 100).
8. Watch progress. The runner waits three seconds between responses, uses a new browser context for each, and only counts responses after a POST acknowledgement plus your confirmation text on the result page.
9. Download the job log. Save configuration JSON to reuse your links, notes, labels, answers, count, and confirmation message. Passwords are not exported. Configuration files contain your answers; store them privately.

**Stopping** takes effect between browser steps. A pending navigation can take up to 45 seconds; stopping cannot retract a submitted response. Any error stops the batch. There are no automatic submission retries: if Google accepted a response but the confirmation was missed, the status is uncertain. Check Google Forms before rerunning, and submit only the remaining count. The confirmed count may undercount this uncertain last response.

## Run locally without typing commands repeatedly

Install Python 3.12 first.

- **Windows:** double-click `start_windows.bat`. On first launch it installs dependencies and Chromium, prompts for a workspace password, and opens the local URL. If the page opens before the server is ready, refresh it.
- **macOS / Linux:** run `bash start_mac_linux.sh` once to launch; subsequent form tests take place in the browser. Some Linux systems need OS libraries; use Docker or install Playwright's documented system dependencies if Chromium cannot start.
- **Docker:** build with `docker build -t formdesk .`, then run `docker run --rm -p 10000:10000 -e APP_PASSWORD -e SECRET_KEY formdesk` after setting those environment variables in your shell. Open http://localhost:10000.

## Files

- `app.py`: login, CSRF-protected API, background job and CSV export.
- `core.py`: published URL validation, prefilled entry parsing, answer validation.
- `runner.py`: Playwright multi-section navigation and confirmation checks.
- `templates/`, `static/`: responsive interface; no external frontend dependencies.
- `Dockerfile`, `render.yaml`: container and Render service configuration.
- `tests/test_app.py`: parser and API regression checks (no live submissions).

Run checks after installing requirements: `python -m unittest discover -s tests -v`.

## Limits and troubleshooting

- **No IDs found:** use Get pre-filled link, not just the published link.
- **Form mismatch:** a duplicate has different IDs; generate a prefilled link from that copy.
- **Title rejected:** change the actual title visible to respondents, not only the Drive filename.
- **Validation error / section did not advance:** inspect required questions, section routing, answer spelling, and missing fields. Run a single response first.
- **Confirmation uncertain:** inspect Google Forms Responses before retrying. Set the exact custom confirmation text.
- **No Next/Submit:** login, language, access, CAPTCHA, or Google's layout may be blocking the runner. No protection bypass is implemented.
- **Date/time fields, grids, quizzes, and specialized validation:** URL parameters are preserved when supported by the parser, but these question types have not been live-tested. Verify individually. File uploads and login-protected forms are unsupported.
- Optional questions omitted from a prefilled link remain omitted. The app cannot promise universal question coverage. Browser automation depends on Google's current page layout.
- Access uses a shared-owner password and signed sessions, not individual user accounts. Restrict deployment access as appropriate. There is no password recovery, persistent job queue, or cross-instance coordination.

## Verification status

Local checks and outcomes are recorded in `VALIDATION.md`. The Render deployment and live Google Forms submissions require your test copy and have not been run on your behalf.
