from typing import Dict, List

from pydantic import BaseModel, ConfigDict, Field


class GenerateRequest(BaseModel):
    prompt: str = Field(..., max_length=4000)
    model: str
    run_sanity_check: bool = True


class Requirement(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    stereotype: str
    name: str
    text: str
    verify_method: str = Field(alias="verifyMethod")
    reprompts: int = 0


class GenerationMetrics(BaseModel):
    task: str
    model: str
    provider: str
    source: str
    llm_calls: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    duration_ms: float
    items: int
    first_pass_rate: float
    success_rate: float
    timestamp: str
    cost_estimate_usd: Dict[str, float]
    actual_cost_usd: float = 0.0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class GenerateResponse(BaseModel):
    requirements: List[Requirement]
    log: List[str]
    metrics: GenerationMetrics


class Block(BaseModel):
    id: str
    name: str
    description: str = ""
    isRoot: bool = False


class Connector(BaseModel):
    id: str
    source: str
    target: str
    kind: str
    label: str = ""


class GenerateDiagramRequest(BaseModel):
    prompt: str = Field(..., max_length=4000)
    model: str


class GenerateDiagramResponse(BaseModel):
    blocks: List[Block]
    connectors: List[Connector]
    log: List[str]
    metrics: GenerationMetrics
