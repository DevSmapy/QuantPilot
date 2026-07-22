# syntax=docker/dockerfile:1

FROM python:3.12.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.6.17 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY . .
RUN uv sync --frozen

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --create-home appuser \
    && mkdir -p /app/storage \
    && chown -R appuser:appuser /app

USER appuser

CMD ["python", "scripts/run_mvp.py", "--help"]
