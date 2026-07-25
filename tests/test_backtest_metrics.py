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


def test_monthly_returns_from_month_end_equity() -> None:
    dates = [
        date(2024, 1, 15),
        date(2024, 1, 31),
        date(2024, 2, 15),
        date(2024, 2, 29),
        date(2024, 3, 15),
    ]
    equity = [1.0, 1.1, 1.15, 1.21, 1.3]
    # Jan end 1.1 → Feb end 1.21 → Mar last 1.3
    out = metrics.monthly_returns(dates, equity)
    assert list(out.keys()) == ["2024-02", "2024-03"]
    assert out["2024-02"] == pytest.approx((1.21 / 1.1) - 1.0)
    assert out["2024-03"] == pytest.approx((1.3 / 1.21) - 1.0)


def test_monthly_returns_skips_calendar_gaps() -> None:
    dates = [
        date(2024, 1, 31),
        date(2024, 3, 31),  # February missing
        date(2024, 4, 30),
    ]
    equity = [1.0, 1.2, 1.3]
    out = metrics.monthly_returns(dates, equity)
    assert "2024-03" not in out  # would mislabel Jan→Mar as March-only
    assert out["2024-04"] == pytest.approx((1.3 / 1.2) - 1.0)


def test_monthly_returns_sorts_unsorted_input() -> None:
    dates = [date(2024, 2, 28), date(2024, 1, 31), date(2024, 3, 31)]
    equity = [1.1, 1.0, 1.21]
    out = metrics.monthly_returns(dates, equity)
    assert out["2024-02"] == pytest.approx(0.1)
    assert out["2024-03"] == pytest.approx((1.21 / 1.1) - 1.0)


def test_monthly_returns_rejects_length_mismatch() -> None:
    with pytest.raises(ValueError):
        metrics.monthly_returns([date(2024, 1, 1)], [1.0, 1.1])
