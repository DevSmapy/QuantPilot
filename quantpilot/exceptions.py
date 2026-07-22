"""Custom exceptions for QuantPilot."""

from __future__ import annotations


class QuantPilotError(Exception):
    """Base exception for QuantPilot."""


class SymbolNotFoundError(QuantPilotError):
    """Raised when a symbol is not available in any provider."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        super().__init__(f"Symbol not found: {symbol}")


class DataNotAvailableError(QuantPilotError):
    """Raised when no price data exists for the requested range."""

    def __init__(self, symbol: str, start: str, end: str) -> None:
        self.symbol = symbol
        self.start = start
        self.end = end
        super().__init__(f"No price data for {symbol} between {start} and {end}")


class OllamaConnectionError(QuantPilotError):
    """Raised when Ollama is unreachable."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        super().__init__(
            f"Ollama not reachable at {base_url}. "
            "Ensure the Ollama container is running and on the same Docker network."
        )


class OllamaModelNotFoundError(QuantPilotError):
    """Raised when the requested model is not available in Ollama."""

    def __init__(self, model: str, base_url: str) -> None:
        self.model = model
        self.base_url = base_url
        super().__init__(
            f"Model '{model}' not found at {base_url}. "
            f"Run: docker exec ollama ollama pull {model}"
        )
