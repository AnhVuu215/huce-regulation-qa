.PHONY: setup lint test ingest eval ablation answer-eval

setup:
	uv sync

lint:
	uv run ruff check .

test:
	uv run pytest

ingest:
	uv run python -m ingestion.cli

eval:
	uv run --group ml python eval/run_eval.py --config $(or $(CONFIG),baseline)

ablation:
	uv run --group ml python eval/run_eval.py --ablation

answer-eval:
	uv run --group ml python eval/run_generation.py --no-fallback
