"""Type-sensitive exact checks against structured values."""

from evals.graders._utils import actual_answer, pointer
from evals.graders.base import failed, passed
from evals.models import EvalCase, EvalOutput, Grade


class ExactGrader:
    name = "exact"

    async def grade(self, case: EvalCase, output: EvalOutput) -> Grade:
        expected = case.expected
        checks = expected.get("exact_checks") or [
            {"path": "/value", "value": expected.get("value")}
        ]
        for check in checks:
            try:
                actual = pointer(actual_answer(output), check.get("path", "/value"))
            except (KeyError, IndexError, ValueError, TypeError):
                return failed(self.name, f"Missing value at {check.get('path', '/value')}")
            target = check.get("value")
            if type(actual) is not type(target) or actual != target:
                return failed(self.name, f"Expected {target!r}, got {actual!r}")
        return passed(self.name, "All configured exact values matched")
