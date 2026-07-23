"""Buy-and-hold benchmark for the simulation window."""

from __future__ import annotations

from datetime import date
from typing import cast

from quantpilot.environment.costs import TradingCosts
from quantpilot.environment.market import HistoricalMarket, intersect_session_dates


def buy_and_hold_final_equity(
    markets: dict[str, HistoricalMarket] | HistoricalMarket,
    *,
    start: date,
    end: date,
    capital: float,
    symbols: list[str] | None = None,
    costs: TradingCosts | None = None,
) -> float:
    """Buy max integer shares at first open(s); value at last close.

    Entry uses the same ``TradingCosts`` as the agent (slippage + commission).
    Positions are marked at the last close without an exit trade.
    """
    costs = costs or TradingCosts()
    if isinstance(markets, HistoricalMarket):
        return _single_bah(
            markets, start=start, end=end, capital=capital, costs=costs
        )

    if not markets:
        raise ValueError("markets must not be empty")
    ordered = symbols or list(markets.keys())
    if not ordered:
        raise ValueError("symbols must not be empty")
    missing = [s for s in ordered if s not in markets]
    if missing:
        raise KeyError(f"Missing markets for symbols: {missing}")

    if len(ordered) == 1:
        return _single_bah(
            markets[ordered[0]],
            start=start,
            end=end,
            capital=capital,
            costs=costs,
        )

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
        qty, leftover = _buy_lot(sleeve, first_open, costs)
        cash += leftover
        equity += qty * last_close
    return cash + equity


def _buy_lot(
    cash: float,
    open_price: float,
    costs: TradingCosts,
) -> tuple[int, float]:
    """Return (shares, leftover_cash) after a full-sleeve buy with costs."""
    if open_price <= 0:
        raise ValueError("open price must be > 0")
    exec_price = costs.exec_price(open_price, action="buy")
    if exec_price <= 0:
        raise ValueError("exec price must be > 0")
    rate = costs.commission_rate
    max_notional = cash / (1.0 + rate) if rate > 0 else cash
    qty = int(max_notional // exec_price)
    if qty <= 0:
        return 0, cash
    notional = qty * exec_price
    fee = costs.commission(notional)
    leftover = cash - notional - fee
    if leftover < -1e-9:
        return 0, cash
    return qty, leftover


def _single_bah(
    market: HistoricalMarket,
    *,
    start: date,
    end: date,
    capital: float,
    costs: TradingCosts,
) -> float:
    dates = market.session_dates(start, end)
    if not dates:
        raise ValueError("No session dates in [start, end]")
    first_open = float(cast(float, market.bar(dates[0])["open"]))
    last_close = float(cast(float, market.bar(dates[-1])["close"]))
    qty, cash = _buy_lot(capital, first_open, costs)
    return cash + qty * last_close
