"""Typer entry points for local evaluation runs and stored comparisons."""

import asyncio
from pathlib import Path

import typer

from evals.config import EvalConfig
from evals.metrics import aggregate, compare
from evals.reporting.console import print_summary
from evals.reporting.json_report import read_run, write_comparison, write_run
from evals.reporting.markdown import write_comparison_report
from evals.runner import run_dataset

app = typer.Typer(no_args_is_help=True, help="Premier League model evaluation tools.")


@app.callback()
def main() -> None:
    """Run evaluation tooling commands."""


@app.command()
def version() -> None:
    """Print the installed framework version."""
    from importlib.metadata import version as package_version

    typer.echo(package_version("premier-league-evals-poc"))


@app.command()
def run(
    dataset: str = typer.Option("smoke"),
    config: Path = typer.Option(Path("evals/eval.yaml"), exists=True),  # noqa: B008
    tag: str | None = typer.Option(None),
    case_id: str | None = typer.Option(None),
) -> None:
    """Run one configured model against a JSONL dataset."""
    settings = EvalConfig.load(config)
    model = settings.model("baseline")
    from evals.adapters.application import adapter_for_model

    async def execute() -> None:
        async with adapter_for_model(model) as adapter:
            result = await run_dataset(
                settings.datasets(dataset),
                adapter,
                model,
                tag=tag,
                case_id=case_id,
                concurrency=settings.data.get("execution", {}).get("concurrency", 1),
            )
        directory = (
            Path(settings.data.get("output", {}).get("directory", ".evals/runs")) / result.run_id
        )
        write_run(result, directory)
        print_summary(aggregate(result))
        typer.echo(f"Run artifact: {directory / 'run.json'}")

    try:
        asyncio.run(execute())
    except (ValueError, OSError) as error:
        raise typer.BadParameter(str(error)) from error


@app.command("compare")
def compare_runs(
    baseline: Path = typer.Argument(..., exists=True),  # noqa: B008
    candidate: Path = typer.Argument(..., exists=True),  # noqa: B008
    output: Path = typer.Option(Path(".evals/comparisons")),  # noqa: B008
) -> None:
    """Compare two stored run.json artifacts."""
    baseline_run, candidate_run = read_run(baseline), read_run(candidate)
    comparison = compare(baseline_run, candidate_run)
    write_comparison(comparison, output)
    write_comparison_report(comparison, baseline_run, candidate_run, output)
    typer.echo(f"Comparison artifacts: {output}")


if __name__ == "__main__":
    app()
