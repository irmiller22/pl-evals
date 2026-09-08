"""Provider-neutral client protocol and the initial Anthropic Messages implementation."""

import asyncio
import json
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Protocol

import httpx

from app.agent.types import Message, ModelResponse, TokenUsage, ToolCall, ToolDefinition
from app.config import ModelConfig


class ModelError(Exception):
    """Safe to report without exposing provider response bodies or credentials."""

    def __init__(self, code: str, message: str, attempts: int = 1):
        super().__init__(message)
        self.code = code
        self.attempts = attempts


class ModelClient(Protocol):
    async def complete(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[ToolDefinition],
        config: ModelConfig,
    ) -> ModelResponse: ...


def retry_delay(header: str | None, fallback: float) -> float:
    if header is None:
        return fallback
    try:
        seconds = float(header)
        if seconds >= 0 and seconds < float("inf"):
            return seconds
    except ValueError:
        try:
            timestamp = parsedate_to_datetime(header)
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
            return max(0, (timestamp - datetime.now(UTC)).total_seconds())
        except (ValueError, TypeError, OverflowError):
            pass
    return fallback


class AnthropicClient:
    def __init__(self, api_key: str, http: httpx.AsyncClient):
        if not api_key.strip():
            raise ValueError("Set ANTHROPIC_API_KEY to enable the analyst")
        self._api_key = api_key
        self._http = http

    async def complete(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[ToolDefinition],
        config: ModelConfig,
    ) -> ModelResponse:
        model = config.model.removeprefix("anthropic/")
        if "/" in model:
            raise ModelError("unsupported_provider", "Only Anthropic models are configured")
        wire_messages = []
        for message in messages:
            blocks: list[dict] = []
            for result in message.tool_results:
                blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": result.call_id,
                        "content": json.dumps(result.content),
                        "is_error": result.is_error,
                    }
                )
            if message.text:
                blocks.append({"type": "text", "text": message.text})
            for call in message.tool_calls:
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": call.call_id,
                        "name": call.name,
                        "input": call.arguments,
                    }
                )
            wire_messages.append({"role": message.role, "content": blocks})
        payload = {
            "model": model,
            "system": system,
            "messages": wire_messages,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.parameters,
                }
                for tool in tools
            ],
        }
        for attempt in range(config.max_retries + 1):
            delay = config.retry_backoff_seconds * (2**attempt)
            try:
                response = await self._http.post(
                    "https://api.anthropic.com/v1/messages",
                    json=payload,
                    headers={"x-api-key": self._api_key, "anthropic-version": "2023-06-01"},
                    timeout=config.provider_timeout_seconds,
                )
            except httpx.TransportError:
                error = ModelError(
                    "provider_transport", "Model request could not complete", attempt + 1
                )
            else:
                if response.is_success:
                    return self._parse(response, attempt + 1)
                error = ModelError(
                    "provider_http",
                    f"Model provider returned HTTP {response.status_code}",
                    attempt + 1,
                )
                if response.status_code != 429 and response.status_code < 500:
                    raise error
                delay = retry_delay(response.headers.get("retry-after"), delay)
            if attempt == config.max_retries:
                raise error
            await asyncio.sleep(delay)
        raise AssertionError("Unreachable retry state")

    @staticmethod
    def _parse(response: httpx.Response, attempts: int) -> ModelResponse:
        try:
            body = response.json()
            calls = []
            texts = []
            for block in body["content"]:
                if block["type"] == "text":
                    texts.append(block["text"])
                elif block["type"] == "tool_use":
                    calls.append(
                        ToolCall(name=block["name"], arguments=block["input"], call_id=block["id"])
                    )
                else:
                    raise ValueError("Unsupported provider content block")
            usage = None
            if body.get("usage") is not None:
                raw = body["usage"]
                usage = TokenUsage(
                    input_tokens=raw["input_tokens"]
                    + raw.get("cache_creation_input_tokens", 0)
                    + raw.get("cache_read_input_tokens", 0),
                    output_tokens=raw["output_tokens"],
                )
            result = ModelResponse(
                text="".join(texts), tool_calls=calls, usage=usage, stop_reason=body["stop_reason"]
            )
            if bool(calls) != (result.stop_reason == "tool_use"):
                raise ValueError("Stop reason disagrees with tool calls")
            return result
        except (ValueError, KeyError, TypeError):
            raise ModelError(
                "invalid_model_response",
                "Model returned an invalid or incomplete response",
                attempts,
            ) from None


class OpenAIClient:
    """OpenAI Responses API client implementing the provider-neutral contract."""

    def __init__(self, api_key: str, http: httpx.AsyncClient):
        if not api_key.strip():
            raise ValueError("Set OPENAI_API_KEY to enable OpenAI models")
        self._api_key = api_key
        self._http = http

    async def complete(
        self,
        *,
        system: str,
        messages: list[Message],
        tools: list[ToolDefinition],
        config: ModelConfig,
    ) -> ModelResponse:
        model = config.model.removeprefix("openai/")
        items: list[dict] = []
        for message in messages:
            if message.role == "user" and message.tool_results:
                items.extend(
                    {
                        "type": "function_call_output",
                        "call_id": item.call_id,
                        "output": json.dumps(item.content),
                    }
                    for item in message.tool_results
                )
            elif message.role == "assistant" and message.tool_calls:
                items.extend(
                    {
                        "type": "function_call",
                        "call_id": call.call_id,
                        "name": call.name,
                        "arguments": json.dumps(call.arguments),
                    }
                    for call in message.tool_calls
                )
                if message.text:
                    items.append({"role": "assistant", "content": message.text})
            elif message.text:
                items.append({"role": message.role, "content": message.text})
        payload = {
            "model": model,
            "instructions": system,
            "input": items,
            "temperature": config.temperature,
            "max_output_tokens": config.max_tokens,
            "parallel_tool_calls": False,
            "text": {"format": {"type": "json_object"}},
            "tools": [
                {
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                    "strict": True,
                }
                for tool in tools
            ],
        }
        for attempt in range(config.max_retries + 1):
            delay = config.retry_backoff_seconds * (2**attempt)
            try:
                response = await self._http.post(
                    "https://api.openai.com/v1/responses",
                    json=payload,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=config.provider_timeout_seconds,
                )
            except httpx.TransportError:
                error = ModelError(
                    "provider_transport", "Model request could not complete", attempt + 1
                )
            else:
                if response.is_success:
                    return self._parse(response, attempt + 1)
                error = ModelError(
                    "provider_http",
                    f"Model provider returned HTTP {response.status_code}",
                    attempt + 1,
                )
                if response.status_code != 429 and response.status_code < 500:
                    raise error
                delay = retry_delay(response.headers.get("retry-after"), delay)
            if attempt == config.max_retries:
                raise error
            await asyncio.sleep(delay)
        raise AssertionError("Unreachable retry state")

    @staticmethod
    def _parse(response: httpx.Response, attempts: int) -> ModelResponse:
        try:
            body = response.json()
            calls: list[ToolCall] = []
            texts: list[str] = []
            for item in body["output"]:
                if item["type"] == "function_call":
                    calls.append(
                        ToolCall(
                            name=item["name"],
                            arguments=json.loads(item["arguments"]),
                            call_id=item["call_id"],
                        )
                    )
                elif item["type"] == "message":
                    texts.extend(
                        part["text"]
                        for part in item.get("content", [])
                        if part.get("type") == "output_text"
                    )
                else:
                    raise ValueError("Unsupported provider output item")
            usage = None
            if body.get("usage") is not None:
                usage = TokenUsage(
                    input_tokens=body["usage"]["input_tokens"],
                    output_tokens=body["usage"]["output_tokens"],
                )
            return ModelResponse(
                text="".join(texts),
                tool_calls=calls,
                usage=usage,
                stop_reason="tool_use" if calls else "end_turn",
            )
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            raise ModelError(
                "invalid_model_response",
                "Model returned an invalid or incomplete response",
                attempts,
            ) from None
