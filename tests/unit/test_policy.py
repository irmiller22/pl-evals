from datetime import UTC, datetime

from evals.models import CaseResult, EvalCase, EvalOutput, EvalRun, Grade
from evals.policy import evaluate, evaluate_comparison


def run(case_id: str, passed: bool, tags=None) -> EvalRun:
    now = datetime.now(UTC)
    case = EvalCase(id=case_id, input={"question": "q"}, expected={}, graders=[], tags=tags or [])
    result = CaseResult(
        case=case,
        status="completed",
        output=EvalOutput(
            response="",
            structured_output=None,
            tool_calls=[],
            tool_trace=[],
            evidence=[],
            latency_ms=100,
            input_tokens=10,
            output_tokens=5,
            estimated_cost_usd=0.001,
        ),
        grades=[Grade(grader="numeric", score=float(passed), passed=passed, reason="test")],
    )
    return EvalRun(
        run_id=case_id,
        model="test",
        dataset_hash="hash",
        started_at=now,
        completed_at=now,
        cases=[result],
    )


def test_absolute_threshold_and_boundary():
    policy = {"numeric": {"minimum": 1}, "p95_latency_ms": {"maximum": 100}}
    assert evaluate(run("a", True), policy).passed
    assert not evaluate(run("a", False), policy).passed


def test_regression_and_critical_case():
    baseline, candidate = run("a", True), run("a", False, ["criticality:high"])
    policy = {"numeric": {"minimum": 0, "max_regression": 0}}
    result = evaluate_comparison(baseline, candidate, policy, critical_cases=True)
    assert not result.passed
    assert any("regressed" in item for item in result.violations)
    assert any("critical case" in item for item in result.violations)


def test_unavailable_metric_fails():
    result = evaluate(run("a", True), {"groundedness": {"minimum": 0.9}})
    assert not result.passed
    assert "unavailable" in result.violations[0]
