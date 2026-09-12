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
