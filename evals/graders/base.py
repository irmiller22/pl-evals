"""Shared grader protocol and helper for consistent results."""

from typing import Any, Protocol

from evals.models import EvalCase, EvalOutput, Grade


class Grader(Protocol):
    name: str

    async def grade(self, case: EvalCase, output: EvalOutput) -> Grade: ...


def passed(name: str, reason: str, score: float = 1.0, **metadata: Any) -> Grade:
    return Grade(grader=name, score=score, passed=True, reason=reason, metadata=metadata)


def failed(name: str, reason: str, score: float = 0.0, **metadata: Any) -> Grade:
    return Grade(grader=name, score=score, passed=False, reason=reason, metadata=metadata)
