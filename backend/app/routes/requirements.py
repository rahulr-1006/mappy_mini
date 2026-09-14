"""Requirement generation: prompt, validate, repair, meter."""

import json
from typing import List

from fastapi import APIRouter

from .. import config, rules, storage
from ..evaluation import MetricsAccumulator
from ..models import GenerateRequest, GenerateResponse, Requirement
from ..llm import LLMError, generate_json
from ..prompts import build_format_reprompt, build_generation_prompt, build_reprompt

router = APIRouter(prefix="/requirements", tags=["requirements"])


REQUIREMENT_KEYS = {"stereotype", "name", "text", "verifyMethod"}


def _parse_requirement_array(raw: str) -> List[dict]:
    data = json.loads(raw)
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list):
                data = value
                break
        else:
            if REQUIREMENT_KEYS & set(data):
                data = [data]
    if not isinstance(data, list):
        raise ValueError("expected a JSON array of requirement objects")
    return data


def _normalize(item: dict) -> dict:
    return {
        "stereotype": item.get("stereotype", ""),
        "name": item.get("name", ""),
        "text": item.get("text", ""),
        "verifyMethod": item.get("verifyMethod", ""),
    }


def _validate(item: dict, run_sanity_check: bool) -> List[str]:
    violations = []
    if item["stereotype"] not in config.ALLOWED_STEREOTYPES:
        violations.append(f"invalid stereotype '{item['stereotype']}'")
    if item["verifyMethod"] not in config.ALLOWED_VERIFY_METHODS:
        violations.append(f"invalid verifyMethod '{item['verifyMethod']}'")

    if run_sanity_check:
        for v in rules.validate_requirement_text(item["text"]):
            violations.append(v.label())

    return violations


async def _parse_with_recovery(text: str, model: str, acc: MetricsAccumulator, note):
    attempt = 0
    current = text

    while True:
        try:
            return [_normalize(i) for i in _parse_requirement_array(current)], attempt
        except (json.JSONDecodeError, ValueError) as exc:
            if attempt >= config.MAX_FORMAT_RETRIES:
                note(
                    f"ERROR parsing LLM output as a JSON array after "
                    f"{attempt} format retry(ies): {exc}"
                )
                return None, attempt
            note(
                f"Response was not a parseable JSON array ({exc}). "
                f"Re-prompting for format only (attempt {attempt + 1})."
            )

        fix_system, fix_prompt = build_format_reprompt(current, "a JSON array of requirement objects")
        try:
            fixed = await generate_json(fix_prompt, model, fix_system)
            acc.add(fixed)
            current = fixed.text
        except LLMError as exc:
            note(f"ERROR during format retry: {exc}")
            return None, attempt
        attempt += 1


def _finish(acc: MetricsAccumulator, items: int, first_pass: int, success: int) -> dict:
    metrics = acc.finalize(
        items=items,
        first_pass_rate=(first_pass / items) if items else 0.0,
        success_rate=(success / items) if items else 0.0,
    )
    return storage.add_eval_record(metrics.to_record())


async def _generate_requirements(payload: GenerateRequest, source: str = "live") -> GenerateResponse:
    log: List[str] = []
    acc = MetricsAccumulator(task="requirements", model=payload.model, source=source)

    def note(message: str) -> None:
        log.append(message)
        storage.log_event(message)

    system, prompt = build_generation_prompt(payload.prompt)
    note(f"Generating requirements with model={payload.model} for prompt: {payload.prompt!r}")

    try:
        initial = await generate_json(prompt, payload.model, system)
        acc.add(initial)
    except LLMError as exc:
        note(f"ERROR calling the model: {exc}")
        metrics = _finish(acc, items=0, first_pass=0, success=0)
        return GenerateResponse(requirements=[], log=log, metrics=metrics)

    raw_items, format_retries = await _parse_with_recovery(
        initial.text, payload.model, acc, note
    )
    if raw_items is None:
        metrics = _finish(acc, items=0, first_pass=0, success=0)
        return GenerateResponse(requirements=[], log=log, metrics=metrics)

    results: List[Requirement] = []
    first_pass_count = 0
    success_count = 0

    for item in raw_items:
        reprompts = 0
        current = item
        violations = _validate(current, payload.run_sanity_check)
        first_pass = not violations

        while violations and reprompts < config.MAX_REPROMPTS:
            note(
                f"Requirement '{current['name']}' failed rules: "
                f"{', '.join(violations)}. Re-prompting (attempt {reprompts + 1})."
            )
            fix_system, reprompt_prompt = build_reprompt(current["text"], violations)
            try:
                fix_result = await generate_json(reprompt_prompt, payload.model, fix_system)
                acc.add(fix_result)
                fixed = _normalize(json.loads(fix_result.text))
                current = {**current, **fixed}
            except (LLMError, json.JSONDecodeError, ValueError) as exc:
                note(f"ERROR during reprompt: {exc}")
                break
            reprompts += 1
            violations = _validate(current, payload.run_sanity_check)

        if first_pass:
            first_pass_count += 1
        if not violations:
            success_count += 1

        if violations:
            note(
                f"Requirement '{current['name']}' still breaks "
                f"{len(violations)} rule(s) after {reprompts} repair attempt(s): "
                f"{', '.join(violations)}."
            )

        results.append(
            Requirement(
                stereotype=current["stereotype"],
                name=current["name"],
                text=current["text"],
                verifyMethod=current["verifyMethod"],
                reprompts=reprompts,
                violations=violations,
                advisories=[a.label() for a in rules.review_requirement_text(current["text"])],
            )
        )

    if payload.run_sanity_check and len(results) > 1:
        dup_violations = rules.find_duplicates([r.model_dump() for r in results])
        for idx, violation in dup_violations.items():
            note(f"Requirement '{results[idx].name}' flagged: {violation.detail}")

    note(
        f"Generation complete: {len(results)} requirement(s) produced."
        + (
            f" Recovered from {format_retries} malformed response(s)."
            if format_retries
            else ""
        )
    )

    metrics = _finish(acc, items=len(results), first_pass=first_pass_count, success=success_count)
    return GenerateResponse(requirements=results, log=log, metrics=metrics)


@router.post("/generate", response_model=GenerateResponse)
async def generate_requirements(payload: GenerateRequest):
    return await _generate_requirements(payload, source="live")
