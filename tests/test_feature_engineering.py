"""Tests for feature_engineering return/volatility helpers."""

from __future__ import annotations

import math

import polars as pl
import pytest

from quantpilot.feature_engineering import (
    log_returns,
    rolling_volatility,
    simple_returns,
)


def test_simple_returns_known_values() -> None:
    prices = pl.Series([100.0, 110.0, 99.0])
    rets = simple_returns(prices)
    assert rets[0] is None
    assert float(rets[1]) == pytest.approx(0.1)
    assert float(rets[2]) == pytest.approx(-0.1)


def test_log_returns_known_values() -> None:
    prices = pl.Series([100.0, 110.0])
    rets = log_returns(prices)
    assert rets[0] is None
    assert float(rets[1]) == pytest.approx(math.log(1.1))


def test_rolling_volatility_annualized(sample_prices: pl.DataFrame) -> None:
    daily = rolling_volatility(sample_prices["close"], window=10, annualize=False)
    ann = rolling_volatility(sample_prices["close"], window=10, annualize=True)
    assert daily.len() == sample_prices.height
    last_daily = float(daily[-1])
    last_ann = float(ann[-1])
    assert last_ann == pytest.approx(last_daily * math.sqrt(252))


def test_rolling_volatility_rejects_invalid_window() -> None:
    with pytest.raises(ValueError):
        rolling_volatility(pl.Series([1.0, 2.0]), window=0)


def test_returns_reject_non_positive_prices() -> None:
    with pytest.raises(ValueError, match="positive"):
        simple_returns(pl.Series([100.0, 0.0, 110.0]))
    with pytest.raises(ValueError, match="positive"):
        log_returns(pl.Series([100.0, -1.0]))
