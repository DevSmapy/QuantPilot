"""Tests for rolling walk-forward helper."""

from __future__ import annotations

<<<<<<< HEAD
from datetime import date, timedelta

import polars as pl
import pytest

from quantpilot.backtest.walk_forward import run_walk_forward
from quantpilot.providers.qseed_schema import QP_CLOSE, QP_DATE
=======
import pytest

from quantpilot.backtest.walk_forward import run_walk_forward
>>>>>>> 90d13fb (feat(backtest): rolling OOS walk-forward helper)
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
<<<<<<< HEAD
<<<<<<< HEAD
    assert folds[0].test_start < folds[1].test_start
=======
    assert folds[0].test_end < folds[1].test_start or folds[0].test_start < folds[1].test_start
>>>>>>> 90d13fb (feat(backtest): rolling OOS walk-forward helper)
=======
    assert folds[0].test_start < folds[1].test_start
>>>>>>> 39ae0ff (fix(analysis-quant): satisfy mypy and ruff on new modules)
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
<<<<<<< HEAD


def test_walk_forward_warms_indicators_for_early_oos_crossover() -> None:
    """Slow SMA needs train history so a cross early in the test window is visible."""
    start = date(2024, 1, 1)
    # 30 flat bars (train), then a sharp rise so fast SMA crosses slow early in OOS.
    closes = [100.0] * 30 + [100.0 + i * 3.0 for i in range(1, 21)]
    prices = pl.DataFrame(
        {
            QP_DATE: [start + timedelta(days=i) for i in range(len(closes))],
            QP_CLOSE: closes,
            "symbol": ["TEST.KS"] * len(closes),
            "open": closes,
            "high": [c + 1.0 for c in closes],
            "low": [c - 1.0 for c in closes],
            "volume": [1000] * len(closes),
            "market": ["KOSPI"] * len(closes),
        }
    )
    strategy = SMACrossStrategy(fast_window=3, slow_window=20)
    folds = run_walk_forward(
        prices,
        strategy,
        train_bars=30,
        test_bars=20,
        step_bars=20,
    )
    assert len(folds) == 1
    test_signals = strategy.run(prices).filter(
        pl.col(QP_DATE) >= folds[0].test_start
    )
    # With warm-up context, at least one buy event should appear in the OOS window.
    assert test_signals.filter(pl.col("signal") == 1).height >= 1
    assert folds[0].result.trades_count >= 1

    # Cold start on test-only would miss the early cross relative to warmed signals.
    cold = strategy.run(prices.slice(30, 20))
    warm_oos = strategy.run(prices).filter(pl.col(QP_DATE) >= folds[0].test_start)
    assert warm_oos.filter(pl.col("signal") == 1).height >= cold.filter(
        pl.col("signal") == 1
    ).height
=======
>>>>>>> 90d13fb (feat(backtest): rolling OOS walk-forward helper)
