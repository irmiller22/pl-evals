import json
from datetime import UTC, datetime

from evals.models import CaseResult, EvalCase, EvalOutput, EvalRun, Grade


def test_eval_models_serialize():
    case = EvalCase(id="case", input={"question": "q"}, expected={"status": "answered"}, graders=[])
    output = EvalOutput(
        response="a",
        structured_output={"status": "unsupported", "reason": "r"},
        tool_calls=[],
        tool_trace=[],
        evidence=[],
        latency_ms=1,
    )
    result = CaseResult(
        case=case,
        status="completed",
        output=output,
        grades=[Grade(grader="schema", score=1, passed=True, reason="ok")],
    )
    run = EvalRun(
        run_id="run",
        model="test",
        dataset_hash="hash",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        cases=[result],
    )
    assert json.loads(run.model_dump_json())["cases"][0]["output"]["response"] == "a"
