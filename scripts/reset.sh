#!/usr/bin/env bash
#
# Put the app back to a clean state for a demo take.
#
# Clears what an audience sees as leftovers from the last run: the chat
# thread, the kept requirements, the saved diagram, the trace links, the
# activity log, and the retrieval index built over them.
#
# Keeps the evaluation history by default, because the local-vs-hosted
# table in the Evaluations tab is built from it and re-running the suite
# costs six real generations.
#
#   ./scripts/reset.sh              clear the run, leave documents loaded
#   ./scripts/reset.sh --wipe-docs  also unload the knowledge base
#   ./scripts/reset.sh --everything also drop the evaluation history
#
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB="${DB_FILE:-$REPO/backend/data/mappy.db}"
BACKEND_PORT=8000

WIPE_DOCS=0
WIPE_EVALS=0

for arg in "$@"; do
  case "$arg" in
    --wipe-docs)  WIPE_DOCS=1 ;;
    --everything) WIPE_DOCS=1; WIPE_EVALS=1 ;;
    -h|--help)    sed -n '3,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)            printf '\033[1;31mfail\033[0m unknown option: %s\n' "$arg" >&2; exit 1 ;;
  esac
done

say() { printf '\033[1;34m==>\033[0m %s\n' "$1"; }

[ -f "$DB" ] || { say "no database at $DB — nothing to clear"; exit 0; }

# The backend holds the database open in WAL mode, which allows this
# second writer. Rows are deleted rather than the file being removed so a
# running server does not end up pointing at a deleted inode.
sqlite3 "$DB" <<SQL
BEGIN;
DELETE FROM chat_messages;
DELETE FROM model_elements;
DELETE FROM diagram_blocks;
DELETE FROM diagram_connectors;
DELETE FROM traces;
DELETE FROM activity_log;
DELETE FROM rag_chunks WHERE source_kind = 'model';
$([ "$WIPE_DOCS" = 1 ] && echo "DELETE FROM documents; DELETE FROM rag_chunks WHERE source_kind = 'document';")
$([ "$WIPE_EVALS" = 1 ] && echo "DELETE FROM eval_log;")
COMMIT;
SQL

if [ $? -ne 0 ]; then
  printf '\033[1;31mfail\033[0m could not write to %s\n' "$DB" >&2
  exit 1
fi

say "cleared the chat thread, requirements, diagram, traces, and activity log"
[ "$WIPE_DOCS" = 1 ]  && say "unloaded the knowledge base"
[ "$WIPE_EVALS" = 1 ] && say "dropped the evaluation history"
[ "$WIPE_EVALS" = 1 ] || say "kept the evaluation history (--everything drops it)"

if curl -s -m 2 "http://localhost:$BACKEND_PORT/health" >/dev/null 2>&1; then
  remaining=$(curl -s -m 5 "http://localhost:$BACKEND_PORT/documents/index" 2>/dev/null || echo '{}')
  say "index now: $remaining"
  echo
  say "reload the browser tab — the page reads its state once on mount"
else
  say "backend is not running; start it with ./scripts/dev.sh"
fi
