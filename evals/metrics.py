"""Aggregate quality and performance metrics for evaluation runs."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from evals.models import EvalRun


def percentile(values: list[float], p: float) -> float | None:
    """Return an interpolated percentile, or None for an empty sample."""
    if not values:
        return None
    if not 0 <= p <= 100:
        raise ValueError("percentile must be between 0 and 100")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * p / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def aggregate(run: EvalRun) -> dict[str, Any]:
    cases = run.cases
    case_passes = [
        result.status == "completed"
        and bool(result.grades)
        and all(grade.status == "completed" and grade.passed for grade in result.grades)
        for result in cases
    ]
    metrics: dict[str, Any] = {
        "case_count": len(cases),
        "completed_cases": sum(result.status == "completed" for result in cases),
        "execution_failures": sum(result.status != "completed" for result in cases),
        "overall_pass_rate": sum(case_passes) / len(cases) if cases else None,
        "grader": {},
        "latency_ms": {},
        "tokens": {},
        "cost_usd": {},
        "failures_by_tag": {},
    }

    assigned: dict[str, list[Any]] = defaultdict(list)
    for result in cases:
        for grade in result.grades:
            assigned[grade.grader].append(grade)
    for name, grades in sorted(assigned.items()):
        metrics["grader"][name] = {
            "pass_rate": sum(grade.passed and grade.status == "completed" for grade in grades)
            / len(grades),
            "mean_score": sum(grade.score for grade in grades) / len(grades),
            "case_count": len(grades),
            "errors": sum(grade.status == "error" for grade in grades),
            "skipped": sum(grade.status == "skipped" for grade in grades),
        }

    latencies = [result.output.latency_ms for result in cases if result.output is not None]
    metrics["latency_ms"] = {
        "mean": sum(latencies) / len(latencies) if latencies else None,
        "p50": percentile(latencies, 50),
        "p95": percentile(latencies, 95),
        "measured_cases": len(latencies),
    }
    inputs = [
        result.output.input_tokens
        for result in cases
        if result.output and result.output.input_tokens is not None
    ]
    outputs = [
        result.output.output_tokens
        for result in cases
        if result.output and result.output.output_tokens is not None
    ]
    costs = [
        result.output.estimated_cost_usd
        for result in cases
        if result.output and result.output.estimated_cost_usd is not None
    ]
    metrics["tokens"] = {
        "input_total": sum(inputs) if len(inputs) == len(cases) else None,
        "output_total": sum(outputs) if len(outputs) == len(cases) else None,
        "input_measured_cases": len(inputs),
        "output_measured_cases": len(outputs),
        "average_total_per_request": (sum(inputs) + sum(outputs)) / len(cases)
        if len(inputs) == len(cases) and len(outputs) == len(cases)
        else None,
    }
    metrics["cost_usd"] = {
        "total": sum(costs) if len(costs) == len(cases) else None,
        "average_per_request": sum(costs) / len(cases)
        if len(costs) == len(cases) and cases
        else None,
        "measured_cases": len(costs),
    }
    failed_tags: Counter[str] = Counter(
        tag
        for result, passed in zip(cases, case_passes, strict=True)
        if not passed
        for tag in result.case.tags
    )
    metrics["failures_by_tag"] = dict(sorted(failed_tags.items()))
    return metrics


@dataclass(frozen=True)
class CaseDelta:
    case_id: str
    classification: str
    baseline_passed: bool
    candidate_passed: bool


def compare(baseline: EvalRun, candidate: EvalRun) -> dict[str, Any]:
    baseline_by_id = {result.case.id: result for result in baseline.cases}
    candidate_by_id = {result.case.id: result for result in candidate.cases}
    if set(baseline_by_id) != set(candidate_by_id):
        raise ValueError("Baseline and candidate must contain the same case IDs")

    def passed(result: Any) -> bool:
        return (
            result.status == "completed"
            and bool(result.grades)
            and all(grade.status == "completed" and grade.passed for grade in result.grades)
        )

    deltas: list[CaseDelta] = []
    for case_id in sorted(baseline_by_id):
        base_passed, cand_passed = passed(baseline_by_id[case_id]), passed(candidate_by_id[case_id])
        if base_passed and cand_passed:
            classification = "both_pass"
        elif not base_passed and not cand_passed:
            classification = "both_fail"
        elif base_passed:
            classification = "baseline_only_pass"
        else:
            classification = "candidate_only_pass"
        deltas.append(CaseDelta(case_id, classification, base_passed, cand_passed))

    base_metrics, cand_metrics = aggregate(baseline), aggregate(candidate)
    return {
        "baseline": base_metrics,
        "candidate": cand_metrics,
        "case_deltas": [delta.__dict__ for delta in deltas],
        "classification_counts": dict(Counter(delta.classification for delta in deltas)),
        "metric_deltas": {
            "overall_pass_rate": _delta(
                base_metrics["overall_pass_rate"], cand_metrics["overall_pass_rate"]
            ),
            "latency_p95_ms": _delta(
                base_metrics["latency_ms"]["p95"], cand_metrics["latency_ms"]["p95"]
            ),
            "average_cost_usd": _delta(
                base_metrics["cost_usd"]["average_per_request"],
                cand_metrics["cost_usd"]["average_per_request"],
            ),
            "input_tokens": _delta(
                base_metrics["tokens"]["input_total"], cand_metrics["tokens"]["input_total"]
            ),
            "output_tokens": _delta(
                base_metrics["tokens"]["output_total"], cand_metrics["tokens"]["output_total"]
            ),
            "average_tokens_per_request": _delta(
                base_metrics["tokens"]["average_total_per_request"],
                cand_metrics["tokens"]["average_total_per_request"],
            ),
        },
    }


def _delta(baseline: float | None, candidate: float | None) -> float | None:
    return candidate - baseline if baseline is not None and candidate is not None else None
