"""Environment DTOs: portfolio state, orders, fills."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal


@dataclass(frozen=True)
class PortfolioSnapshot:
    """Cash, position, and mark-to-market equity at a price."""

    cash: float
    qty: int
    avg_cost: float
    last_price: float
    equity: float
    unrealized_pnl: float

    @property
    def stock_value(self) -> float:
        return self.qty * self.last_price


@dataclass(frozen=True)
class PendingOrder:
    """Order queued for next-session open fill."""

    action: Literal["buy", "sell"]
    size: float
    reason: str
    decision_date: date


@dataclass(frozen=True)
class Fill:
    """Executed order at open."""

    action: Literal["buy", "sell"]
    qty: int
    price: float
    date: date
    reason: str


@dataclass(frozen=True)
class QueueResult:
    """Outcome of PaperBroker.queue."""

    accepted: bool
    message: str


@dataclass(frozen=True)
class FillResult:
    """Outcome of PaperBroker.fill_pending."""

    fill: Fill | None
    rejected_reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.fill is not None
