"""SQLite persistence.

Public functions are unchanged from the JSON-file version this replaced, so
nothing upstream had to change. If a state.json is present on first run its
contents are migrated in, then it is left alone as a backup.
"""

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import List

from . import config

_lock = threading.Lock()
_initialised = False

DB_FILE = os.environ.get("DB_FILE", os.path.join(config.DATA_DIR, "mappy.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS model_elements (
    id            TEXT PRIMARY KEY,
    stereotype    TEXT,
    name          TEXT,
    text          TEXT,
    verify_method TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS diagram_blocks (
    id          TEXT PRIMARY KEY,
    name        TEXT,
    description TEXT,
    is_root     INTEGER NOT NULL DEFAULT 0,
    position    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS diagram_connectors (
    id       TEXT PRIMARY KEY,
    source   TEXT,
    target   TEXT,
    kind     TEXT,
    label    TEXT,
    position INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS traces (
    id             TEXT PRIMARY KEY,
    requirement_id TEXT NOT NULL,
    block_id       TEXT NOT NULL,
    kind           TEXT NOT NULL,
    rationale      TEXT,
    UNIQUE (requirement_id, block_id, kind)
);

CREATE TABLE IF NOT EXISTS activity_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    message   TEXT NOT NULL,
    verbose   INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS eval_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp         TEXT NOT NULL,
    task              TEXT,
    model             TEXT,
    provider          TEXT,
    source            TEXT,
    llm_calls         INTEGER,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    total_tokens      INTEGER,
    cache_read_tokens INTEGER DEFAULT 0,
    cache_write_tokens INTEGER DEFAULT 0,
    duration_ms       REAL,
    items             INTEGER,
    first_pass_rate   REAL,
    success_rate      REAL,
    actual_cost_usd   REAL DEFAULT 0,
    cost_estimate_usd TEXT
);
"""

EVAL_COLUMNS = [
    "timestamp", "task", "model", "provider", "source", "llm_calls",
    "prompt_tokens", "completion_tokens", "total_tokens", "cache_read_tokens",
    "cache_write_tokens", "duration_ms", "items", "first_pass_rate",
    "success_rate", "actual_cost_usd",
]

NUMERIC_EVAL_COLUMNS = [
    "llm_calls", "prompt_tokens", "completion_tokens", "total_tokens",
    "cache_read_tokens", "cache_write_tokens", "duration_ms", "items",
    "first_pass_rate", "success_rate", "actual_cost_usd",
]


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE, timeout=10.0)
    conn.row_factory = sqlite3.Row
    # let readers run while a writer holds the file
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _ensure_db() -> None:
    global _initialised
    if _initialised:
        return
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with _connect() as conn:
        conn.executescript(SCHEMA)
    _initialised = True
    _migrate_from_json()


def _migrate_from_json() -> None:
    """One-off import of the old state.json, if one is sitting there and the
    database is still empty. The file is left in place as a backup."""
    legacy = getattr(config, "STATE_FILE", os.path.join(config.DATA_DIR, "state.json"))
    if not os.path.exists(legacy):
        return

    with _connect() as conn:
        already = conn.execute("SELECT COUNT(*) FROM eval_log").fetchone()[0]
        already += conn.execute("SELECT COUNT(*) FROM model_elements").fetchone()[0]
    if already:
        return

    try:
        with open(legacy) as f:
            state = json.load(f)
    except (OSError, json.JSONDecodeError):
        return

    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        for el in state.get("model_elements", []):
            conn.execute(
                "INSERT OR IGNORE INTO model_elements "
                "(id, stereotype, name, text, verify_method, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (el.get("id"), el.get("stereotype"), el.get("name"),
                 el.get("text"), el.get("verifyMethod"), now),
            )

        diagram = state.get("diagram", {})
        for i, b in enumerate(diagram.get("blocks", [])):
            conn.execute(
                "INSERT OR IGNORE INTO diagram_blocks "
                "(id, name, description, is_root, position) VALUES (?,?,?,?,?)",
                (b.get("id"), b.get("name"), b.get("description"),
                 1 if b.get("isRoot") else 0, i),
            )
        for i, c in enumerate(diagram.get("connectors", [])):
            conn.execute(
                "INSERT OR IGNORE INTO diagram_connectors "
                "(id, source, target, kind, label, position) VALUES (?,?,?,?,?,?)",
                (c.get("id"), c.get("source"), c.get("target"),
                 c.get("kind"), c.get("label"), i),
            )

        for t in state.get("traces", []):
            conn.execute(
                "INSERT OR IGNORE INTO traces "
                "(id, requirement_id, block_id, kind, rationale) VALUES (?,?,?,?,?)",
                (t.get("id"), t.get("requirement_id"), t.get("block_id"),
                 t.get("kind"), t.get("rationale")),
            )

        for e in state.get("activity_log", []):
            conn.execute(
                "INSERT INTO activity_log (timestamp, message, verbose) VALUES (?,?,?)",
                (e.get("timestamp", now), e.get("message", ""),
                 1 if e.get("verbose") else 0),
            )

        for r in state.get("eval_log", []):
            values = [r.get(c) for c in EVAL_COLUMNS]
            conn.execute(
                f"INSERT INTO eval_log ({','.join(EVAL_COLUMNS)}, cost_estimate_usd) "
                f"VALUES ({','.join('?' * len(EVAL_COLUMNS))}, ?)",
                (*values, json.dumps(r.get("cost_estimate_usd", {}))),
            )


def _element_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "stereotype": row["stereotype"],
        "name": row["name"],
        "text": row["text"],
        "verifyMethod": row["verify_method"],
    }


def get_state() -> dict:
    """Kept for the couple of callers that want everything at once."""
    return {
        "model_elements": list_model_elements(),
        "activity_log": get_activity_log(),
        "diagram": get_diagram(),
        "eval_log": get_eval_log(),
        "traces": get_traces(),
    }


def list_model_elements() -> List[dict]:
    with _lock:
        _ensure_db()
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM model_elements ORDER BY created_at, rowid"
            ).fetchall()
    return [_element_row(r) for r in rows]


def add_model_elements(elements: List[dict]) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        _ensure_db()
        with _connect() as conn:
            for el in elements:
                conn.execute(
                    "INSERT OR REPLACE INTO model_elements "
                    "(id, stereotype, name, text, verify_method, created_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (el.get("id"), el.get("stereotype"), el.get("name"),
                     el.get("text"), el.get("verifyMethod"), now),
                )
    return {"model_elements": list_model_elements()}


def delete_model_element(element_id: str) -> dict:
    with _lock:
        _ensure_db()
        with _connect() as conn:
            conn.execute("DELETE FROM model_elements WHERE id = ?", (element_id,))
            # a trace pointing at a deleted requirement is dead weight
            conn.execute("DELETE FROM traces WHERE requirement_id = ?", (element_id,))
    return {"model_elements": list_model_elements()}


def get_diagram() -> dict:
    with _lock:
        _ensure_db()
        with _connect() as conn:
            blocks = conn.execute(
                "SELECT * FROM diagram_blocks ORDER BY position"
            ).fetchall()
            connectors = conn.execute(
                "SELECT * FROM diagram_connectors ORDER BY position"
            ).fetchall()
    return {
        "blocks": [
            {"id": b["id"], "name": b["name"], "description": b["description"],
             "isRoot": bool(b["is_root"])}
            for b in blocks
        ],
        "connectors": [
            {"id": c["id"], "source": c["source"], "target": c["target"],
             "kind": c["kind"], "label": c["label"]}
            for c in connectors
        ],
    }


def save_diagram(blocks: List[dict], connectors: List[dict]) -> dict:
    """A saved diagram replaces the previous one, so this is a swap rather
    than an append."""
    with _lock:
        _ensure_db()
        with _connect() as conn:
            conn.execute("DELETE FROM diagram_blocks")
            conn.execute("DELETE FROM diagram_connectors")
            for i, b in enumerate(blocks):
                conn.execute(
                    "INSERT INTO diagram_blocks "
                    "(id, name, description, is_root, position) VALUES (?,?,?,?,?)",
                    (b.get("id"), b.get("name"), b.get("description"),
                     1 if b.get("isRoot") else 0, i),
                )
            for i, c in enumerate(connectors):
                conn.execute(
                    "INSERT INTO diagram_connectors "
                    "(id, source, target, kind, label, position) VALUES (?,?,?,?,?,?)",
                    (c.get("id"), c.get("source"), c.get("target"),
                     c.get("kind"), c.get("label"), i),
                )
            # blocks the new diagram no longer contains cannot be traced to
            conn.execute(
                "DELETE FROM traces WHERE block_id NOT IN "
                "(SELECT id FROM diagram_blocks)"
            )
    return get_diagram()


def clear_diagram() -> dict:
    with _lock:
        _ensure_db()
        with _connect() as conn:
            conn.execute("DELETE FROM diagram_blocks")
            conn.execute("DELETE FROM diagram_connectors")
            conn.execute("DELETE FROM traces")
    return get_diagram()


def get_traces() -> List[dict]:
    with _lock:
        _ensure_db()
        with _connect() as conn:
            rows = conn.execute("SELECT * FROM traces ORDER BY rowid").fetchall()
    return [
        {"id": r["id"], "requirement_id": r["requirement_id"],
         "block_id": r["block_id"], "kind": r["kind"], "rationale": r["rationale"]}
        for r in rows
    ]


def add_traces(traces: List[dict]) -> List[dict]:
    with _lock:
        _ensure_db()
        with _connect() as conn:
            for t in traces:
                # the unique index makes re-adding the same link a no-op
                conn.execute(
                    "INSERT OR IGNORE INTO traces "
                    "(id, requirement_id, block_id, kind, rationale) VALUES (?,?,?,?,?)",
                    (t.get("id"), t.get("requirement_id"), t.get("block_id"),
                     t.get("kind"), t.get("rationale")),
                )
    return get_traces()


def delete_trace(trace_id: str) -> List[dict]:
    with _lock:
        _ensure_db()
        with _connect() as conn:
            conn.execute("DELETE FROM traces WHERE id = ?", (trace_id,))
    return get_traces()


def get_activity_log() -> List[dict]:
    with _lock:
        _ensure_db()
        with _connect() as conn:
            rows = conn.execute(
                "SELECT timestamp, message, verbose FROM activity_log ORDER BY id"
            ).fetchall()
    return [
        {"timestamp": r["timestamp"], "message": r["message"],
         "verbose": bool(r["verbose"])}
        for r in rows
    ]


def log_event(message: str, verbose: bool = False) -> dict:
    with _lock:
        _ensure_db()
        with _connect() as conn:
            conn.execute(
                "INSERT INTO activity_log (timestamp, message, verbose) VALUES (?,?,?)",
                (datetime.now(timezone.utc).isoformat(), message, 1 if verbose else 0),
            )
    return {"message": message}


def get_eval_log() -> List[dict]:
    with _lock:
        _ensure_db()
        with _connect() as conn:
            rows = conn.execute("SELECT * FROM eval_log ORDER BY id").fetchall()
    records = []
    for r in rows:
        record = {c: r[c] for c in EVAL_COLUMNS}
        # records written before a column existed read back as NULL, and
        # callers sum these -- dict.get with a default does not help, the key
        # is present and the value is None
        for c in NUMERIC_EVAL_COLUMNS:
            if record[c] is None:
                record[c] = 0
        # records predating the provider column are all local runs, since
        # the hosted provider did not exist when they were written
        if record["provider"] is None:
            record["provider"] = "ollama"
        record["cost_estimate_usd"] = json.loads(r["cost_estimate_usd"] or "{}")
        records.append(record)
    return records


def add_eval_record(record: dict) -> dict:
    with _lock:
        _ensure_db()
        with _connect() as conn:
            conn.execute(
                f"INSERT INTO eval_log ({','.join(EVAL_COLUMNS)}, cost_estimate_usd) "
                f"VALUES ({','.join('?' * len(EVAL_COLUMNS))}, ?)",
                (*[record.get(c) for c in EVAL_COLUMNS],
                 json.dumps(record.get("cost_estimate_usd", {}))),
            )
    return record
