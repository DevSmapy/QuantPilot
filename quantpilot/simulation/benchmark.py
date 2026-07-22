"""Buy-and-hold benchmark for the simulation window."""

from __future__ import annotations

from datetime import date

from quantpilot.environment.market import HistoricalMarket


def buy_and_hold_final_equity(
    market: HistoricalMarket,
    *,
    start: date,
    end: date,
    capital: float,
) -> float:
    """Buy max integer shares at first open; value at last close."""
    dates = market.session_dates(start, end)
    if not dates:
        raise ValueError("No session dates in [start, end]")
    first_open = float(market.bar(dates[0])["open"])
    last_close = float(market.bar(dates[-1])["close"])
    if first_open <= 0:
        raise ValueError("first open price must be > 0")
    qty = int(capital // first_open)
    cash = capital - qty * first_open
    return cash + qty * last_close
