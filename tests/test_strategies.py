"""Tests for trading strategies and Strategy protocol."""

from __future__ import annotations

import polars as pl

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
    import pytest

    with pytest.raises(ValueError):
        RSIReversionStrategy(oversold=70.0, overbought=30.0)
