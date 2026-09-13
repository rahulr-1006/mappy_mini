#!/usr/bin/env bash
#
# Start Mini-MAPPy (backend + frontend) and wait until both actually answer.
#
# The waiting is the point: the frontend fetches its data once on mount, so if
# the API isn't up yet the page loads with "Load failed" and never retries.
#
#   ./scripts/dev.sh          start both, then open the browser
#   ./scripts/dev.sh --no-open   start both, don't open a browser
#
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PORT=8000
FRONTEND_PORT=5173
BACKEND_LOG=/tmp/mappy-backend.log
FRONTEND_LOG=/tmp/mappy-frontend.log
OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
MODEL="llama3.1:8b"

say()  { printf '\033[1;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m warn\033[0m %s\n' "$1"; }
die()  { printf '\033[1;31mfail\033[0m %s\n' "$1" >&2; exit 1; }

# --- preflight ---------------------------------------------------------------

command -v python3 >/dev/null || die "python3 not found"
command -v npm     >/dev/null || die "npm not found"

if ! curl -s -m 3 "$OLLAMA_HOST/api/tags" >/dev/null 2>&1; then
  warn "Ollama is not reachable at $OLLAMA_HOST"
  warn "start it with:  ollama serve   (or: brew services start ollama)"
  warn "continuing -- hosted Claude models will still work if a key is set"
elif ! curl -s -m 3 "$OLLAMA_HOST/api/tags" | grep -q "$MODEL"; then
  warn "$MODEL is not pulled. Local generation will fail until you run:"
  warn "  ollama pull $MODEL"
fi

# --- first-run setup ---------------------------------------------------------

if [ ! -d "$REPO/backend/venv" ]; then
  say "creating backend venv (first run)"
  python3 -m venv "$REPO/backend/venv" || die "could not create venv"
  "$REPO/backend/venv/bin/pip" install -q -r "$REPO/backend/requirements.txt" \
    || die "pip install failed"
fi

if [ ! -d "$REPO/frontend/node_modules" ]; then
  say "installing frontend dependencies (first run)"
  (cd "$REPO/frontend" && npm install --silent) || die "npm install failed"
fi

# --- free the ports ----------------------------------------------------------

for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  pids="$(lsof -ti ":$port" 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    say "stopping process already on :$port"
    echo "$pids" | xargs kill 2>/dev/null || true
  fi
done
sleep 1

# --- backend -----------------------------------------------------------------

say "starting backend on :$BACKEND_PORT"
(
  cd "$REPO/backend" || exit 1
  # shellcheck disable=SC1091
  source venv/bin/activate
  nohup uvicorn app.main:app --reload --port "$BACKEND_PORT" > "$BACKEND_LOG" 2>&1 &
)

for _ in $(seq 1 40); do
  curl -s -m 2 "http://localhost:$BACKEND_PORT/health" >/dev/null 2>&1 && break
  sleep 1
done
curl -s -m 2 "http://localhost:$BACKEND_PORT/health" >/dev/null 2>&1 \
  || die "backend never came up -- see $BACKEND_LOG"
say "backend ready"

# --- frontend ----------------------------------------------------------------

say "starting frontend on :$FRONTEND_PORT"
(
  cd "$REPO/frontend" || exit 1
  nohup npm run dev > "$FRONTEND_LOG" 2>&1 &
)

for _ in $(seq 1 40); do
  curl -s -m 2 -o /dev/null "http://localhost:$FRONTEND_PORT" 2>/dev/null && break
  sleep 1
done
curl -s -m 2 -o /dev/null "http://localhost:$FRONTEND_PORT" 2>/dev/null \
  || die "frontend never came up -- see $FRONTEND_LOG"
say "frontend ready"

# --- done --------------------------------------------------------------------

echo
echo "  app       http://localhost:$FRONTEND_PORT"
echo "  diagram   http://localhost:$FRONTEND_PORT/diagram-view"
echo "  api docs  http://localhost:$BACKEND_PORT/docs"
echo
echo "  logs      tail -f $BACKEND_LOG"
echo "            tail -f $FRONTEND_LOG"
echo "  stop      ./scripts/stop.sh"
echo

if [ "${1:-}" != "--no-open" ] && command -v open >/dev/null; then
  open "http://localhost:$FRONTEND_PORT"
fi
