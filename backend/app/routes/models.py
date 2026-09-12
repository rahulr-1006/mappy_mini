import httpx
from fastapi import APIRouter

from .. import config

router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
async def list_models():
    """Local Ollama models actually pulled on this machine, plus the hosted
    Anthropic models when an API key is configured."""
    names: list = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{config.OLLAMA_HOST}/api/tags")
            resp.raise_for_status()
            names = [m["name"] for m in resp.json().get("models", [])]
    except httpx.HTTPError:
        pass

    ordered = [m for m in config.AVAILABLE_MODELS if m in names]
    ordered += [m for m in names if m not in ordered]
    local = ordered or config.AVAILABLE_MODELS

    hosted = config.ANTHROPIC_MODELS if config.ANTHROPIC_API_KEY else []

    return {
        "models": local + hosted,
        "default": config.DEFAULT_MODEL,
        "local": local,
        "hosted": hosted,
    }
