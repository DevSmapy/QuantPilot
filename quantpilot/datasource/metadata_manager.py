"""Q-SEED metadata management."""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from quantpilot.providers.qseed_schema import (
    COMPLETED_DATA_LIST_FILE,
    KRX_LIST_FILE,
    LAST_DATE_FILE,
)


class MetadataManager:
    """Reads symbol lists and freshness metadata from Q-SEED data_log."""

    def __init__(self, data_log_path: Path) -> None:
        self._data_log_path = data_log_path
        self._symbols: dict[str, str] | None = None
        self._completed: set[str] | None = None

    @property
    def krx_list_path(self) -> Path:
        return self._data_log_path / KRX_LIST_FILE

    @property
    def last_date_path(self) -> Path:
        return self._data_log_path / LAST_DATE_FILE

    @property
    def completed_list_path(self) -> Path:
        return self._data_log_path / COMPLETED_DATA_LIST_FILE

    def _load_symbols(self) -> dict[str, str]:
        if self._symbols is not None:
            return self._symbols

        symbols: dict[str, str] = {}
        if self.krx_list_path.exists():
            with self.krx_list_path.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ticker = row.get("Ticker", "").strip()
                    market = row.get("Market", "").strip()
                    if ticker:
                        symbols[ticker] = market

        self._symbols = symbols
        return symbols

    def _load_completed(self) -> set[str]:
        if self._completed is not None:
            return self._completed

        completed: set[str] = set()
        if self.completed_list_path.exists():
            completed = {
                line.strip()
                for line in self.completed_list_path.read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            }

        self._completed = completed
        return completed

    def has_symbol(self, symbol: str) -> bool:
        """Return True if the symbol exists in krx_list metadata."""
        return symbol in self._load_symbols()

    def get_market(self, symbol: str) -> str | None:
        """Return market name for a symbol, if known."""
        return self._load_symbols().get(symbol)

    def list_symbols(self) -> list[str]:
        """Return all symbols from krx_list.csv."""
        return sorted(self._load_symbols())

    def has_data(self, symbol: str) -> bool:
        """Return True if symbol appears in completed_data_list.txt."""
        return symbol in self._load_completed()

    def get_last_date(self) -> date | None:
        """Return latest data date from last_date.txt."""
        if not self.last_date_path.exists():
            return None

        raw = self.last_date_path.read_text(encoding="utf-8").strip()
        if not raw:
            return None

        return datetime.strptime(raw, "%Y-%m-%d").date()
