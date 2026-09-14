import pytest


@pytest.fixture
def store(tmp_path, monkeypatch):
    """A fresh database per test."""
    from app import config, storage

    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(storage, "DB_FILE", str(tmp_path / "test.db"))
    monkeypatch.setattr(storage, "_initialised", False)
    return storage


def test_model_elements_round_trip(store):
    store.add_model_elements(
        [{"id": "r1", "stereotype": "functionalRequirement", "name": "n",
          "text": "t", "verifyMethod": "Test"}]
    )
    elements = store.list_model_elements()

    assert len(elements) == 1
    # verify_method is stored snake_case but the API speaks camelCase
    assert elements[0]["verifyMethod"] == "Test"


def test_deleting_a_requirement_removes_its_traces(store):
    """A trace pointing at a deleted requirement would show up in coverage
    as a link to nothing."""
    store.add_model_elements([{"id": "r1", "name": "n", "text": "t",
                               "stereotype": "s", "verifyMethod": "Test"}])
    store.save_diagram([{"id": "b1", "name": "B", "isRoot": False}], [])
    store.add_traces([{"id": "t1", "requirement_id": "r1", "block_id": "b1",
                       "kind": "satisfy", "rationale": ""}])
    assert len(store.get_traces()) == 1

    store.delete_model_element("r1")

    assert store.get_traces() == []


def test_saving_a_new_diagram_drops_traces_to_vanished_blocks(store):
    store.add_model_elements([{"id": "r1", "name": "n", "text": "t",
                               "stereotype": "s", "verifyMethod": "Test"}])
    store.save_diagram([{"id": "b1", "name": "Old", "isRoot": False}], [])
    store.add_traces([{"id": "t1", "requirement_id": "r1", "block_id": "b1",
                       "kind": "satisfy", "rationale": ""}])

    store.save_diagram([{"id": "b2", "name": "New", "isRoot": False}], [])

    assert store.get_traces() == []


def test_the_same_trace_twice_is_not_duplicated(store):
    store.add_model_elements([{"id": "r1", "name": "n", "text": "t",
                               "stereotype": "s", "verifyMethod": "Test"}])
    store.save_diagram([{"id": "b1", "name": "B", "isRoot": False}], [])
    link = {"id": "t1", "requirement_id": "r1", "block_id": "b1",
            "kind": "satisfy", "rationale": ""}

    store.add_traces([link])
    store.add_traces([{**link, "id": "t2"}])

    assert len(store.get_traces()) == 1


def test_diagram_block_order_is_preserved(store):
    blocks = [{"id": f"b{i}", "name": f"B{i}", "isRoot": i == 0} for i in range(5)]
    store.save_diagram(blocks, [])

    assert [b["id"] for b in store.get_diagram()["blocks"]] == [b["id"] for b in blocks]


def test_eval_records_read_back_with_numbers_not_nulls(store):
    """Records written before a column existed come back NULL, and callers
    sum these -- a None here crashes the summary."""
    store.add_eval_record({"task": "requirements", "model": "m", "provider": "ollama",
                           "source": "live", "timestamp": "2026-01-01T00:00:00Z"})

    record = store.get_eval_log()[0]

    assert record["prompt_tokens"] == 0
    assert record["actual_cost_usd"] == 0
    assert record["cost_estimate_usd"] == {}


def test_missing_provider_reads_back_as_local(store):
    store.add_eval_record({"task": "requirements", "model": "m",
                           "timestamp": "2026-01-01T00:00:00Z"})

    assert store.get_eval_log()[0]["provider"] == "ollama"


def test_saved_diagram_remembers_its_prompt(store):
    store.save_diagram([{"id": "b1", "name": "B", "isRoot": True}], [], "a ground station")

    assert store.get_diagram()["prompt"] == "a ground station"


def test_saving_without_a_prompt_keeps_the_previous_one(store):
    """Re-saving an edited diagram should not wipe the prompt that can
    regenerate it."""
    store.save_diagram([{"id": "b1", "name": "B", "isRoot": True}], [], "a ground station")
    store.save_diagram([{"id": "b2", "name": "C", "isRoot": True}], [])

    assert store.get_diagram()["prompt"] == "a ground station"


def test_clearing_the_diagram_drops_the_prompt(store):
    store.save_diagram([{"id": "b1", "name": "B", "isRoot": True}], [], "a ground station")
    store.clear_diagram()

    assert store.get_diagram()["prompt"] == ""
