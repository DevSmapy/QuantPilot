"""Relative Strength Index indicator."""

from __future__ import annotations

import polars as pl


def rsi(series: pl.Series, window: int = 14) -> pl.Series:
    """Calculate RSI for a numeric price series."""
    if window < 1:
        raise ValueError("window must be >= 1")

    prices = series.cast(pl.Float64)
    delta = prices.diff()
    gain = delta.clip(lower_bound=0.0)
    loss = (-delta).clip(lower_bound=0.0)

    avg_gain = gain.rolling_mean(window_size=window)
    avg_loss = loss.rolling_mean(window_size=window)
    rs = avg_gain / avg_loss

    return pl.DataFrame({"avg_gain": avg_gain, "avg_loss": avg_loss, "rs": rs}).select(
        pl.when((pl.col("avg_loss") == 0) & (pl.col("avg_gain") == 0))
        .then(50.0)
        .when(pl.col("avg_loss") == 0)
        .then(100.0)
        .otherwise(100.0 - (100.0 / (1.0 + pl.col("rs"))))
        .fill_nan(50.0)
        .alias("rsi")
    )["rsi"]
