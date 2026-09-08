"""Threshold and regression policy evaluation for runs and comparisons."""

from dataclasses import dataclass, field
from typing import Any

from evals.metrics import aggregate, compare
from evals.models import EvalRun


@dataclass(frozen=True)
class PolicyResult:
    passed: bool
    violations: list[str] = field(default_factory=list)


def evaluate(
    run: EvalRun, policy: dict[str, dict[str, float]], *, critical_cases: bool = False
) -> PolicyResult:
    metrics = aggregate(run)
    violations = _absolute_violations(metrics, policy)
    if critical_cases:
        violations.extend(_critical_violations(run))
    return PolicyResult(not violations, violations)


def evaluate_comparison(
    baseline: EvalRun,
    candidate: EvalRun,
    policy: dict[str, dict[str, float]],
    *,
    critical_cases: bool = False,
) -> PolicyResult:
    comparison = compare(baseline, candidate)
    violations = _absolute_violations(comparison["candidate"], policy)
    base, cand = comparison["baseline"], comparison["candidate"]
    for name, rule in policy.items():
        maximum_regression = rule.get("max_regression")
        if maximum_regression is None:
            continue
        before = _metric(base, name)
        after = _metric(cand, name)
        if before is None or after is None:
            violations.append(f"{name}: unavailable for regression comparison")
        elif before - after > maximum_regression:
            violations.append(
                f"{name}: regressed by {before - after:.6g}, maximum is {maximum_regression:.6g}"
            )
    if critical_cases:
        violations.extend(_critical_violations(candidate))
    return PolicyResult(not violations, violations)


def _absolute_violations(metrics: dict[str, Any], policy: dict[str, dict[str, float]]) -> list[str]:
    violations = []
    for name, rule in policy.items():
        minimum, maximum = rule.get("minimum"), rule.get("maximum")
        value = _metric(metrics, name)
        if value is None and (minimum is not None or maximum is not None):
            violations.append(f"{name}: metric unavailable")
        elif value is not None and minimum is not None and value < minimum:
            violations.append(f"{name}: {value:.6g} is below minimum {minimum:.6g}")
        elif value is not None and maximum is not None and value > maximum:
            violations.append(f"{name}: {value:.6g} exceeds maximum {maximum:.6g}")
    return violations


def _metric(metrics: dict[str, Any], name: str) -> float | None:
    if name in metrics.get("grader", {}):
        return metrics["grader"][name]["pass_rate"]
    aliases = {
        "p95_latency_ms": ("latency_ms", "p95"),
        "avg_cost_usd": ("cost_usd", "average_per_request"),
    }
    if name in aliases:
        group, key = aliases[name]
        return metrics[group][key]
    if name == "overall_pass_rate":
        return metrics["overall_pass_rate"]
    return None


def _critical_violations(run: EvalRun) -> list[str]:
    violations = []
    for result in run.cases:
        if "criticality:high" not in result.case.tags:
            continue
        if (
            result.status != "completed"
            or not result.grades
            or not all(grade.status == "completed" and grade.passed for grade in result.grades)
        ):
            violations.append(f"critical case failed: {result.case.id}")
    return violations
