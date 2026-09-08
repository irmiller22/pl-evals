"""Small generic helpers used by deterministic graders."""

import math
from typing import Any


def pointer(value: Any, path: str) -> Any:
    if path in ("", "/"):
        return value
    current = value
    for part in path.lstrip("/").split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current[part]
        else:
            raise KeyError(path)
    return current


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def actual_answer(output: Any) -> dict:
    return output.structured_output or {}
