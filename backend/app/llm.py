"""Provider-neutral LLM entry point.

Routes a generation to either local Ollama or the hosted Anthropic API
based on the model id, so the same generation pipeline (and the same
evaluation metrics) work against either provider.
"""

from dataclasses import dataclass


@dataclass
class LLMResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    duration_ms: float
    # Providers that cache a stable prompt prefix report these; Ollama
    # does not, so they stay zero for local generation.
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class LLMError(Exception):
    pass


def provider_for(model: str) -> str:
    return "anthropic" if model.startswith("claude-") else "ollama"


async def generate_json(prompt: str, model: str, system: str | None = None) -> LLMResult:
    # Imported here rather than at module scope so the client modules can
    # import LLMResult from this module without a circular import.
    if provider_for(model) == "anthropic":
        from . import anthropic_client

        return await anthropic_client.generate_json(prompt, model, system)

    from . import ollama_client

    return await ollama_client.generate_json(prompt, model, system)
