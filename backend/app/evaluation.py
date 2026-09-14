"""What every generation cost, and how good the result was.

Two halves. The metering -- tokens, latency, call count, cost -- is
mechanical and runs on every generation. The semantic review at the bottom
is a second model scoring what a regex cannot see, and runs on demand.
Both end up in the same evaluation log, which is why they live together.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List

from .llm import LLMResult, provider_for

# Anthropic first-party API list prices, USD per 1M tokens, verified
# 2026-06-24. Used to estimate what this workload would cost against a
# hosted API instead of local Ollama, across three capability tiers.
# Re-check https://www.anthropic.com/pricing before quoting these.
REFERENCE_RATES: Dict[str, Dict[str, float]] = {
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    "claude-sonnet-5": {"input": 2.00, "output": 10.00},
    "claude-opus-5": {"input": 5.00, "output": 25.00},
}


def estimate_hosted_cost(prompt_tokens: int, completion_tokens: int) -> Dict[str, float]:
    return {
        name: round(
            prompt_tokens / 1_000_000 * rates["input"]
            + completion_tokens / 1_000_000 * rates["output"],
            6,
        )
        for name, rates in REFERENCE_RATES.items()
    }


def actual_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Real money spent on this generation. Local inference is free; a
    hosted model bills at its own rate."""
    rates = REFERENCE_RATES.get(model)
    if rates is None:
        return 0.0
    return round(
        prompt_tokens / 1_000_000 * rates["input"]
        + completion_tokens / 1_000_000 * rates["output"],
        6,
    )


@dataclass
class GenerationMetrics:
    task: str
    model: str
    provider: str
    source: str
    llm_calls: int
    prompt_tokens: int
    completion_tokens: int
    duration_ms: float
    items: int
    first_pass_rate: float
    success_rate: float
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_record(self) -> dict:
        return {
            **asdict(self),
            "total_tokens": self.prompt_tokens + self.completion_tokens,
            "cost_estimate_usd": estimate_hosted_cost(self.prompt_tokens, self.completion_tokens),
            "actual_cost_usd": actual_cost(self.model, self.prompt_tokens, self.completion_tokens),
        }


class MetricsAccumulator:
    def __init__(self, task: str, model: str, source: str = "live"):
        self.task = task
        self.model = model
        self.source = source
        self.llm_calls = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.duration_ms = 0.0
        self.cache_read_tokens = 0
        self.cache_write_tokens = 0

    def add(self, result: LLMResult) -> None:
        self.llm_calls += 1
        self.prompt_tokens += result.prompt_tokens
        self.completion_tokens += result.completion_tokens
        self.duration_ms += result.duration_ms
        self.cache_read_tokens += result.cache_read_tokens
        self.cache_write_tokens += result.cache_write_tokens

    def finalize(self, items: int, first_pass_rate: float, success_rate: float) -> GenerationMetrics:
        return GenerationMetrics(
            task=self.task,
            model=self.model,
            provider=provider_for(self.model),
            source=self.source,
            llm_calls=self.llm_calls,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            duration_ms=self.duration_ms,
            items=items,
            first_pass_rate=first_pass_rate,
            success_rate=success_rate,
            cache_read_tokens=self.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens,
        )


def summarize(records: List[dict]) -> dict:
    if not records:
        return {
            "generations": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0,
            "total_duration_ms": 0.0,
            "avg_first_pass_rate": 0.0,
            "avg_success_rate": 0.0,
            "avg_duration_ms": 0.0,
            "estimated_hosted_cost_totals": {name: 0.0 for name in REFERENCE_RATES},
            "total_cache_read_tokens": 0,
            "total_cache_write_tokens": 0,
            "actual_spend_usd": 0.0,
            "by_provider": {},
        }

    total_prompt_tokens = sum(r["prompt_tokens"] for r in records)
    total_completion_tokens = sum(r["completion_tokens"] for r in records)
    total_duration_ms = sum(r["duration_ms"] for r in records)
    count = len(records)

    # Recomputed from stored token counts rather than summing each record's
    # saved estimate, so a rate correction applies to history too.
    cost_totals = estimate_hosted_cost(total_prompt_tokens, total_completion_tokens)

    by_provider: Dict[str, dict] = {}
    for r in records:
        p = r.get("provider", "ollama")
        bucket = by_provider.setdefault(
            p, {"generations": 0, "tokens": 0, "duration_ms": 0.0, "first_pass": 0.0, "spend_usd": 0.0}
        )
        bucket["generations"] += 1
        bucket["tokens"] += r["prompt_tokens"] + r["completion_tokens"]
        bucket["duration_ms"] += r["duration_ms"]
        bucket["first_pass"] += r["first_pass_rate"]
        bucket["spend_usd"] += r.get("actual_cost_usd", 0.0)

    for bucket in by_provider.values():
        n = bucket["generations"]
        bucket["avg_first_pass_rate"] = bucket.pop("first_pass") / n
        bucket["avg_duration_ms"] = bucket["duration_ms"] / n
        bucket["spend_usd"] = round(bucket["spend_usd"], 6)

    return {
        "generations": count,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_prompt_tokens + total_completion_tokens,
        "total_duration_ms": total_duration_ms,
        "avg_first_pass_rate": sum(r["first_pass_rate"] for r in records) / count,
        "avg_success_rate": sum(r["success_rate"] for r in records) / count,
        "avg_duration_ms": total_duration_ms / count,
        "estimated_hosted_cost_totals": cost_totals,
        "total_cache_read_tokens": sum(r.get("cache_read_tokens", 0) for r in records),
        "total_cache_write_tokens": sum(r.get("cache_write_tokens", 0) for r in records),
        "actual_spend_usd": round(sum(r.get("actual_cost_usd", 0.0) for r in records), 6),
        "by_provider": by_provider,
    }


# --------------------------------------------------------------------------
# Semantic review -- a second model scoring what the rules cannot see
# --------------------------------------------------------------------------
#
# The rule engine in `rules.py` is lexical: it can tell you a requirement
# says "shall" and avoids "user-friendly", but not whether it bundles three
# needs into one sentence or states something no test could ever falsify.
# Those are the defects that survive a clean rule pass and reach a design
# review.
#
# Scoring the same requirements on criteria a regex cannot reach lets the
# two signals be compared. Where they disagree -- a requirement the rules
# pass and the judge fails -- is the interesting set, because it bounds
# what lexical validation is worth.

CRITERIA = ["singular", "verifiable", "implementation_free", "unambiguous", "necessary"]

# Below this mean, a requirement is worth a human's attention regardless of
# whether it passed the lexical rules.
CONCERN_THRESHOLD = 3.5


def normalize_review(item: dict) -> dict:
    scores = {}
    for c in CRITERIA:
        raw = item.get(c)
        if raw is None:
            # absent is not the same as bad -- score 0 marks it ungraded so
            # it drops out of the mean instead of dragging it to the floor
            scores[c] = 0
            continue
        try:
            scores[c] = max(1, min(5, int(raw)))
        except (TypeError, ValueError):
            scores[c] = 0
    graded = [v for v in scores.values() if v > 0]
    return {
        "index": item.get("index"),
        **scores,
        "mean": round(sum(graded) / len(graded), 2) if graded else 0.0,
        "comment": str(item.get("comment", ""))[:300],
    }


def summarize_reviews(reviews: List[dict], rule_failures: Dict[int, List[str]]) -> dict:
    """Cross-tabulate the judge against the rule engine.

    `rule_failures` maps requirement index to the lexical violations it has,
    so an empty list means the rules passed it.
    """
    if not reviews:
        return {
            "reviewed": 0,
            "criteria_means": {c: 0.0 for c in CRITERIA},
            "mean_score": 0.0,
            "flagged": [],
            "passed_rules_but_judge_flagged": 0,
        }

    criteria_means = {
        c: round(sum(r[c] for r in reviews) / len(reviews), 2) for c in CRITERIA
    }

    flagged = [r for r in reviews if r["mean"] and r["mean"] < CONCERN_THRESHOLD]

    # the set that matters: clean on the rules, weak on substance
    blind_spot = sum(
        1
        for r in flagged
        if not rule_failures.get(r["index"], [])
    )

    return {
        "reviewed": len(reviews),
        "criteria_means": criteria_means,
        "mean_score": round(sum(r["mean"] for r in reviews) / len(reviews), 2),
        "flagged": flagged,
        "passed_rules_but_judge_flagged": blind_spot,
    }
