.PHONY: help sync lock test lint format build up up-external down demo demo-ai shell ollama-network

help:
	@echo "QuantPilot Docker + uv commands"
	@echo "  make sync           - install deps with uv"
	@echo "  make lock           - regenerate uv.lock"
	@echo "  make test           - run unit tests"
	@echo "  make lint           - ruff + black + mypy"
	@echo "  make build          - build Docker image"
	@echo "  make up             - start bundled Ollama + dev container"
	@echo "  make up-external    - start dev container only (use with make ollama-network)"
	@echo "  make ollama-network - connect existing ollama container to quantpilot network"
	@echo "  make demo           - run MVP demo (skip AI)"
	@echo "  make demo-ai        - run MVP demo with Ollama review"

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
	docker compose --profile dev --profile bundled-ollama up -d ollama quantpilot-dev

up-external:
	docker compose --profile dev up -d quantpilot-dev

ollama-network:
	@docker network inspect quantpilot_default >/dev/null 2>&1 || \
		(echo "Network quantpilot_default not found. Run 'make up' or 'make up-external' first." && exit 1)
	@docker inspect ollama >/dev/null 2>&1 || \
		(echo "Container 'ollama' not found. Start your existing Ollama container first." && exit 1)
	@if docker inspect -f '{{range $$k, _ := .NetworkSettings.Networks}}{{$$k}} {{end}}' ollama | grep -q 'quantpilot_default'; then \
		echo "Container 'ollama' is already connected to quantpilot_default."; \
	else \
		docker network connect quantpilot_default ollama; \
		echo "Connected 'ollama' to quantpilot_default."; \
	fi

down:
	docker compose --profile dev --profile bundled-ollama down

demo:
	docker compose run --rm quantpilot python scripts/run_mvp.py --symbol 005930.KS --start 2023-01-01 --end 2023-12-31 --skip-ai

demo-ai:
	docker compose run --rm quantpilot python scripts/run_mvp.py --symbol 005930.KS --start 2023-01-01 --end 2023-12-31

shell:
	docker compose exec quantpilot-dev bash
