import re
import time

import anthropic

from . import config
from .llm import LLMError, LLMResult

_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$")

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


def _strip_fences(text: str) -> str:
    """Claude tends to wrap JSON in a markdown code fence; Ollama's
    format="json" mode never does. Strip it so both providers hand the
    same shape to the existing parsers."""
    return _FENCE.sub("", text).strip()


async def generate_json(prompt: str, model: str) -> LLMResult:
    client = _get_client()
    started = time.perf_counter()

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=16000,
            messages=[{"role": "user", "content": prompt}],
        )
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

    return LLMResult(
        text=_strip_fences(text),
        prompt_tokens=response.usage.input_tokens,
        completion_tokens=response.usage.output_tokens,
        duration_ms=duration_ms,
    )
