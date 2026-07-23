"""Single-run simulation session wiring environment and agent."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import cast

from quantpilot.agent.base import TradingAgent
from quantpilot.agent.decision import TradeDecision, normalize_decision
from quantpilot.environment.broker import PaperBroker
from quantpilot.environment.clock import SimulationClock
from quantpilot.environment.costs import TradingCosts
from quantpilot.environment.market import HistoricalMarket, intersect_session_dates
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

    ``equity`` is end-of-day mark-to-market at closes. When a fill occurs,
    ``equity_after_fill`` is mark-to-market at that session's opens (post-fill).
    ``qty`` is total share count across symbols (prefer ``holdings``).
    """

    date: date
    cash: float
    equity: float
    qty: int
    decision: TradeDecision | None = None
    fill: Fill | None = None
    fill_rejected: str | None = None
    discarded_pending: bool = False
    holdings: dict[str, int] = field(default_factory=dict)
    avg_costs: dict[str, float] = field(default_factory=dict)
    equity_after_fill: float | None = None


ProgressCallback = Callable[[ProgressEvent], None]


class SimulationSession:
    """Run fill → MTM → (optional) decide → queue over trading days."""

    def __init__(
        self,
        *,
        markets: dict[str, HistoricalMarket] | HistoricalMarket,
        agent: TradingAgent,
        symbols: list[str] | str,
        capital: float,
        target: float,
        decision_every: int = 5,
        costs: TradingCosts | None = None,
        observation_builder: ObservationBuilder | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> None:
        if decision_every < 1:
            raise ValueError("decision_every must be >= 1")

        if isinstance(markets, HistoricalMarket):
            symbol = symbols if isinstance(symbols, str) else symbols[0]
            self._markets = {symbol: markets}
            self._symbols = [symbol]
        else:
            if isinstance(symbols, str):
                ordered = [symbols]
            else:
                ordered = list(symbols)
            if not ordered:
                raise ValueError("symbols must not be empty")
            missing = [s for s in ordered if s not in markets]
            if missing:
                raise KeyError(f"Missing markets for symbols: {missing}")
            self._markets = {s: markets[s] for s in ordered}
            self._symbols = ordered

        self._agent = agent
        self._capital = capital
        self._target = target
        self._decision_every = decision_every
        self._costs = costs or TradingCosts()
        self._builder = observation_builder or ObservationBuilder()
        self._on_progress = on_progress

    @property
    def symbols(self) -> list[str]:
        return list(self._symbols)

    def run(self, start: date, end: date) -> SimResult:
        dates = intersect_session_dates(self._markets, start, end)
        if not dates:
            raise ValueError(f"No trading sessions between {start} and {end}")

        clock = SimulationClock(dates)
        broker = PaperBroker(self._capital, costs=self._costs)
        equity_curve: list[EquityPoint] = []
        decisions: list[DecisionRecord] = []
        fills: list[Fill] = []
        fill_rejects: list[FillReject] = []
        default_symbol = self._symbols[0]

        while True:
            as_of = clock.as_of
            opens = {
                symbol: float(cast(float, self._markets[symbol].bar(as_of)["open"]))
                for symbol in self._symbols
            }
            closes = {
                symbol: float(cast(float, self._markets[symbol].bar(as_of)["close"]))
                for symbol in self._symbols
            }

            fill: Fill | None = None
            fill_rejected: str | None = None
            equity_after_fill: float | None = None
            pending = broker.pending
            if pending is not None:
                open_price = opens[pending.symbol]
                fill_result = broker.fill_pending(open_price, as_of)
                fill = fill_result.fill
                if fill is not None:
                    fills.append(fill)
                    equity_after_fill = broker.mark_to_market(opens)
                elif fill_result.rejected_reason is not None:
                    fill_rejected = fill_result.rejected_reason
                    fill_rejects.append(
                        FillReject(date=as_of, reason=fill_result.rejected_reason)
                    )

            equity = broker.mark_to_market(closes)
            snap = broker.snapshot(closes)
            equity_curve.append(
                EquityPoint(
                    date=as_of,
                    equity=equity,
                    cash=snap.cash,
                    qty=snap.total_shares,
                    holdings=dict(snap.holdings),
                    equity_after_fill=equity_after_fill,
                )
            )

            applied: TradeDecision | None = None
            if clock.is_decision_day(self._decision_every):
                visibles = {
                    symbol: self._markets[symbol].visible(as_of)
                    for symbol in self._symbols
                }
                obs = self._builder.build(
                    symbols=self._symbols,
                    visibles=visibles,
                    as_of=as_of,
                    portfolio=snap,
                    capital=self._capital,
                    target=self._target,
                    remaining_sessions=clock.remaining_sessions,
                    session_index=clock.session_index,
                    session_count=clock.session_count,
                )
                requested = self._agent.decide(obs)
                applied = normalize_decision(
                    requested,
                    universe=self._symbols,
                    default_symbol=default_symbol,
                )
                queue_symbol = applied.symbol or default_symbol
                queue_result = broker.queue(
                    applied.action,
                    applied.size,
                    applied.reason,
                    as_of,
                    symbol=queue_symbol,
                )
                detail = queue_result.message
                queued = queue_result.accepted and applied.action != "hold"
                if not queue_result.accepted and applied.action != "hold":
                    applied = TradeDecision.hold(reason=queue_result.message)
                    broker.queue("hold", 0.0, applied.reason, as_of, symbol=default_symbol)
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
                        qty=snap.total_shares,
                        decision=applied,
                        fill=fill,
                        fill_rejected=fill_rejected,
                        holdings=dict(snap.holdings),
                        avg_costs=dict(snap.avg_costs),
                        equity_after_fill=equity_after_fill,
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
                    holdings=dict(broker.holdings()),
                    avg_costs={
                        symbol: broker.avg_cost(symbol)
                        for symbol in broker.holdings()
                    },
                )
            )

        final_equity = equity_curve[-1].equity
        bah = buy_and_hold_final_equity(
            self._markets,
            start=start,
            end=end,
            capital=self._capital,
            symbols=self._symbols,
            costs=self._costs,
        )

        return SimResult(
            symbol=self._symbols[0],
            symbols=list(self._symbols),
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
            total_fees=broker.total_fees,
        )
