#!/usr/bin/env bash
set -euo pipefail

# ===== À ADAPTER SI BESOIN =====
SRC="/c/dev/galerie-flask"   # ton projet côté Git Bash (C:\dev\galerie-flask)
USB="/e"                     # ta clé USB (E:\ = /e)
NAME="galerie-flask-$(date +%Y-%m-%d-%H%M).tar.gz"
# ===============================

OUT="$USB/$NAME"

echo "🧩 Création archive (sans venv/.git/__pycache__/*.pyc) → $OUT"
tar -czf "$OUT" \
  --exclude='venv' \
  --exclude='.git' \
  --exclude='*/__pycache__' \
  --exclude='*.pyc' \
  -C "$SRC" .

echo "✅ Archive prête: $OUT"
