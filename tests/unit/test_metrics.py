from datetime import UTC, datetime

import pytest

from evals.metrics import aggregate, compare, percentile
from evals.models import CaseResult, EvalCase, EvalOutput, EvalRun, Grade


def result(case_id: str, passed: bool, latency: float, tags=None) -> CaseResult:
    case = EvalCase(
        id=case_id, input={"question": case_id}, expected={}, graders=[], tags=tags or []
    )
    return CaseResult(
        case=case,
        status="completed",
        output=EvalOutput(
            response="",
            structured_output=None,
            tool_calls=[],
            tool_trace=[],
            evidence=[],
            latency_ms=latency,
            input_tokens=10,
            output_tokens=5,
            estimated_cost_usd=0.01,
        ),
        grades=[Grade(grader="schema", score=float(passed), passed=passed, reason="test")],
    )


def run(results):
    now = datetime.now(UTC)
    return EvalRun(
        run_id="run",
        model="test",
        dataset_hash="hash",
        started_at=now,
        completed_at=now,
        cases=results,
    )


def test_percentile_and_empty():
    assert percentile([], 50) is None
    assert percentile([1, 2, 3, 4], 50) == 2.5
    with pytest.raises(ValueError):
        percentile([1], 101)


def test_aggregate_includes_failures_and_missing_usage():
    metrics = aggregate(
        run([result("a", True, 100, ["team:a"]), result("b", False, 300, ["team:b"])])
    )
    assert metrics["overall_pass_rate"] == 0.5
    assert metrics["grader"]["schema"]["pass_rate"] == 0.5
    assert metrics["latency_ms"]["p95"] == 290
    assert metrics["tokens"]["input_total"] == 20
    assert metrics["cost_usd"]["total"] == 0.02
    assert metrics["failures_by_tag"] == {"team:b": 1}


def test_missing_cost_is_unavailable():
    item = result("a", True, 100)
    item.output.estimated_cost_usd = None
    assert aggregate(run([item]))["cost_usd"]["total"] is None


def test_compare_classifies_cases_and_requires_same_set():
    base = run([result("a", True, 100), result("b", False, 100), result("c", False, 100)])
    cand = run([result("a", False, 200), result("b", True, 200), result("c", False, 200)])
    comparison = compare(base, cand)
    assert comparison["classification_counts"] == {
        "baseline_only_pass": 1,
        "candidate_only_pass": 1,
        "both_fail": 1,
    }
    assert comparison["metric_deltas"]["overall_pass_rate"] == 0
    with pytest.raises(ValueError, match="same case IDs"):
        compare(base, run([result("a", True, 100)]))
