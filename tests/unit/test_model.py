import json

import httpx
import pytest

from app.agent.model import AnthropicClient, ModelError, retry_delay
from app.agent.types import Message, ToolCall, ToolDefinition, ToolReply
from app.config import ModelConfig


def response_body(**overrides):
    return {
        "content": [{"type": "text", "text": "{}"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 10, "output_tokens": 4},
        **overrides,
    }


async def test_wire_contract_and_cache_usage():
    def handler(request):
        payload = json.loads(request.content)
        assert request.headers["anthropic-version"] == "2023-06-01"
        assert request.headers["x-api-key"] == "test-key"
        assert payload["model"] == "test-model"
        assert payload["system"] == "system"
        assert payload["tools"][0]["input_schema"] == {"type": "object"}
        assert payload["messages"][1]["content"][0]["type"] == "tool_use"
        assert payload["messages"][2]["content"][0]["tool_use_id"] == "call-1"
        return httpx.Response(
            200,
            json=response_body(
                usage={
                    "input_tokens": 10,
                    "output_tokens": 4,
                    "cache_read_input_tokens": 20,
                    "cache_creation_input_tokens": 5,
                }
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await AnthropicClient("test-key", http).complete(
            system="system",
            messages=[
                Message(role="user", text="question"),
                Message(
                    role="assistant",
                    tool_calls=[ToolCall(call_id="call-1", name="tool", arguments={})],
                ),
                Message(
                    role="user", tool_results=[ToolReply(call_id="call-1", content={"value": 2})]
                ),
            ],
            tools=[ToolDefinition(name="tool", description="test", parameters={"type": "object"})],
            config=ModelConfig(model="anthropic/test-model"),
        )
    assert result.usage.input_tokens == 35
    assert result.usage.output_tokens == 4


@pytest.mark.parametrize("status,expected_calls", [(429, 3), (500, 3), (401, 1), (400, 1)])
async def test_retry_budget_and_safe_errors(status, expected_calls):
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(status, text="secret-provider-body", headers={"retry-after": "0"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(ModelError) as failure:
            await AnthropicClient("test-key", http).complete(
                system="system",
                messages=[],
                tools=[],
                config=ModelConfig(model="test-model", retry_backoff_seconds=0),
            )
    assert calls == expected_calls == failure.value.attempts
    assert "secret" not in str(failure.value)


@pytest.mark.parametrize(
    "body",
    [
        response_body(stop_reason="max_tokens"),
        {},
        response_body(content=[{"type": "tool_use", "id": "x", "name": "tool", "input": []}]),
        response_body(stop_reason="tool_use"),
    ],
)
async def test_invalid_provider_output_not_retried(body):
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(ModelError, match="invalid or incomplete"):
            await AnthropicClient("key", http).complete(
                system="", messages=[], tools=[], config=ModelConfig(model="test")
            )
    assert calls == 1


def test_retry_after_validation():
    assert retry_delay("0", 1) == 0
    assert retry_delay("-1", 2) == 2
    assert retry_delay("nan", 2) == 2
    assert retry_delay("garbage", 2) == 2


async def test_transient_transport_recovers_with_tool_call():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("private connection detail")
        return httpx.Response(
            200,
            json=response_body(
                stop_reason="tool_use",
                content=[
                    {
                        "type": "tool_use",
                        "id": "one",
                        "name": "count_team_matches",
                        "input": {"team": "Alpha"},
                    }
                ],
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        response = await AnthropicClient("key", http).complete(
            system="system",
            messages=[],
            tools=[],
            config=ModelConfig(model="test", retry_backoff_seconds=0),
        )
    assert calls == 2
    assert response.tool_calls[0].arguments == {"team": "Alpha"}
