"""Buy-and-hold benchmark for the simulation window."""

from __future__ import annotations

from datetime import date
from typing import cast

from quantpilot.environment.market import HistoricalMarket, intersect_session_dates


def buy_and_hold_final_equity(
    markets: dict[str, HistoricalMarket] | HistoricalMarket,
    *,
    start: date,
    end: date,
    capital: float,
    symbols: list[str] | None = None,
) -> float:
    """Buy max integer shares at first open(s); value at last close.

    Single-market (legacy): pass one ``HistoricalMarket``.
    Multi-symbol: equal cash split across ``symbols``, no fees/slippage.
    """
    if isinstance(markets, HistoricalMarket):
        return _single_bah(markets, start=start, end=end, capital=capital)

    if not markets:
        raise ValueError("markets must not be empty")
    ordered = symbols or list(markets.keys())
    if not ordered:
        raise ValueError("symbols must not be empty")
    missing = [s for s in ordered if s not in markets]
    if missing:
        raise KeyError(f"Missing markets for symbols: {missing}")

    if len(ordered) == 1:
        return _single_bah(markets[ordered[0]], start=start, end=end, capital=capital)

    dates = intersect_session_dates(markets, start, end)
    if not dates:
        raise ValueError("No session dates in [start, end]")
    first, last = dates[0], dates[-1]
    sleeve = capital / len(ordered)
    cash = 0.0
    equity = 0.0
    for symbol in ordered:
        market = markets[symbol]
        first_open = float(cast(float, market.bar(first)["open"]))
        last_close = float(cast(float, market.bar(last)["close"]))
        if first_open <= 0:
            raise ValueError(f"first open price must be > 0 for {symbol}")
        qty = int(sleeve // first_open)
        cash += sleeve - qty * first_open
        equity += qty * last_close
    return cash + equity


def _single_bah(
    market: HistoricalMarket,
    *,
    start: date,
    end: date,
    capital: float,
) -> float:
    dates = market.session_dates(start, end)
    if not dates:
        raise ValueError("No session dates in [start, end]")
    first_open = float(cast(float, market.bar(dates[0])["open"]))
    last_close = float(cast(float, market.bar(dates[-1])["close"]))
    if first_open <= 0:
        raise ValueError("first open price must be > 0")
    qty = int(capital // first_open)
    cash = capital - qty * first_open
    return cash + qty * last_close
