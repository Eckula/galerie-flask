#!/usr/bin/env bash
set -euo pipefail

# ===== À ADAPTER =====
ARCHIVE="/e/galerie-flask-*.tar.gz"   # chemin vers l’archive sur la clé (E:\ = /e)
DEST="/c/dev/galerie-flask"           # dossier où vit ton projet sur le PC Privé
# =====================

# 0) Choisir la dernière archive si * correspond
LATEST_ARCHIVE="$(ls -t $ARCHIVE | head -n1)"
[ -f "$LATEST_ARCHIVE" ] || { echo "❌ Archive introuvable: $ARCHIVE"; exit 1; }
echo "📦 Archive détectée: $LATEST_ARCHIVE"

# 1) Sauvegarder l'ancien dossier (pour préserver DB/.env si besoin)
if [ -d "$DEST" ]; then
  BACKUP="${DEST}.bak-$(date +%Y-%m-%d-%H%M)"
  echo "🗄  Backup de l'ancienne version → $BACKUP"
  mv "$DEST" "$BACKUP"
fi

# 2) Extraire dans DEST
mkdir -p "$DEST"
echo "📤 Extraction dans: $DEST"
tar -xzf "$LATEST_ARCHIVE" -C "$DEST"

# 3) Si une ancienne DB/.env existent dans le backup et que tu veux les garder, remets-les
if [ -n "${BACKUP-}" ]; then
  if [ -f "$BACKUP/gallery.db" ] && [ ! -f "$DEST/gallery.db" ]; then
    echo "💾 Préserve l'ancienne DB"
    cp "$BACKUP/gallery.db" "$DEST/gallery.db"
  fi
  if [ -f "$BACKUP/.env" ] && [ ! -f "$DEST/.env" ]; then
    echo "🔐 Préserve l'ancien .env"
    cp "$BACKUP/.env" "$DEST/.env"
  fi
fi

# 4) Créer/activer le venv + installer deps
echo "🐍 Préparation venv + dépendances"
cd "$DEST"
if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
$PY -m venv venv

# Activer (Git Bash Windows ou Linux)
if [ -f "venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
else
  # shellcheck disable=SC1091
  source venv/Scripts/activate
fi

pip install --upgrade pip
pip install -r requirements.txt

# 5) Migrer la DB si absente et migrations présentes
export FLASK_APP=app.py
if [ ! -f gallery.db ] && [ -d migrations ]; then
  echo "🛠  gallery.db absente → flask db upgrade"
  if ! flask db upgrade; then
    echo "⚠️  'flask db upgrade' a échoué (vérifie FLASK_APP/migrations)."
  fi
fi

echo "✅ Projet mis à jour dans: $DEST"
echo "▶️  Pour lancer maintenant:"
echo "    flask run"
