.PHONY: help sync lock test lint format build up down demo demo-ai shell

help:
	@echo "QuantPilot Docker + uv commands"
	@echo "  make sync     - install deps with uv"
	@echo "  make lock     - regenerate uv.lock"
	@echo "  make test     - run unit tests"
	@echo "  make lint     - ruff + black + mypy"
	@echo "  make build    - build Docker image"
	@echo "  make up       - start dev container"
	@echo "  make ollama-network - connect existing ollama container to quantpilot network"
	@echo "  make demo     - run MVP demo (skip AI)"
	@echo "  make demo-ai  - run MVP demo with Ollama review"

sync:
	uv sync

lock:
	uv lock

test:
	uv run pytest -m "not integration"

lint:
	uv run ruff check .
	uv run black --check .
	uv run mypy quantpilot

format:
	uv run black .
	uv run ruff check --fix .

build:
	docker compose build quantpilot

up:
	docker compose --profile dev up -d quantpilot-dev

ollama-network:
	docker network connect quantpilot_default ollama 2>/dev/null || true

down:
	docker compose --profile dev down

demo:
	docker compose run --rm quantpilot python scripts/run_mvp.py --symbol 005930.KS --start 2023-01-01 --end 2023-12-31 --skip-ai

demo-ai:
	docker compose run --rm quantpilot python scripts/run_mvp.py --symbol 005930.KS --start 2023-01-01 --end 2023-12-31

shell:
	docker compose exec quantpilot-dev bash
