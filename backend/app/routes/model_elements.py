import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import config, knowledge, rules, storage

router = APIRouter(prefix="/model-elements", tags=["model-elements"])


class CreateElementsRequest(BaseModel):
    elements: List[dict]


class UpdateElementRequest(BaseModel):
    """Every field optional: the engineer may be fixing one word of the text
    or reclassifying the stereotype, and should not have to resend the rest."""

    stereotype: Optional[str] = None
    name: Optional[str] = Field(default=None, max_length=200)
    text: Optional[str] = Field(default=None, max_length=4000)
    verifyMethod: Optional[str] = None


def _check(element: dict) -> List[str]:
    """The same rulebook the generated requirements face. A requirement an
    engineer typed by hand is not exempt -- the checker exists because
    people break these rules too."""
    violations = []
    if element.get("stereotype") not in config.ALLOWED_STEREOTYPES:
        violations.append(f"invalid stereotype '{element.get('stereotype', '')}'")
    if element.get("verifyMethod") not in config.ALLOWED_VERIFY_METHODS:
        violations.append(f"invalid verifyMethod '{element.get('verifyMethod', '')}'")
    for v in rules.validate_requirement_text(element.get("text", "")):
        violations.append(f"{v.rule}: {v.detail}")
    return violations


def _with_violations(elements: List[dict]) -> List[dict]:
    return [{**e, "violations": _check(e)} for e in elements]


@router.get("")
async def list_elements():
    return _with_violations(storage.list_model_elements())


@router.post("")
async def create_elements(payload: CreateElementsRequest):
    elements = [{**e, "id": str(uuid.uuid4())} for e in payload.elements]
    storage.add_model_elements(elements)
    storage.log_event(f"Created {len(elements)} model element(s).")

    # what the tool writes becomes what the tool can retrieve
    result = await knowledge.reindex_model()
    storage.log_event(
        f"Re-indexed the model: {result['requirements']} requirement(s), "
        f"{result['blocks']} block(s), {result['chunks']} chunk(s)."
    )
    return _with_violations(storage.list_model_elements())


@router.patch("/{element_id}")
async def update_element(element_id: str, payload: UpdateElementRequest):
    fields = payload.model_dump(exclude_none=True)
    updated = storage.update_model_element(element_id, fields)
    if updated is None:
        raise HTTPException(status_code=404, detail="No such model element.")

    violations = _check(updated)
    storage.log_event(
        f"Edited requirement {updated['name']!r} by hand: "
        + ("passes the rule check." if not violations else f"{len(violations)} rule(s) broken.")
    )
    await knowledge.reindex_model()
    return {**updated, "violations": violations}


@router.delete("/{element_id}")
async def delete_element(element_id: str):
    element = storage.get_model_element(element_id)
    storage.delete_model_element(element_id)
    storage.log_event(
        f"Deleted requirement {element['name']!r}." if element
        else f"Deleted model element {element_id}."
    )
    await knowledge.reindex_model()
    return _with_violations(storage.list_model_elements())
