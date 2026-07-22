"""Paper broker with next-open fill and close mark-to-market."""

from __future__ import annotations

from datetime import date
from typing import Literal

from quantpilot.environment.types import (
    Fill,
    FillResult,
    PendingOrder,
    PortfolioSnapshot,
    QueueResult,
)


class PaperBroker:
    """Long-only cash account with integer share lots and zero fees."""

    def __init__(self, cash: float) -> None:
        if cash < 0:
            raise ValueError("cash must be >= 0")
        self._cash = float(cash)
        self._qty = 0
        self._avg_cost = 0.0
        self._pending: PendingOrder | None = None
        self._last_price = 0.0

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def qty(self) -> int:
        return self._qty

    @property
    def avg_cost(self) -> float:
        return self._avg_cost

    @property
    def pending(self) -> PendingOrder | None:
        return self._pending

    def snapshot(self, price: float) -> PortfolioSnapshot:
        equity = self._cash + self._qty * price
        unrealized = (price - self._avg_cost) * self._qty if self._qty else 0.0
        return PortfolioSnapshot(
            cash=self._cash,
            qty=self._qty,
            avg_cost=self._avg_cost,
            last_price=price,
            equity=equity,
            unrealized_pnl=unrealized,
        )

    def queue(
        self,
        action: Literal["buy", "sell", "hold"],
        size: float,
        reason: str,
        decision_date: date,
    ) -> QueueResult:
        """Register a pending order. Rejects invalid sell/size; hold clears pending."""
        if action == "hold":
            self._pending = None
            return QueueResult(accepted=True, message="hold")

        if action == "sell":
            if not str(reason).strip():
                self._pending = None
                return QueueResult(accepted=False, message="sell_requires_reason")
            if self._qty <= 0:
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
        )
        return QueueResult(accepted=True, message="queued")

    def fill_pending(self, open_price: float, on: date) -> FillResult:
        """Execute pending order at today's open."""
        order = self._pending
        self._pending = None
        if order is None:
            return FillResult(fill=None)

        if open_price <= 0:
            return FillResult(fill=None, rejected_reason="bad_price")

        if order.action == "buy":
            budget = self._cash * order.size
            shares = int(budget // open_price)
            if shares <= 0:
                return FillResult(fill=None, rejected_reason="zero_shares")
            cost = shares * open_price
            new_qty = self._qty + shares
            if new_qty > 0:
                self._avg_cost = ((self._qty * self._avg_cost) + cost) / new_qty
            self._cash -= cost
            self._qty = new_qty
            return FillResult(
                fill=Fill(
                    action="buy",
                    qty=shares,
                    price=open_price,
                    date=on,
                    reason=order.reason,
                )
            )

        shares = int(self._qty * order.size)
        if shares <= 0:
            return FillResult(fill=None, rejected_reason="zero_shares")
        shares = min(shares, self._qty)
        proceeds = shares * open_price
        self._cash += proceeds
        self._qty -= shares
        if self._qty == 0:
            self._avg_cost = 0.0
        return FillResult(
            fill=Fill(
                action="sell",
                qty=shares,
                price=open_price,
                date=on,
                reason=order.reason,
            )
        )

    def mark_to_market(self, close_price: float) -> float:
        """Update last price and return equity at close."""
        self._last_price = close_price
        return self._cash + self._qty * close_price

    def discard_pending(self) -> PendingOrder | None:
        """Drop any unfilled pending order (e.g. last session). Return discarded order."""
        order = self._pending
        self._pending = None
        return order
