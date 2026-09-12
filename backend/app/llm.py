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


class LLMError(Exception):
    pass


def provider_for(model: str) -> str:
    return "anthropic" if model.startswith("claude-") else "ollama"


async def generate_json(prompt: str, model: str) -> LLMResult:
    # Imported here rather than at module scope so the client modules can
    # import LLMResult from this module without a circular import.
    if provider_for(model) == "anthropic":
        from . import anthropic_client

        return await anthropic_client.generate_json(prompt, model)

    from . import ollama_client

    return await ollama_client.generate_json(prompt, model)
