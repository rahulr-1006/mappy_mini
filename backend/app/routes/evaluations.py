import json
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .. import config, rules, storage
from ..evaluation import (
    REFERENCE_RATES,
    MetricsAccumulator,
    normalize_review,
    summarize,
    summarize_reviews,
)
from ..llm import LLMError, generate_json
from ..models import GenerateDiagramRequest, GenerateRequest
from ..prompts import build_judge_prompt
from .diagram import _generate_diagram
from .requirements import _generate_requirements

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


# The golden set: fixed prompts, re-runnable, so a prompt or model change
# is compared on identical inputs. These are real generations run
# sequentially, so the full suite takes several minutes on a local 8B
# model -- an on-demand benchmark, not something to fire mid-session.

REQUIREMENT_PROMPTS = [
    "an autonomous coffee maker that grinds beans on demand and shuts off if the pot is removed",
    "a drone delivery system that avoids obstacles and returns to base on low battery",
    "a home security system with motion detection and remote monitoring",
]

DIAGRAM_PROMPTS = [
    "a reusable orbital launch vehicle with a recoverable booster and an expendable upper stage",
    "a drip coffee maker with a water reservoir, heating element, pump, and brew basket",
    "a quadcopter drone with a flight controller, motors, battery, and camera gimbal",
]

# One short prompt, run against each model in turn. Deliberately smaller
# than the full suite: the point of a head-to-head is a controlled
# comparison you can actually wait for, not a benchmark you start and come
# back to.
HEADTOHEAD_PROMPT = "a satellite ground station that tracks a single LEO spacecraft"


class RunSuiteRequest(BaseModel):
    model: str = config.DEFAULT_MODEL


class JudgeRequest(BaseModel):
    model: str = config.DEFAULT_MODEL


@router.get("")
async def get_evaluations():
    records = storage.get_eval_log()
    return {
        "records": records,
        "summary": summarize(records),
        "reference_rates": REFERENCE_RATES,
    }


@router.post("/judge")
async def judge_requirements(payload: JudgeRequest):
    """Score the kept requirements on criteria the lexical rules cannot see,
    and report where the two signals disagree."""
    log: List[str] = []
    requirements = storage.list_model_elements()
    acc = MetricsAccumulator(task="judge", model=payload.model, source="live")

    def note(message: str) -> None:
        log.append(message)
        storage.log_event(message)

    def finish(reviews):
        rule_failures = {
            i: [f"{v.rule}" for v in rules.validate_requirement_text(r.get("text", ""))]
            for i, r in enumerate(requirements)
        }
        summary = summarize_reviews(reviews, rule_failures)
        metrics = acc.finalize(
            items=len(reviews),
            first_pass_rate=1.0 if reviews else 0.0,
            success_rate=1.0 if reviews else 0.0,
        )
        return {
            "reviews": [
                {**r, "name": requirements[r["index"]].get("name", "")}
                for r in reviews
                if isinstance(r.get("index"), int) and 0 <= r["index"] < len(requirements)
            ],
            "summary": summary,
            "rule_failures": {str(k): v for k, v in rule_failures.items()},
            "log": log,
            "metrics": storage.add_eval_record(metrics.to_record()),
        }

    if not requirements:
        note("Semantic review needs kept requirements.")
        return finish([])

    note(f"Reviewing {len(requirements)} requirement(s) with judge model={payload.model}.")

    try:
        system, user = build_judge_prompt(requirements)
        result = await generate_json(user, payload.model, system)
        acc.add(result)
    except LLMError as exc:
        note(f"ERROR calling the judge model: {exc}")
        return finish([])

    try:
        data = json.loads(result.text)
        raw = data.get("reviews", data) if isinstance(data, dict) else data
        if not isinstance(raw, list):
            raise ValueError("expected a JSON array of reviews")
    except (json.JSONDecodeError, ValueError) as exc:
        note(f"ERROR parsing judge output: {exc}")
        return finish([])

    reviews = [normalize_review(item) for item in raw]
    payload_out = finish(reviews)
    flagged = payload_out["summary"]["flagged"]
    blind = payload_out["summary"]["passed_rules_but_judge_flagged"]
    note(
        f"Semantic review complete: {len(reviews)} reviewed, {len(flagged)} flagged, "
        f"{blind} of those passed the lexical rules."
    )
    payload_out["log"] = log
    return payload_out


class HeadToHeadRequest(BaseModel):
    models: List[str] = Field(default_factory=list, max_length=4)


@router.post("/head-to-head")
async def head_to_head(payload: HeadToHeadRequest):
    models = payload.models or [config.DEFAULT_MODEL]
    storage.log_event(f"Head-to-head: running one prompt against {', '.join(models)}.")
    result = await _run_head_to_head(models)
    for row in result["rows"]:
        storage.log_event(
            f"  {row['model']}: {row['items']} requirement(s), "
            f"{row['success_rate']:.0%} valid, {row['duration_ms'] / 1000:.1f}s, "
            f"${row['actual_cost_usd']:.4f}."
        )
    return result


@router.post("/run-suite")
async def run_suite(payload: RunSuiteRequest):
    await _run_suite(payload.model)
    records = storage.get_eval_log()
    suite_records = [r for r in records if r.get("source") == "suite"]
    return {
        "summary": summarize(records),
        "suite_summary": summarize(suite_records),
        "prompts_run": len(REQUIREMENT_PROMPTS) + len(DIAGRAM_PROMPTS),
    }


async def _run_head_to_head(models: List[str]) -> dict:
    """Same prompt, same rulebook, several models, one table.

    The provider comparison in the evaluation log is assembled from
    whatever happens to be in it, which means it compares runs that were
    never controlled against each other. This runs them back to back on one
    prompt so the numbers are comparable by construction.
    """
    rows = []
    for model in models:
        response = await _generate_requirements(
            GenerateRequest(prompt=HEADTOHEAD_PROMPT, model=model, run_sanity_check=True),
            source="headtohead",
        )
        metrics = response.metrics
        rows.append(
            {
                "model": model,
                "provider": metrics.provider,
                "items": metrics.items,
                "first_pass_rate": metrics.first_pass_rate,
                "success_rate": metrics.success_rate,
                "duration_ms": metrics.duration_ms,
                "llm_calls": metrics.llm_calls,
                "total_tokens": metrics.total_tokens,
                "actual_cost_usd": metrics.actual_cost_usd,
                "rules_broken": sorted(
                    {v.split(" ")[0] for r in response.requirements for v in r.violations}
                ),
            }
        )

    return {"prompt": HEADTOHEAD_PROMPT, "rows": rows}


async def _run_suite(model: str) -> None:
    """Every golden prompt, one model. Results land in the evaluation log
    tagged source="suite", which is what the caller reads back."""
    for prompt in REQUIREMENT_PROMPTS:
        await _generate_requirements(
            GenerateRequest(prompt=prompt, model=model, run_sanity_check=True),
            source="suite",
        )

    for prompt in DIAGRAM_PROMPTS:
        await _generate_diagram(
            GenerateDiagramRequest(prompt=prompt, model=model),
            source="suite",
        )
