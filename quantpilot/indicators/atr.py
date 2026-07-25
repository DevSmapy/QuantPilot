"""Average True Range indicator (Wilder)."""

from __future__ import annotations

import polars as pl


def atr(
    high: pl.Series,
    low: pl.Series,
    close: pl.Series,
    window: int = 14,
) -> pl.Series:
    """Wilder Average True Range from high/low/close series.

    True range is smoothed with Wilder's RMA (``alpha = 1 / window``,
    ``adjust=False``), matching common charting platforms more closely than
    a simple moving average of TR.
    """
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

    return true_range.ewm_mean(alpha=1.0 / float(window), adjust=False)
