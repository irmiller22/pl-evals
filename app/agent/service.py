"""Bounded model/tool orchestration, with complete evidence and partial failure traces."""

import asyncio
from time import perf_counter

from pydantic import ValidationError

from app.agent.model import ModelClient, ModelError
from app.agent.prompts import system_prompt
from app.agent.types import (
    AskRequest,
    AskResponse,
    FinalAnswer,
    Message,
    TokenUsage,
    ToolCall,
    ToolDefinition,
    ToolExecution,
    ToolReply,
)
from app.config import ModelConfig
from app.football.tools import FootballTools


class AgentError(Exception):
    def __init__(self, code: str, message: str, partial_output: dict, attempts: int = 0):
        super().__init__(message)
        self.code = code
        self.partial_output = partial_output
        self.attempts = attempts


class AnalystService:
    def __init__(
        self,
        client: ModelClient,
        tools: FootballTools,
        config: ModelConfig,
        prompt: str | None = None,
    ):
        self.client = client
        self.tools = tools
        self.config = config
        self.prompt = prompt if prompt is not None else system_prompt(tools.repository.teams)

    async def ask(self, request: AskRequest) -> AskResponse:
        started = perf_counter()
        calls: list[ToolCall] = []
        trace: list[ToolExecution] = []
        input_tokens = output_tokens = 0
        usage_known = True

        def partial() -> dict:
            return {
                "tool_calls": [call.model_dump() for call in calls],
                "tool_trace": [item.model_dump() for item in trace],
                "latency_ms": (perf_counter() - started) * 1000,
                "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}
                if usage_known
                else None,
            }

        try:
            async with asyncio.timeout(self.config.application_timeout_seconds):
                messages = [Message(role="user", text=request.question)]
                definitions = [
                    ToolDefinition.model_validate(tool) for tool in self.tools.definitions()
                ]
                for _ in range(self.config.max_model_turns):
                    response = await self.client.complete(
                        system=self.prompt,
                        messages=messages,
                        tools=definitions,
                        config=self.config,
                    )
                    if response.usage is None:
                        usage_known = False
                    else:
                        input_tokens += response.usage.input_tokens
                        output_tokens += response.usage.output_tokens
                    if response.tool_calls:
                        ids = [call.call_id for call in calls + response.tool_calls]
                        if len(ids) != len(set(ids)):
                            raise ModelError("duplicate_call_id", "Model reused a tool call ID")
                        if len(calls) + len(response.tool_calls) > self.config.max_tool_calls:
                            raise ModelError("tool_limit", "Maximum tool call count exceeded")
                        messages.append(
                            Message(
                                role="assistant", text=response.text, tool_calls=response.tool_calls
                            )
                        )
                        replies = []
                        for call in response.tool_calls:
                            calls.append(call)
                            execution = ToolExecution(
                                call_id=call.call_id,
                                name=call.name,
                                requested_arguments=call.arguments,
                                status="validation_error",
                            )
                            trace.append(execution)
                            try:
                                execution.validated_arguments = self.tools.validate(
                                    call.name, call.arguments
                                )
                            except ValueError:
                                execution.error = {
                                    "code": "invalid_arguments",
                                    "message": (
                                        "Unknown tool or invalid arguments; "
                                        "use the supplied schemas and teams"
                                    ),
                                }
                            else:
                                execution.status = "tool_error"
                                execution.error = {
                                    "code": "tool_incomplete",
                                    "message": "Tool execution did not complete",
                                }
                                try:
                                    result = await asyncio.to_thread(
                                        self.tools.execute,
                                        call.name,
                                        execution.validated_arguments,
                                    )
                                except Exception:
                                    execution.error = {
                                        "code": "tool_error",
                                        "message": "Football query failed",
                                    }
                                else:
                                    execution.result = result.model_dump(mode="json")
                                    execution.status = "success"
                                    execution.error = None
                            replies.append(
                                ToolReply(
                                    call_id=call.call_id,
                                    content=execution.result
                                    if execution.result is not None
                                    else {"error": execution.error},
                                    is_error=execution.status != "success",
                                )
                            )
                        messages.append(Message(role="user", tool_results=replies))
                        continue
                    final = FinalAnswer.model_validate_json(response.text)
                    if final.structured_answer.status == "answered" and not any(
                        item.status == "success" for item in trace
                    ):
                        raise ModelError(
                            "missing_evidence",
                            "A factual answer requires successful tool execution",
                        )
                    evidence = list(
                        dict.fromkeys(
                            match_id
                            for item in trace
                            if item.result is not None
                            for match_id in item.result["evidence"]
                        )
                    )
                    return AskResponse(
                        **final.model_dump(),
                        tool_calls=calls,
                        tool_trace=trace,
                        evidence=evidence,
                        model=self.config.model,
                        usage=TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens)
                        if usage_known
                        else None,
                        latency_ms=(perf_counter() - started) * 1000,
                    )
                raise ModelError("turn_limit", "Maximum model turn count exceeded")
        except TimeoutError:
            raise AgentError("timeout", "Application deadline exceeded", partial()) from None
        except ModelError as error:
            raise AgentError(error.code, str(error), partial(), error.attempts) from None
        except ValidationError:
            raise AgentError(
                "invalid_answer", "Model final answer failed schema validation", partial()
            ) from None
