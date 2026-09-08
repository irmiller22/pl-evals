"""Provider-independent evaluation data contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EvalModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvalCase(EvalModel):
    id: str = Field(min_length=1)
    input: dict
    expected: dict
    graders: list[str]
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class EvalOutput(EvalModel):
    response: str
    structured_output: dict | None
    tool_calls: list[dict]
    tool_trace: list[dict]
    evidence: list[str]
    latency_ms: float = Field(ge=0, allow_inf_nan=False)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    metadata: dict = Field(default_factory=dict)


class Grade(EvalModel):
    grader: str
    status: Literal["completed", "error", "skipped"] = "completed"
    score: float = Field(ge=0, le=1, allow_inf_nan=False)
    passed: bool
    reason: str
    metadata: dict = Field(default_factory=dict)


class CaseResult(EvalModel):
    case: EvalCase
    status: Literal["completed", "execution_error", "timeout"]
    output: EvalOutput | None = None
    error: dict | None = None
    partial_output: dict | None = None
    grades: list[Grade] = Field(default_factory=list)


class EvalRun(EvalModel):
    run_id: str
    model: str
    git_sha: str | None = None
    dataset_hash: str
    started_at: datetime
    completed_at: datetime
    cases: list[CaseResult]
