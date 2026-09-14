"""One entry point for generation. Dispatches on the model id: claude-*
goes to the Anthropic API, anything else goes to local Ollama. Both
return the same LLMResult so the rest of the pipeline does not care.

The Anthropic system prompt is marked cacheable, but at current prompt
lengths it does not cache: the prefix is below the model's minimum, so
cache_read_tokens and cache_write_tokens stay zero. It is left in because
it starts working on its own if the instructions grow.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass

import anthropic
import httpx

from . import config


@dataclass
class LLMResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    duration_ms: float
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class LLMError(Exception):
    pass


def provider_for(model: str) -> str:
    return "anthropic" if model.startswith("claude-") else "ollama"


async def generate_json(prompt: str, model: str, system: str | None = None) -> LLMResult:
    if provider_for(model) == "anthropic":
        return await _anthropic_generate(prompt, model, system)
    return await _ollama_generate(prompt, model, system)


async def _ollama_generate(prompt: str, model: str, system: str | None) -> LLMResult:
    body = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }
    if system:
        body["system"] = system

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{config.OLLAMA_HOST}/api/generate", json=body)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise LLMError(f"Ollama request failed: {exc}") from exc

    data = resp.json()
    return LLMResult(
        text=data["response"],
        prompt_tokens=data.get("prompt_eval_count", 0),
        completion_tokens=data.get("eval_count", 0),
        duration_ms=data.get("total_duration", 0) / 1e6,
    )


_FENCE_OPEN = re.compile(r"^\s*```(?:json)?\s*", re.IGNORECASE)

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        if not config.ANTHROPIC_API_KEY:
            raise LLMError(
                "ANTHROPIC_API_KEY is not set -- add it to backend/.env to use Claude models."
            )
        _client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def _extract_json(text: str) -> str:
    body = _FENCE_OPEN.sub("", text.strip())
    start = min(
        (i for i in (body.find("{"), body.find("[")) if i != -1),
        default=-1,
    )
    if start == -1:
        return body.strip()
    try:
        value, _ = json.JSONDecoder().raw_decode(body[start:])
    except json.JSONDecodeError:
        return body[start:].strip()
    return json.dumps(value)


async def _anthropic_generate(prompt: str, model: str, system: str | None) -> LLMResult:
    client = _get_client()
    started = time.perf_counter()

    kwargs = {
        "model": model,
        "max_tokens": 16000,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    try:
        response = await client.messages.create(**kwargs)
    except anthropic.AuthenticationError as exc:
        raise LLMError("Anthropic rejected the API key (401).") from exc
    except anthropic.RateLimitError as exc:
        raise LLMError("Anthropic rate limit hit (429).") from exc
    except anthropic.APIStatusError as exc:
        raise LLMError(f"Anthropic API error {exc.status_code}: {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise LLMError(f"Could not reach the Anthropic API: {exc}") from exc

    duration_ms = (time.perf_counter() - started) * 1000

    if response.stop_reason == "refusal":
        raise LLMError("Anthropic declined the request (stop_reason=refusal).")

    text = "".join(block.text for block in response.content if block.type == "text")

    usage = response.usage
    return LLMResult(
        text=_extract_json(text),
        prompt_tokens=usage.input_tokens,
        completion_tokens=usage.output_tokens,
        duration_ms=duration_ms,
        cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
        cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
    )
