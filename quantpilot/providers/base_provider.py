"""Abstract base class for data providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

import polars as pl


class BaseProvider(ABC):
    """Base interface for all QuantPilot data providers."""

    @abstractmethod
    def has_symbol(self, symbol: str) -> bool:
        """Return True if this provider can serve the given symbol."""

    @abstractmethod
    def get_price(self, symbol: str, start: date, end: date) -> pl.DataFrame:
        """Return OHLCV price data for a symbol within a date range."""

    @abstractmethod
    def list_symbols(self) -> list[str]:
        """Return all symbols known to this provider."""

    @abstractmethod
    def get_last_date(self) -> date | None:
        """Return the latest available data date, if known."""

    def get_fundamental(self, symbol: str) -> pl.DataFrame:
        """Return fundamental data. Not implemented in MVP."""
        raise NotImplementedError(
            f"{type(self).__name__} does not support get_fundamental yet."
        )

    def get_news(self, symbol: str) -> pl.DataFrame:
        """Return news data. Not implemented in MVP."""
        raise NotImplementedError(
            f"{type(self).__name__} does not support get_news yet."
        )
