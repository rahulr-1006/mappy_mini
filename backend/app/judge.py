"""Semantic review of requirements by a second model.

The rule engine in `rules.py` is lexical: it can tell you a requirement says
"shall" and avoids "user-friendly", but not whether it bundles three needs
into one sentence or states something no test could ever falsify. Those are
the defects that survive a clean rule pass and reach a design review.

This scores the same requirements on criteria a regex cannot reach, so the
two signals can be compared. Where they disagree -- a requirement the rules
pass and the judge fails -- is the interesting set, because it bounds what
lexical validation is worth.
"""

from __future__ import annotations

from typing import Dict, List

CRITERIA = ["singular", "verifiable", "implementation_free", "unambiguous", "necessary"]

# Below this mean, a requirement is worth a human's attention regardless of
# whether it passed the lexical rules.
CONCERN_THRESHOLD = 3.5


def normalize_review(item: dict) -> dict:
    scores = {}
    for c in CRITERIA:
        raw = item.get(c)
        if raw is None:
            # absent is not the same as bad -- score 0 marks it ungraded so
            # it drops out of the mean instead of dragging it to the floor
            scores[c] = 0
            continue
        try:
            scores[c] = max(1, min(5, int(raw)))
        except (TypeError, ValueError):
            scores[c] = 0
    graded = [v for v in scores.values() if v > 0]
    return {
        "index": item.get("index"),
        **scores,
        "mean": round(sum(graded) / len(graded), 2) if graded else 0.0,
        "comment": str(item.get("comment", ""))[:300],
    }


def summarize_reviews(reviews: List[dict], rule_failures: Dict[int, List[str]]) -> dict:
    """Cross-tabulate the judge against the rule engine.

    `rule_failures` maps requirement index to the lexical violations it has,
    so an empty list means the rules passed it.
    """
    if not reviews:
        return {
            "reviewed": 0,
            "criteria_means": {c: 0.0 for c in CRITERIA},
            "mean_score": 0.0,
            "flagged": [],
            "passed_rules_but_judge_flagged": 0,
        }

    criteria_means = {
        c: round(sum(r[c] for r in reviews) / len(reviews), 2) for c in CRITERIA
    }

    flagged = [r for r in reviews if r["mean"] and r["mean"] < CONCERN_THRESHOLD]

    # the set that matters: clean on the rules, weak on substance
    blind_spot = sum(
        1
        for r in flagged
        if not rule_failures.get(r["index"], [])
    )

    return {
        "reviewed": len(reviews),
        "criteria_means": criteria_means,
        "mean_score": round(sum(r["mean"] for r in reviews) / len(reviews), 2),
        "flagged": flagged,
        "passed_rules_but_judge_flagged": blind_spot,
    }
