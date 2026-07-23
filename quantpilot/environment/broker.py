"""Paper broker with next-open fill and close mark-to-market."""

from __future__ import annotations

from datetime import date
from typing import Literal

from quantpilot.environment.costs import TradingCosts
from quantpilot.environment.types import (
    Fill,
    FillResult,
    PendingOrder,
    PortfolioSnapshot,
    Position,
    QueueResult,
)


class PaperBroker:
    """Long-only multi-symbol cash account with optional trading costs."""

    def __init__(
        self,
        cash: float,
        *,
        costs: TradingCosts | None = None,
    ) -> None:
        if cash < 0:
            raise ValueError("cash must be >= 0")
        self._cash = float(cash)
        self._positions: dict[str, Position] = {}
        self._pending: PendingOrder | None = None
        self._costs = costs or TradingCosts()
        self._total_fees = 0.0

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def total_fees(self) -> float:
        return self._total_fees

    @property
    def pending(self) -> PendingOrder | None:
        return self._pending

    def qty(self, symbol: str | None = None) -> int:
        """Shares for one symbol, or total shares if symbol is None."""
        if symbol is None:
            return sum(pos.qty for pos in self._positions.values())
        pos = self._positions.get(symbol)
        return pos.qty if pos is not None else 0

    def avg_cost(self, symbol: str) -> float:
        pos = self._positions.get(symbol)
        return pos.avg_cost if pos is not None else 0.0

    def holdings(self) -> dict[str, int]:
        return {symbol: pos.qty for symbol, pos in self._positions.items() if pos.qty}

    def _require_prices(self, prices: dict[str, float]) -> None:
        missing = [symbol for symbol in self.holdings() if symbol not in prices]
        if missing:
            raise KeyError(f"Missing mark prices for holdings: {missing}")

    def snapshot(self, prices: dict[str, float]) -> PortfolioSnapshot:
        self._require_prices(prices)
        holdings = self.holdings()
        avg_costs = {symbol: self.avg_cost(symbol) for symbol in holdings}
        equity = self._cash
        unrealized = 0.0
        for symbol, qty in holdings.items():
            price = prices[symbol]
            equity += qty * price
            unrealized += (price - avg_costs[symbol]) * qty
        return PortfolioSnapshot(
            cash=self._cash,
            holdings=holdings,
            mark_prices=dict(prices),
            avg_costs=avg_costs,
            equity=equity,
            unrealized_pnl=unrealized,
        )

    def queue(
        self,
        action: Literal["buy", "sell", "hold"],
        size: float,
        reason: str,
        decision_date: date,
        *,
        symbol: str,
    ) -> QueueResult:
        """Register a pending order. Rejects invalid sell/size; hold clears pending."""
        if action == "hold":
            self._pending = None
            return QueueResult(accepted=True, message="hold")

        if not str(symbol).strip():
            self._pending = None
            return QueueResult(accepted=False, message="symbol_required")

        symbol = str(symbol).strip()

        if action == "sell":
            if not str(reason).strip():
                self._pending = None
                return QueueResult(accepted=False, message="sell_requires_reason")
            if self.qty(symbol) <= 0:
                self._pending = None
                return QueueResult(accepted=False, message="sell_zero_qty")

        if size <= 0 or size > 1:
            self._pending = None
            return QueueResult(accepted=False, message="invalid_size")

        if action == "buy" and self._cash <= 0:
            self._pending = None
            return QueueResult(accepted=False, message="buy_zero_cash")

        self._pending = PendingOrder(
            action=action,
            size=size,
            reason=str(reason).strip(),
            decision_date=decision_date,
            symbol=symbol,
        )
        return QueueResult(accepted=True, message="queued")

    def fill_pending(self, open_price: float, on: date) -> FillResult:
        """Execute pending order at today's open for the queued symbol."""
        order = self._pending
        self._pending = None
        if order is None:
            return FillResult(fill=None)

        if open_price <= 0:
            return FillResult(fill=None, rejected_reason="bad_price")

        exec_price = self._costs.exec_price(open_price, action=order.action)
        if exec_price <= 0:
            return FillResult(fill=None, rejected_reason="bad_price")

        if order.action == "buy":
            return self._fill_buy(order, exec_price, on)
        return self._fill_sell(order, exec_price, on)

    def _fill_buy(self, order: PendingOrder, exec_price: float, on: date) -> FillResult:
        # Solve shares so shares*price + commission(shares*price) <= budget.
        budget = self._cash * order.size
        rate = self._costs.commission_rate
        max_notional = budget / (1.0 + rate) if rate > 0 else budget
        shares = int(max_notional // exec_price)
        if shares <= 0:
            return FillResult(fill=None, rejected_reason="zero_shares")

        notional = shares * exec_price
        fee = self._costs.commission(notional)
        total = notional + fee
        if total > self._cash + 1e-9:
            return FillResult(fill=None, rejected_reason="zero_shares")

        pos = self._positions.get(order.symbol) or Position()
        new_qty = pos.qty + shares
        if new_qty > 0:
            pos.avg_cost = ((pos.qty * pos.avg_cost) + notional) / new_qty
        pos.qty = new_qty
        self._positions[order.symbol] = pos
        self._cash -= total
        self._total_fees += fee
        return FillResult(
            fill=Fill(
                action="buy",
                qty=shares,
                price=exec_price,
                date=on,
                reason=order.reason,
                symbol=order.symbol,
                fee=fee,
            )
        )

    def _fill_sell(self, order: PendingOrder, exec_price: float, on: date) -> FillResult:
        pos = self._positions.get(order.symbol) or Position()
        shares = int(pos.qty * order.size)
        if shares <= 0:
            return FillResult(fill=None, rejected_reason="zero_shares")
        shares = min(shares, pos.qty)
        notional = shares * exec_price
        fee = self._costs.commission(notional)
        proceeds = notional - fee
        if proceeds < 0:
            return FillResult(fill=None, rejected_reason="zero_shares")

        self._cash += proceeds
        pos.qty -= shares
        if pos.qty == 0:
            pos.avg_cost = 0.0
            self._positions.pop(order.symbol, None)
        else:
            self._positions[order.symbol] = pos
        self._total_fees += fee
        return FillResult(
            fill=Fill(
                action="sell",
                qty=shares,
                price=exec_price,
                date=on,
                reason=order.reason,
                symbol=order.symbol,
                fee=fee,
            )
        )

    def mark_to_market(self, prices: dict[str, float]) -> float:
        """Return equity at the given mark prices."""
        self._require_prices(prices)
        equity = self._cash
        for symbol, pos in self._positions.items():
            if pos.qty:
                equity += pos.qty * prices[symbol]
        return equity

    def discard_pending(self) -> PendingOrder | None:
        """Drop any unfilled pending order (e.g. last session). Return discarded order."""
        order = self._pending
        self._pending = None
        return order
