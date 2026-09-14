"""Chat endpoints. Retrieves context, answers, and drafts requirements."""

import json
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .. import config, knowledge, rag, rules, storage
from ..evaluation import MetricsAccumulator
from ..llm import LLMError, generate_json
from ..prompts import build_chat_prompt, build_reprompt

router = APIRouter(prefix="/chat", tags=["chat"])

HISTORY_TURNS = 12


class ChatRequest(BaseModel):
    message: str = Field(..., max_length=4000)
    model: str = config.DEFAULT_MODEL


def _normalize(item: dict) -> dict:
    return {
        "stereotype": item.get("stereotype", ""),
        "name": item.get("name", ""),
        "text": item.get("text", ""),
        "verifyMethod": item.get("verifyMethod", ""),
    }


def _violations(item: dict) -> List[str]:
    out = []
    if item["stereotype"] not in config.ALLOWED_STEREOTYPES:
        out.append(f"invalid stereotype '{item['stereotype']}'")
    if item["verifyMethod"] not in config.ALLOWED_VERIFY_METHODS:
        out.append(f"invalid verifyMethod '{item['verifyMethod']}'")
    for v in rules.validate_requirement_text(item["text"]):
        out.append(v.label())
    return out


async def _repair(
    item: dict, violations: List[str], model: str, acc: MetricsAccumulator
) -> tuple[dict, List[str], int]:
    reprompts = 0
    current = item

    while violations and reprompts < config.MAX_REPROMPTS:
        storage.log_event(
            f"Chat requirement {current['name']!r} failed rules: "
            f"{', '.join(violations)}. Re-prompting (attempt {reprompts + 1})."
        )
        fix_system, fix_prompt = build_reprompt(current["text"], violations)
        try:
            fix_result = await generate_json(fix_prompt, model, fix_system)
            acc.add(fix_result)
            current = {**current, **_normalize(json.loads(fix_result.text))}
        except (LLMError, json.JSONDecodeError, ValueError) as exc:
            storage.log_event(f"Chat repair failed for {current['name']!r}: {exc}")
            break
        reprompts += 1
        violations = _violations(current)

    if violations:
        storage.log_event(
            f"Chat requirement {current['name']!r} still breaks "
            f"{len(violations)} rule(s) after {reprompts} repair attempt(s): "
            f"{', '.join(violations)}."
        )

    return current, violations, reprompts


@router.get("")
async def get_chat():
    return storage.get_chat_messages()


@router.delete("")
async def clear_chat():
    storage.clear_chat()
    storage.log_event("Cleared the chat thread.")
    return []


@router.post("")
async def send_message(payload: ChatRequest):
    acc = MetricsAccumulator(task="chat", model=payload.model, source="live")
    history = storage.get_chat_messages()[-HISTORY_TURNS:]

    storage.add_chat_message("user", payload.message)

    already_asked = any(
        m["role"] == "assistant" and not m.get("requirements") for m in history
    )
    prior = next(
        (m["content"] for m in reversed(history) if m["role"] == "user"), ""
    )
    chunks, method = await knowledge.retrieve(f"{prior}\n{payload.message}".strip())
    if chunks:
        storage.log_event(knowledge.describe(chunks, method))

    system, user = build_chat_prompt(
        history,
        payload.message,
        must_produce=already_asked,
        context=rag.format_context(chunks),
    )

    try:
        result = await generate_json(user, payload.model, system)
        acc.add(result)
    except LLMError as exc:
        reply = f"Could not reach the model: {exc}"
        msg = storage.add_chat_message("assistant", reply)
        storage.add_eval_record(
            acc.finalize(items=0, first_pass_rate=0.0, success_rate=0.0).to_record()
        )
        return {"messages": storage.get_chat_messages(), "message": msg}

    try:
        data = json.loads(result.text)
        reply = str(data.get("reply", "")).strip()
        raw = data.get("requirements") or []
        if not isinstance(raw, list):
            raw = []
    except (json.JSONDecodeError, ValueError, AttributeError):
        reply, raw = result.text.strip()[:1500], []

    requirements = []
    first_pass_count = 0
    for item in raw:
        norm = _normalize(item)
        if not norm["text"]:
            continue
        violations = _violations(norm)
        if not violations:
            first_pass_count += 1
        norm, violations, reprompts = await _repair(norm, violations, payload.model, acc)
        norm["violations"] = violations
        norm["reprompts"] = reprompts
        norm["advisories"] = [a.label() for a in rules.review_requirement_text(norm["text"])]
        requirements.append(norm)

    if not reply:
        reply = (
            f"Drafted {len(requirements)} requirement(s)."
            if requirements
            else "No response text was returned."
        )

    sources = [
        {"name": c.citation(), "kind": c.source_kind, "score": round(c.score, 3)}
        for c in chunks
    ]
    msg = storage.add_chat_message("assistant", reply, requirements, sources=sources)

    clean = sum(1 for r in requirements if not r["violations"])
    repaired = sum(1 for r in requirements if r["reprompts"] and not r["violations"])
    storage.log_event(
        f"Chat turn with model={payload.model}: "
        + (
            f"{len(requirements)} requirement(s) drafted, {clean} clean "
            f"({first_pass_count} first pass, {repaired} after repair)."
            if requirements
            else "asked for more detail."
        )
    )

    metrics = acc.finalize(
        items=len(requirements),
        first_pass_rate=(first_pass_count / len(requirements)) if requirements else 0.0,
        success_rate=(clean / len(requirements)) if requirements else 0.0,
    )
    storage.add_eval_record(metrics.to_record())

    return {"messages": storage.get_chat_messages(), "message": msg}
