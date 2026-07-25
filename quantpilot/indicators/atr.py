"""Average True Range indicator."""

from __future__ import annotations

import polars as pl


def atr(
    high: pl.Series,
    low: pl.Series,
    close: pl.Series,
    window: int = 14,
) -> pl.Series:
    """Calculate Average True Range from high/low/close series."""
    if window < 1:
        raise ValueError("window must be >= 1")
    if not (high.len() == low.len() == close.len()):
        raise ValueError("high, low, and close must have the same length")

    frame = pl.DataFrame(
        {
            "high": high.cast(pl.Float64),
            "low": low.cast(pl.Float64),
            "close": close.cast(pl.Float64),
        }
    ).with_columns(pl.col("close").shift(1).alias("prev_close"))

    true_range = frame.select(
        pl.max_horizontal(
            pl.col("high") - pl.col("low"),
            (pl.col("high") - pl.col("prev_close")).abs(),
            (pl.col("low") - pl.col("prev_close")).abs(),
        ).alias("tr")
    )["tr"]

    return true_range.rolling_mean(window_size=window)
