"""Numeric comparisons against structured answer values."""

from evals.graders._utils import actual_answer, finite_number, pointer
from evals.graders.base import failed, passed
from evals.models import EvalCase, EvalOutput, Grade


class NumericGrader:
    name = "numeric"

    async def grade(self, case: EvalCase, output: EvalOutput) -> Grade:
        expected = case.expected
        checks = expected.get("numeric_checks")
        if checks is None:
            checks = [{"path": "/value", "value": expected.get("value")}]
        if expected.get("status", "answered") != "answered":
            return failed(self.name, "Expected case is not an answered numeric result")
        for check in checks:
            target = check.get("value")
            if not finite_number(target):
                return failed(self.name, "Expected numeric value is missing or invalid")
            try:
                actual = pointer(actual_answer(output), check.get("path", "/value"))
            except (KeyError, IndexError, ValueError, TypeError):
                return failed(self.name, f"Missing numeric value at {check.get('path', '/value')}")
            if not finite_number(actual):
                return failed(self.name, "Actual numeric value is missing or invalid")
            if check.get("exact", False):
                matches = type(actual) is type(target) and actual == target
            else:
                abs_tol = check.get("abs_tol", 0.000001)
                rel_tol = check.get("rel_tol", 0)
                matches = abs(actual - target) <= max(abs_tol, rel_tol * abs(target))
            if not matches:
                return failed(
                    self.name, f"Expected {target} at {check.get('path', '/value')}, got {actual}"
                )
        return passed(self.name, "All configured numeric values matched")
