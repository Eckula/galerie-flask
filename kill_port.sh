#!/usr/bin/env bash
set -euo pipefail
PORT="${1:-5000}"
PIDS=$(netstat -ano | grep ":$PORT" | awk '{print $5}' | grep -E '^[0-9]+$' | sort -u || true)
if [ -z "${PIDS}" ]; then
  echo "Aucun process sur le port ${PORT}."
  exit 0
fi
for pid in $PIDS; do
  echo "Killing PID $pid on port ${PORT}"
  cmd.exe /c taskkill /PID "$pid" /F >/dev/null 2>&1 || true
done
echo "✅ Port ${PORT} libéré."
