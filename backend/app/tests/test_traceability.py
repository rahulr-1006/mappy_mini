from app.traceability import compute_coverage, validate_trace

REQS = [
    {"id": "r1", "name": "Landing legs", "stereotype": "functionalRequirement"},
    {"id": "r2", "name": "Descent rate", "stereotype": "performanceRequirement"},
]
BLOCKS = [
    {"id": "b0", "name": "Launch Vehicle", "isRoot": True},
    {"id": "b1", "name": "Recovery"},
    {"id": "b2", "name": "Ground Ops"},
]


def test_validate_trace_accepts_a_well_formed_link():
    link = {"requirement_id": "r1", "block_id": "b1", "kind": "satisfy"}
    assert validate_trace(link, {"r1"}, {"b1"}) == []


def test_validate_trace_rejects_unknown_ids_and_kinds():
    link = {"requirement_id": "nope", "block_id": "also-nope", "kind": "implements"}
    violations = validate_trace(link, {"r1"}, {"b1"})
    assert len(violations) == 3


def test_uncovered_requirement_is_reported():
    traces = [{"requirement_id": "r1", "block_id": "b1", "kind": "satisfy"}]
    cov = compute_coverage(REQS, BLOCKS, traces)

    assert cov["requirements_covered"] == 1
    assert cov["requirements_uncovered"] == 1
    assert cov["coverage_rate"] == 0.5

    by_id = {r["requirement_id"]: r for r in cov["rows"]}
    assert by_id["r1"]["covered"] is True
    assert by_id["r1"]["satisfied_by"][0]["name"] == "Recovery"
    assert by_id["r2"]["covered"] is False


def test_only_satisfy_links_count_toward_coverage():
    """A requirement that is merely refined or verified is not satisfied --
    nothing in the design has been committed to building it."""
    traces = [{"requirement_id": "r1", "block_id": "b1", "kind": "refine"}]
    cov = compute_coverage(REQS, BLOCKS, traces)

    assert cov["requirements_covered"] == 0
    # the link still exists, so the block is not an orphan
    assert "b1" not in [b["id"] for b in cov["orphan_blocks"]]


def test_orphan_blocks_exclude_the_root():
    traces = [{"requirement_id": "r1", "block_id": "b1", "kind": "satisfy"}]
    cov = compute_coverage(REQS, BLOCKS, traces)

    orphans = {b["id"] for b in cov["orphan_blocks"]}
    assert orphans == {"b2"}


def test_empty_model_does_not_divide_by_zero():
    cov = compute_coverage([], [], [])
    assert cov["coverage_rate"] == 0.0
    assert cov["rows"] == []
