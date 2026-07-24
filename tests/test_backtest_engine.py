"""Tests for backtest engine and strategy."""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from quantpilot.backtest.engine import BacktestEngine
from quantpilot.environment.costs import TradingCosts
from quantpilot.indicators.rsi import rsi
from quantpilot.indicators.sma import sma
from quantpilot.providers.qseed_schema import QP_CLOSE, QP_DATE
from quantpilot.strategy.sma_cross import SMACrossStrategy


def test_sma_indicator(sample_prices: pl.DataFrame) -> None:
    values = sma(sample_prices["close"], 5)
    assert values.null_count() >= 4


def test_rsi_indicator(sample_prices: pl.DataFrame) -> None:
    values = rsi(sample_prices["close"], 14)
    assert values.len() == sample_prices.height


def test_rsi_flat_price_returns_neutral_value() -> None:
    flat_prices = pl.Series("close", [100.0] * 20)
    values = rsi(flat_prices, 14)
    assert values.drop_nulls()[-1] == 50.0


def test_sma_cross_strategy_generates_signals(sample_prices: pl.DataFrame) -> None:
    strategy = SMACrossStrategy(fast_window=5, slow_window=20)
    signals = strategy.run(sample_prices)
    assert "signal" in signals.columns
    assert signals["signal"].is_in([-1, 0, 1]).all()


def test_backtest_engine_deterministic_metrics() -> None:
    prices = pl.DataFrame(
        {
            QP_DATE: [
                date(2024, 1, 1),
                date(2024, 1, 2),
                date(2024, 1, 3),
                date(2024, 1, 4),
                date(2024, 1, 5),
            ],
            QP_CLOSE: [100.0, 102.0, 101.0, 103.0, 105.0],
        }
    )
    signals = pl.DataFrame(
        {
            QP_DATE: prices[QP_DATE],
            "signal": [0, 1, 0, 0, -1],
        }
    )

    result = BacktestEngine().run(prices, signals)

    assert result.trades_count == 1
    assert result.total_return == pytest.approx(0.02941176470588225)
    assert result.mdd == pytest.approx(-0.009803921568627416)
    assert result.sharpe == pytest.approx(9.165151389911701)
    assert result.cagr > 0.0
    assert result.equity_curve == pytest.approx(
        [1.0, 1.0, 0.9901960784313726, 1.0098039215686274, 1.0294117647058822]
    )
    assert result.trade_pnls == []
    assert result.win_rate == 0.0
    assert result.profit_factor == 0.0


def test_backtest_engine_round_trip_and_costs() -> None:
    prices = pl.DataFrame(
        {
            QP_DATE: [
                date(2024, 1, 1),
                date(2024, 1, 2),
                date(2024, 1, 3),
                date(2024, 1, 4),
                date(2024, 1, 5),
            ],
            QP_CLOSE: [100.0, 100.0, 110.0, 110.0, 110.0],
        }
    )
    # Enter on bar1 signal -> execute at bar2; exit on bar3 signal -> execute at bar4.
    signals = pl.DataFrame(
        {
            QP_DATE: prices[QP_DATE],
            "signal": [1, 0, -1, 0, 0],
        }
    )

    free = BacktestEngine().run(prices, signals)
    costly = BacktestEngine().run(
        prices, signals, costs=TradingCosts(commission_rate=0.01, slippage_bps=0.0)
    )

    assert free.trades_count == 2
    assert len(free.trade_pnls) == 1
    assert free.trade_pnls[0] == pytest.approx(0.1)
    assert free.win_rate == 1.0
    assert free.profit_factor == float("inf")
    assert costly.total_return < free.total_return
    assert costly.equity_curve[-1] < free.equity_curve[-1]


def test_backtest_engine_returns_metrics(sample_prices: pl.DataFrame) -> None:
    strategy = SMACrossStrategy(fast_window=5, slow_window=20)
    signals = strategy.run(sample_prices)
    engine = BacktestEngine()
    result = engine.run(sample_prices, signals)

    assert isinstance(result.total_return, float)
    assert isinstance(result.cagr, float)
    assert isinstance(result.mdd, float)
    assert isinstance(result.sharpe, float)
    assert isinstance(result.sortino, float)
    assert isinstance(result.profit_factor, float)
    assert isinstance(result.win_rate, float)
    assert len(result.equity_curve) == sample_prices.height
    assert result.trades_count >= 0
