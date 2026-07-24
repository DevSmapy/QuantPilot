"""Tests for backtest performance metrics."""

from __future__ import annotations

from datetime import date

import pytest

from quantpilot.backtest import metrics


def test_max_drawdown_and_sharpe_match_prior_helpers() -> None:
    curve = [1.0, 1.0, 0.9901960784313726, 1.0098039215686274, 1.0294117647058822]
    assert metrics.max_drawdown(curve) == pytest.approx(-0.009803921568627416)
    assert metrics.sharpe_ratio(curve) == pytest.approx(9.165151389911701)


def test_sortino_ignores_upside_in_denominator() -> None:
    curve = [1.0, 0.9, 1.0]
    returns = metrics.period_returns(curve)
    assert returns[0] < 0
    assert returns[1] > 0
    sortino = metrics.sortino_ratio(curve)
    sharpe = metrics.sharpe_ratio(curve)
    assert sortino > sharpe


def test_profit_factor_and_win_rate() -> None:
    pnls = [0.1, -0.05, 0.2, -0.05]
    assert metrics.profit_factor(pnls) == pytest.approx(3.0)
    assert metrics.win_rate(pnls) == pytest.approx(0.5)


def test_profit_factor_no_losses_with_gains() -> None:
    assert metrics.profit_factor([0.1, 0.2]) == float("inf")


def test_empty_trades_metrics() -> None:
    assert metrics.profit_factor([]) == 0.0
    assert metrics.win_rate([]) == 0.0


def test_cagr_positive_over_year() -> None:
    value = metrics.cagr(1.1, date(2024, 1, 1), date(2025, 1, 1))
    assert value == pytest.approx(0.1, abs=1e-3)
