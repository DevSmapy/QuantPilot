"""Single-run simulation session wiring environment and agent."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from quantpilot.agent.base import TradingAgent
from quantpilot.agent.decision import TradeDecision, normalize_decision
from quantpilot.environment.broker import PaperBroker
from quantpilot.environment.clock import SimulationClock
from quantpilot.environment.market import HistoricalMarket
from quantpilot.environment.observation import ObservationBuilder
from quantpilot.environment.types import Fill
from quantpilot.simulation.benchmark import buy_and_hold_final_equity
from quantpilot.simulation.result import (
    DecisionRecord,
    EquityPoint,
    FillReject,
    SimResult,
)


@dataclass(frozen=True)
class ProgressEvent:
    """Daily progress for CLI / logging.

    Timing: orders decided at end-of-day (with that day's close) fill at the
    next session's open — not same-bar look-ahead into future dates.
    """

    date: date
    cash: float
    equity: float
    qty: int
    decision: TradeDecision | None = None
    fill: Fill | None = None
    fill_rejected: str | None = None
    discarded_pending: bool = False


ProgressCallback = Callable[[ProgressEvent], None]


class SimulationSession:
    """Run fill → MTM → (optional) decide → queue over trading days."""

    def __init__(
        self,
        *,
        market: HistoricalMarket,
        agent: TradingAgent,
        symbol: str,
        capital: float,
        target: float,
        decision_every: int = 5,
        observation_builder: ObservationBuilder | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> None:
        if decision_every < 1:
            raise ValueError("decision_every must be >= 1")
        self._market = market
        self._agent = agent
        self._symbol = symbol
        self._capital = capital
        self._target = target
        self._decision_every = decision_every
        self._builder = observation_builder or ObservationBuilder()
        self._on_progress = on_progress

    def run(self, start: date, end: date) -> SimResult:
        dates = self._market.session_dates(start, end)
        if not dates:
            raise ValueError(f"No trading sessions between {start} and {end}")

        clock = SimulationClock(dates)
        broker = PaperBroker(self._capital)
        equity_curve: list[EquityPoint] = []
        decisions: list[DecisionRecord] = []
        fills: list[Fill] = []
        fill_rejects: list[FillReject] = []

        while True:
            as_of = clock.as_of
            bar = self._market.bar(as_of)
            open_price = float(bar["open"])
            close_price = float(bar["close"])

            # 1) Fill prior-day pending at today's open (never same-day as decision).
            fill_result = broker.fill_pending(open_price, as_of)
            fill = fill_result.fill
            if fill is not None:
                fills.append(fill)
            elif fill_result.rejected_reason is not None:
                fill_rejects.append(
                    FillReject(date=as_of, reason=fill_result.rejected_reason)
                )

            # 2) Mark to market at close.
            equity = broker.mark_to_market(close_price)
            snap = broker.snapshot(close_price)
            equity_curve.append(
                EquityPoint(
                    date=as_of,
                    equity=equity,
                    cash=snap.cash,
                    qty=snap.qty,
                )
            )

            # 3) End-of-day decision (may include last day; that pending is discarded).
            decision_record: DecisionRecord | None = None
            applied: TradeDecision | None = None
            if clock.is_decision_day(self._decision_every):
                visible = self._market.visible(as_of)
                obs = self._builder.build(
                    symbol=self._symbol,
                    visible=visible,
                    as_of=as_of,
                    portfolio=snap,
                    capital=self._capital,
                    target=self._target,
                    remaining_sessions=clock.remaining_sessions,
                    session_index=clock.session_index,
                    session_count=clock.session_count,
                )
                requested = self._agent.decide(obs)
                applied = normalize_decision(requested)
                queue_result = broker.queue(
                    applied.action,
                    applied.size,
                    applied.reason,
                    as_of,
                )
                detail = queue_result.message
                queued = queue_result.accepted and applied.action != "hold"
                if not queue_result.accepted and applied.action != "hold":
                    applied = TradeDecision.hold(reason=queue_result.message)
                    broker.queue("hold", 0.0, applied.reason, as_of)
                    queued = False
                    detail = queue_result.message

                decisions.append(
                    DecisionRecord(
                        date=as_of,
                        requested=requested,
                        applied=applied,
                        queued=queued,
                        detail=detail,
                    )
                )

            if self._on_progress is not None:
                self._on_progress(
                    ProgressEvent(
                        date=as_of,
                        cash=snap.cash,
                        equity=equity,
                        qty=snap.qty,
                        decision=applied,
                        fill=fill,
                        fill_rejected=fill_result.rejected_reason,
                    )
                )

            if not clock.advance():
                break

        discarded = broker.discard_pending()
        if discarded is not None and self._on_progress is not None:
            last = equity_curve[-1]
            self._on_progress(
                ProgressEvent(
                    date=last.date,
                    cash=last.cash,
                    equity=last.equity,
                    qty=last.qty,
                    discarded_pending=True,
                )
            )

        final_equity = equity_curve[-1].equity
        bah = buy_and_hold_final_equity(
            self._market,
            start=start,
            end=end,
            capital=self._capital,
        )

        return SimResult(
            symbol=self._symbol,
            start=dates[0],
            end=dates[-1],
            capital=self._capital,
            target=self._target,
            final_equity=final_equity,
            hit_target=final_equity >= self._target,
            equity_curve=equity_curve,
            decisions=decisions,
            fills=fills,
            fill_rejects=fill_rejects,
            discarded_pending=discarded,
            buy_and_hold_equity=bah,
        )
