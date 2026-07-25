"""Exponential Moving Average indicator."""

from __future__ import annotations

import polars as pl


def ema(series: pl.Series, window: int) -> pl.Series:
    """Calculate exponential moving average for a numeric series."""
    if window < 1:
        raise ValueError("window must be >= 1")
    return series.cast(pl.Float64).ewm_mean(span=window, adjust=False)
