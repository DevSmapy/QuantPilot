"""Tests for trading strategies and Strategy protocol."""

from __future__ import annotations

import polars as pl
<<<<<<< HEAD
import pytest
=======
>>>>>>> 6148b96 (feat(strategy): Protocol + RSI reversion)

from quantpilot.backtest.engine import BacktestEngine
from quantpilot.strategy.base import Strategy
from quantpilot.strategy.rsi_reversion import RSIReversionStrategy
from quantpilot.strategy.sma_cross import SMACrossStrategy


def _assert_is_strategy(strategy: Strategy) -> None:
    assert callable(strategy.run)


def test_sma_cross_uses_strategy_protocol(sample_prices: pl.DataFrame) -> None:
    strategy = SMACrossStrategy(fast_window=5, slow_window=20)
    _assert_is_strategy(strategy)
    signals = strategy.run(sample_prices)
    assert signals["signal"].is_in([-1, 0, 1]).all()


def test_rsi_reversion_generates_event_signals(sample_prices: pl.DataFrame) -> None:
    strategy = RSIReversionStrategy(window=5, oversold=40.0, overbought=60.0)
    _assert_is_strategy(strategy)
    signals = strategy.run(sample_prices)
    assert "signal" in signals.columns
    assert "rsi" in signals.columns
    assert signals["signal"].is_in([-1, 0, 1]).all()


def test_both_strategies_run_on_same_engine(sample_prices: pl.DataFrame) -> None:
    engine = BacktestEngine()
    for strategy in (
        SMACrossStrategy(fast_window=5, slow_window=20),
        RSIReversionStrategy(window=5, oversold=40.0, overbought=60.0),
    ):
        result = engine.run(sample_prices, strategy.run(sample_prices))
        assert len(result.equity_curve) == sample_prices.height
        assert isinstance(result.total_return, float)


def test_rsi_reversion_rejects_invalid_thresholds() -> None:
<<<<<<< HEAD
    with pytest.raises(ValueError):
        RSIReversionStrategy(oversold=70.0, overbought=30.0)


def test_rsi_reversion_emits_edge_triggered_events_only() -> None:
    """Consecutive oversold/overbought bars should yield a single edge each."""
    # Build closes so RSI stays below oversold then above overbought for several bars.
    # Falling prices → oversold regime, then rising → overbought.
    falling = [100.0 - i * 2.0 for i in range(25)]
    rising = [falling[-1] + i * 4.0 for i in range(1, 26)]
    closes = falling + rising
    from datetime import date, timedelta

    from quantpilot.providers.qseed_schema import QP_CLOSE, QP_DATE

    prices = pl.DataFrame(
        {
            QP_DATE: [date(2024, 1, 1) + timedelta(days=i) for i in range(len(closes))],
            QP_CLOSE: closes,
        }
    )
    strategy = RSIReversionStrategy(window=5, oversold=40.0, overbought=60.0)
    signals = strategy.run(prices)
    buys = signals.filter(pl.col("signal") == 1)
    sells = signals.filter(pl.col("signal") == -1)
    assert buys.height >= 1
    assert sells.height >= 1

    # No two consecutive non-zero signals of the same sign (regime persistence → 0).
    signal_list = signals["signal"].to_list()
    for i in range(1, len(signal_list)):
        if signal_list[i] != 0 and signal_list[i] == signal_list[i - 1]:
            raise AssertionError(
                f"repeated edge signal {signal_list[i]} at index {i}"
            )

    # While RSI remains in oversold after entry edge, further bars must be 0.
    oversold_mask = signals["rsi"] < 40.0
    oversold_signals = signals.filter(oversold_mask)["signal"].to_list()
    assert oversold_signals.count(1) == 1
    overbought_signals = signals.filter(signals["rsi"] > 60.0)["signal"].to_list()
    assert overbought_signals.count(-1) == 1
=======
    import pytest

    with pytest.raises(ValueError):
        RSIReversionStrategy(oversold=70.0, overbought=30.0)
>>>>>>> 6148b96 (feat(strategy): Protocol + RSI reversion)
