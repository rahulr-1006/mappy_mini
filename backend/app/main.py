from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import (
    activity_log,
    chat,
    diagram,
    documents,
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
app.include_router(chat.router)
app.include_router(documents.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
