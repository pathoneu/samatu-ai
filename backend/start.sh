#!/usr/bin/env bash
# Start the Sąmatų AI backend using the project venv.
# Usage:  cd ~/samatu-ai/backend && ./start.sh
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
VENV_PY="$REPO_ROOT/venv/bin/python"

if [ ! -x "$VENV_PY" ]; then
  echo "ERROR: venv not found at $VENV_PY"
  echo "Create one with:  python3 -m venv $REPO_ROOT/venv"
  exit 1
fi

# Kill any stale uvicorn on port 8000 so --reload doesn't conflict.
if lsof -ti :8000 >/dev/null 2>&1; then
  echo "Stopping existing process on port 8000…"
  lsof -ti :8000 | xargs kill -9 2>/dev/null || true
  sleep 1
fi

cd "$SCRIPT_DIR"
exec "$VENV_PY" -m uvicorn main:app --reload --port 8000
