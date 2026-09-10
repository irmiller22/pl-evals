# Token usage estimates

This document estimates the API tokens needed to run the committed evaluation suites. It is a budgeting guide for the first live runs, not a billing guarantee. Actual usage must come from the `input_tokens` and `output_tokens` reported by each provider and recorded in the run artifact.

## Workloads

The repository currently contains:

| Workload | Cases | Composition |
| --- | ---: | --- |
| Smoke | 10 | 8 factual questions and 2 unsupported questions |
| Golden (configured) | 80 | 60 golden, 10 unsupported, and 10 adversarial questions |
| Full committed files | 90 | Golden plus the separate smoke file; use the configured suite to avoid duplicate cases |

The normal analyst flow uses one model response for an unsupported answer and usually two responses for a factual answer: one tool-selection response and one final-answer response. Comparisons run the same cases once for the baseline and once for the candidate, so analyst usage is approximately doubled.

## Planning estimates

These ranges include the system prompt, tool definitions, conversation history, tool results, and final JSON response. They assume successful cases, one tool call for ordinary factual questions, no retries, and the default `max_tokens: 4096` output cap. The cap is a limit, not an expected amount consumed.

| Run | Analyst input tokens | Analyst output tokens | Total analyst tokens |
| --- | ---: | ---: | ---: |
| One model, one smoke run | 35,000–60,000 | 2,000–5,000 | 37,000–65,000 |
| One model, one configured golden run | 280,000–480,000 | 16,000–40,000 | 296,000–520,000 |
| Baseline + candidate smoke comparison | 70,000–120,000 | 4,000–10,000 | 74,000–130,000 |
| Baseline + candidate configured golden comparison | 560,000–960,000 | 32,000–80,000 | 592,000–1,040,000 |

The ranges are intentionally broad. A comparison or head-to-head case can require more than one tool round, while an unsupported case usually needs only one model response. Retries, malformed answers, or extra corrective tool calls increase usage.

## Judge usage

Groundedness cases use the independently configured judge model when a judge is injected into the runner. The configured golden suite has 20 groundedness cases (10 unsupported and 10 adversarial); smoke has 2. A judge call does not use football tools, but its input contains the question, candidate answer, structured answer, evidence, and tool trace.

For planning, budget **1,200–3,000 input tokens and 50–150 output tokens per judge case**:

| Judge workload | Judge input tokens | Judge output tokens |
| --- | ---: | ---: |
| Smoke | 2,400–6,000 | 100–300 |
| Configured golden | 24,000–60,000 | 1,000–3,000 |
| Baseline + candidate configured golden | 48,000–120,000 | 2,000–6,000 |

The `evals run` CLI injects the judge automatically when `JUDGE_MODEL` is configured. If no judge model is configured, groundedness is recorded as unavailable/error and these judge tokens are not incurred.

## Model-by-model budgeting

For the example models in `.env.example`—Claude Sonnet, Haiku, and Opus; and OpenAI GPT-5.4, GPT-5 mini, and GPT-5 nano—token counts should start from the same workload ranges above. Model choice mainly changes output verbosity, tool-call reliability, retries, and therefore where a run lands inside the range. It does not change the number of dataset cases.

Before a full comparison, run one smoke case per model:

```bash
make eval-run DATASET=smoke CASE_ID=mun-away-wins-001
```

Record the reported totals from the resulting `run.json`, then multiply the observed per-case totals by the planned suite size. Run the full smoke suite next, and only then spend for the configured golden comparison.

## Example price estimate

The following is one arbitrary baseline/candidate pairing for budgeting:

- **Baseline:** Claude Sonnet 4.6 — **$3.00 / million input tokens** and **$15.00 / million output tokens**.
- **Candidate:** Claude Opus 4.6 — **$5.00 / million input tokens** and **$25.00 / million output tokens**.

Rates are standard, non-batch rates retrieved on 2026-09-08 from [Anthropic's pricing documentation](https://platform.claude.com/docs/en/about-claude/pricing). Verify rates before a live run because provider pricing and model aliases change.

Applying those rates to the configured golden comparison estimate (560,000–960,000 input tokens and 32,000–80,000 output tokens across both analyst runs) and dividing the range across the two model runs gives:

| Model | Input estimate | Output estimate | Estimated cost |
| --- | ---: | ---: | ---: |
| Claude Sonnet 4.6 baseline | $0.84–$1.44 | $0.24–$0.60 | **$1.08–$2.04** |
| Claude Opus 4.6 candidate | $1.40–$2.40 | $0.40–$1.00 | **$1.80–$3.40** |
| **Paired analyst total** |  |  | **$2.88–$5.44** |

The paired total is **$2.88–$5.44**, with a midpoint planning estimate of approximately **$4.16**. Optional groundedness judging, retries, and uncached/repeated prompt tokens can add to this amount; use the judge estimates above when a judge is configured.

## What is and is not included

Included: analyst requests, repeated model turns, tool-result context, final responses, and optional judge calls. Excluded: local DuckDB work, report generation, HTTP transport overhead, and failed requests that return no provider usage data. Provider prompt caching, if enabled or reported, may affect billing even when the logical token count is similar.

Never commit API keys or `.env` files. Keep live run artifacts under `.evals/`, review them for provider metadata, and publish only intentionally sanitized results.
