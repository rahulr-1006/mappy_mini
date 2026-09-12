import uuid
from typing import List

from fastapi import APIRouter
from pydantic import BaseModel

from .. import storage

router = APIRouter(prefix="/model-elements", tags=["model-elements"])


class CreateElementsRequest(BaseModel):
    elements: List[dict]


@router.get("")
async def list_elements():
    return storage.get_state()["model_elements"]


@router.post("")
async def create_elements(payload: CreateElementsRequest):
    elements = [{**e, "id": str(uuid.uuid4())} for e in payload.elements]
    state = storage.add_model_elements(elements)
    storage.log_event(f"Created {len(elements)} model element(s).")
    return state["model_elements"]


@router.delete("/{element_id}")
async def delete_element(element_id: str):
    state = storage.delete_model_element(element_id)
    storage.log_event(f"Deleted model element {element_id}.")
    return state["model_elements"]
