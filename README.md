# Premier League AI Evals POC

A single-repository proof of concept for a reusable AI evaluation framework, demonstrated through an assistant that answers questions about a completed Premier League season using structured match data.

The framework will compare baseline and candidate AI configurations to detect regressions in answer correctness, tool use, groundedness, abstention, latency, token usage, and estimated cost.

## Project status

The project is in the planning stage. The application, evaluation framework, datasets, and CI workflow have not been implemented yet. The [build plan](doc/PLAN.md) defines the implementation phases, contracts, and acceptance criteria.

The season, public data source, model provider, and default models remain to be selected. Setup instructions and executable commands will be added as implementation lands.

## Example application

The assistant will answer questions such as:

- “How many away matches did Manchester United win?”
- “What was Manchester United’s home record?”
- “What were the results between two teams?”

Factual answers must come from constrained, deterministic football tools backed by the loaded season. The assistant must abstain when the data cannot answer a question, such as a request for player goal totals when only match-level statistics are available.

Each response will include answer text, a typed structured answer, attempted tool calls, full tool execution traces, evidence IDs, and available usage and latency measurements. Traces will retain validated arguments and complete tool results so graders can assess whether the answer is supported.

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

These commands describe the intended interface; they are not available yet:

```bash
python -m app.main
python -m evals.cli run --dataset smoke
python -m evals.cli compare
python -m evals.cli report <run-id>
pytest
```

The API will expose `POST /ask` and `GET /health`. Evaluation artifacts will be written under `.evals/runs/<run-id>/` as `run.json` and `report.md`.

Model names and credentials will come from configuration or environment variables. Normal tests will use mocks or fakes and will not require paid API calls. The planned GitHub Actions workflow will run tests and smoke evaluations, upload artifacts, and fail when policy checks fail; full golden comparisons will be manually triggerable. The live-model behavior of PR evaluations still needs to be decided.

## Scope

The POC focuses on one completed season, constrained football tools, local evaluation, and baseline/candidate comparison. Dashboards, database servers, distributed workers, authentication, and multi-tenancy are outside scope.

See [doc/PLAN.md](doc/PLAN.md) for the ordered build phases and completion checklist.
