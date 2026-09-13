from app.prompts import build_chat_prompt, build_diagram_prompt

REQS = [
    {"name": "Pass scheduling", "text": "The station shall compute pass windows."},
    {"name": "Antenna pointing", "text": "The station shall steer within 0.1 degrees."},
]


def test_diagram_prompt_without_requirements_is_description_only():
    system, user = build_diagram_prompt("a ground station")

    assert "a ground station" in user
    assert "REQUIREMENTS THE DESIGN MUST SATISFY" not in user
    assert "design must follow from them" not in system


def test_diagram_prompt_with_requirements_carries_them_in():
    system, user = build_diagram_prompt("a ground station", REQS)

    assert "REQUIREMENTS THE DESIGN MUST SATISFY" in user
    assert "steer within 0.1 degrees" in user
    # the extra instruction only appears when there is something to satisfy
    assert "they define the scope of the design" in system


def test_empty_requirements_list_falls_back_to_description_only():
    _, user = build_diagram_prompt("a ground station", [])

    assert "REQUIREMENTS THE DESIGN MUST SATISFY" not in user


def test_breadth_floor_only_applies_without_requirements():
    """With requirements to bound it, the design should be scoped by them.
    Without, ask for the breadth the domain would normally have."""
    bare, _ = build_diagram_prompt("a ground station")
    scoped, _ = build_diagram_prompt("a ground station", REQS)

    assert "6-9 subsystem blocks" in bare
    assert "6-9 subsystem blocks" not in scoped
    assert "unjustified scope" in scoped


def test_chat_prompt_carries_the_transcript():
    history = [
        {"role": "user", "content": "A ground station.", "requirements": []},
        {"role": "assistant", "content": "Which band?", "requirements": []},
    ]
    _, user = build_chat_prompt(history, "S-band.")

    assert "COLLEAGUE: A ground station." in user
    assert "YOU: Which band?" in user
    assert user.rstrip().endswith("COLLEAGUE: S-band.")


def test_chat_prompt_reports_failed_rule_checks_back_to_the_model():
    """Without this the model cannot fix anything when asked, because it
    never learns the checker rejected its last answer."""
    history = [
        {
            "role": "assistant",
            "content": "Here you go.",
            "requirements": [
                {"name": "Pointing", "violations": ["word_count: only 20 words, needs >= 40"]},
                {"name": "Downlink", "violations": []},
            ],
        }
    ]
    _, user = build_chat_prompt(history, "fix them")

    assert 'FAILS the rule check: word_count' in user
    assert '"Downlink" passed the rule check' in user


def test_must_produce_directive_is_opt_in():
    history = [{"role": "assistant", "content": "Which band?", "requirements": []}]

    _, without = build_chat_prompt(history, "S-band.")
    _, with_it = build_chat_prompt(history, "S-band.", must_produce=True)

    assert "not an acceptable response" not in without
    assert "not an acceptable response" in with_it


def test_the_directive_does_not_disturb_the_cacheable_half():
    system_a, _ = build_chat_prompt([], "x")
    system_b, _ = build_chat_prompt([], "x", must_produce=True)

    assert system_a == system_b
