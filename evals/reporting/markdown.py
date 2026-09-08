"""Readable comparison report with actionable per-case regressions."""

from pathlib import Path
from typing import Any

from evals.models import EvalRun


def render_comparison(comparison: dict[str, Any], baseline: EvalRun, candidate: EvalRun) -> str:
    lines = [
        "# Evaluation comparison",
        "",
        "## Summary",
        "",
        f"- Baseline: `{baseline.model}`",
        f"- Candidate: `{candidate.model}`",
        f"- Cases: {len(candidate.cases)}",
        "",
        "## Metrics",
        "",
        "| Metric | Baseline | Candidate | Delta |",
        "|---|---:|---:|---:|",
    ]
    for name, delta in comparison["metric_deltas"].items():
        base = _metric_value(comparison["baseline"], name)
        cand = _metric_value(comparison["candidate"], name)
        lines.append(f"| {name} | {_fmt(base)} | {_fmt(cand)} | {_fmt(delta)} |")
    regressions = [
        item for item in comparison["case_deltas"] if item["classification"] == "baseline_only_pass"
    ]
    improvements = [
        item
        for item in comparison["case_deltas"]
        if item["classification"] == "candidate_only_pass"
    ]
    lines += ["", "## Regressions", ""] + _case_list(regressions, baseline, candidate)
    lines += ["", "## Improvements", ""] + _case_list(improvements, baseline, candidate)
    return "\n".join(lines) + "\n"


def write_comparison_report(
    comparison: dict[str, Any], baseline: EvalRun, candidate: EvalRun, directory: Path
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "report.md"
    path.write_text(render_comparison(comparison, baseline, candidate), encoding="utf-8")
    return path


def _metric_value(metrics: dict[str, Any], name: str) -> float | None:
    mapping = {
        "overall_pass_rate": ("overall_pass_rate",),
        "latency_p95_ms": ("latency_ms", "p95"),
        "average_cost_usd": ("cost_usd", "average_per_request"),
    }
    value: Any = metrics
    for key in mapping[name]:
        value = value.get(key) if isinstance(value, dict) else None
    return value


def _fmt(value: Any) -> str:
    return (
        "unavailable"
        if value is None
        else f"{value:.6g}"
        if isinstance(value, float)
        else str(value)
    )


def _case_list(items: list[dict[str, Any]], baseline: EvalRun, candidate: EvalRun) -> list[str]:
    base = {item.case.id: item for item in baseline.cases}
    cand = {item.case.id: item for item in candidate.cases}
    lines: list[str] = []
    if not items:
        return ["No cases."]
    for item in items:
        case_id = item["case_id"]
        lines += [
            f"### `{case_id}`",
            "",
            f"Question: {cand[case_id].case.input.get('question', '')}",
            f"Baseline status: `{base[case_id].status}`; "
            f"Candidate status: `{cand[case_id].status}`",
            "",
        ]
    return lines
