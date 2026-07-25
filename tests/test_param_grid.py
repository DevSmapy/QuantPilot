"""Tests for the fixed parameter grid helper."""

from __future__ import annotations

import polars as pl
import pytest

from quantpilot.backtest.param_grid import run_param_grid
from quantpilot.strategy.sma_cross import SMACrossStrategy


def test_run_param_grid_evaluates_each_row(sample_prices: pl.DataFrame) -> None:
    grid = [
        {"fast_window": 5, "slow_window": 20},
        {"fast_window": 10, "slow_window": 30},
    ]
    rows = run_param_grid(
        sample_prices,
        strategy_factory=SMACrossStrategy,
        param_grid=grid,
    )
    assert len(rows) == 2
    assert rows[0].params == grid[0]
    assert rows[1].params == grid[1]
    assert isinstance(rows[0].result.total_return, float)
    assert len(rows[0].result.equity_curve) == sample_prices.height


def test_run_param_grid_rejects_empty(sample_prices: pl.DataFrame) -> None:
    with pytest.raises(ValueError, match="empty"):
        run_param_grid(
            sample_prices,
            strategy_factory=SMACrossStrategy,
            param_grid=[],
        )


def test_run_param_grid_accepts_rsi_factory(sample_prices: pl.DataFrame) -> None:
    from quantpilot.strategy.rsi_reversion import RSIReversionStrategy

    rows = run_param_grid(
        sample_prices,
        strategy_factory=RSIReversionStrategy,
        param_grid=[{"window": 5, "oversold": 40.0, "overbought": 60.0}],
    )
    assert len(rows) == 1
    assert rows[0].params["window"] == 5
