"""Persist run and comparison artifacts."""

import json
from pathlib import Path
from typing import Any

from evals.models import EvalRun


def write_run(run: EvalRun, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "run.json"
    path.write_text(json.dumps(run.model_dump(mode="json"), indent=2, sort_keys=True) + "\n")
    return path


def read_run(path: Path) -> EvalRun:
    return EvalRun.model_validate_json(path.read_text(encoding="utf-8"))


def write_comparison(comparison: dict[str, Any], directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "comparison.json"
    path.write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n")
    return path
