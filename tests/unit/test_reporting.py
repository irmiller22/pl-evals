from datetime import UTC, datetime

from typer.testing import CliRunner

from evals.cli import app
from evals.models import CaseResult, EvalCase, EvalOutput, EvalRun, Grade
from evals.reporting.json_report import write_run


def test_cli_compare_writes_artifacts(tmp_path):
    now = datetime.now(UTC)
    runs = []
    for model, passed in (("base", True), ("candidate", False)):
        case = EvalCase(id="case", input={"question": "q"}, expected={}, graders=[])
        result = CaseResult(
            case=case,
            status="completed",
            output=EvalOutput(
                response="answer",
                structured_output=None,
                tool_calls=[],
                tool_trace=[],
                evidence=[],
                latency_ms=10,
                input_tokens=2,
                output_tokens=1,
                estimated_cost_usd=0.001,
            ),
            grades=[Grade(grader="schema", score=float(passed), passed=passed, reason="test")],
        )
        runs.append(
            write_run(
                EvalRun(
                    run_id=model,
                    model=model,
                    dataset_hash="hash",
                    started_at=now,
                    completed_at=now,
                    cases=[result],
                ),
                tmp_path / model,
            )
        )
    result = CliRunner().invoke(
        app, ["compare", str(runs[0]), str(runs[1]), "--output", str(tmp_path / "out")]
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "out" / "comparison.json").is_file()
    assert (tmp_path / "out" / "report.md").is_file()
