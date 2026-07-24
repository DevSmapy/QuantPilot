"""Simple moving average crossover strategy."""

from __future__ import annotations

import polars as pl

from quantpilot.indicators.sma import sma
from quantpilot.providers.qseed_schema import QP_CLOSE, QP_DATE


class SMACrossStrategy:
    """Long-only SMA crossover strategy (fast/slow golden cross)."""

    def __init__(self, fast_window: int = 20, slow_window: int = 60) -> None:
        if fast_window >= slow_window:
            raise ValueError("fast_window must be smaller than slow_window")
        self.fast_window = fast_window
        self.slow_window = slow_window

    def run(self, prices: pl.DataFrame) -> pl.DataFrame:
        """Generate trade signals from OHLCV price data."""
        if QP_CLOSE not in prices.columns:
            raise ValueError(f"prices must contain '{QP_CLOSE}' column")

        frame = prices.sort(QP_DATE)
        close = frame[QP_CLOSE]
        frame = frame.with_columns(
            sma(close, self.fast_window).alias("fast_sma"),
            sma(close, self.slow_window).alias("slow_sma"),
        )

        signals = (
            frame.with_columns(
                pl.when(pl.col("fast_sma") > pl.col("slow_sma"))
                .then(1)
                .when(pl.col("fast_sma") < pl.col("slow_sma"))
                .then(-1)
                .otherwise(0)
                .alias("position")
            )
            .with_columns(
                pl.col("position").shift(1).fill_null(0).alias("prev_position")
            )
            .with_columns(
                pl.when((pl.col("position") == 1) & (pl.col("prev_position") <= 0))
                .then(1)
                .when((pl.col("position") == -1) & (pl.col("prev_position") >= 0))
                .then(-1)
                .otherwise(0)
                .alias("signal")
            )
            .select(QP_DATE, "signal", "fast_sma", "slow_sma", QP_CLOSE)
        )
        return signals
