import json

import pytest

from app.agent.model import ModelError
from app.agent.types import ModelResponse
from app.config import ModelConfig
from evals.graders.llm_judge import JudgeError, LLMJudgeGrader
from evals.models import EvalCase, EvalOutput


class JudgeClient:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.system, self.message = response, error, None, None

    async def complete(self, **kwargs):
        self.system, self.message = kwargs["system"], kwargs["messages"][0].text
        if self.error:
            raise self.error
        return ModelResponse(text=self.response, stop_reason="end_turn")


def case():
    return EvalCase(id="case", input={"question": "How many?"}, expected={}, graders=[])


def output():
    return EvalOutput(
        response="Four",
        structured_output={"status": "answered", "kind": "count", "value": 4},
        tool_calls=[],
        tool_trace=[{"status": "success", "result": {"value": 4, "evidence": ["m1"]}}],
        evidence=["m1"],
        latency_ms=1,
    )


@pytest.mark.asyncio
async def test_judge_normalizes_and_marks_pass():
    client = JudgeClient(json.dumps({"score": 4, "reason": "Supported by the tool result."}))
    grade = await LLMJudgeGrader(client, ModelConfig(model="judge"), "rubric").grade(
        case(), output()
    )
    assert grade.passed and grade.score == 1 and grade.metadata["judge_score"] == 4
    assert "DATA" in client.message and "RUBRIC" in client.system


@pytest.mark.asyncio
async def test_judge_low_score_is_quality_failure():
    client = JudgeClient('{"score": 2, "reason":"Partial support"}')
    grade = await LLMJudgeGrader(client, ModelConfig(model="judge"), "rubric").grade(
        case(), output()
    )
    assert not grade.passed and grade.score == 0.5


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "{}",
        '{"score": 5, "reason":"bad"}',
        '{"score": 2.0, "reason":"bad"}',
        '{"score": 2, "reason":" "}',
    ],
)
@pytest.mark.asyncio
async def test_judge_rejects_malformed_output(text):
    with pytest.raises(JudgeError):
        await LLMJudgeGrader(JudgeClient(text), ModelConfig(model="judge"), "rubric").grade(
            case(), output()
        )


@pytest.mark.asyncio
async def test_judge_provider_failure_is_sanitized():
    with pytest.raises(JudgeError, match="provider"):
        await LLMJudgeGrader(
            JudgeClient(error=ModelError("provider_http", "provider body secret")),
            ModelConfig(model="judge"),
            "rubric",
        ).grade(case(), output())
