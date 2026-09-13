import asyncio

import pytest

from app import rag


def test_heading_aware_chunking_keeps_sections_separate():
    doc = (
        "# Site Specification\n\n"
        "## 1. Power\n\n"
        "The UPS carries the station load for 20 minutes.\n\n"
        "## 2. Cooling\n\n"
        "The equipment room is held between 18 and 27 degrees.\n"
    )
    chunks = rag.chunk_document(doc)

    assert len(chunks) == 2
    # each chunk carries the document title and its own heading, so a
    # passage stays interpretable once it is out of context
    assert all(c.startswith("Site Specification — ") for c in chunks)
    power = next(c for c in chunks if "20 minutes" in c)
    assert "18 and 27 degrees" not in power


def test_chunking_falls_back_to_paragraphs_without_headings():
    doc = "\n\n".join(f"Paragraph {i} with enough words to matter here." for i in range(40))
    chunks = rag.chunk_document(doc)

    assert len(chunks) > 1
    assert all(len(c.split()) <= rag.DOC_CHUNK_WORDS * 2 for c in chunks)


def test_empty_document_produces_no_chunks():
    assert rag.chunk_document("") == []
    assert rag.chunk_document("   \n\n  ") == []


def test_model_element_chunk_includes_what_makes_it_findable():
    chunk = rag.chunk_model_element(
        {
            "stereotype": "performanceRequirement",
            "name": "Antenna pointing",
            "text": "The antenna shall hold 0.1 degrees.",
            "verifyMethod": "Test",
        }
    )
    assert "performanceRequirement" in chunk
    assert "Test" in chunk
    assert "0.1 degrees" in chunk


def test_block_chunk_folds_in_its_interfaces():
    blocks = [
        {"id": "root", "name": "Ground Station", "description": "the whole thing"},
        {"id": "pwr", "name": "Power System", "description": "supplies power"},
    ]
    connectors = [
        {"id": "c1", "source": "root", "target": "pwr", "kind": "composition", "label": "electrical power"}
    ]
    chunk = rag.chunk_block(blocks[1], connectors, blocks)

    assert "Power System" in chunk
    # the edge is named from the block's own perspective, with the far end
    # resolved to a name rather than an opaque id
    assert "Ground Station" in chunk
    assert "electrical power" in chunk


def test_pack_unpack_round_trips_a_vector():
    vector = [0.5, -0.25, 0.125]
    assert rag.unpack(rag.pack(vector)) == pytest.approx(vector)


def test_cosine_handles_degenerate_input():
    assert rag.cosine([], [1.0]) == 0.0
    assert rag.cosine([0.0, 0.0], [1.0, 1.0]) == 0.0
    assert rag.cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_lexical_score_ignores_stopwords():
    # "the" and "shall" carry no signal, so a match on them alone scores zero
    assert rag.lexical_score("the shall", "the system shall") == 0.0
    assert rag.lexical_score("antenna pointing", "antenna pointing accuracy") > 0.9


def test_rank_falls_back_to_lexical_when_embeddings_are_unavailable(monkeypatch):
    async def unavailable(_texts):
        raise rag.EmbeddingUnavailable("ollama is down")

    monkeypatch.setattr(rag, "embed", unavailable)

    candidates = [
        {"source_kind": "document", "source_id": "d1", "source_name": "spec.md",
         "text": "The diesel generator reaches rated output within 45 seconds.", "embedding": None},
        {"source_kind": "document", "source_id": "d1", "source_name": "spec.md",
         "text": "Crew handover occurs at 0600 and 1800 local time.", "embedding": None},
    ]
    chunks, method = asyncio.run(rag.rank("diesel generator output", candidates))

    assert method == "lexical"
    assert chunks and "diesel generator" in chunks[0].text


def test_rank_on_an_empty_index_returns_nothing():
    chunks, method = asyncio.run(rag.rank("anything", []))
    assert chunks == []
    assert method == "empty"


def test_format_context_labels_each_passage_with_its_source():
    chunks = [
        rag.Chunk("document", "d1", "icd.md", "S-band downlink at 2.0 Mbps."),
        rag.Chunk("model", "current", "Antenna pointing", "REQUIREMENT ..."),
    ]
    out = rag.format_context(chunks)

    assert "[1] source: icd.md" in out
    # model-sourced context is marked as such, so the model can tell a
    # project document from something it wrote itself twenty minutes ago
    assert "[2] source: model:Antenna pointing" in out


def test_format_context_is_empty_when_nothing_was_retrieved():
    assert rag.format_context([]) == ""
