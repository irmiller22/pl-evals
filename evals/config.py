"""YAML configuration loading with explicit environment substitution."""

import os
import re
from pathlib import Path
from typing import Any

import yaml

from app.config import ModelConfig


class EvalConfig:
    def __init__(self, data: dict[str, Any], path: Path):
        self.data = data
        self.path = path

    @classmethod
    def load(cls, path: Path) -> "EvalConfig":
        data = expand_env(yaml.safe_load(path.read_text(encoding="utf-8")))
        if not isinstance(data, dict) or data.get("version") != 1:
            raise ValueError("eval.yaml must contain version: 1")
        return cls(data, path)

    def datasets(self, name: str) -> list[Path]:
        entries = self.data.get("datasets", {}).get(name)
        if not isinstance(entries, list) or not entries:
            raise ValueError(f"Unknown or empty dataset: {name}")
        root = self.path.parent.parent
        paths = [root / entry for entry in entries]
        missing = [str(path) for path in paths if not path.is_file()]
        if missing:
            raise ValueError(f"Dataset files do not exist: {missing}")
        return paths

    def model(self, name: str) -> ModelConfig:
        data = self.data.get(name)
        if not isinstance(data, dict):
            raise ValueError(f"Missing {name} model configuration")
        return ModelConfig.model_validate(data)


def expand_env(value: Any) -> Any:
    if isinstance(value, str):
        return re.sub(
            r"\$\{([A-Z0-9_]+)\}", lambda match: os.environ.get(match.group(1), ""), value
        )
    if isinstance(value, dict):
        return {key: expand_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [expand_env(item) for item in value]
    return value
