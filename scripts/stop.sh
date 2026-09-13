#!/usr/bin/env bash
#
# Stop the Mini-MAPPy dev servers.
#
set -uo pipefail

stopped=0
for port in 8000 5173; do
  pids="$(lsof -ti ":$port" 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    echo "$pids" | xargs kill 2>/dev/null || true
    printf 'stopped :%s\n' "$port"
    stopped=1
  fi
done

[ "$stopped" -eq 0 ] && echo "nothing running on :8000 or :5173"
exit 0
