# Premier League AI Evals POC

A public experiment in evaluating and comparing AI models using a Premier League match dataset. The project will establish a baseline with an accessible starting model, then run the same evaluations against other models to measure differences in quality, speed, token usage, and estimated cost.

The baseline is configurable: a Sonnet model is one possible starting point, rather than a fixed requirement or a claim about model rankings. Candidate models may perform better or worse on different measures. The goal is to make those tradeoffs visible through reproducible cases and per-case evidence.

An assistant that answers questions about a completed Premier League season provides the test application. The evaluation framework will measure answer correctness, tool use, groundedness, and abstention alongside performance and cost.

## Project status

Phases 0–4 and the deterministic portion of Phase 5–7 of the [build plan](doc/PLAN.md) are implemented locally: the Python project, reproducible 2024/25 dataset, deterministic football tools, typed analyst responses, Anthropic and OpenAI model adapters, `POST /ask`, evaluation contracts, an in-process adapter, deterministic graders, JSONL loading, and resilient case execution.

CI evaluations are still pending. Aggregate metrics, paired baseline/candidate execution, case classification, policy threshold evaluation, configurable token pricing, an independently configurable LLM judge, reproducible smoke/golden/unsupported/adversarial datasets, and JSON/Markdown reporting are implemented and tested. The CLI supports `run` and `compare`; live provider behavior and model comparison results have not been verified.

## Get started

Requires Python 3.12+, `uv`, and `make`. From the repository root:

```bash
make setup
make ingest
make check
make generate-datasets
make cli
make serve
```

The server listens at `http://127.0.0.1:8000`; `GET /health` returns `{"status":"ok"}`. No API key is needed for tests, ingestion, CLI help, or the health endpoint. `make serve` loads `.env` when present; direct Python execution reads exported environment variables.

The included [dataset documentation](app/data/README.md) identifies the pinned OpenFootball source, CC0 license, checksums, normalization rules, and query semantics. Ingestion runs offline by default; `--download` retrieves the same pinned source again.

To call a deterministic tool directly:

```python
from app.football.repository import FootballRepository
from app.football.tools import FootballTools

tools = FootballTools(FootballRepository())
result = tools.execute("count_team_matches", {
    "team": "Manchester United", "venue": "away", "result": "win",
})
print(result.model_dump())  # Value, contributing match IDs, and normalized arguments.
```

Repeated development commands are available through the Makefile:

| Command | Purpose |
| --- | --- |
| `make` / `make help` | List available targets. |
| `make setup` | Install the locked development dependencies. |
| `make ingest` | Regenerate match data from the included source. |
| `make generate-datasets` | Regenerate all eval JSONL from deterministic repository calculations. |
| `make test` | Run offline unit and integration tests. |
| `make typecheck` | Run mypy on application, evaluation, and script code. |
| `make lint` | Check Ruff lint rules without changing files. |
| `make format` | Apply Ruff formatting. |
| `make format-check` | Check formatting without changing files. |
| `make compile` | Verify application and evaluation modules compile. |
| `make check` | Run lint, formatting checks, type checks, tests, and compilation. |
| `make serve` | Start the local API. |
| `make cli` | Display evaluation CLI help. |

All environment-dependent targets use `uv` with `--locked`. `make check` does not reformat files or make paid model calls. Override the executable with `make UV=/path/to/uv check` when needed.

## Run the analyst

Copy `.env.example` to `.env` and set `APP_MODEL` plus the matching provider key. Anthropic IDs use `ANTHROPIC_API_KEY` and may optionally start with `anthropic/`; OpenAI IDs use `OPENAI_API_KEY` and may optionally start with `openai/`. Model IDs change and retire, so verify availability in your account. `APP_MODEL` falls back to `BASELINE_MODEL` when empty. The Anthropic adapter supports Claude API IDs (Bedrock-style IDs are not supported); the OpenAI adapter uses the Responses API.

```bash
cp .env.example .env
# Edit .env with your model ID and API key.
make serve
```

In another terminal:

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"How many away matches did Manchester United win?"}'
```

Requests to `/ask` make paid model calls. `/docs` exposes the request and response schemas. Missing model configuration returns HTTP 503; invalid questions return 422; provider/answer failures return 502; the application deadline returns 504. Execution failures include a sanitized code and partial trace rather than a fabricated unsupported answer.

The analyst validates final JSON against discriminated answer models and requires a successful tool execution for factual answers. It preserves requested and validated arguments, complete tool outputs, and contributing match IDs. Unsupported questions can return an explicit reason without calling a tool. Semantic correctness and agreement between prose and structured values will be checked by the evaluation graders in later phases.

`ModelConfig` provides a 30-second provider timeout, 120-second application deadline, at most two transient retries, eight model turns, and eight tool calls. In-process callers can override these limits and the system prompt independently for each service. Latency spans model requests, retries, and tool work inside the service; HTTP setup is excluded. Usage aggregates reported tokens across completed model responses, including cache tokens; if a response omits usage, the aggregate is unavailable. Usage from requests that fail before returning a response cannot be measured. Read-only tool work already running in a thread may finish after a request deadline.

The provider wire format follows the [Anthropic Messages API](https://platform.claude.com/docs/en/api/messages/create) or the [OpenAI Responses API](https://developers.openai.com/api/docs/guides/migrate-to-responses). OpenAI model IDs can be prefixed with `openai/` (for example, `openai/gpt-5.4`) and use `OPENAI_API_KEY`; see the [OpenAI models overview](https://developers.openai.com/api/docs/models) for current IDs and availability.

## Example application

The assistant will answer questions such as:

- “How many away matches did Manchester United win?”
- “What was Manchester United’s home record?”
- “What were the results between two teams?”

Factual answers must come from constrained, deterministic football tools backed by the loaded season. The assistant must abstain when the data cannot answer a question, such as a request for player goal totals when only match-level statistics are available.

Each response will include answer text, a typed structured answer, attempted tool calls, full tool execution traces, evidence IDs, and available usage and latency measurements. Traces will retain validated arguments and complete tool results so graders can assess whether the answer is supported.

## Public repository expectations

The repository will include evaluation definitions, reproducible data preparation, and documentation so others can run comparisons with their own model credentials. Only data permitted for redistribution will be committed, with source attribution, season, and applicable terms documented. Credentials and local environment files must stay out of version control; any published run artifacts must be reviewed for secrets and provider/account metadata.

Published results should identify the exact baseline and candidate model IDs, configuration, dataset version, and run date. Findings describe performance on this suite and configuration; they are not a general ranking of model capability. This is an independent experiment, not an official Premier League project.

## Evaluation commands

`evals run` executes one configured model against a selected JSONL dataset and writes a `run.json` artifact. It requires the model and provider credentials referenced by `evals/eval.yaml`:

```bash
cp .env.example .env
# Set BASELINE_MODEL and the matching provider API key in .env.
evals run --dataset smoke
```

`evals compare` compares two stored run artifacts by case ID and writes `comparison.json` and `report.md`:

```bash
evals compare \
  .evals/runs/<baseline-run-id>/run.json \
  .evals/runs/<candidate-run-id>/run.json
```

The paired runner API is available for programmatic baseline/candidate execution; CLI wiring for one command that launches both configurations, policy enforcement, and judge configuration is still pending. Runs involving cases with `groundedness` require injecting the configured LLM judge; otherwise that grade is recorded as unavailable/error rather than silently passing.

## Planned architecture

| Area | Responsibility |
| --- | --- |
| `app/` | FastAPI endpoints, provider adapter, and football assistant orchestration. |
| `app/football/` | Dataset queries, team normalization, and deterministic tools. |
| `app/data/` | A committed, normalized snapshot of the selected season. |
| `evals/` | Generic runner, graders, metrics, policies, pricing, and reports. |
| `evals/adapters/` | Mapping from the application service to the generic evaluation output. |
| `evals/datasets/`, `evals/rubrics/`, `evals/eval.yaml` | Evaluation cases, judge rubrics, and configuration. |
| `scripts/` | Reproducible data ingestion and evaluation case generation. |
| `tests/` | Unit and integration coverage with fakes for external model calls. |

Application logic, evaluation infrastructure, and evaluation content have separate responsibilities. The generic framework must contain no Premier League business rules. Local evaluations will call the application service in-process, without requiring an HTTP server.

The proposed stack is Python 3.12+, FastAPI, Pydantic v2, Typer, httpx, DuckDB, PyYAML, pytest, and pytest-asyncio.

## Evaluation flow

1. Load JSONL cases with inputs, expected results, graders, and tags.
2. Run the same selected cases against baseline and candidate configurations.
3. Capture answers, tool traces, evidence, latency, and available token/cost data.
4. Apply deterministic numeric, exact-value, schema, tool-call, and abstention graders, plus an independently configured LLM judge for groundedness.
5. Aggregate metrics, compare cases, and apply quality and performance policies.
6. Write console output, a JSON artifact, and a Markdown comparison report.

Planned suites include a ten-case smoke suite, a 50–75-case golden dataset, and separate unsupported and adversarial datasets. Expected statistics will be generated or validated using deterministic data calculations.

Schema and abstention grading will apply to every case. Supported questions must fail abstention grading if the assistant unnecessarily refuses. Groundedness grading will inspect full tool results and check that answer text agrees with the structured answer.

A case passes only when execution and every assigned grader succeed. Execution failures and grader errors remain in metric denominators and produce a nonzero CLI exit status. Configured policy metrics that are unavailable fail explicitly. Critical cases must pass even if the baseline also fails.

Comparisons will classify cases as both passing, both failing, baseline-only passing, or candidate-only passing. Baseline-only passing cases identify regressions. Reports will preserve per-case outputs and grader reasons alongside aggregate metrics.

## Planned interface

These commands are available unless noted:

```bash
python -m evals.cli run --dataset smoke
python -m evals.cli compare <baseline-run.json> <candidate-run.json>
python -m evals.cli report <run-id>
```

The API exposes `POST /ask` and `GET /health`. Evaluation artifacts will be written under `.evals/runs/<run-id>/` as `run.json` and `report.md`.

Model names and credentials will come from configuration or environment variables. Normal tests will use mocks or fakes and will not require paid API calls. The planned GitHub Actions workflow will run tests and smoke evaluations, upload artifacts, and fail when policy checks fail; full golden comparisons will be manually triggerable. The live-model behavior of PR evaluations still needs to be decided.

## Scope

The POC focuses on one completed season, constrained football tools, local evaluation, and baseline/candidate comparison. Dashboards, database servers, distributed workers, authentication, and multi-tenancy are outside scope.

See [doc/PLAN.md](doc/PLAN.md) for the ordered build phases and completion checklist.
