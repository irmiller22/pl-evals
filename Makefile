.DEFAULT_GOAL := help

UV ?= uv
PYTHON_DIRS := app evals scripts tests

.PHONY: help setup ingest generate-datasets test typecheck lint format format-check compile check serve cli

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Install the locked development environment
	$(UV) sync --locked

ingest: ## Rebuild the normalized CSV from the pinned local source
	$(UV) run --locked python -m scripts.ingest_dataset

generate-datasets: ## Generate eval JSONL from deterministic repository calculations
	$(UV) run --locked python -m scripts.generate_eval_cases

test: ## Run offline unit and integration tests
	$(UV) run --locked pytest

typecheck: ## Check application, framework, and script types
	$(UV) run --locked mypy

lint: ## Check Python lint rules without changing files
	$(UV) run --locked ruff check $(PYTHON_DIRS)

format: ## Format Python files
	$(UV) run --locked ruff format $(PYTHON_DIRS)

format-check: ## Check formatting without changing files
	$(UV) run --locked ruff format --check $(PYTHON_DIRS)

compile: ## Verify application and evaluation modules compile
	$(UV) run --locked python -m compileall -q app evals

check: lint format-check typecheck test compile ## Run all local validation checks

serve: ## Start the local API on 127.0.0.1:8000
	$(UV) run --locked $(if $(wildcard .env),--env-file .env) python -m app.main

cli: ## Show evaluation CLI help
	$(UV) run --locked python -m evals.cli --help
