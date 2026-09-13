from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .llm import generate_json
from .routes import (
    activity_log,
    diagram,
    evaluations,
    model_elements,
    models,
    requirements,
    traces,
)

app = FastAPI(title="Mini-MAPPy backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(requirements.router)
app.include_router(models.router)
app.include_router(model_elements.router)
app.include_router(activity_log.router)
app.include_router(diagram.router)
app.include_router(evaluations.router)
app.include_router(traces.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/dev/ollama-roundtrip")
async def ollama_roundtrip():
    prompt = (
        "Return a JSON array containing one object with fields "
        "stereotype, name, text, verifyMethod, describing a made-up "
        "functional requirement for a coffee maker."
    )
    result = await generate_json(prompt, config.DEFAULT_MODEL)
    return {"model": config.DEFAULT_MODEL, "raw_response": result.text}
