"""Everything that decides whether generated output is valid: the INCOSE
writing checks for requirements, structural validation for diagrams, and
trace link validation with coverage analysis. No model calls here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Dict, List, Optional


WORD_COUNT_MIN = 40

VAGUE_TERMS = [
    "some", "any", "allowable", "several", "many", "a lot of", "a few",
    "almost always", "very nearly", "nearly", "about", "close to",
    "almost", "approximate",
]

UNACHIEVABLE_ABSOLUTES = [
    "100% reliability", "100% availability", "all", "every", "always", "never",
]

PRONOUNS = ["it", "this", "that", "he", "she", "they", "them"]

ESCAPE_CLAUSES = [
    "so far as is possible", "as little as possible", "where possible",
    "as much as possible", "if it should prove necessary", "as appropriate",
    "as required", "to the extent practical",
]

OPEN_ENDED_CLAUSES = ["including but not limited to", "and so on"]

SUPERFLUOUS_PHRASES = ["be designed to", "be able to", "be capable of"]

DUPLICATE_SIMILARITY_THRESHOLD = 0.85


RULE_CATALOG = {
    "word_count": ("MM-R01", "Complete", "carries enough detail to stand alone"),
    "contains_shall": ("MM-R02", "Conforming", "states an obligation, not a description"),
    "vague_terms": ("MM-R03", "Unambiguous", "avoids terms with no verifiable meaning"),
    "unachievable_absolutes": ("MM-R04", "Feasible", "avoids absolutes nothing can satisfy"),
    "pronouns": ("MM-R05", "Unambiguous", "names its subject rather than referring back"),
    "escape_clauses": ("MM-R06", "Verifiable", "avoids get-out clauses that void the obligation"),
    "open_ended_clauses": ("MM-R07", "Complete", "avoids open-ended lists"),
    "superfluous_phrases": ("MM-R08", "Concise", "avoids filler and negative obligations"),
    "duplicate_requirement": ("MM-R09", "Unique", "does not restate another requirement"),
    "exclusionary_assumption": ("MM-R10", "Necessary", "does not embed an unjustified human limit"),
}


@dataclass
class RuleViolation:
    rule: str
    detail: str

    @property
    def id(self) -> str:
        return RULE_CATALOG.get(self.rule, ("MM-R??", "", ""))[0]

    @property
    def characteristic(self) -> str:
        return RULE_CATALOG.get(self.rule, ("", "", ""))[1]

    @property
    def intent(self) -> str:
        return RULE_CATALOG.get(self.rule, ("", "", ""))[2]

    def label(self) -> str:
        char = f" ({self.characteristic})" if self.characteristic else ""
        return f"{self.id}{char} {self.rule}: {self.detail}"


def _whole_word_hits(terms: List[str], text_lower: str) -> List[str]:
    return [t for t in terms if re.search(r"\b" + re.escape(t) + r"\b", text_lower)]


def _substring_hits(terms: List[str], text_lower: str) -> List[str]:
    return [t for t in terms if t in text_lower]


def check_word_count(text: str) -> Optional[RuleViolation]:
    count = len(text.split())
    if count < WORD_COUNT_MIN:
        return RuleViolation("word_count", f"only {count} words, needs >= {WORD_COUNT_MIN}")
    return None


def check_contains_shall(text: str) -> Optional[RuleViolation]:
    if not _whole_word_hits(["shall"], text.lower()):
        return RuleViolation("contains_shall", "missing the word 'shall'")
    return None


def check_vague_terms(text: str) -> Optional[RuleViolation]:
    hits = _whole_word_hits(VAGUE_TERMS, text.lower())
    if hits:
        return RuleViolation("vague_terms", f"uses vague term(s): {', '.join(hits)}")
    return None


def check_unachievable_absolutes(text: str) -> Optional[RuleViolation]:
    hits = _whole_word_hits(UNACHIEVABLE_ABSOLUTES, text.lower())
    if hits:
        return RuleViolation("unachievable_absolutes", f"uses unachievable absolute(s): {', '.join(hits)}")
    return None


def check_pronouns(text: str) -> Optional[RuleViolation]:
    hits = _whole_word_hits(PRONOUNS, text.lower())
    if hits:
        return RuleViolation("pronouns", f"uses pronoun(s): {', '.join(hits)}")
    return None


def check_escape_clauses(text: str) -> Optional[RuleViolation]:
    hits = _substring_hits(ESCAPE_CLAUSES, text.lower())
    if hits:
        return RuleViolation("escape_clauses", f"uses escape clause(s): {', '.join(hits)}")
    return None


def check_open_ended_clauses(text: str) -> Optional[RuleViolation]:
    hits = _substring_hits(OPEN_ENDED_CLAUSES, text.lower())
    if hits:
        return RuleViolation("open_ended_clauses", f"uses open-ended clause(s): {', '.join(hits)}")
    return None


def check_superfluous_phrases(text: str) -> Optional[RuleViolation]:
    text_lower = text.lower()
    hits = _substring_hits(SUPERFLUOUS_PHRASES, text_lower)
    if _whole_word_hits(["not"], text_lower):
        hits.append("not")
    if hits:
        return RuleViolation("superfluous_phrases", f"uses superfluous phrase(s): {', '.join(hits)}")
    return None


HUMAN_CAPABILITY_TERMS = [
    "lift", "lifting", "carry", "reach", "grip", "grasp", "kneel", "crouch",
    "stand for", "unaided", "unassisted", "by hand", "manually operate",
    "eyesight", "visual acuity", "hearing", "audible alarm", "colour-coded",
    "color-coded", "able-bodied", "dexterity", "two-handed", "one-handed",
]

JUSTIFICATION_TERMS = [
    "percentile", "anthropometric", "mil-std-1472", "iso 9241", "en 614",
    "wcag", "section 508", "ada ", "accessibility standard", "human factors",
    "ergonomic standard", "per standard", "in accordance with",
]


def check_exclusionary_assumptions(text: str) -> Optional[RuleViolation]:
    lowered = text.lower()
    hits = _whole_word_hits(
        [t for t in HUMAN_CAPABILITY_TERMS if " " not in t], lowered
    ) + _substring_hits([t for t in HUMAN_CAPABILITY_TERMS if " " in t], lowered)
    if not hits:
        return None
    if _substring_hits(JUSTIFICATION_TERMS, lowered):
        return None
    return RuleViolation(
        "exclusionary_assumption",
        f"constrains human capability ({', '.join(sorted(set(hits)))}) without naming "
        f"an anthropometric, ergonomic, or accessibility standard to justify the limit",
    )


RULES = [
    check_word_count,
    check_contains_shall,
    check_vague_terms,
    check_unachievable_absolutes,
    check_pronouns,
    check_escape_clauses,
    check_open_ended_clauses,
    check_superfluous_phrases,
]


ADVISORY_RULES = [
    check_exclusionary_assumptions,
]


def validate_requirement_text(text: str) -> List[RuleViolation]:
    violations = []
    for rule in RULES:
        result = rule(text)
        if result is not None:
            violations.append(result)
    return violations


def review_requirement_text(text: str) -> List[RuleViolation]:
    out = []
    for rule in ADVISORY_RULES:
        result = rule(text)
        if result is not None:
            out.append(result)
    return out


def find_duplicates(requirements: List[dict]) -> Dict[int, RuleViolation]:
    violations: Dict[int, RuleViolation] = {}
    for i in range(len(requirements)):
        for j in range(i):
            ratio = SequenceMatcher(
                None,
                requirements[i]["text"].lower(),
                requirements[j]["text"].lower(),
            ).ratio()
            if ratio >= DUPLICATE_SIMILARITY_THRESHOLD:
                violations[i] = RuleViolation(
                    "duplicate_requirement",
                    f"near-duplicate of requirement #{j} ({ratio:.0%} similar)",
                )
                break
    return violations


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


ALLOWED_TRACE_KINDS = ["satisfy", "refine", "verify"]

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
