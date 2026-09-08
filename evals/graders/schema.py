"""Deterministic validation of the application response shape."""

from evals.graders.base import failed, passed
from evals.models import EvalCase, EvalOutput, Grade


class SchemaGrader:
    name = "schema"

    async def grade(self, case: EvalCase, output: EvalOutput) -> Grade:
        value = output.structured_output
        if not isinstance(value, dict) or value.get("status") not in {"answered", "unsupported"}:
            return failed(self.name, "structured_output must have status answered or unsupported")
        if value["status"] == "unsupported":
            if not isinstance(value.get("reason"), str) or not value["reason"].strip():
                return failed(self.name, "Unsupported output requires a nonempty reason")
            if "kind" in value or "value" in value:
                return failed(self.name, "Unsupported output cannot contain kind or value")
        else:
            if not isinstance(value.get("kind"), str) or "value" not in value:
                return failed(self.name, "Answered output requires kind and value")
            expected_kind = case.expected.get("kind")
            if expected_kind is not None and value["kind"] != expected_kind:
                return failed(
                    self.name, f"Expected answer kind {expected_kind!r}, got {value['kind']!r}"
                )
        expected_status = case.expected.get("status")
        if expected_status is not None and value["status"] != expected_status:
            return failed(
                self.name, f"Expected status {expected_status!r}, got {value['status']!r}"
            )
        return passed(self.name, "Structured output matches the required response shape")
