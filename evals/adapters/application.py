"""In-process adapter between the analyst contract and generic eval output."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from app.agent.model import AnthropicClient, ModelClient
from app.agent.service import AgentError, AnalystService
from app.agent.types import AskRequest
from app.config import ModelConfig
from app.football.repository import FootballRepository
from app.football.tools import FootballTools
from evals.models import EvalCase, EvalOutput


class ApplicationAdapter:
    def __init__(self, client: ModelClient, *, repository: FootballRepository | None = None):
        self.client = client
        self.repository = repository or FootballRepository()

    async def run(self, case: EvalCase, model_config: ModelConfig) -> EvalOutput:
        if "question" not in case.input or not isinstance(case.input["question"], str):
            raise ValueError(f"Case {case.id} input must contain a string question")
        service = AnalystService(self.client, FootballTools(self.repository), model_config)
        try:
            result = await service.ask(AskRequest(question=case.input["question"]))
        except AgentError:
            raise
        usage = result.usage
        return EvalOutput(
            response=result.answer,
            structured_output=result.structured_answer.model_dump(mode="json"),
            tool_calls=[call.model_dump(mode="json") for call in result.tool_calls],
            tool_trace=[item.model_dump(mode="json") for item in result.tool_trace],
            evidence=result.evidence,
            latency_ms=result.latency_ms,
            input_tokens=usage.input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
            metadata={"model": result.model},
        )


@asynccontextmanager
async def anthropic_adapter() -> AsyncIterator[ApplicationAdapter]:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key.strip():
        raise ValueError("Set ANTHROPIC_API_KEY before running a live evaluation")
    async with httpx.AsyncClient() as http:
        yield ApplicationAdapter(AnthropicClient(key, http))
