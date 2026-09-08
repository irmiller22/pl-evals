"""Dataset loading and resilient per-case evaluation execution."""

import asyncio
import hashlib
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from app.agent.service import AgentError
from app.config import ModelConfig
from evals.graders.abstention import AbstentionGrader
from evals.graders.base import Grader
from evals.graders.exact import ExactGrader
from evals.graders.numeric import NumericGrader
from evals.graders.schema import SchemaGrader
from evals.graders.tool_call import ToolCallGrader
from evals.models import CaseResult, EvalCase, EvalOutput, EvalRun, Grade


class Adapter(Protocol):
    async def run(self, case: EvalCase, model_config: ModelConfig) -> EvalOutput: ...


GRADERS: dict[str, Grader] = {
    "numeric": NumericGrader(),
    "exact": ExactGrader(),
    "schema": SchemaGrader(),
    "tool_call": ToolCallGrader(),
    "abstention": AbstentionGrader(),
}


def load_cases(
    paths: Iterable[Path], *, tag: str | None = None, case_id: str | None = None
) -> tuple[list[EvalCase], str]:
    raw_lines: list[bytes] = []
    cases: list[EvalCase] = []
    seen: set[str] = set()
    for path in paths:
        for line_number, line in enumerate(path.read_bytes().splitlines(), 1):
            if not line.strip():
                continue
            raw_lines.append(line)
            try:
                case = EvalCase.model_validate_json(line)
            except ValueError as error:
                raise ValueError(f"Invalid eval case {path}:{line_number}: {error}") from error
            if case.id in seen:
                raise ValueError(f"Duplicate eval case ID: {case.id}")
            seen.add(case.id)
            if case_id is not None and case.id != case_id:
                continue
            if tag is not None and tag not in case.tags:
                continue
            cases.append(case)
    cases.sort(key=lambda item: item.id)
    if not cases:
        raise ValueError("No evaluation cases selected")
    return cases, hashlib.sha256(b"\n".join(raw_lines)).hexdigest()


def effective_graders(case: EvalCase) -> list[str]:
    names = list(dict.fromkeys([*case.graders, "schema", "abstention"]))
    unknown = set(names) - set(GRADERS)
    if unknown:
        raise ValueError(f"Unknown grader(s) for {case.id}: {sorted(unknown)}")
    return names


def failure_grades(names: Iterable[str], *, status: str, reason: str) -> list[Grade]:
    return [
        Grade(grader=name, status=status, score=0, passed=False, reason=reason) for name in names
    ]


async def grade_case(case: EvalCase, output: EvalOutput) -> list[Grade]:
    grades: list[Grade] = []
    for name in effective_graders(case):
        grader = GRADERS[name]
        try:
            grade = await grader.grade(case, output)
            grades.append(grade)
        except Exception as error:  # Grader isolation is part of the runner contract.
            grades.append(
                Grade(
                    grader=name,
                    status="error",
                    score=0,
                    passed=False,
                    reason=f"Grader failed: {type(error).__name__}",
                )
            )
    return grades


async def run_cases(
    cases: list[EvalCase], adapter: Adapter, model_config: ModelConfig, *, concurrency: int = 1
) -> list[CaseResult]:
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")
    semaphore = asyncio.Semaphore(concurrency)

    async def run_one(case: EvalCase) -> CaseResult:
        names = effective_graders(case)
        async with semaphore:
            try:
                output = await adapter.run(case, model_config)
            except AgentError as error:
                status = "timeout" if error.code == "timeout" else "execution_error"
                return CaseResult(
                    case=case,
                    status=status,
                    error={
                        "code": error.code,
                        "message": str(error),
                        "attempts": error.attempts,
                    },
                    partial_output=error.partial_output,
                    grades=failure_grades(names, status="skipped", reason=error.code),
                )
            except Exception as error:
                return CaseResult(
                    case=case,
                    status="execution_error",
                    error={
                        "code": "adapter_error",
                        "message": f"Adapter failed: {type(error).__name__}",
                    },
                    partial_output=None,
                    grades=failure_grades(names, status="skipped", reason="adapter_error"),
                )
            return CaseResult(
                case=case, status="completed", output=output, grades=await grade_case(case, output)
            )

    return await asyncio.gather(*(run_one(case) for case in cases))


async def run_dataset(
    paths: Iterable[Path],
    adapter: Adapter,
    model_config: ModelConfig,
    *,
    tag: str | None = None,
    case_id: str | None = None,
    concurrency: int = 1,
    run_id: str | None = None,
) -> EvalRun:
    cases, dataset_hash = load_cases(paths, tag=tag, case_id=case_id)
    started = datetime.now(UTC)
    results = await run_cases(cases, adapter, model_config, concurrency=concurrency)
    return EvalRun(
        run_id=run_id or uuid.uuid4().hex,
        model=model_config.model,
        dataset_hash=dataset_hash,
        started_at=started,
        completed_at=datetime.now(UTC),
        cases=results,
    )
