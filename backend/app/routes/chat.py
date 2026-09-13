import json
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .. import config, rules, storage
from ..evaluation import MetricsAccumulator
from ..llm import LLMError, generate_json
from ..prompts import build_chat_prompt

router = APIRouter(prefix="/chat", tags=["chat"])

# enough context for the model to follow the thread without resending a
# transcript that grows without bound
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
        out.append(f"{v.rule}: {v.detail}")
    return out


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

    # the model will happily ask forever, so the decision to stop asking is
    # made here rather than left to its judgement: one clarifying turn is
    # allowed, after that it must produce
    already_asked = any(
        m["role"] == "assistant" and not m.get("requirements") for m in history
    )
    system, user = build_chat_prompt(history, payload.message, must_produce=already_asked)

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
        # a conversational turn is still useful even when the JSON envelope
        # is malformed, so fall back to the raw text rather than erroring
        reply, raw = result.text.strip()[:1500], []

    requirements = []
    for item in raw:
        norm = _normalize(item)
        if not norm["text"]:
            continue
        norm["violations"] = _violations(norm)
        requirements.append(norm)

    if not reply:
        reply = (
            f"Drafted {len(requirements)} requirement(s)."
            if requirements
            else "No response text was returned."
        )

    msg = storage.add_chat_message("assistant", reply, requirements)

    clean = sum(1 for r in requirements if not r["violations"])
    storage.log_event(
        f"Chat turn with model={payload.model}: "
        + (
            f"{len(requirements)} requirement(s) drafted, {clean} clean."
            if requirements
            else "asked for more detail."
        )
    )

    metrics = acc.finalize(
        items=len(requirements),
        first_pass_rate=(clean / len(requirements)) if requirements else 0.0,
        success_rate=(clean / len(requirements)) if requirements else 0.0,
    )
    storage.add_eval_record(metrics.to_record())

    return {"messages": storage.get_chat_messages(), "message": msg}
