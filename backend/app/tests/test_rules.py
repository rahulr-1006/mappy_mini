import pytest

from app import rules
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


def test_a_requirement_that_cannot_be_fixed_keeps_its_violations():
    """The repair loop is bounded, so some requirements come back still
    broken. Those must not be presented as if they passed."""
    from app.models import Requirement

    req = Requirement(
        stereotype="functionalRequirement",
        name="Layout",
        text="The layout shall be designed to accommodate maintenance.",
        verifyMethod="Inspection",
        reprompts=3,
        violations=["superfluous_phrases: uses superfluous phrase(s): be designed to"],
    )

    assert req.violations
    assert req.reprompts == 3


def test_a_clean_requirement_has_no_violations():
    from app.models import Requirement

    req = Requirement(
        stereotype="functionalRequirement",
        name="Clean",
        text=GOOD_REQUIREMENT,
        verifyMethod="Test",
    )

    assert req.violations == []


class TestRuleIdentifiers:
    def test_every_check_has_an_id_and_a_characteristic(self):
        # a violation with no catalogue entry would render as "MM-R??",
        # which is the kind of thing that ships unnoticed
        for name in rules.RULE_CATALOG:
            rule_id, characteristic, intent = rules.RULE_CATALOG[name]
            assert rule_id.startswith("MM-R")
            assert characteristic
            assert intent

    def test_label_reads_id_characteristic_then_what_went_wrong(self):
        violation = rules.RuleViolation("pronouns", "uses pronoun(s): it")
        assert violation.label() == "MM-R05 (Unambiguous) pronouns: uses pronoun(s): it"

    def test_unknown_rule_degrades_rather_than_raising(self):
        violation = rules.RuleViolation("invented_rule", "something")
        assert violation.id == "MM-R??"
        assert "invented_rule" in violation.label()


class TestExclusionaryAssumptions:
    UNJUSTIFIED = (
        "The operator shall lift the antenna feed assembly unaided during "
        "scheduled maintenance and complete the replacement within thirty minutes."
    )
    JUSTIFIED = (
        "The operator shall lift the antenna feed assembly, with mass limited to "
        "the 5th percentile female lifting capability per MIL-STD-1472, during "
        "scheduled maintenance within thirty minutes."
    )
    UNRELATED = (
        "The ground station shall downlink payload data at a minimum rate of two "
        "megabits per second during each scheduled contact window."
    )

    def test_flags_a_human_limit_with_no_justification(self):
        advisories = rules.review_requirement_text(self.UNJUSTIFIED)
        assert len(advisories) == 1
        assert advisories[0].rule == "exclusionary_assumption"
        assert "lift" in advisories[0].detail

    def test_accepts_the_same_limit_once_a_standard_is_named(self):
        # the check objects to the limit being arbitrary, not to the limit
        assert rules.review_requirement_text(self.JUSTIFIED) == []

    def test_ignores_requirements_that_constrain_no_one(self):
        assert rules.review_requirement_text(self.UNRELATED) == []

    def test_advisories_are_not_rule_failures(self):
        # the repair loop runs off validate_requirement_text; an advisory
        # appearing there would have a model rewrite the constraint away
        failures = {v.rule for v in rules.validate_requirement_text(self.UNJUSTIFIED)}
        assert "exclusionary_assumption" not in failures
        assert rules.check_exclusionary_assumptions not in rules.RULES
