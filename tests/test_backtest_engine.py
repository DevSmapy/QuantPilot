"""Tests for backtest engine and strategy."""

from __future__ import annotations

import polars as pl

from quantpilot.backtest.engine import BacktestEngine
from quantpilot.indicators.rsi import rsi
from quantpilot.indicators.sma import sma
from quantpilot.strategy.sma_cross import SMACrossStrategy


def test_sma_indicator(sample_prices: pl.DataFrame) -> None:
    values = sma(sample_prices["close"], 5)
    assert values.null_count() >= 4


def test_rsi_indicator(sample_prices: pl.DataFrame) -> None:
    values = rsi(sample_prices["close"], 14)
    assert values.len() == sample_prices.height


def test_sma_cross_strategy_generates_signals(sample_prices: pl.DataFrame) -> None:
    strategy = SMACrossStrategy(fast_window=5, slow_window=20)
    signals = strategy.run(sample_prices)
    assert "signal" in signals.columns
    assert signals["signal"].is_in([-1, 0, 1]).all()


def test_backtest_engine_returns_metrics(sample_prices: pl.DataFrame) -> None:
    strategy = SMACrossStrategy(fast_window=5, slow_window=20)
    signals = strategy.run(sample_prices)
    engine = BacktestEngine()
    result = engine.run(sample_prices, signals)

    assert isinstance(result.total_return, float)
    assert isinstance(result.cagr, float)
    assert isinstance(result.mdd, float)
    assert isinstance(result.sharpe, float)
    assert result.trades_count >= 0
