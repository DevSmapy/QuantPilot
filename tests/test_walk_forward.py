"""Tests for rolling walk-forward helper."""

from __future__ import annotations

import pytest

from quantpilot.backtest.walk_forward import run_walk_forward
from quantpilot.strategy.sma_cross import SMACrossStrategy


def test_walk_forward_produces_at_least_two_folds(sample_prices) -> None:
    strategy = SMACrossStrategy(fast_window=5, slow_window=20)
    folds = run_walk_forward(
        sample_prices,
        strategy,
        train_bars=40,
        test_bars=20,
        step_bars=20,
    )
    assert len(folds) >= 2
    assert folds[0].test_end < folds[1].test_start or folds[0].test_start < folds[1].test_start
    for fold in folds:
        assert fold.train_start <= fold.train_end
        assert fold.test_start <= fold.test_end
        assert fold.train_end < fold.test_start
        assert len(fold.result.equity_curve) == 20


def test_walk_forward_rejects_invalid_window_sizes(sample_prices) -> None:
    strategy = SMACrossStrategy(fast_window=5, slow_window=20)
    with pytest.raises(ValueError):
        run_walk_forward(
            sample_prices,
            strategy,
            train_bars=0,
            test_bars=10,
            step_bars=5,
        )
