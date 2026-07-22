"""Historical price market with look-ahead-safe visibility."""

from __future__ import annotations

from datetime import date

import polars as pl

from quantpilot.providers.qseed_schema import (
    QP_CLOSE,
    QP_DATE,
    QP_HIGH,
    QP_LOW,
    QP_OPEN,
    QP_VOLUME,
)


class HistoricalMarket:
    """Hold full OHLCV and expose only bars with date <= as_of."""

    def __init__(self, prices: pl.DataFrame) -> None:
        required = {QP_DATE, QP_OPEN, QP_HIGH, QP_LOW, QP_CLOSE, QP_VOLUME}
        missing = required - set(prices.columns)
        if missing:
            raise ValueError(f"prices missing columns: {sorted(missing)}")
        if prices.is_empty():
            raise ValueError("prices must not be empty")

        self._prices = prices.sort(QP_DATE).unique(subset=[QP_DATE], keep="last")

    def session_dates(self, start: date, end: date) -> list[date]:
        """Trading dates in [start, end] inclusive."""
        if start > end:
            raise ValueError("start must be <= end")
        frame = self._prices.filter(
            (pl.col(QP_DATE) >= start) & (pl.col(QP_DATE) <= end)
        )
        return frame[QP_DATE].to_list()

    def prior_session_count(self, before: date) -> int:
        """Number of trading sessions with date < before."""
        return self._prices.filter(pl.col(QP_DATE) < before).height

    def visible(self, as_of: date) -> pl.DataFrame:
        """All bars with date <= as_of (includes lookback before sim start)."""
        return self._prices.filter(pl.col(QP_DATE) <= as_of)

    def bar(self, on: date) -> dict[str, float | date]:
        """Return OHLCV for a single session date."""
        rows = self._prices.filter(pl.col(QP_DATE) == on)
        if rows.is_empty():
            raise KeyError(f"No bar for date {on}")
        row = rows.row(0, named=True)
        return {
            "date": row[QP_DATE],
            "open": float(row[QP_OPEN]),
            "high": float(row[QP_HIGH]),
            "low": float(row[QP_LOW]),
            "close": float(row[QP_CLOSE]),
            "volume": float(row[QP_VOLUME]),
        }
