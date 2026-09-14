"""The FastAPI app, plus the few endpoints small enough to live here."""

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config, storage
from .routes import chat, diagram, documents, evaluations, model_elements, requirements, traces

app = FastAPI(title="Mini-MAPPy backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(requirements.router)
app.include_router(model_elements.router)
app.include_router(diagram.router)
app.include_router(evaluations.router)
app.include_router(traces.router)
app.include_router(chat.router)
app.include_router(documents.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/activity-log")
async def activity_log():
    return storage.get_activity_log()


@app.get("/models")
async def list_models():
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
