"""Simulation result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from quantpilot.agent.decision import TradeDecision
from quantpilot.environment.types import Fill, PendingOrder


@dataclass(frozen=True)
class EquityPoint:
    """One session equity snapshot.

    ``qty`` is total share count across symbols (notional-blind). Prefer
    ``holdings`` for multi-symbol clarity. ``equity_after_fill`` is open MTM
    right after a fill on that day, when present.
    """

    date: date
    equity: float
    cash: float
    qty: int
    holdings: dict[str, int] = field(default_factory=dict)
    equity_after_fill: float | None = None


@dataclass(frozen=True)
class DecisionRecord:
    """One agent decision and whether it was accepted into the broker queue."""

    date: date
    requested: TradeDecision
    applied: TradeDecision
    queued: bool
    detail: str


@dataclass(frozen=True)
class FillReject:
    date: date
    reason: str


@dataclass
class SimResult:
    """Outcome of one SimulationSession.run()."""

    symbol: str
    start: date
    end: date
    capital: float
    target: float
    final_equity: float
    hit_target: bool
    equity_curve: list[EquityPoint] = field(default_factory=list)
    decisions: list[DecisionRecord] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    fill_rejects: list[FillReject] = field(default_factory=list)
    discarded_pending: PendingOrder | None = None
    buy_and_hold_equity: float | None = None
    symbols: list[str] = field(default_factory=list)
    total_fees: float = 0.0

    def __post_init__(self) -> None:
        if not self.symbols:
            self.symbols = [self.symbol]

    @property
    def total_return(self) -> float:
        if self.capital == 0:
            return 0.0
        return (self.final_equity / self.capital) - 1.0
