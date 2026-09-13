"""Wires the chunking and scoring in `rag` to the database in `storage`.

Kept separate so `rag` stays pure and testable without a database, and so
there is one place that decides when the index gets rewritten.
"""

from __future__ import annotations

import uuid
from typing import List, Optional, Sequence

from . import rag, storage
from .rag import Chunk, EmbeddingUnavailable

MODEL_SOURCE_ID = "current"


async def _embedded_rows(texts: Sequence[str], source_name: str) -> tuple[List[dict], bool]:
    """Build chunk rows, embedding the batch if the model is reachable. The
    flag says whether embeddings actually happened, so the caller can log
    what is true rather than what was intended."""
    rows = [
        {"id": str(uuid.uuid4()), "source_name": source_name, "text": t, "embedding": None}
        for t in texts
    ]
    if not rows:
        return rows, False
    try:
        vectors = await rag.embed(texts)
    except EmbeddingUnavailable:
        return rows, False
    for row, vec in zip(rows, vectors):
        row["embedding"] = rag.pack(vec)
    return rows, True


async def index_document(doc_id: str, name: str, content: str) -> dict:
    chunks = rag.chunk_document(content)
    rows, embedded = await _embedded_rows(chunks, name)
    storage.replace_chunks("document", doc_id, rows)
    return {"chunks": len(rows), "embedded": embedded}


async def reindex_model() -> dict:
    """Re-chunk the MBSE model as it now stands. Cheap enough to run on
    every write: a model of this size is tens of chunks, and an index that
    silently lags the model is worse than no index at all."""
    elements = storage.list_model_elements()
    diagram = storage.get_diagram()
    blocks = diagram.get("blocks", [])
    connectors = diagram.get("connectors", [])

    texts: List[str] = []
    names: List[str] = []

    for el in elements:
        texts.append(rag.chunk_model_element(el))
        names.append(el.get("name", "requirement"))
    for block in blocks:
        texts.append(rag.chunk_block(block, connectors, blocks))
        names.append(block.get("name", "block"))

    rows: List[dict] = []
    embedded = False
    if texts:
        rows, embedded = await _embedded_rows(texts, "")
        for row, name in zip(rows, names):
            row["source_name"] = name

    storage.replace_chunks("model", MODEL_SOURCE_ID, rows)
    return {
        "chunks": len(rows),
        "embedded": embedded,
        "requirements": len(elements),
        "blocks": len(blocks),
    }


async def retrieve(
    query: str,
    top_k: int = rag.DEFAULT_TOP_K,
    source_kind: Optional[str] = None,
) -> tuple[List[Chunk], str]:
    """Returns the chunks worth putting in a prompt, and the method that
    found them ("embedding", "lexical", or "empty")."""
    if not query.strip():
        return [], "empty"
    candidates = storage.list_chunks(source_kind)
    return await rag.rank(query, candidates, top_k=top_k)


def describe(chunks: Sequence[Chunk], method: str) -> str:
    """One activity-log line describing what retrieval actually did, named
    down to the sources, so a reader can check the claim."""
    if not chunks:
        return f"Retrieved no relevant context ({method})."
    docs = sum(1 for c in chunks if c.source_kind == "document")
    model = len(chunks) - docs
    names = ", ".join(dict.fromkeys(c.citation() for c in chunks))
    return (
        f"Retrieved {len(chunks)} chunk(s) by {method} search "
        f"({docs} from documents, {model} from the model): {names}."
    )
