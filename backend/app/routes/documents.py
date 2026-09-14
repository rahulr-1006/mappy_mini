import os
import uuid
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile

from .. import knowledge, storage

router = APIRouter(prefix="/documents", tags=["documents"])

SEED_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "seed_docs")

# Uploads are read into memory and chunked, so the ceiling is about keeping
# a stray binary from becoming a 50MB row rather than about disk.
MAX_UPLOAD_BYTES = 2_000_000


def _decode(raw: bytes, name: str) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        # a PDF or a Word file lands here; say so plainly rather than
        # indexing mojibake that will surface as nonsense in retrieval
        raise HTTPException(
            status_code=415,
            detail=(
                f"{name} is not UTF-8 text. Convert it to .txt or .md before "
                f"uploading -- binary formats are not parsed."
            ),
        )


@router.get("")
async def list_documents():
    return {"documents": storage.list_documents(), "index": storage.index_stats()}


@router.get("/index")
async def index_status():
    return storage.index_stats()


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than 2 MB.")
    name = file.filename or "untitled"
    content = _decode(raw, name)
    if not content.strip():
        raise HTTPException(status_code=400, detail=f"{name} is empty.")
    return await _ingest(name, content, origin="upload")


async def _ingest(name: str, content: str, origin: str) -> dict:
    if storage.document_name_exists(name):
        name = f"{name} ({uuid.uuid4().hex[:6]})"
    doc_id = str(uuid.uuid4())
    storage.add_document(doc_id, name, content, origin=origin)
    result = await knowledge.index_document(doc_id, name, content)
    storage.log_event(
        f"Indexed document {name!r}: {result['chunks']} chunk(s), "
        + ("embedded." if result["embedded"] else "no embedding model, lexical only.")
    )
    return {
        "document": {"id": doc_id, "name": name, "origin": origin, **result},
        "index": storage.index_stats(),
    }


@router.post("/seed")
async def seed_documents():
    """Load the bundled reference corpus. Idempotent by name, so pressing it
    twice does not give you the corpus twice."""
    added: List[dict] = []
    if not os.path.isdir(SEED_DIR):
        raise HTTPException(status_code=500, detail="Seed corpus is missing from the install.")

    for filename in sorted(os.listdir(SEED_DIR)):
        if not filename.endswith((".md", ".txt")):
            continue
        if storage.document_name_exists(filename):
            continue
        with open(os.path.join(SEED_DIR, filename)) as f:
            content = f.read()
        doc_id = str(uuid.uuid4())
        storage.add_document(doc_id, filename, content, origin="seed")
        result = await knowledge.index_document(doc_id, filename, content)
        added.append({"id": doc_id, "name": filename, **result})

    storage.log_event(
        f"Seeded the knowledge base with {len(added)} reference document(s)."
        if added
        else "Seed corpus already loaded; nothing added."
    )
    return {"added": added, "index": storage.index_stats()}


@router.post("/reindex")
async def reindex():
    """Re-chunk and re-embed everything. Use after pulling the embedding
    model, to upgrade an index built while it was unavailable."""
    docs = storage.list_documents(include_content=True)
    total = 0
    embedded_all = True
    for doc in docs:
        result = await knowledge.index_document(doc["id"], doc["name"], doc["content"])
        total += result["chunks"]
        embedded_all = embedded_all and result["embedded"]

    model = await knowledge.reindex_model()
    storage.log_event(
        f"Rebuilt the index: {total} document chunk(s) from {len(docs)} document(s), "
        f"{model['chunks']} model chunk(s)."
        + ("" if embedded_all and model["embedded"] else " Embedding model was unreachable for part of it.")
    )
    return storage.index_stats()


@router.post("/search")
async def search(payload: dict):
    """Exposed so the retrieval step can be shown on its own, rather than
    only ever being visible as its effect on a generation."""
    query = str(payload.get("query", ""))
    chunks, method = await knowledge.retrieve(query, top_k=int(payload.get("top_k", 6)))
    return {
        "method": method,
        "results": [
            {
                "source_kind": c.source_kind,
                "source_name": c.source_name,
                "score": round(c.score, 4),
                "text": c.text,
            }
            for c in chunks
        ],
    }


@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    doc = storage.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="No such document.")
    storage.delete_document(doc_id)
    storage.log_event(f"Removed document {doc['name']!r} from the knowledge base.")
    return {"documents": storage.list_documents(), "index": storage.index_stats()}
