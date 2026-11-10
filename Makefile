.PHONY: setup lint format test ingest eval ablation answer-eval

setup:
	uv sync

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

test:
	uv run pytest

ingest:
	uv run python -m huce_qa.ingestion.cli

eval:
	uv run --group ml python eval/run_eval.py --config $(or $(CONFIG),baseline)

ablation:
	uv run --group ml python eval/run_eval.py --ablation

answer-eval:
	uv run --group ml python eval/run_generation.py --no-fallback
