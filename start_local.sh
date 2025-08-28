#!/usr/bin/env bash
# start_local.sh — lancer localement via Git Bash
set -e
export FLASK_APP=app.py
export FLASK_ENV=production

flask db upgrade || true
waitress-serve --listen=127.0.0.1:5000 app:app
