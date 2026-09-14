"""SQLite persistence. Every read and write goes through here."""

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import List, Optional

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

CREATE TABLE IF NOT EXISTS chat_messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    role         TEXT NOT NULL,
    content      TEXT NOT NULL,
    requirements TEXT,
    sources      TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
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

CREATE TABLE IF NOT EXISTS documents (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    origin     TEXT NOT NULL DEFAULT 'upload',
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- One row per retrievable passage, from either knowledge source. The
-- embedding is a packed float32 blob; it is null when the chunk was
-- indexed while the embedding model was unreachable, and retrieval falls
-- back to lexical scoring for those.
CREATE TABLE IF NOT EXISTS rag_chunks (
    id          TEXT PRIMARY KEY,
    source_kind TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    source_name TEXT NOT NULL,
    text        TEXT NOT NULL,
    embedding   BLOB,
    position    INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS rag_chunks_source
    ON rag_chunks (source_kind, source_id);

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
        columns = {r["name"] for r in conn.execute("PRAGMA table_info(chat_messages)")}
        if "sources" not in columns:
            conn.execute("ALTER TABLE chat_messages ADD COLUMN sources TEXT")
    _initialised = True


def _element_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "stereotype": row["stereotype"],
        "name": row["name"],
        "text": row["text"],
        "verifyMethod": row["verify_method"],
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


def update_model_element(element_id: str, fields: dict) -> Optional[dict]:
    columns = {
        "stereotype": "stereotype",
        "name": "name",
        "text": "text",
        "verifyMethod": "verify_method",
    }
    updates = {columns[k]: v for k, v in fields.items() if k in columns}
    if not updates:
        return get_model_element(element_id)

    assignments = ", ".join(f"{c} = ?" for c in updates)
    with _lock:
        _ensure_db()
        with _connect() as conn:
            cur = conn.execute(
                f"UPDATE model_elements SET {assignments} WHERE id = ?",
                (*updates.values(), element_id),
            )
            if cur.rowcount == 0:
                return None
    return get_model_element(element_id)


def get_model_element(element_id: str) -> Optional[dict]:
    with _lock:
        _ensure_db()
        with _connect() as conn:
            row = conn.execute(
                "SELECT * FROM model_elements WHERE id = ?", (element_id,)
            ).fetchone()
    return _element_row(row) if row else None


def delete_model_element(element_id: str) -> dict:
    with _lock:
        _ensure_db()
        with _connect() as conn:
            conn.execute("DELETE FROM model_elements WHERE id = ?", (element_id,))
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
            row = conn.execute(
                "SELECT value FROM meta WHERE key = 'diagram_prompt'"
            ).fetchone()
            prompt = row["value"] if row else ""
    return {
        "prompt": prompt,
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


def save_diagram(blocks: List[dict], connectors: List[dict],
                 prompt: str | None = None) -> dict:
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
            conn.execute(
                "DELETE FROM traces WHERE block_id NOT IN "
                "(SELECT id FROM diagram_blocks)"
            )
            if prompt is not None:
                conn.execute(
                    "INSERT OR REPLACE INTO meta (key, value) VALUES (?,?)",
                    ("diagram_prompt", prompt),
                )
    return get_diagram()


def clear_diagram() -> dict:
    with _lock:
        _ensure_db()
        with _connect() as conn:
            conn.execute("DELETE FROM diagram_blocks")
            conn.execute("DELETE FROM diagram_connectors")
            conn.execute("DELETE FROM traces")
            conn.execute("DELETE FROM meta WHERE key = 'diagram_prompt'")
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


def get_chat_messages() -> List[dict]:
    with _lock:
        _ensure_db()
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM chat_messages ORDER BY id"
            ).fetchall()
    return [
        {
            "id": r["id"],
            "role": r["role"],
            "content": r["content"],
            "requirements": json.loads(r["requirements"] or "[]"),
            "sources": json.loads(r["sources"] or "[]"),
            "timestamp": r["created_at"],
        }
        for r in rows
    ]


def add_chat_message(
    role: str,
    content: str,
    requirements: List[dict] | None = None,
    sources: List[dict] | None = None,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        _ensure_db()
        with _connect() as conn:
            cur = conn.execute(
                "INSERT INTO chat_messages "
                "(role, content, requirements, sources, created_at) VALUES (?,?,?,?,?)",
                (role, content, json.dumps(requirements or []), json.dumps(sources or []), now),
            )
            new_id = cur.lastrowid
    return {
        "id": new_id,
        "role": role,
        "content": content,
        "requirements": requirements or [],
        "sources": sources or [],
        "timestamp": now,
    }


def clear_chat() -> List[dict]:
    with _lock:
        _ensure_db()
        with _connect() as conn:
            conn.execute("DELETE FROM chat_messages")
    return []


def get_eval_log() -> List[dict]:
    with _lock:
        _ensure_db()
        with _connect() as conn:
            rows = conn.execute("SELECT * FROM eval_log ORDER BY id").fetchall()
    records = []
    for r in rows:
        record = {c: r[c] for c in EVAL_COLUMNS}
        for c in NUMERIC_EVAL_COLUMNS:
            if record[c] is None:
                record[c] = 0
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


def _document_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "origin": row["origin"],
        "content": row["content"],
        "created_at": row["created_at"],
    }


def list_documents(include_content: bool = False) -> List[dict]:
    with _lock:
        _ensure_db()
        with _connect() as conn:
            rows = conn.execute(
                "SELECT d.*, "
                "(SELECT COUNT(*) FROM rag_chunks c "
                " WHERE c.source_kind='document' AND c.source_id=d.id) AS chunks "
                "FROM documents d ORDER BY d.created_at"
            ).fetchall()
    out = []
    for r in rows:
        doc = _document_row(r)
        doc["chunks"] = r["chunks"]
        doc["word_count"] = len(doc["content"].split())
        if not include_content:
            doc.pop("content")
        out.append(doc)
    return out


def get_document(doc_id: str) -> Optional[dict]:
    with _lock:
        _ensure_db()
        with _connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
    return _document_row(row) if row else None


def add_document(doc_id: str, name: str, content: str, origin: str = "upload") -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        _ensure_db()
        with _connect() as conn:
            conn.execute(
                "INSERT INTO documents (id, name, origin, content, created_at) "
                "VALUES (?,?,?,?,?)",
                (doc_id, name, origin, content, now),
            )
    return {"id": doc_id, "name": name, "origin": origin, "created_at": now}


def delete_document(doc_id: str) -> None:
    with _lock:
        _ensure_db()
        with _connect() as conn:
            conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
            conn.execute(
                "DELETE FROM rag_chunks WHERE source_kind='document' AND source_id=?",
                (doc_id,),
            )


def document_name_exists(name: str) -> bool:
    with _lock:
        _ensure_db()
        with _connect() as conn:
            row = conn.execute("SELECT 1 FROM documents WHERE name=?", (name,)).fetchone()
    return row is not None


def replace_chunks(source_kind: str, source_id: str, chunks: List[dict]) -> int:
    with _lock:
        _ensure_db()
        with _connect() as conn:
            conn.execute(
                "DELETE FROM rag_chunks WHERE source_kind=? AND source_id=?",
                (source_kind, source_id),
            )
            conn.executemany(
                "INSERT INTO rag_chunks "
                "(id, source_kind, source_id, source_name, text, embedding, position) "
                "VALUES (?,?,?,?,?,?,?)",
                [
                    (c["id"], source_kind, source_id, c["source_name"],
                     c["text"], c.get("embedding"), i)
                    for i, c in enumerate(chunks)
                ],
            )
    return len(chunks)


def list_chunks(source_kind: Optional[str] = None) -> List[dict]:
    query = "SELECT * FROM rag_chunks"
    params: tuple = ()
    if source_kind:
        query += " WHERE source_kind=?"
        params = (source_kind,)
    with _lock:
        _ensure_db()
        with _connect() as conn:
            rows = conn.execute(query, params).fetchall()
    return [
        {
            "id": r["id"],
            "source_kind": r["source_kind"],
            "source_id": r["source_id"],
            "source_name": r["source_name"],
            "text": r["text"],
            "embedding": r["embedding"],
        }
        for r in rows
    ]


def index_stats() -> dict:
    with _lock:
        _ensure_db()
        with _connect() as conn:
            rows = conn.execute(
                "SELECT source_kind, COUNT(*) AS n, "
                "SUM(CASE WHEN embedding IS NULL THEN 0 ELSE 1 END) AS embedded "
                "FROM rag_chunks GROUP BY source_kind"
            ).fetchall()
            docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    by_kind = {r["source_kind"]: {"chunks": r["n"], "embedded": r["embedded"] or 0} for r in rows}
    return {
        "documents": docs,
        "document_chunks": by_kind.get("document", {}).get("chunks", 0),
        "model_chunks": by_kind.get("model", {}).get("chunks", 0),
        "total_chunks": sum(v["chunks"] for v in by_kind.values()),
        "embedded_chunks": sum(v["embedded"] for v in by_kind.values()),
    }
