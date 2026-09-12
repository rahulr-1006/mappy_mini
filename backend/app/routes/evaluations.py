from fastapi import APIRouter
from pydantic import BaseModel

from .. import config, eval_suite, storage
from ..evaluation import REFERENCE_RATES, summarize

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


class RunSuiteRequest(BaseModel):
    model: str = config.DEFAULT_MODEL


@router.get("")
async def get_evaluations():
    records = storage.get_eval_log()
    return {
        "records": records,
        "summary": summarize(records),
        "reference_rates": REFERENCE_RATES,
    }


@router.post("/run-suite")
async def run_suite(payload: RunSuiteRequest):
    await eval_suite.run_suite(payload.model)
    records = storage.get_eval_log()
    suite_records = [r for r in records if r.get("source") == "suite"]
    return {
        "summary": summarize(records),
        "suite_summary": summarize(suite_records),
        "prompts_run": len(eval_suite.REQUIREMENT_PROMPTS) + len(eval_suite.DIAGRAM_PROMPTS),
    }
