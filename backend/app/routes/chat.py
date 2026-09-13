import json
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .. import config, rules, storage
from ..evaluation import MetricsAccumulator
from ..llm import LLMError, generate_json
from ..prompts import build_chat_prompt, build_reprompt

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


async def _repair(
    item: dict, violations: List[str], model: str, acc: MetricsAccumulator
) -> tuple[dict, List[str], int]:
    """Send a failing draft back with the rules it broke, on a tighter budget
    than the Requirements tab. Returns the best version reached, its remaining
    violations, and how many repair attempts it cost."""
    reprompts = 0
    current = item

    while violations and reprompts < config.CHAT_MAX_REPROMPTS:
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
    first_pass_count = 0
    for item in raw:
        norm = _normalize(item)
        if not norm["text"]:
            continue
        violations = _violations(norm)
        if not violations:
            first_pass_count += 1
        # chat drafts are held to the same rulebook as the Requirements tab,
        # so a failing draft goes back to the model with the rule it broke
        # rather than landing in the thread as a red card nothing repairs
        norm, violations, reprompts = await _repair(norm, violations, payload.model, acc)
        norm["violations"] = violations
        norm["reprompts"] = reprompts
        requirements.append(norm)

    if not reply:
        reply = (
            f"Drafted {len(requirements)} requirement(s)."
            if requirements
            else "No response text was returned."
        )

    msg = storage.add_chat_message("assistant", reply, requirements)

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
