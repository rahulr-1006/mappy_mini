"""Trace links between requirements and model elements.

The SysML relationships that matter for coverage analysis:

  satisfy  a design element fulfils a requirement (the workhorse)
  refine   an element elaborates a requirement without fulfilling it
  verify   a test case demonstrates a requirement is met

A requirement nothing satisfies is the classic systems-engineering defect --
it was written, agreed, and then never allocated to anything that builds it.
Coverage analysis exists to surface exactly that.
"""

from __future__ import annotations

from typing import Dict, List

ALLOWED_TRACE_KINDS = ["satisfy", "refine", "verify"]

# Only "satisfy" counts toward coverage: refining or verifying a requirement
# does not mean anything in the design actually fulfils it.
COVERAGE_KIND = "satisfy"


def validate_trace(trace: dict, requirement_ids: set, block_ids: set) -> List[str]:
    violations = []
    if trace.get("kind") not in ALLOWED_TRACE_KINDS:
        violations.append(f"invalid kind '{trace.get('kind')}'")
    if trace.get("requirement_id") not in requirement_ids:
        violations.append(f"unknown requirement '{trace.get('requirement_id')}'")
    if trace.get("block_id") not in block_ids:
        violations.append(f"unknown block '{trace.get('block_id')}'")
    return violations


def compute_coverage(requirements: List[dict], blocks: List[dict], traces: List[dict]) -> dict:
    """Which requirements are satisfied by something, and which design
    elements exist without satisfying anything."""
    satisfied: Dict[str, List[str]] = {}
    for t in traces:
        if t.get("kind") == COVERAGE_KIND:
            satisfied.setdefault(t["requirement_id"], []).append(t["block_id"])

    block_names = {b["id"]: b.get("name", b["id"]) for b in blocks}

    rows = []
    for req in requirements:
        block_ids = satisfied.get(req["id"], [])
        rows.append(
            {
                "requirement_id": req["id"],
                "name": req.get("name", ""),
                "stereotype": req.get("stereotype", ""),
                "satisfied_by": [
                    {"id": bid, "name": block_names.get(bid, bid)} for bid in block_ids
                ],
                "covered": bool(block_ids),
            }
        )

    linked_blocks = {t["block_id"] for t in traces}
    orphan_blocks = [
        {"id": b["id"], "name": b.get("name", "")}
        for b in blocks
        if b["id"] not in linked_blocks and not b.get("isRoot")
    ]

    covered = sum(1 for r in rows if r["covered"])
    total = len(rows)

    return {
        "rows": rows,
        "orphan_blocks": orphan_blocks,
        "requirements_total": total,
        "requirements_covered": covered,
        "requirements_uncovered": total - covered,
        "coverage_rate": (covered / total) if total else 0.0,
    }
