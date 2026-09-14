"""Retrieval over the two knowledge sources the architecture calls for:
system documents the engineer uploads, and the MBSE model this tool is
itself building.

Both are chunked into the same index, so a query can pull a paragraph of
an ICD and a requirement written twenty minutes ago in the same result
set. Elements committed to the model are re-indexed on write, which is
what closes the loop: what MAPPy generates becomes what MAPPy retrieves.

Embeddings run locally through Ollama. When that is unavailable the index
falls back to lexical scoring rather than failing -- retrieval that is
merely good is better than a demo that cannot answer.
"""

from __future__ import annotations

import math
import re
import struct
from dataclasses import dataclass
from typing import List, Sequence

import httpx

from . import config

# Small, fast, and good enough for paragraph-scale technical prose. Pulled
# with `ollama pull nomic-embed-text`.
EMBED_MODEL = "nomic-embed-text"

# Chunk sizes are in words. Requirements and blocks are short enough to be
# their own chunk; prose documents get split with overlap so a sentence
# spanning a boundary is still reachable from either side.
DOC_CHUNK_WORDS = 180
DOC_CHUNK_OVERLAP = 40

DEFAULT_TOP_K = 6

# Below this cosine similarity a chunk is noise rather than context, and
# padding the prompt with noise is how a grounded answer turns into a
# confidently wrong one.
MIN_SCORE = 0.30


class EmbeddingUnavailable(Exception):
    pass


@dataclass
class Chunk:
    source_kind: str  # "document" | "model"
    source_id: str
    source_name: str
    text: str
    score: float = 0.0

    def citation(self) -> str:
        return f"{self.source_name}" if self.source_kind == "document" else f"model:{self.source_name}"


# --- embedding ---------------------------------------------------------------


def pack(vector: Sequence[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def unpack(blob: bytes) -> List[float]:
    return list(struct.unpack(f"{len(blob) // 4}f", blob))


async def embed(texts: Sequence[str]) -> List[List[float]]:
    """Embed a batch. Raises EmbeddingUnavailable so callers can decide
    whether to fall back rather than having that choice made for them."""
    if not texts:
        return []
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{config.OLLAMA_HOST}/api/embed",
                json={"model": EMBED_MODEL, "input": list(texts)},
            )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise EmbeddingUnavailable(str(exc)) from exc

    vectors = data.get("embeddings")
    if not vectors or len(vectors) != len(texts):
        raise EmbeddingUnavailable("embedding response did not match the batch")
    return vectors


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# --- lexical fallback --------------------------------------------------------

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with",
    "is", "are", "be", "shall", "at", "by", "from", "as", "that", "this",
    "it", "its", "which", "will", "must",
}


def _terms(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOPWORDS and len(t) > 2]


def lexical_score(query: str, text: str) -> float:
    """Overlap coefficient over content terms. Crude next to embeddings,
    but it degrades gracefully and never returns a confident wrong answer."""
    q, d = set(_terms(query)), set(_terms(text))
    if not q or not d:
        return 0.0
    return len(q & d) / len(q)


# --- chunking ----------------------------------------------------------------


def _pack_paragraphs(paragraphs: List[str], prefix: str = "") -> List[str]:
    """Pack paragraphs up to the target size so a chunk is a coherent
    passage rather than a fixed slice, carrying an overlap so a passage
    split across a boundary stays reachable from the following chunk."""
    chunks: List[str] = []
    current: List[str] = []
    count = 0

    for para in paragraphs:
        words = para.split()
        if count + len(words) > DOC_CHUNK_WORDS and current:
            chunks.append("\n\n".join(current))
            tail = " ".join("\n\n".join(current).split()[-DOC_CHUNK_OVERLAP:])
            current, count = ([tail] if tail else []), len(tail.split())
        current.append(para)
        count += len(words)

    if current:
        chunks.append("\n\n".join(current))

    out: List[str] = []
    for c in chunks:
        words = c.split()
        if len(words) <= DOC_CHUNK_WORDS * 2:
            out.append(c)
            continue
        # a single oversized paragraph still has to be broken somewhere
        for i in range(0, len(words), DOC_CHUNK_WORDS):
            out.append(" ".join(words[i : i + DOC_CHUNK_WORDS]))

    return [f"{prefix}\n\n{c}" if prefix else c for c in out if c.strip()]


def chunk_document(text: str) -> List[str]:
    """Split on section headings where the document has them.

    Engineering documents are written in sections precisely because each one
    covers a separable concern, so a heading boundary is a better chunk
    boundary than any word count. Every chunk is prefixed with the document
    title and its own heading: without that, a chunk about a 20 minute
    holding time does not say what is being held up, and retrieval on
    "backup power" never finds it.
    """
    lines = text.splitlines()
    title = next((l.lstrip("# ").strip() for l in lines if l.startswith("# ")), "")

    sections: List[tuple[str, List[str]]] = []
    heading = ""
    body: List[str] = []
    for line in lines:
        if re.match(r"^#{2,3} ", line):
            if body:
                sections.append((heading, body))
            heading = re.sub(r"^#+\s*", "", line).strip()
            body = []
        elif line.startswith("# "):
            continue
        else:
            body.append(line)
    if body:
        sections.append((heading, body))

    # no headings at all, or headings that carve out nothing: treat as prose
    if not any(h for h, _ in sections):
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        return _pack_paragraphs(paragraphs, prefix=title)

    out: List[str] = []
    for heading, body_lines in sections:
        content = "\n".join(body_lines).strip()
        if not content:
            continue
        prefix = " — ".join(p for p in (title, heading) if p)
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
        out.extend(_pack_paragraphs(paragraphs, prefix=prefix))
    return out


def chunk_model_element(element: dict) -> str:
    """One requirement, one chunk. The stereotype and verify method are
    part of the text because they are part of what makes it findable --
    'which requirements are verified by test' is a real query."""
    return (
        f"REQUIREMENT [{element.get('stereotype', '')}] {element.get('name', '')}\n"
        f"Verified by: {element.get('verifyMethod', '')}\n"
        f"{element.get('text', '')}"
    )


def chunk_block(block: dict, connectors: Sequence[dict], blocks: Sequence[dict]) -> str:
    """A block on its own says little. A block plus the interfaces it sits
    on is the unit an engineer actually reasons about, so the edges are
    folded into the block's own chunk."""
    names = {b["id"]: b.get("name", b["id"]) for b in blocks}
    lines = [
        f"BLOCK {block.get('name', '')}" + (" (root system)" if block.get("isRoot") else ""),
        block.get("description", ""),
    ]
    edges = [
        f"  - {names.get(c['source'], c['source'])} --{c.get('kind', '')}--> "
        f"{names.get(c['target'], c['target'])}: {c.get('label', '')}"
        for c in connectors
        if c.get("source") == block["id"] or c.get("target") == block["id"]
    ]
    if edges:
        lines.append("Interfaces:")
        lines.extend(edges)
    return "\n".join(l for l in lines if l.strip())


# --- retrieval ---------------------------------------------------------------


async def rank(
    query: str,
    candidates: List[dict],
    top_k: int = DEFAULT_TOP_K,
    min_score: float = MIN_SCORE,
) -> tuple[List[Chunk], str]:
    """Score candidate chunks against the query. Returns the surviving
    chunks and which method produced them, so the caller can say so in the
    log rather than implying embeddings that did not run."""
    if not candidates:
        return [], "empty"

    method = "embedding"
    scored: List[Chunk] = []

    try:
        [query_vec] = await embed([query])
        for row in candidates:
            vec = unpack(row["embedding"]) if row.get("embedding") else None
            score = cosine(query_vec, vec) if vec else 0.0
            scored.append(_chunk(row, score))
    except EmbeddingUnavailable:
        method = "lexical"
        scored = [_chunk(row, lexical_score(query, row["text"])) for row in candidates]

    # a lexical overlap coefficient and a cosine similarity are not on the
    # same scale, so the floor has to move with the method
    floor = min_score if method == "embedding" else 0.12
    scored.sort(key=lambda c: c.score, reverse=True)
    return [c for c in scored[:top_k] if c.score >= floor], method


def _chunk(row: dict, score: float) -> Chunk:
    return Chunk(
        source_kind=row["source_kind"],
        source_id=row["source_id"],
        source_name=row["source_name"],
        text=row["text"],
        score=score,
    )


def format_context(chunks: Sequence[Chunk]) -> str:
    """Render retrieved chunks for a prompt, labelled so the model can cite
    where something came from and so a reader can check it."""
    if not chunks:
        return ""
    parts = [
        f"[{i + 1}] source: {c.citation()}\n{c.text}" for i, c in enumerate(chunks)
    ]
    return "\n\n".join(parts)
