import pytest

from evals.graders.abstention import AbstentionGrader
from evals.graders.exact import ExactGrader
from evals.graders.numeric import NumericGrader
from evals.graders.schema import SchemaGrader
from evals.graders.tool_call import ToolCallGrader
from evals.models import EvalCase, EvalOutput


def case(expected, graders=("numeric",)):
    return EvalCase(id="case", input={"question": "q"}, expected=expected, graders=list(graders))


def output(value, *, status="answered", kind="count", calls=None):
    structured = {"status": status}
    if status == "answered":
        structured |= {"kind": kind, "value": value}
    else:
        structured["reason"] = "Unavailable"
    return EvalOutput(
        response="answer",
        structured_output=structured,
        tool_calls=calls or [],
        tool_trace=[],
        evidence=[],
        latency_ms=1,
    )


@pytest.mark.asyncio
async def test_numeric_exact_and_tolerance():
    assert (await NumericGrader().grade(case({"status": "answered", "value": 2}), output(2))).passed
    assert not (
        await NumericGrader().grade(case({"status": "answered", "value": 2}), output(3))
    ).passed
    average = case({"status": "answered", "value": 1.0}, ("numeric",))
    assert (await NumericGrader().grade(average, output(1.0000005, kind="average"))).passed
    assert not (await NumericGrader().grade(average, output(True))).passed


@pytest.mark.asyncio
async def test_exact_is_type_sensitive():
    assert (await ExactGrader().grade(case({"value": False}, ("exact",)), output(False))).passed
    assert not (await ExactGrader().grade(case({"value": False}, ("exact",)), output(0))).passed


@pytest.mark.asyncio
async def test_schema_and_abstention_status():
    unsupported = case({"status": "unsupported"}, ())
    good = output(None, status="unsupported")
    assert (await SchemaGrader().grade(unsupported, good)).passed
    assert (await AbstentionGrader().grade(unsupported, good)).passed
    supported = case({"status": "answered", "kind": "count"}, ())
    assert not (await AbstentionGrader().grade(supported, good)).passed


@pytest.mark.asyncio
async def test_tool_call_semantics_and_extras():
    expected = {
        "tool": {
            "name": "count_team_matches",
            "arguments": {"team": "Manchester United", "venue": "away"},
        }
    }
    calls = [
        {
            "name": "count_team_matches",
            "arguments": {"team": "Manchester United", "venue": "away", "result": "win"},
        }
    ]
    assert not (
        await ToolCallGrader().grade(case(expected, ("tool_call",)), output(1, calls=calls))
    ).passed
    expected["tool"]["allow_extra_arguments"] = True
    assert (
        await ToolCallGrader().grade(case(expected, ("tool_call",)), output(1, calls=calls))
    ).passed
