"""Structured supported/unsupported behavior grader."""

from evals.graders.base import failed, passed
from evals.models import EvalCase, EvalOutput, Grade


class AbstentionGrader:
    name = "abstention"

    async def grade(self, case: EvalCase, output: EvalOutput) -> Grade:
        expected = case.expected.get("status")
        actual = (output.structured_output or {}).get("status")
        if expected not in {"answered", "unsupported"}:
            return failed(self.name, "Case must declare expected status answered or unsupported")
        if actual != expected:
            return failed(self.name, f"Expected status {expected!r}, got {actual!r}")
        return passed(self.name, f"Structured status correctly indicates {expected}")
