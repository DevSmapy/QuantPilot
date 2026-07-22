"""Simple Moving Average indicator."""

from __future__ import annotations

import polars as pl


def sma(series: pl.Series, window: int) -> pl.Series:
    """Calculate simple moving average for a numeric series."""
    if window < 1:
        raise ValueError("window must be >= 1")
    return series.cast(pl.Float64).rolling_mean(window_size=window)
