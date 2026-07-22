"""Abstract base class for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """Base interface for AI research providers."""

    @abstractmethod
    def review_strategy(
        self,
        strategy_name: str,
        metrics: dict[str, float | int | str],
        summary: str,
    ) -> str:
        """Return a natural-language review of strategy backtest results."""
