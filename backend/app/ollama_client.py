import httpx

from . import config
from .llm import LLMError, LLMResult


class OllamaError(LLMError):
    pass


async def generate_json(prompt: str, model: str, system: str | None = None) -> LLMResult:
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
        raise OllamaError(f"Ollama request failed: {exc}") from exc

    data = resp.json()
    return LLMResult(
        text=data["response"],
        prompt_tokens=data.get("prompt_eval_count", 0),
        completion_tokens=data.get("eval_count", 0),
        duration_ms=data.get("total_duration", 0) / 1e6,
    )
