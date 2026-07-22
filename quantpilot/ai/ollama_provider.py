"""Ollama LLM provider for strategy review and generation."""

from __future__ import annotations

from typing import Any

import httpx

from quantpilot.ai.base_llm import BaseLLMProvider
from quantpilot.exceptions import (
    OllamaConnectionError,
    OllamaModelNotFoundError,
    OllamaResponseError,
)


class OllamaProvider(BaseLLMProvider):
    """Generate text using a local Ollama model."""

    def __init__(
        self,
        base_url: str = "http://ollama:11434",
        model: str = "llama3.2",
        timeout: float = 300.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def generate(
        self,
        prompt: str,
        *,
        format_json: bool = False,
        options: dict[str, Any] | None = None,
    ) -> str:
        """Request a completion from Ollama."""
        payload: dict[str, object] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if format_json:
            payload["format"] = "json"
        if options:
            payload["options"] = options

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                )
                if response.status_code == 404:
                    raise OllamaModelNotFoundError(self.model, self.base_url)
                response.raise_for_status()
        except (OllamaModelNotFoundError, OllamaConnectionError, OllamaResponseError):
            raise
        except httpx.ConnectError as exc:
            raise OllamaConnectionError(self.base_url) from exc
        except httpx.HTTPError as exc:
            raise OllamaConnectionError(self.base_url) from exc

        data = response.json()
        text = str(data.get("response", "")).strip()
        if not text:
            raise OllamaResponseError(self.base_url, self.model)
        return text

    def review_strategy(
        self,
        strategy_name: str,
        metrics: dict[str, float | int | str],
        summary: str,
    ) -> str:
        """Request a concise strategy review from Ollama."""
        return self.generate(_build_prompt(strategy_name, metrics, summary))


def _build_prompt(
    strategy_name: str,
    metrics: dict[str, float | int | str],
    summary: str,
) -> str:
    metric_lines = "\n".join(f"- {key}: {value}" for key, value in metrics.items())
    return (
        "You are a quantitative trading researcher.\n"
        f"Review the following strategy backtest briefly in Korean (3-5 sentences).\n\n"
        f"Strategy: {strategy_name}\n"
        f"Summary: {summary}\n\n"
        f"Metrics:\n{metric_lines}\n\n"
        "Mention strengths, risks, and one improvement suggestion."
    )
