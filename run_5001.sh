#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# venv si besoin
if [ ! -d venv ]; then
  python -m venv venv
fi

# activer venv (Git Bash Windows puis Linux)
if [ -f "venv/Scripts/activate" ]; then
  source venv/Scripts/activate
else
  source venv/bin/activate
fi

# deps
pip install -r requirements.txt
pip install Flask-Migrate >/dev/null 2>&1 || true

# Flask env
export FLASK_APP=app.py
export FLASK_DEBUG=1

echo "== Routes =="
flask --app app.py routes

echo "== Running on http://127.0.0.1:5001 =="
flask run -p 5001
