from pathlib import Path

import pytest

from app.config import ModelConfig
from evals.models import EvalOutput
from evals.runner import run_paired


class Adapter:
    def __init__(self, value):
        self.value = value

    async def run(self, case, model_config):
        expected = case.expected
        if expected.get("status") == "unsupported":
            structured = {"status": "unsupported", "reason": "Unavailable"}
        else:
            structured = {"status": "answered", "kind": expected["kind"], "value": self.value}
        return EvalOutput(
            response="answer",
            structured_output=structured,
            tool_calls=[],
            tool_trace=[],
            evidence=[],
            latency_ms=1,
            input_tokens=2,
            output_tokens=1,
        )


@pytest.mark.asyncio
async def test_paired_runs_share_cases_and_metadata():
    baseline, candidate = await run_paired(
        [Path("evals/datasets/smoke.jsonl")],
        Adapter(4),
        Adapter(3),
        ModelConfig(model="baseline"),
        ModelConfig(model="candidate"),
        concurrency=2,
        metadata={"dataset": "smoke"},
    )
    assert [result.case.id for result in baseline.cases] == [
        result.case.id for result in candidate.cases
    ]
    assert baseline.metadata["role"] == "baseline"
    assert candidate.metadata["role"] == "candidate"
    assert baseline.dataset_hash == candidate.dataset_hash
