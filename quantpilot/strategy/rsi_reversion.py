"""RSI mean-reversion strategy (long-only event signals)."""

from __future__ import annotations

import polars as pl

from quantpilot.indicators.rsi import rsi
from quantpilot.providers.qseed_schema import QP_CLOSE, QP_DATE


class RSIReversionStrategy:
<<<<<<< HEAD
    """Enter when RSI first becomes oversold; exit when first overbought."""
=======
    """Enter when RSI is oversold; exit when RSI is overbought."""
>>>>>>> 6148b96 (feat(strategy): Protocol + RSI reversion)

    def __init__(
        self,
        window: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
    ) -> None:
        if window < 1:
            raise ValueError("window must be >= 1")
        if not (0.0 < oversold < overbought < 100.0):
            raise ValueError("require 0 < oversold < overbought < 100")
        self.window = window
        self.oversold = oversold
        self.overbought = overbought

    def run(self, prices: pl.DataFrame) -> pl.DataFrame:
<<<<<<< HEAD
        """Generate edge-triggered trade signals from OHLCV price data."""
=======
        """Generate trade signals from OHLCV price data."""
>>>>>>> 6148b96 (feat(strategy): Protocol + RSI reversion)
        if QP_CLOSE not in prices.columns:
            raise ValueError(f"prices must contain '{QP_CLOSE}' column")

        frame = prices.sort(QP_DATE)
        rsi_values = rsi(frame[QP_CLOSE], self.window)
        with_rsi = frame.with_columns(rsi_values.alias("rsi"))

        return (
            with_rsi.with_columns(
                pl.when(pl.col("rsi") < self.oversold)
<<<<<<< HEAD
                .then(pl.lit("oversold"))
                .when(pl.col("rsi") > self.overbought)
                .then(pl.lit("overbought"))
                .otherwise(pl.lit("neutral"))
                .alias("regime")
            )
            .with_columns(pl.col("regime").shift(1).alias("prev_regime"))
            .with_columns(
                pl.when(
                    (pl.col("regime") == "oversold")
                    & (pl.col("prev_regime") != "oversold")
                )
                .then(1)
                .when(
                    (pl.col("regime") == "overbought")
                    & (pl.col("prev_regime") != "overbought")
                )
                .then(-1)
                .otherwise(0)
                .alias("signal")
            )
            .select(QP_DATE, "signal", "rsi", QP_CLOSE)
=======
                .then(1)
                .when(pl.col("rsi") > self.overbought)
                .then(-1)
                .otherwise(0)
                .alias("signal")
            ).select(QP_DATE, "signal", "rsi", QP_CLOSE)
>>>>>>> 6148b96 (feat(strategy): Protocol + RSI reversion)
        )
