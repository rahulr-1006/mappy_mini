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

# The Batch API runs the same requests asynchronously at half price, which
# is the relevant comparison for bulk document generation.
BATCH_DISCOUNT = 0.5


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
