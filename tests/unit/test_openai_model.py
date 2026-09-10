import json

import httpx
import pytest

from app.agent.model import OpenAIClient
from app.agent.types import Message, ModelResponse, ToolDefinition, ToolReply
from app.config import ModelConfig


def body(*, function=False):
    output = (
        [
            {
                "type": "function_call",
                "call_id": "call-1",
                "name": "tool",
                "arguments": '{"team":"Alpha"}',
            }
        ]
        if function
        else [{"type": "message", "content": [{"type": "output_text", "text": '{"ok":true}'}]}]
    )
    return {"output": output, "usage": {"input_tokens": 12, "output_tokens": 5}}


@pytest.mark.asyncio
async def test_openai_responses_wire_format_and_parse():
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json=body(
                function=not any(
                    item.get("type") == "function_call_output" for item in requests[-1]["input"]
                )
            ),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = OpenAIClient("openai-key", http)
        first = await client.complete(
            system="system",
            messages=[Message(role="user", text="question")],
            tools=[ToolDefinition(name="tool", description="desc", parameters={"type": "object"})],
            config=ModelConfig(model="openai/gpt-5-mini"),
        )
        second = await client.complete(
            system="system",
            messages=[
                Message(role="user", text="question"),
                Message(role="assistant", tool_calls=first.tool_calls),
                Message(
                    role="user", tool_results=[ToolReply(call_id="call-1", content={"value": 1})]
                ),
            ],
            tools=[],
            config=ModelConfig(model="openai/gpt-5-mini"),
        )
    assert isinstance(first, ModelResponse)
    assert first.tool_calls[0].arguments == {"team": "Alpha"}
    assert second.text == '{"ok":true}'
    assert requests[0]["tools"][0]["type"] == "function"
    assert requests[1]["input"][-1]["type"] == "function_call_output"


@pytest.mark.asyncio
async def test_openai_provider_headers_and_prefix():
    def handler(request):
        assert request.headers["Authorization"] == "Bearer secret"
        return httpx.Response(200, json=body())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        result = await OpenAIClient("secret", http).complete(
            system="", messages=[], tools=[], config=ModelConfig(model="openai/gpt-5-nano")
        )
    assert result.usage.input_tokens == 12
