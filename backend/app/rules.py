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

# VAL-8 extension: superfluous phrases beyond the assigned FR-7 subset.
SUPERFLUOUS_PHRASES = ["be designed to", "be able to", "be capable of"]

# VAL-9 extension: batch-level near-duplicate detection. Unlike the rules
# above, this can't be checked one requirement at a time -- it needs the
# whole generated batch to compare against.
DUPLICATE_SIMILARITY_THRESHOLD = 0.85


@dataclass
class RuleViolation:
    rule: str
    detail: str


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


def validate_requirement_text(text: str) -> List[RuleViolation]:
    violations = []
    for rule in RULES:
        result = rule(text)
        if result is not None:
            violations.append(result)
    return violations


def find_duplicates(requirements: List[dict]) -> Dict[int, RuleViolation]:
    """VAL-9, batch-level: flag requirements whose text nearly repeats an
    earlier one in the same generated batch. The per-requirement rules
    above can't catch this since each requirement is checked in isolation.
    """
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
