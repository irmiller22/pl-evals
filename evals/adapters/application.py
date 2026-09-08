"""In-process adapter between the analyst contract and generic eval output."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from app.agent.model import AnthropicClient, ModelClient, OpenAIClient
from app.agent.service import AgentError, AnalystService
from app.agent.types import AskRequest
from app.config import ModelConfig
from app.football.repository import FootballRepository
from app.football.tools import FootballTools
from evals.models import EvalCase, EvalOutput
from evals.pricing import Price, estimate_cost, price_for


class ApplicationAdapter:
    def __init__(
        self,
        client: ModelClient,
        *,
        repository: FootballRepository | None = None,
        prices: dict[str, Price] | None = None,
    ):
        self.client = client
        self.repository = repository or FootballRepository()
        self.prices = prices or {}

    async def run(self, case: EvalCase, model_config: ModelConfig) -> EvalOutput:
        if "question" not in case.input or not isinstance(case.input["question"], str):
            raise ValueError(f"Case {case.id} input must contain a string question")
        service = AnalystService(self.client, FootballTools(self.repository), model_config)
        try:
            result = await service.ask(AskRequest(question=case.input["question"]))
        except AgentError:
            raise
        usage = result.usage
        price = price_for(result.model, self.prices)
        return EvalOutput(
            response=result.answer,
            structured_output=result.structured_answer.model_dump(mode="json"),
            tool_calls=[call.model_dump(mode="json") for call in result.tool_calls],
            tool_trace=[item.model_dump(mode="json") for item in result.tool_trace],
            evidence=result.evidence,
            latency_ms=result.latency_ms,
            input_tokens=usage.input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
            estimated_cost_usd=estimate_cost(
                usage.input_tokens if usage else None, usage.output_tokens if usage else None, price
            )
            if price
            else None,
            metadata={"model": result.model, "pricing_available": price is not None},
        )


@asynccontextmanager
async def anthropic_adapter() -> AsyncIterator[ApplicationAdapter]:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key.strip():
        raise ValueError("Set ANTHROPIC_API_KEY before running a live evaluation")
    async with httpx.AsyncClient() as http:
        yield ApplicationAdapter(AnthropicClient(key, http))


@asynccontextmanager
async def openai_adapter() -> AsyncIterator[ApplicationAdapter]:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key.strip():
        raise ValueError("Set OPENAI_API_KEY before running OpenAI evaluations")
    async with httpx.AsyncClient() as http:
        yield ApplicationAdapter(OpenAIClient(key, http))


@asynccontextmanager
async def adapter_for_model(model: ModelConfig) -> AsyncIterator[ApplicationAdapter]:
    """Create the live adapter selected by a model ID."""
    model_name = model.model.removeprefix("anthropic/")
    if model.model.startswith("openai/") or model_name.startswith(("gpt-", "o")):
        async with openai_adapter() as adapter:
            yield adapter
    else:
        async with anthropic_adapter() as adapter:
            yield adapter
