import json
import re
import time

import anthropic

from . import config
from .llm import LLMError, LLMResult

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
    """Return just the JSON value from a chat response.

    Ollama's format="json" mode guarantees the body is nothing but JSON.
    The Messages API has no such switch, so Claude may wrap the JSON in a
    markdown fence and follow it with commentary explaining its reasoning.
    Decoding the first complete value and ignoring the rest handles the
    fence, the trailing prose, and both together.
    """
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
        # let the caller's parser produce the error message
        return body[start:].strip()
    return json.dumps(value)


async def generate_json(prompt: str, model: str, system: str | None = None) -> LLMResult:
    client = _get_client()
    started = time.perf_counter()

    kwargs = {
        "model": model,
        "max_tokens": 16000,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        # The instructions are byte-identical on every call, so mark them
        # cacheable. Caching is a prefix match -- this only pays off because
        # the volatile half of the prompt lives in `messages`, after it.
        #
        # Measured 2026-09-13: this currently no-ops. A prefix shorter than
        # the model's minimum cacheable length is silently not cached, and
        # our instructions are ~700-930 tokens. Probing with a padded
        # prompt confirmed the plumbing is right -- Sonnet 5 at ~4.5k tokens
        # wrote the cache on the first call and read it back on the second
        # (input tokens 932 -> 14). Haiku 4.5 did not cache even at ~2.5k,
        # so its minimum is higher still.
        #
        # Deliberately not padding the prompt to cross that threshold:
        # paying for thousands of filler input tokens to unlock a discount
        # on those same tokens is a net loss. This becomes worthwhile if the
        # instructions genuinely grow -- few-shot examples, or the INCOSE
        # rule text inline -- at which point it starts working for free.
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
