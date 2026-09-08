"""Compact terminal output for local runs."""

from typing import Any


def print_summary(metrics: dict[str, Any]) -> None:
    print(f"Cases: {metrics['case_count']}")
    print(f"Pass rate: {_fmt(metrics['overall_pass_rate'])}")
    print(f"P95 latency (ms): {_fmt(metrics['latency_ms']['p95'])}")
    print(f"Average cost (USD): {_fmt(metrics['cost_usd']['average_per_request'])}")
    for name, value in metrics["grader"].items():
        print(f"{name}: {_fmt(value['pass_rate'])}")


def _fmt(value: Any) -> str:
    return (
        "unavailable"
        if value is None
        else f"{value:.4f}"
        if isinstance(value, float)
        else str(value)
    )
