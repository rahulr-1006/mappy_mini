import pytest

from app.rules import (
    check_contains_shall,
    check_escape_clauses,
    check_open_ended_clauses,
    check_pronouns,
    check_superfluous_phrases,
    check_unachievable_absolutes,
    check_vague_terms,
    check_word_count,
    find_duplicates,
    validate_requirement_text,
)

GOOD_REQUIREMENT = (
    "The onboard navigation subsystem shall compute an updated position "
    "estimate at a rate of ten hertz during flight operations, using data "
    "fused from the inertial measurement unit and satellite receiver, "
    "enabling the flight control computer to maintain course within the "
    "specified tolerance band."
)

PROPULSION_REQUIREMENT = (
    "The propulsion subsystem shall throttle output based on commanded "
    "thrust setpoints received from the flight control computer over the "
    "primary data bus during all phases of powered flight operations."
)


def test_good_requirement_passes_all_rules():
    assert validate_requirement_text(GOOD_REQUIREMENT) == []


@pytest.mark.parametrize(
    "checker,text,expected_rule",
    [
        (check_word_count, "The system shall work.", "word_count"),
        (check_contains_shall, GOOD_REQUIREMENT.replace("shall", "will"), "contains_shall"),
        (
            check_vague_terms,
            GOOD_REQUIREMENT + " Several backup units shall also be available.",
            "vague_terms",
        ),
        (
            check_unachievable_absolutes,
            GOOD_REQUIREMENT + " All sensors shall always report data.",
            "unachievable_absolutes",
        ),
        (check_pronouns, GOOD_REQUIREMENT + " It shall log this event.", "pronouns"),
        (
            check_escape_clauses,
            GOOD_REQUIREMENT + " This shall be logged where possible.",
            "escape_clauses",
        ),
        (
            check_open_ended_clauses,
            GOOD_REQUIREMENT + " This covers sensors, actuators, and so on.",
            "open_ended_clauses",
        ),
        (
            check_superfluous_phrases,
            GOOD_REQUIREMENT + " The unit shall be able to restart.",
            "superfluous_phrases",
        ),
    ],
)
def test_known_bad_cases_are_caught(checker, text, expected_rule):
    result = checker(text)
    assert result is not None, f"expected a violation for {expected_rule}"
    assert result.rule == expected_rule


def test_validate_requirement_text_aggregates_multiple_violations():
    bad_text = (
        "It shall fix some things where possible, including but not "
        "limited to sensors and so on."
    )
    rule_names = {v.rule for v in validate_requirement_text(bad_text)}
    assert rule_names == {
        "word_count",
        "pronouns",
        "vague_terms",
        "escape_clauses",
        "open_ended_clauses",
        "superfluous_phrases",
    }


def test_find_duplicates_flags_near_identical_requirements():
    """VAL-9 extension: the per-requirement rules above check each
    requirement in isolation, so they can't catch the LLM restating the
    same requirement twice under a different name. This needs a
    batch-level comparison instead."""
    requirements = [
        {"text": GOOD_REQUIREMENT},
        {"text": GOOD_REQUIREMENT.replace("ten hertz", "10 hertz")},
        {"text": PROPULSION_REQUIREMENT},
    ]

    violations = find_duplicates(requirements)

    assert 0 not in violations
    assert 2 not in violations
    assert 1 in violations
    assert violations[1].rule == "duplicate_requirement"


def test_find_duplicates_is_empty_for_distinct_requirements():
    requirements = [{"text": GOOD_REQUIREMENT}, {"text": PROPULSION_REQUIREMENT}]
    assert find_duplicates(requirements) == {}
