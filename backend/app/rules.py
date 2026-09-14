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


# Each check gets a stable identifier and the INCOSE quality characteristic
# it serves. The identifiers are ours (MM-*), deliberately not INCOSE rule
# numbers: the characteristics in INCOSE-TP-2010-006-04 are stable and
# quotable, its rule numbering is not something to assert from memory in
# front of someone who knows the standard. The mapping below is the honest
# claim -- this check exists to serve that characteristic.
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
        """How a violation reads to an engineer: the identifier, the quality
        characteristic it bears on, then what actually went wrong."""
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


# VAL-10 extension, and the one check here that is not about wording.
#
# A requirement that fixes a human capability -- a lifting weight, a reach,
# a reaction time, an acuity -- without saying where the figure came from
# silently defines who is allowed to operate the system. That is a design
# decision being made by default rather than on purpose, and it is the kind
# of thing that surfaces late and expensively.
#
# The check does not object to the constraint. Plenty of them are real and
# necessary. It objects to the constraint appearing with no anthropometric
# standard, population percentile, or accessibility standard named beside
# it. The fix is usually one clause, not a redesign.
HUMAN_CAPABILITY_TERMS = [
    "lift", "lifting", "carry", "reach", "grip", "grasp", "kneel", "crouch",
    "stand for", "unaided", "unassisted", "by hand", "manually operate",
    "eyesight", "visual acuity", "hearing", "audible alarm", "colour-coded",
    "color-coded", "able-bodied", "dexterity", "two-handed", "one-handed",
]

# Naming any of these is what turns an arbitrary limit into a justified one.
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


# Deliberately not in RULES. These are judgement calls for a person, not
# defects for the repair loop to fix: a model told to "fix" an exclusionary
# constraint will delete it, and silently dropping an accessibility
# consideration is worse than stating one badly. Advisories are reported
# beside a requirement and never gate whether it counts as clean.
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
    """Advisories: things worth a human's attention that are not rule
    failures. Separate from validate_requirement_text so nothing here
    triggers a rewrite."""
    out = []
    for rule in ADVISORY_RULES:
        result = rule(text)
        if result is not None:
            out.append(result)
    return out


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
