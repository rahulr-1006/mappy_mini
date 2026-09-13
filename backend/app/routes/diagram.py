import json
import uuid
from typing import List

from fastapi import APIRouter

from .. import config, knowledge, rag, storage
from ..diagram_rules import validate_diagram
from ..evaluation import MetricsAccumulator
from ..models import GenerateDiagramRequest, GenerateDiagramResponse
from ..llm import LLMError, generate_json
from ..prompts import build_diagram_prompt, build_diagram_reprompt

router = APIRouter(prefix="/diagram", tags=["diagram"])


def _parse_diagram_object(raw: str) -> dict:
    data = json.loads(raw)
    if isinstance(data, list) and data:
        # some models wrap the object in a one-element array
        data = data[0]
    if not isinstance(data, dict) or "blocks" not in data or "connectors" not in data:
        raise ValueError("expected a JSON object with 'blocks' and 'connectors'")
    return data


def _normalize_block(item: dict) -> dict:
    return {
        "id": str(item.get("id", "")),
        "name": item.get("name", ""),
        "description": item.get("description", ""),
        "isRoot": bool(item.get("isRoot", False)),
    }


def _normalize_connector(item: dict) -> dict:
    return {
        "id": str(item.get("id", "")),
        "source": str(item.get("source", "")),
        "target": str(item.get("target", "")),
        "kind": item.get("kind", ""),
        "label": item.get("label", ""),
    }


def _system_description(override: str, requirements: List[dict]) -> tuple[str, str]:
    """What system is this a diagram of?

    The conversation already answers that, so asking for it a second time in
    a separate box is how the requirements and the diagram end up describing
    two different systems. Order of preference: an explicit override, then
    what the engineer actually said in chat, then the requirements alone.
    """
    if override.strip():
        return override.strip(), "the prompt given"

    messages = storage.get_chat_messages()
    said = [m["content"] for m in messages if m["role"] == "user"]
    if said:
        # the opening description plus the detail that followed it; later
        # turns are usually corrections and belong in the picture too
        joined = "\n".join(said[:4])
        return joined[:2000], "the chat conversation"

    if requirements:
        return (
            "The system described by the following requirements.",
            "the kept requirements",
        )
    return "", "nothing"


def _finish(acc: MetricsAccumulator, items: int, first_pass: bool, success: bool) -> dict:
    metrics = acc.finalize(
        items=items,
        first_pass_rate=1.0 if first_pass else 0.0,
        success_rate=1.0 if success else 0.0,
    )
    return storage.add_eval_record(metrics.to_record())


async def _generate_diagram(payload: GenerateDiagramRequest, source: str = "live") -> GenerateDiagramResponse:
    log: List[str] = []
    acc = MetricsAccumulator(task="diagram", model=payload.model, source=source)

    def note(message: str) -> None:
        log.append(message)
        storage.log_event(message)

    requirements = storage.list_model_elements()
    description, origin = _system_description(payload.prompt, requirements)

    if not description:
        note(
            "Nothing to diagram: no requirements are in the model and the "
            "conversation has not described a system yet."
        )
        metrics = _finish(acc, items=0, first_pass=False, success=False)
        return GenerateDiagramResponse(blocks=[], connectors=[], log=log, metrics=metrics)

    # the design is retrieved against the requirements it has to satisfy,
    # so the documents that shaped them also shape the architecture
    query = description + "\n" + "\n".join(r.get("text", "") for r in requirements[:8])
    chunks, method = await knowledge.retrieve(query, top_k=5)
    if chunks:
        note(knowledge.describe(chunks, method))

    system, prompt = build_diagram_prompt(
        description, requirements, context=rag.format_context(chunks)
    )
    if requirements:
        note(
            f"Generating block diagram with model={payload.model} from "
            f"{len(requirements)} kept requirement(s); system description taken "
            f"from {origin}."
        )
    else:
        note(
            f"Generating block diagram with model={payload.model} from {origin} "
            f"with no requirements to bound the scope."
        )

    try:
        initial = await generate_json(prompt, payload.model, system)
        acc.add(initial)
    except LLMError as exc:
        note(f"ERROR calling the model: {exc}")
        metrics = _finish(acc, items=0, first_pass=False, success=False)
        return GenerateDiagramResponse(blocks=[], connectors=[], log=log, metrics=metrics)

    try:
        data = _parse_diagram_object(initial.text)
    except (json.JSONDecodeError, ValueError) as exc:
        note(f"ERROR parsing LLM output as a diagram JSON object: {exc}")
        metrics = _finish(acc, items=0, first_pass=False, success=False)
        return GenerateDiagramResponse(blocks=[], connectors=[], log=log, metrics=metrics)

    reprompts = 0
    first_pass = True
    while True:
        blocks = [_normalize_block(b) for b in data.get("blocks", [])]
        connectors = [_normalize_connector(c) for c in data.get("connectors", [])]
        violations = validate_diagram(blocks, connectors)

        if violations and reprompts == 0:
            first_pass = False

        if not violations or reprompts >= config.MAX_REPROMPTS:
            if violations:
                note(f"Diagram still has issues after {reprompts} repair attempt(s): {', '.join(violations)}.")
            break

        note(f"Diagram failed validation: {', '.join(violations)}. Re-prompting (attempt {reprompts + 1}).")
        fix_system, reprompt_prompt = build_diagram_reprompt(json.dumps(data), violations)
        try:
            fix_result = await generate_json(reprompt_prompt, payload.model, fix_system)
            acc.add(fix_result)
            data = _parse_diagram_object(fix_result.text)
        except (LLMError, json.JSONDecodeError, ValueError) as exc:
            note(f"ERROR during diagram reprompt: {exc}")
            break
        reprompts += 1

    note(f"Diagram generation complete: {len(blocks)} block(s), {len(connectors)} connector(s).")

    metrics = _finish(acc, items=len(blocks), first_pass=first_pass, success=not violations)
    return GenerateDiagramResponse(blocks=blocks, connectors=connectors, log=log, metrics=metrics)


@router.post("/generate", response_model=GenerateDiagramResponse)
async def generate_diagram(payload: GenerateDiagramRequest):
    return await _generate_diagram(payload, source="live")


@router.get("")
async def get_diagram():
    return storage.get_diagram()


@router.post("")
async def save_diagram(payload: dict):
    blocks = payload.get("blocks", [])
    connectors = payload.get("connectors", [])

    id_map = {block["id"]: str(uuid.uuid4()) for block in blocks}
    saved_blocks = [{**block, "id": id_map[block["id"]]} for block in blocks]
    saved_connectors = [
        {
            **connector,
            "id": str(uuid.uuid4()),
            "source": id_map.get(connector["source"], connector["source"]),
            "target": id_map.get(connector["target"], connector["target"]),
        }
        for connector in connectors
    ]

    diagram = storage.save_diagram(
        saved_blocks, saved_connectors, payload.get("prompt")
    )
    storage.log_event(f"Saved diagram with {len(saved_blocks)} block(s) to the model.")
    result = await knowledge.reindex_model()
    storage.log_event(
        f"Re-indexed the model: {result['requirements']} requirement(s), "
        f"{result['blocks']} block(s), {result['chunks']} chunk(s)."
    )
    return diagram


@router.delete("")
async def delete_diagram():
    diagram = storage.clear_diagram()
    storage.log_event("Cleared the saved diagram.")
    await knowledge.reindex_model()
    return diagram
