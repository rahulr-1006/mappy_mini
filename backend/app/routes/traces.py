import json
import uuid
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from .. import config, storage
from ..evaluation import MetricsAccumulator
from ..llm import LLMError, generate_json
from ..prompts import build_trace_prompt
from ..traceability import compute_coverage, validate_trace

router = APIRouter(prefix="/traces", tags=["traces"])


class TraceLink(BaseModel):
    requirement_id: str
    block_id: str
    kind: str = "satisfy"
    rationale: str = ""


class CreateTracesRequest(BaseModel):
    traces: List[TraceLink]


class SuggestRequest(BaseModel):
    model: str = config.DEFAULT_MODEL


def _current_sets() -> tuple:
    requirements = storage.list_model_elements()
    blocks = storage.get_diagram()["blocks"]
    return requirements, blocks


@router.get("")
async def list_traces():
    return storage.get_traces()


@router.get("/coverage")
async def coverage():
    requirements, blocks = _current_sets()
    return compute_coverage(requirements, blocks, storage.get_traces())


@router.post("")
async def create_traces(payload: CreateTracesRequest):
    requirements, blocks = _current_sets()
    req_ids = {r["id"] for r in requirements}
    block_ids = {b["id"] for b in blocks}

    accepted, rejected = [], []
    for link in payload.traces:
        item = link.model_dump()
        violations = validate_trace(item, req_ids, block_ids)
        if violations:
            rejected.append({**item, "violations": violations})
            continue
        accepted.append({**item, "id": str(uuid.uuid4())})

    if accepted:
        storage.add_traces(accepted)
        storage.log_event(f"Added {len(accepted)} trace link(s).")

    return {
        "traces": storage.get_traces(),
        "accepted": len(accepted),
        "rejected": rejected,
    }


@router.delete("/{trace_id}")
async def delete_trace(trace_id: str):
    traces = storage.delete_trace(trace_id)
    storage.log_event(f"Removed trace link {trace_id}.")
    return traces


@router.post("/suggest")
async def suggest_traces(payload: SuggestRequest):
    """Propose links for a human to confirm. Nothing is persisted here --
    the engineer accepts or rejects each one."""
    log: List[str] = []
    requirements, blocks = _current_sets()
    acc = MetricsAccumulator(task="traces", model=payload.model, source="live")

    def note(message: str) -> None:
        log.append(message)
        storage.log_event(message)

    if not requirements or not blocks:
        note("Trace suggestion needs both kept requirements and a saved diagram.")
        metrics = acc.finalize(items=0, first_pass_rate=0.0, success_rate=0.0)
        return {
            "suggestions": [],
            "log": log,
            "metrics": storage.add_eval_record(metrics.to_record()),
        }

    note(
        f"Suggesting trace links with model={payload.model} "
        f"for {len(requirements)} requirement(s) and {len(blocks)} block(s)."
    )

    try:
        trace_system, trace_user = build_trace_prompt(requirements, blocks)
        result = await generate_json(trace_user, payload.model, trace_system)
        acc.add(result)
    except LLMError as exc:
        note(f"ERROR calling the model: {exc}")
        metrics = acc.finalize(items=0, first_pass_rate=0.0, success_rate=0.0)
        return {
            "suggestions": [],
            "log": log,
            "metrics": storage.add_eval_record(metrics.to_record()),
        }

    try:
        data = json.loads(result.text)
        raw = data.get("traces", data) if isinstance(data, dict) else data
        if not isinstance(raw, list):
            raise ValueError("expected a JSON array of trace links")
    except (json.JSONDecodeError, ValueError) as exc:
        note(f"ERROR parsing trace suggestions: {exc}")
        metrics = acc.finalize(items=0, first_pass_rate=0.0, success_rate=0.0)
        return {
            "suggestions": [],
            "log": log,
            "metrics": storage.add_eval_record(metrics.to_record()),
        }

    req_ids = {r["id"] for r in requirements}
    block_ids = {b["id"] for b in blocks}
    existing = {(t["requirement_id"], t["block_id"], t["kind"]) for t in storage.get_traces()}

    suggestions, dropped = [], 0
    for item in raw:
        link = {
            "requirement_id": str(item.get("requirement_id", "")),
            "block_id": str(item.get("block_id", "")),
            "kind": item.get("kind", "satisfy"),
            "rationale": item.get("rationale", ""),
        }
        # a hallucinated id is the expected failure here, so drop rather than
        # surface links that point at nothing
        if validate_trace(link, req_ids, block_ids):
            dropped += 1
            continue
        if (link["requirement_id"], link["block_id"], link["kind"]) in existing:
            continue
        suggestions.append(link)

    if dropped:
        note(f"Discarded {dropped} suggested link(s) referencing unknown ids.")
    note(f"Proposed {len(suggestions)} trace link(s) for review.")

    metrics = acc.finalize(
        items=len(suggestions),
        first_pass_rate=1.0 if not dropped else 0.0,
        success_rate=1.0 if suggestions else 0.0,
    )
    return {
        "suggestions": suggestions,
        "log": log,
        "metrics": storage.add_eval_record(metrics.to_record()),
    }
