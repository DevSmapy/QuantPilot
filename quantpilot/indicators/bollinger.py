"""Bollinger Bands indicator."""

from __future__ import annotations

import polars as pl


def bollinger(
    series: pl.Series,
    window: int = 20,
    num_std: float = 2.0,
) -> pl.DataFrame:
    """Return middle/upper/lower Bollinger Bands.

    Columns: ``mid``, ``upper``, ``lower``.
    """
    if window < 1:
        raise ValueError("window must be >= 1")
    if num_std < 0:
        raise ValueError("num_std must be >= 0")

    prices = series.cast(pl.Float64)
    mid = prices.rolling_mean(window_size=window)
    std = prices.rolling_std(window_size=window)
    upper = mid + (std * num_std)
    lower = mid - (std * num_std)
    return pl.DataFrame({"mid": mid, "upper": upper, "lower": lower})
