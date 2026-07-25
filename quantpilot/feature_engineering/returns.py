"""Price return and volatility feature helpers."""

from __future__ import annotations

import math

import polars as pl


def simple_returns(series: pl.Series) -> pl.Series:
    """Per-bar simple returns ``(p_t / p_{t-1}) - 1`` (first value null)."""
    prices = series.cast(pl.Float64)
    prev = prices.shift(1)
    return (prices / prev) - 1.0


def log_returns(series: pl.Series) -> pl.Series:
    """Per-bar log returns ``ln(p_t / p_{t-1})`` (first value null)."""
    prices = series.cast(pl.Float64)
    prev = prices.shift(1)
    ratio = prices / prev
    return ratio.log()


def rolling_volatility(
    series: pl.Series,
    window: int = 20,
    *,
    annualize: bool = True,
    trading_days: int = 252,
) -> pl.Series:
    """Rolling standard deviation of simple returns.

    When ``annualize`` is true, multiplies by ``sqrt(trading_days)``.
    """
    if window < 1:
        raise ValueError("window must be >= 1")
    if trading_days < 1:
        raise ValueError("trading_days must be >= 1")

    rets = simple_returns(series)
    vol = rets.rolling_std(window_size=window)
    if annualize:
        scale = math.sqrt(trading_days)
        return vol * scale
    return vol
