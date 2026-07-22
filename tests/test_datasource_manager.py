"""Tests for DataSourceManager."""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from quantpilot.datasource.datasource_manager import DataSourceManager
from quantpilot.exceptions import SymbolNotFoundError
from quantpilot.providers.base_provider import BaseProvider


class _StubProvider(BaseProvider):
    def __init__(self, symbols: list[str], frame: pl.DataFrame) -> None:
        self._symbols = symbols
        self._frame = frame

    def has_symbol(self, symbol: str) -> bool:
        return symbol in self._symbols

    def get_price(self, symbol: str, start: date, end: date) -> pl.DataFrame:
        return self._frame.filter(
            (pl.col("symbol") == symbol)
            & (pl.col("date") >= start)
            & (pl.col("date") <= end)
        )

    def list_symbols(self) -> list[str]:
        return self._symbols

    def get_last_date(self) -> date | None:
        return None


def test_datasource_manager_routes_to_provider(sample_prices: pl.DataFrame) -> None:
    provider = _StubProvider(["TEST.KS"], sample_prices)
    manager = DataSourceManager([provider])
    result = manager.get_price("TEST.KS", date(2023, 1, 1), date(2023, 2, 1))
    assert not result.is_empty()


def test_datasource_manager_symbol_not_found(sample_prices: pl.DataFrame) -> None:
    provider = _StubProvider(["TEST.KS"], sample_prices)
    manager = DataSourceManager([provider])
    with pytest.raises(SymbolNotFoundError):
        manager.get_price("MISSING.KS", date(2023, 1, 1), date(2023, 2, 1))


def test_datasource_manager_requires_provider() -> None:
    with pytest.raises(ValueError):
        DataSourceManager([])
