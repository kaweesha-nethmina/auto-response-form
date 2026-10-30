#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
read -r -s -p 'Workspace password (at least 16 characters): ' APP_PASSWORD
export APP_PASSWORD
printf '\nOpen http://127.0.0.1:5000 in your browser.\n'
.venv/bin/python app.py
