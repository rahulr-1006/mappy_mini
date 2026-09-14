"""Fixed golden prompt set, re-runnable to benchmark a model + prompt change.

Runs real generations against Ollama sequentially, so expect this to take
several minutes on a local 8B model -- it is an on-demand benchmark, not
something to trigger in the middle of an interactive session.
"""

from .models import GenerateDiagramRequest, GenerateRequest
from .routes.diagram import _generate_diagram
from .routes.requirements import _generate_requirements

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


async def run_head_to_head(models: list[str]) -> dict:
    """Same prompt, same rulebook, several models, one table.

    The provider comparison elsewhere is assembled from whatever happens to
    be in the evaluation log, which means it compares runs that were never
    controlled against each other. This runs them back to back on one
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


async def run_suite(model: str) -> dict:
    runs = []

    for prompt in REQUIREMENT_PROMPTS:
        response = await _generate_requirements(
            GenerateRequest(prompt=prompt, model=model, run_sanity_check=True),
            source="suite",
        )
        runs.append({"task": "requirements", "prompt": prompt, "metrics": response.metrics})

    for prompt in DIAGRAM_PROMPTS:
        response = await _generate_diagram(
            GenerateDiagramRequest(prompt=prompt, model=model),
            source="suite",
        )
        runs.append({"task": "diagram", "prompt": prompt, "metrics": response.metrics})

    return {"model": model, "runs": runs}
