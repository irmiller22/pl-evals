from pathlib import Path

import pytest

from app.agent.service import AgentError
from app.config import ModelConfig
from evals.models import EvalCase, EvalOutput
from evals.runner import effective_graders, load_cases, run_cases


def test_load_cases_is_sorted_and_hashed():
    path = Path("evals/datasets/smoke.jsonl")
    cases, digest = load_cases([path], tag="smoke")
    assert [case.id for case in cases] == sorted(case.id for case in cases)
    assert len(digest) == 64
    assert "schema" in effective_graders(cases[0])
    with pytest.raises(ValueError, match="No evaluation"):
        load_cases([path], tag="missing")


class FakeAdapter:
    def __init__(self, failures=()):
        self.failures = set(failures)

    async def run(self, case: EvalCase, model_config: ModelConfig) -> EvalOutput:
        if case.id in self.failures:
            raise AgentError("timeout", "Application deadline exceeded", {"tool_trace": []})
        if case.expected.get("status") == "unsupported":
            structured = {"status": "unsupported", "reason": "Unavailable"}
        else:
            structured = {
                "status": "answered",
                "kind": case.expected["kind"],
                "value": case.expected["value"],
            }
        return EvalOutput(
            response="answer",
            structured_output=structured,
            tool_calls=[],
            tool_trace=[],
            evidence=[],
            latency_ms=1,
        )


@pytest.mark.asyncio
async def test_runner_continues_after_case_failure():
    cases, _ = load_cases([Path("evals/datasets/smoke.jsonl")])
    results = await run_cases(
        cases, FakeAdapter({cases[0].id}), ModelConfig(model="test"), concurrency=2
    )
    assert len(results) == 4
    assert results[0].status == "timeout"
    assert all(result.grades for result in results)
    assert results[1].status == "completed"
