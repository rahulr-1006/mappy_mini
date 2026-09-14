"""Tests for the rule engine and for traceability coverage."""

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
    compute_coverage,
    find_duplicates,
    validate_requirement_text,
    validate_trace,
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
        assert rules.review_requirement_text(self.JUSTIFIED) == []

    def test_ignores_requirements_that_constrain_no_one(self):
        assert rules.review_requirement_text(self.UNRELATED) == []

    def test_advisories_are_not_rule_failures(self):
        failures = {v.rule for v in rules.validate_requirement_text(self.UNJUSTIFIED)}
        assert "exclusionary_assumption" not in failures
        assert rules.check_exclusionary_assumptions not in rules.RULES


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
    traces = [{"requirement_id": "r1", "block_id": "b1", "kind": "refine"}]
    cov = compute_coverage(REQS, BLOCKS, traces)

    assert cov["requirements_covered"] == 0
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
