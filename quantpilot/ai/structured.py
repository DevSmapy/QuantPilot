"""Structured LLM extraction via instructor + OpenAI-compatible Ollama."""

from __future__ import annotations

from typing import Any

import instructor
from openai import OpenAI
from pydantic import BaseModel

from quantpilot.config import Settings, get_settings


def create_instructor_client(settings: Settings | None = None) -> Any:
    """Build an instructor client pointed at the configured Ollama OpenAI API."""
    cfg = settings or get_settings()
    base = cfg.ollama_base_url.rstrip("/")
    if not base.endswith("/v1"):
        base = f"{base}/v1"
    raw = OpenAI(base_url=base, api_key="ollama")
    return instructor.from_openai(raw, mode=instructor.Mode.JSON)


def extract_structured[T: BaseModel](
    response_model: type[T],
    *,
    messages: list[dict[str, str]],
    model: str | None = None,
    settings: Settings | None = None,
    max_retries: int = 2,
) -> T:
    """Extract a pydantic model from the chat model."""
    cfg = settings or get_settings()
    client = create_instructor_client(cfg)
    result = client.chat.completions.create(
        model=model or cfg.ollama_model,
        response_model=response_model,
        messages=messages,
        max_retries=max_retries,
    )
    return result  # type: ignore[no-any-return]
