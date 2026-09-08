"""Thin HTTP interface with request-scoped provider connections."""

import os
from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException

from app.agent.model import AnthropicClient, OpenAIClient
from app.agent.service import AgentError, AnalystService
from app.agent.types import AskRequest, AskResponse
from app.config import ModelConfig
from app.football.repository import FootballRepository
from app.football.tools import FootballTools

app = FastAPI(title="Premier League AI Evals POC", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


async def get_service() -> AsyncIterator[AnalystService]:
    try:
        config = ModelConfig.from_env()
        model_name = config.model.removeprefix("anthropic/")
        provider = (
            "openai"
            if config.model.startswith("openai/") or model_name.startswith(("gpt-", "o"))
            else "anthropic"
        )
        key_name = "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY"
        key = os.environ.get(key_name, "")
        if not key.strip():
            raise ValueError(f"Set {key_name} to enable the analyst")
    except ValueError:
        raise HTTPException(
            503, "Configure APP_MODEL (or BASELINE_MODEL) and the selected provider API key"
        ) from None
    async with httpx.AsyncClient() as http:
        client = OpenAIClient(key, http) if provider == "openai" else AnthropicClient(key, http)
        yield AnalystService(client, FootballTools(FootballRepository()), config)


@app.post("/ask", response_model=AskResponse)
async def ask(
    request: AskRequest, service: Annotated[AnalystService, Depends(get_service)]
) -> AskResponse:
    try:
        return await service.ask(request)
    except AgentError as error:
        raise HTTPException(
            504 if error.code == "timeout" else 502,
            detail={
                "code": error.code,
                "message": str(error),
                "partial_output": error.partial_output,
                "attempts": error.attempts,
            },
        ) from None
