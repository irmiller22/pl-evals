"""Evaluation CLI bootstrap; execution commands arrive with the runner."""

import typer

app = typer.Typer(no_args_is_help=True, help="Premier League model evaluation tools.")


@app.callback()
def main() -> None:
    """Run evaluation tooling commands."""


@app.command()
def version() -> None:
    """Print the installed framework version."""
    from importlib.metadata import version as package_version

    typer.echo(package_version("premier-league-evals-poc"))


if __name__ == "__main__":
    app()
