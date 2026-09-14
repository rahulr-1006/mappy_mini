from app.evaluation import normalize_review, summarize_reviews


def review(index, score, comment="x"):
    return normalize_review(
        {
            "index": index,
            "singular": score,
            "verifiable": score,
            "implementation_free": score,
            "unambiguous": score,
            "necessary": score,
            "comment": comment,
        }
    )


def test_scores_are_clamped_to_the_one_to_five_scale():
    r = normalize_review(
        {"index": 0, "singular": 9, "verifiable": -3, "implementation_free": 4,
         "unambiguous": 4, "necessary": 4}
    )
    assert r["singular"] == 5
    assert r["verifiable"] == 1


def test_non_numeric_scores_do_not_raise():
    r = normalize_review({"index": 0, "singular": "great", "verifiable": None})
    assert r["singular"] == 0
    assert r["verifiable"] == 0


def test_mean_ignores_ungraded_criteria():
    r = normalize_review({"index": 0, "singular": 4, "verifiable": 2})
    # only the two graded criteria count, not the three missing ones
    assert r["mean"] == 3.0


def test_blind_spot_counts_only_requirements_the_rules_passed():
    """The interesting set: clean on the lexical rules, weak on substance.
    That number is what bounds the value of lexical validation."""
    reviews = [review(0, 2), review(1, 2), review(2, 5)]
    rule_failures = {0: [], 1: ["word_count"], 2: []}

    summary = summarize_reviews(reviews, rule_failures)

    assert len(summary["flagged"]) == 2          # indices 0 and 1 scored low
    assert summary["passed_rules_but_judge_flagged"] == 1   # only index 0


def test_summary_of_no_reviews_is_safe():
    summary = summarize_reviews([], {})
    assert summary["reviewed"] == 0
    assert summary["mean_score"] == 0.0
    assert summary["flagged"] == []
