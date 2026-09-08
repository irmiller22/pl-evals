"""Per-service configuration; secrets are read only when constructing the API service."""

import os

from pydantic import BaseModel, ConfigDict, Field


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    model: str = Field(min_length=1, pattern=r"\S")
    temperature: float = Field(default=0, ge=0, le=1)
    max_tokens: int = Field(default=4096, gt=0)
    provider_timeout_seconds: float = Field(default=30, gt=0)
    application_timeout_seconds: float = Field(default=120, gt=0)
    max_retries: int = Field(default=2, ge=0, le=10)
    retry_backoff_seconds: float = Field(default=1, ge=0)
    max_model_turns: int = Field(default=8, gt=0)
    max_tool_calls: int = Field(default=8, gt=0)

    @classmethod
    def from_env(cls) -> "ModelConfig":
        model = os.environ.get("APP_MODEL") or os.environ.get("BASELINE_MODEL", "")
        if not model.strip():
            raise ValueError("Set APP_MODEL or BASELINE_MODEL to an Anthropic model ID")
        return cls(model=model)
