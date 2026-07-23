"""Environment DTOs: portfolio state, orders, fills."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal


@dataclass(frozen=True)
class PortfolioSnapshot:
    """Cash, holdings, and mark-to-market equity."""

    cash: float
    holdings: dict[str, int]
    mark_prices: dict[str, float]
    avg_costs: dict[str, float]
    equity: float
    unrealized_pnl: float

    @property
    def total_shares(self) -> int:
        """Sum of share counts across symbols (notional-blind; prefer holdings)."""
        return sum(self.holdings.values())

    @property
    def qty(self) -> int:
        """Alias for total_shares (kept for CLI/KPI compatibility)."""
        return self.total_shares

    @property
    def stock_value(self) -> float:
        missing = [s for s in self.holdings if s not in self.mark_prices]
        if missing:
            raise KeyError(f"Missing mark prices for holdings: {missing}")
        return sum(
            qty * self.mark_prices[symbol] for symbol, qty in self.holdings.items()
        )


@dataclass(frozen=True)
class PendingOrder:
    """Order queued for next-session open fill."""

    action: Literal["buy", "sell"]
    size: float
    reason: str
    decision_date: date
    symbol: str


@dataclass(frozen=True)
class Fill:
    """Executed order at open."""

    action: Literal["buy", "sell"]
    qty: int
    price: float
    date: date
    reason: str
    symbol: str
    fee: float = 0.0


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


@dataclass
class Position:
    """Open long position for one symbol."""

    qty: int = 0
    avg_cost: float = 0.0
