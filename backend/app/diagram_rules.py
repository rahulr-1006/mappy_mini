from __future__ import annotations

from typing import List

ALLOWED_CONNECTOR_KINDS = [
    "composition",
    "aggregation",
    "association",
    "dependency",
    "generalization",
]


def validate_diagram(blocks: List[dict], connectors: List[dict]) -> List[str]:
    violations: List[str] = []

    ids = [b.get("id") for b in blocks]
    if len(set(ids)) != len(ids):
        violations.append("duplicate block ids")

    names = [b.get("name", "") for b in blocks]
    if len(set(names)) != len(names):
        violations.append("duplicate block names")

    for block in blocks:
        if not block.get("name", "").strip():
            violations.append(f"block '{block.get('id')}' has an empty name")

    roots = [b for b in blocks if b.get("isRoot")]
    if len(roots) != 1:
        violations.append(f"expected exactly 1 root block, found {len(roots)}")

    id_set = set(ids)
    for conn in connectors:
        source = conn.get("source")
        target = conn.get("target")
        if source not in id_set:
            violations.append(f"connector '{conn.get('id')}' has unknown source '{source}'")
        if target not in id_set:
            violations.append(f"connector '{conn.get('id')}' has unknown target '{target}'")
        if source == target:
            violations.append(f"connector '{conn.get('id')}' is a self-loop")
        if conn.get("kind") not in ALLOWED_CONNECTOR_KINDS:
            violations.append(f"connector '{conn.get('id')}' has invalid kind '{conn.get('kind')}'")

    return violations
