#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

export PYTHONPATH="$ROOT/backend"
export PATH="${HOME}/.local/node/bin:${PATH}"

if [[ ! -d frontend/dist ]]; then
  echo "Baue Frontend…"
  (cd frontend && npm install && npm run build)
fi

HOST="$(PYTHONPATH="$ROOT/backend" python -c 'from app.config import load_config; print(load_config().host)')"
PORT="$(PYTHONPATH="$ROOT/backend" python -c 'from app.config import load_config; print(load_config().port)')"

exec uvicorn app.main:app --host "$HOST" --port "$PORT"
