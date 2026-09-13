from app.prompts import build_diagram_prompt

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
