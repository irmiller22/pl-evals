import asyncio
import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.agent.service import AgentError, AnalystService
from app.agent.types import AskRequest, AskResponse, ModelResponse, TokenUsage, ToolCall
from app.api import app, get_service
from app.config import ModelConfig
from app.football.tools import FootballTools


class ScriptedClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.messages = []

    async def complete(self, **kwargs):
        self.messages.append(list(kwargs["messages"]))
        return next(self.responses)


def tool_response(call_id="one", **args):
    return ModelResponse(
        tool_calls=[
            ToolCall(
                name="count_team_matches", arguments={"team": "Alpha", **args}, call_id=call_id
            )
        ],
        stop_reason="tool_use",
        usage=TokenUsage(input_tokens=10, output_tokens=5),
    )


def final_response(value=4, unsupported=False):
    structured = (
        {"status": "unsupported", "reason": "No player data"}
        if unsupported
        else {"status": "answered", "kind": "count", "value": value}
    )
    return ModelResponse(
        text=json.dumps(
            {
                "answer": "No player data" if unsupported else f"{value} matches",
                "structured_answer": structured,
            }
        ),
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=20, output_tokens=6),
    )


async def test_api_question_tool_answer_trace(repository):
    client = ScriptedClient([tool_response(), final_response()])
    service = AnalystService(client, FootballTools(repository), ModelConfig(model="test"))
    app.dependency_overrides[get_service] = lambda: service
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            response = await http.post("/ask", json={"question": "How many Alpha matches?"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    answer = AskResponse.model_validate(response.json())
    assert answer.structured_answer.value == 4
    assert len(answer.evidence) == 4
    assert answer.usage == TokenUsage(input_tokens=30, output_tokens=11)
    assert answer.tool_trace[0].validated_arguments["venue"] == "all"
    assert client.messages[1][-1].tool_results[0].content == answer.tool_trace[0].result
    assert answer.latency_ms > 0


async def test_unsupported_no_tools(repository):
    service = AnalystService(
        ScriptedClient([final_response(unsupported=True)]),
        FootballTools(repository),
        ModelConfig(model="test"),
    )
    answer = await service.ask(AskRequest(question="Top scorer?"))
    assert answer.structured_answer.status == "unsupported"
    assert answer.evidence == answer.tool_calls == answer.tool_trace == []


async def test_bad_arguments_corrected_and_zero_evidence(repository):
    client = ScriptedClient(
        [
            tool_response(venue="neutral"),
            tool_response("two", venue="away", result="win"),
            final_response(0),
        ]
    )
    answer = await AnalystService(client, FootballTools(repository), ModelConfig(model="test")).ask(
        AskRequest(question="Away wins?")
    )
    assert [item.status for item in answer.tool_trace] == ["validation_error", "success"]
    assert answer.evidence == []
    assert client.messages[1][-1].tool_results[0].is_error


@pytest.mark.parametrize(
    "responses,limits,code",
    [
        ([final_response()], {}, "missing_evidence"),
        ([tool_response()], {"max_model_turns": 1}, "turn_limit"),
        ([tool_response(), tool_response("two")], {"max_tool_calls": 1}, "tool_limit"),
        ([tool_response(), tool_response()], {}, "duplicate_call_id"),
        ([ModelResponse(text="not json", stop_reason="end_turn")], {}, "invalid_answer"),
    ],
)
async def test_execution_failures_preserve_partial_results(repository, responses, limits, code):
    service = AnalystService(
        ScriptedClient(responses), FootballTools(repository), ModelConfig(model="test", **limits)
    )
    with pytest.raises(AgentError) as failure:
        await service.ask(AskRequest(question="Question"))
    assert failure.value.code == code
    assert failure.value.partial_output["latency_ms"] >= 0
    if code in {"turn_limit", "tool_limit", "duplicate_call_id"}:
        assert failure.value.partial_output["tool_trace"][0]["result"]["value"] == 4


async def test_application_deadline(repository):
    class SlowClient:
        async def complete(self, **kwargs):
            await asyncio.sleep(1)

    service = AnalystService(
        SlowClient(),
        FootballTools(repository),
        ModelConfig(model="test", application_timeout_seconds=0.01),
    )
    with pytest.raises(AgentError) as failure:
        await service.ask(AskRequest(question="Question"))
    assert failure.value.code == "timeout"


async def test_missing_credentials_is_explicit(monkeypatch):
    for key in ("APP_MODEL", "BASELINE_MODEL", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        response = await http.post("/ask", json={"question": "Question"})
        health = await http.get("/health")
    assert response.status_code == 503
    assert health.status_code == 200


async def test_multiple_tools_and_missing_usage(repository):
    first = tool_response()
    first.tool_calls.append(
        ToolCall(name="count_team_matches", arguments={"team": "Beta"}, call_id="two")
    )
    first.usage = None
    client = ScriptedClient([first, final_response()])
    answer = await AnalystService(client, FootballTools(repository), ModelConfig(model="test")).ask(
        AskRequest(question="Compare Alpha and Beta")
    )
    assert len(answer.tool_trace) == 2
    assert len(answer.evidence) == 4  # Duplicate evidence IDs are removed.
    assert len(client.messages[1][-1].tool_results) == 2
    assert answer.usage is None


async def test_tool_failure_is_returned_without_internal_details(repository, monkeypatch):
    tools = FootballTools(repository)

    def broken(*args):
        raise RuntimeError("private database path")

    monkeypatch.setattr(tools, "execute", broken)
    client = ScriptedClient([tool_response(), final_response(unsupported=True)])
    answer = await AnalystService(client, tools, ModelConfig(model="test")).ask(
        AskRequest(question="Question")
    )
    assert answer.tool_trace[0].status == "tool_error"
    assert answer.tool_trace[0].result is None
    assert "private" not in answer.model_dump_json()


@pytest.mark.parametrize("question", ["", "   ", "x" * 10001])
async def test_api_invalid_question(repository, question):
    service = AnalystService(
        ScriptedClient([]), FootballTools(repository), ModelConfig(model="test")
    )
    app.dependency_overrides[get_service] = lambda: service
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            response = await http.post("/ask", json={"question": question})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 422


async def test_api_returns_structured_failure(repository):
    service = AnalystService(
        ScriptedClient([final_response()]), FootballTools(repository), ModelConfig(model="test")
    )
    app.dependency_overrides[get_service] = lambda: service
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
            response = await http.post("/ask", json={"question": "Question"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 502
    assert response.json()["detail"]["code"] == "missing_evidence"
    assert "partial_output" in response.json()["detail"]
