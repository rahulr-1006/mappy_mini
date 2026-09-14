"""Retrieval. Chunking, embedding, and scoring, with a lexical fallback for
when the embedding model is unreachable. No database dependency, so it can
be tested on its own.
"""

from __future__ import annotations

import math
import re
import struct
from dataclasses import dataclass
from typing import List, Sequence

import httpx

from . import config

EMBED_MODEL = "nomic-embed-text"

DOC_CHUNK_WORDS = 180
DOC_CHUNK_OVERLAP = 40

DEFAULT_TOP_K = 6

MIN_SCORE = 0.30

LEXICAL_MIN_SCORE = 0.12


class EmbeddingUnavailable(Exception):
    pass


@dataclass
class Chunk:
    source_kind: str
    source_id: str
    source_name: str
    text: str
    score: float = 0.0

    def citation(self) -> str:
        return f"{self.source_name}" if self.source_kind == "document" else f"model:{self.source_name}"


def pack(vector: Sequence[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def unpack(blob: bytes) -> List[float]:
    return list(struct.unpack(f"{len(blob) // 4}f", blob))


async def embed(texts: Sequence[str]) -> List[List[float]]:
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


_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "on", "with",
    "is", "are", "be", "shall", "at", "by", "from", "as", "that", "this",
    "it", "its", "which", "will", "must",
}


def _terms(text: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOPWORDS and len(t) > 2]


def lexical_score(query: str, text: str) -> float:
    q, d = set(_terms(query)), set(_terms(text))
    if not q or not d:
        return 0.0
    return len(q & d) / len(q)


def _pack_paragraphs(paragraphs: List[str], prefix: str = "") -> List[str]:
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
        for i in range(0, len(words), DOC_CHUNK_WORDS):
            out.append(" ".join(words[i : i + DOC_CHUNK_WORDS]))

    return [f"{prefix}\n\n{c}" if prefix else c for c in out if c.strip()]


def chunk_document(text: str) -> List[str]:
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

    if not any(h for h, _ in sections):
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        return _pack_paragraphs(paragraphs, prefix=title)

    out: List[str] = []
    for heading, body_lines in sections:
        content = "\n".join(body_lines).strip()
        if not content:
            continue
        prefix = ": ".join(p for p in (title, heading) if p)
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
        out.extend(_pack_paragraphs(paragraphs, prefix=prefix))
    return out


def chunk_model_element(element: dict) -> str:
    return (
        f"REQUIREMENT [{element.get('stereotype', '')}] {element.get('name', '')}\n"
        f"Verified by: {element.get('verifyMethod', '')}\n"
        f"{element.get('text', '')}"
    )


def chunk_block(block: dict, connectors: Sequence[dict], blocks: Sequence[dict]) -> str:
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


async def rank(
    query: str,
    candidates: List[dict],
    top_k: int = DEFAULT_TOP_K,
    min_score: float = MIN_SCORE,
) -> tuple[List[Chunk], str]:
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

    floor = min_score if method == "embedding" else LEXICAL_MIN_SCORE
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
    if not chunks:
        return ""
    parts = [
        f"[{i + 1}] source: {c.citation()}\n{c.text}" for i, c in enumerate(chunks)
    ]
    return "\n\n".join(parts)
