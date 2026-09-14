"""The failure the source material names: a model wraps its array in prose
and the parser rejects the whole batch. Detection was already there; these
cover the recovery."""

import asyncio

import pytest

from app.evaluation import MetricsAccumulator
from app.llm import LLMError, LLMResult
from app.routes import requirements as req_route

GOOD = '[{"stereotype": "functionalRequirement", "name": "A thing", "text": "shall", "verifyMethod": "Test"}]'
PREAMBLE = "Certainly! Here are the requirements you asked for:\n\n" + GOOD


def _run(text, replies, monkeypatch):
    """Drive the recovery with a scripted sequence of model replies."""
    notes = []
    calls = {"n": 0}

    async def fake_generate(prompt, model, system=None):
        calls["n"] += 1
        if not replies:
            raise LLMError("no more scripted replies")
        return LLMResult(text=replies.pop(0), prompt_tokens=1, completion_tokens=1, duration_ms=1.0)

    monkeypatch.setattr(req_route, "generate_json", fake_generate)
    acc = MetricsAccumulator(task="requirements", model="test-model")
    items, retries = asyncio.run(
        req_route._parse_with_recovery(text, "test-model", acc, notes.append)
    )
    return items, retries, notes, calls["n"]


def test_clean_json_needs_no_retry(monkeypatch):
    items, retries, notes, calls = _run(GOOD, [], monkeypatch)

    assert len(items) == 1
    assert retries == 0
    assert calls == 0
    assert notes == []


def test_prose_around_the_array_is_recovered(monkeypatch):
    # the exact failure mode the source material reported
    items, retries, notes, calls = _run(PREAMBLE, [GOOD], monkeypatch)

    assert len(items) == 1
    assert items[0]["name"] == "A thing"
    assert retries == 1
    assert calls == 1
    assert "format only (attempt 1)" in notes[0]


def test_recovery_is_bounded_and_gives_up_cleanly(monkeypatch):
    items, retries, notes, calls = _run(
        "not json at all", ["still not json", "nor this"], monkeypatch
    )

    # bounded by MAX_FORMAT_RETRIES rather than looping on a model that
    # will not comply
    assert items is None
    assert retries == 2
    assert calls == 2
    assert "after 2 format retry(ies)" in notes[-1]


def test_a_failed_retry_call_does_not_raise(monkeypatch):
    # the model being unreachable mid-recovery is an ordinary outcome
    items, retries, notes, calls = _run(PREAMBLE, [], monkeypatch)

    assert items is None
    assert "ERROR during format retry" in notes[-1]


def test_retries_are_counted_in_the_metrics(monkeypatch):
    notes = []

    async def fake_generate(prompt, model, system=None):
        return LLMResult(text=GOOD, prompt_tokens=7, completion_tokens=11, duration_ms=5.0)

    monkeypatch.setattr(req_route, "generate_json", fake_generate)
    acc = MetricsAccumulator(task="requirements", model="test-model")
    asyncio.run(req_route._parse_with_recovery(PREAMBLE, "test-model", acc, notes.append))

    # the repair cost real tokens; hiding them would understate the run
    assert acc.llm_calls == 1
    assert acc.prompt_tokens == 7
