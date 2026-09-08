"""Semantic expected-tool matching, independent of football-specific aliases."""

from evals.graders.base import failed, passed
from evals.models import EvalCase, EvalOutput, Grade


class ToolCallGrader:
    name = "tool_call"

    async def grade(self, case: EvalCase, output: EvalOutput) -> Grade:
        expected = case.expected.get("tool")
        if not isinstance(expected, dict):
            return failed(self.name, "Case has no expected tool call")
        calls = output.tool_calls
        matches = [call for call in calls if call.get("name") == expected.get("name")]
        if not matches:
            return failed(
                self.name,
                f"Expected tool {expected.get('name')!r}, got {[c.get('name') for c in calls]}",
            )
        actual = matches[0].get("arguments", {})
        required = expected.get("arguments", {})
        mismatches = {
            key: (required_value, actual.get(key))
            for key, required_value in required.items()
            if actual.get(key) != required_value
        }
        allow_extra = bool(expected.get("allow_extra_arguments", False))
        extras = set(actual) - set(required)
        if mismatches:
            return failed(self.name, f"Tool arguments mismatched: {mismatches}")
        if extras and not allow_extra:
            return failed(self.name, f"Unexpected tool arguments: {sorted(extras)}")
        return passed(self.name, "Expected tool and semantic arguments were used")
