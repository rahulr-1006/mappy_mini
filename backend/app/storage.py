import json
import os
import threading
from datetime import datetime, timezone
from typing import List

from . import config

_lock = threading.Lock()


def _ensure_file() -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    if not os.path.exists(config.STATE_FILE):
        with open(config.STATE_FILE, "w") as f:
            json.dump(
                {
                    "model_elements": [],
                    "activity_log": [],
                    "diagram": {"blocks": [], "connectors": []},
                    "eval_log": [],
                    "traces": [],
                },
                f,
            )


def _read() -> dict:
    _ensure_file()
    with open(config.STATE_FILE) as f:
        return json.load(f)


def _write(state: dict) -> None:
    with open(config.STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_state() -> dict:
    with _lock:
        return _read()


def add_model_elements(elements: List[dict]) -> dict:
    with _lock:
        state = _read()
        state["model_elements"].extend(elements)
        _write(state)
        return state


def delete_model_element(element_id: str) -> dict:
    with _lock:
        state = _read()
        state["model_elements"] = [
            e for e in state["model_elements"] if e.get("id") != element_id
        ]
        _write(state)
        return state


def get_diagram() -> dict:
    with _lock:
        return _read().get("diagram", {"blocks": [], "connectors": []})


def save_diagram(blocks: List[dict], connectors: List[dict]) -> dict:
    with _lock:
        state = _read()
        state["diagram"] = {"blocks": blocks, "connectors": connectors}
        _write(state)
        return state["diagram"]


def clear_diagram() -> dict:
    with _lock:
        state = _read()
        state["diagram"] = {"blocks": [], "connectors": []}
        _write(state)
        return state["diagram"]


def get_traces() -> List[dict]:
    with _lock:
        return _read().get("traces", [])


def add_traces(traces: List[dict]) -> List[dict]:
    with _lock:
        state = _read()
        existing = state.setdefault("traces", [])
        # a requirement/block/kind triple is the identity -- adding the same
        # link twice should not create a duplicate row in the matrix
        seen = {(t["requirement_id"], t["block_id"], t["kind"]) for t in existing}
        for t in traces:
            key = (t["requirement_id"], t["block_id"], t["kind"])
            if key not in seen:
                existing.append(t)
                seen.add(key)
        _write(state)
        return existing


def delete_trace(trace_id: str) -> List[dict]:
    with _lock:
        state = _read()
        state["traces"] = [t for t in state.get("traces", []) if t.get("id") != trace_id]
        _write(state)
        return state["traces"]


def get_eval_log() -> List[dict]:
    with _lock:
        return _read().get("eval_log", [])


def add_eval_record(record: dict) -> dict:
    with _lock:
        state = _read()
        state.setdefault("eval_log", []).append(record)
        _write(state)
        return record


def log_event(message: str, verbose: bool = False) -> dict:
    with _lock:
        state = _read()
        state["activity_log"].append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": message,
                "verbose": verbose,
            }
        )
        _write(state)
        return state
