"""Tests for SimulationClock and HistoricalMarket look-ahead safety."""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from quantpilot.environment.clock import SimulationClock
from quantpilot.environment.market import HistoricalMarket


def test_clock_decision_days() -> None:
    dates = [date(2024, 1, d) for d in (2, 3, 4, 5, 8, 9)]
    clock = SimulationClock(dates)
    assert clock.is_decision_day(5)
    clock.advance()
    assert not clock.is_decision_day(5)
    while clock.session_index < 5:
        clock.advance()
    assert clock.as_of == date(2024, 1, 9)
    assert clock.is_decision_day(5)


def test_market_visible_has_no_future(sample_prices: pl.DataFrame) -> None:
    market = HistoricalMarket(sample_prices)
    as_of = date(2023, 2, 1)
    visible = market.visible(as_of)
    assert visible["date"].max() <= as_of
    later = sample_prices.filter(pl.col("date") > as_of)
    assert later.height > 0


def test_market_session_dates_window(sample_prices: pl.DataFrame) -> None:
    market = HistoricalMarket(sample_prices)
    sessions = market.session_dates(date(2023, 1, 10), date(2023, 1, 20))
    assert sessions[0] == date(2023, 1, 10)
    assert sessions[-1] == date(2023, 1, 20)
    assert all(date(2023, 1, 10) <= d <= date(2023, 1, 20) for d in sessions)


def test_prior_session_count(sample_prices: pl.DataFrame) -> None:
    market = HistoricalMarket(sample_prices)
    assert market.prior_session_count(date(2023, 1, 11)) == 10


def test_market_missing_bar_raises(sample_prices: pl.DataFrame) -> None:
    market = HistoricalMarket(sample_prices)
    with pytest.raises(KeyError):
        market.bar(date(2099, 1, 1))


def test_market_does_not_expose_full_prices_attr() -> None:
    assert not hasattr(HistoricalMarket, "prices")
