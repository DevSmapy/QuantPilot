"""Moving Average Convergence Divergence (MACD) indicator."""

from __future__ import annotations

import polars as pl

from quantpilot.indicators.ema import ema


def macd(
    series: pl.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pl.DataFrame:
    """Return MACD line, signal line, and histogram as a DataFrame.

    Columns: ``macd``, ``signal``, ``histogram``.
    """
    if fast < 1 or slow < 1 or signal < 1:
        raise ValueError("fast, slow, and signal must be >= 1")
    if fast >= slow:
        raise ValueError("fast must be smaller than slow")

    prices = series.cast(pl.Float64)
    macd_line = ema(prices, fast) - ema(prices, slow)
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return pl.DataFrame(
        {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram,
        }
    )
