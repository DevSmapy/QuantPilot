"""Central data access layer for QuantPilot."""

from __future__ import annotations

from datetime import date

import polars as pl

from quantpilot.exceptions import SymbolNotFoundError
from quantpilot.providers.base_provider import BaseProvider


class DataSourceManager:
    """Route data requests to providers in Local First order."""

    def __init__(self, providers: list[BaseProvider]) -> None:
        if not providers:
            raise ValueError("At least one provider is required.")
        self._providers = providers

    def has_symbol(self, symbol: str) -> bool:
        """Return True if any provider can serve the symbol."""
        return any(provider.has_symbol(symbol) for provider in self._providers)

    def get_price(self, symbol: str, start: date, end: date) -> pl.DataFrame:
        """Return OHLCV data from the first provider that has the symbol."""
        for provider in self._providers:
            if provider.has_symbol(symbol):
                return provider.get_price(symbol, start, end)
        raise SymbolNotFoundError(symbol)

    def list_symbols(self) -> list[str]:
        """Return merged unique symbols from all providers."""
        symbols: set[str] = set()
        for provider in self._providers:
            symbols.update(provider.list_symbols())
        return sorted(symbols)

    def get_last_date(self) -> date | None:
        """Return the latest date from the first provider that reports one."""
        for provider in self._providers:
            last_date = provider.get_last_date()
            if last_date is not None:
                return last_date
        return None
