"""Tests for SimulationSession and LLM agent fallbacks."""

from __future__ import annotations

from datetime import date
from typing import Any

import polars as pl

from quantpilot.agent.base import TradingAgent
from quantpilot.agent.decision import TradeDecision
from quantpilot.agent.hold import HoldAgent
from quantpilot.agent.llm import LlmTradingAgent
from quantpilot.environment.market import HistoricalMarket
from quantpilot.environment.observation import AgentObservation, SymbolView
from quantpilot.environment.types import PortfolioSnapshot
from quantpilot.simulation.benchmark import buy_and_hold_final_equity
from quantpilot.simulation.session import SimulationSession


def _obs(
    *,
    cash: float,
    holdings: dict[str, int] | None = None,
    equity: float | None = None,
) -> AgentObservation:
    holdings = holdings or {}
    mark = {symbol: 101.0 for symbol in holdings} or {"TEST.KS": 101.0}
    avg = {symbol: 100.0 for symbol in holdings}
    stock = sum(holdings.get(s, 0) * mark[s] for s in mark)
    return AgentObservation(
        as_of=date(2024, 1, 2),
        symbols=["TEST.KS"],
        legs=[
            SymbolView(
                symbol="TEST.KS",
                recent_bars=[
                    {
                        "date": "2024-01-02",
                        "open": 100.0,
                        "close": 101.0,
                        "volume": 1.0,
                    }
                ],
                sma_20=100.0,
                sma_60=None,
                rsi_14=50.0,
            )
        ],
        portfolio=PortfolioSnapshot(
            cash=cash,
            holdings=holdings,
            mark_prices=mark,
            avg_costs=avg,
            equity=cash + stock if equity is None else equity,
            unrealized_pnl=10.0 if holdings else 0.0,
        ),
        capital=1000.0,
        target=1200.0,
        remaining_sessions=5,
        session_index=0,
        session_count=6,
    )


class ScriptedAgent(TradingAgent):
    """Return a fixed sequence of decisions (repeats last)."""

    def __init__(self, decisions: list[TradeDecision]) -> None:
        self._decisions = decisions
        self._idx = 0
        self.calls = 0

    def decide(self, observation: AgentObservation) -> TradeDecision:
        self.calls += 1
        decision = self._decisions[min(self._idx, len(self._decisions) - 1)]
        self._idx += 1
        return decision


class FakeLLM:
    def __init__(self, responses: list[str], *, fail: bool = False) -> None:
        self._responses = responses
        self.calls = 0
        self.fail = fail
        self.last_options: dict[str, Any] | None = None

    def generate(
        self,
        prompt: str,
        *,
        format_json: bool = False,
        options: dict[str, Any] | None = None,
    ) -> str:
        self.last_options = options
        if self.fail:
            raise ConnectionError("boom")
        raw = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return raw


def test_hold_agent_session_preserves_cash(sample_prices: pl.DataFrame) -> None:
    market = HistoricalMarket(sample_prices)
    start, end = date(2023, 1, 10), date(2023, 2, 10)
    session = SimulationSession(
        markets=market,
        agent=HoldAgent(),
        symbols="TEST.KS",
        capital=1_000_000.0,
        target=1_100_000.0,
        decision_every=5,
    )
    result = session.run(start, end)
    assert result.final_equity == 1_000_000.0
    assert result.buy_and_hold_equity is not None
    assert len(result.equity_curve) == len(market.session_dates(start, end))
    assert result.fills == []


def test_scripted_buy_sell_cashizes_and_records_fills(
    sample_prices: pl.DataFrame,
) -> None:
    market = HistoricalMarket(sample_prices)
    start, end = date(2023, 1, 1), date(2023, 1, 10)
    agent = ScriptedAgent(
        [
            TradeDecision(action="buy", size=1.0, reason="enter"),
            TradeDecision(action="sell", size=1.0, reason="exit"),
            TradeDecision.hold(),
        ]
    )
    session = SimulationSession(
        markets=market,
        agent=agent,
        symbols="TEST.KS",
        capital=10_000.0,
        target=12_000.0,
        decision_every=1,
    )
    result = session.run(start, end)

    assert any(f.action == "buy" for f in result.fills)
    assert any(f.action == "sell" for f in result.fills)
    assert result.equity_curve[-1].qty == 0
    assert result.final_equity == result.equity_curve[-1].cash
    assert result.final_equity > 0
    assert all(
        d.applied.action != "sell" or d.applied.reason for d in result.decisions
    )


def test_last_day_decision_pending_is_discarded(
    sample_prices: pl.DataFrame,
) -> None:
    market = HistoricalMarket(sample_prices)
    start, end = date(2023, 1, 1), date(2023, 1, 3)
    agent = ScriptedAgent(
        [TradeDecision(action="buy", size=1.0, reason="enter")]
    )
    session = SimulationSession(
        markets=market,
        agent=agent,
        symbols="TEST.KS",
        capital=10_000.0,
        target=12_000.0,
        decision_every=1,
    )
    result = session.run(start, end)
    # Decisions on days before last fill next morning; last-day decision is discarded.
    assert result.discarded_pending is not None
    assert result.discarded_pending.action == "buy"
    assert result.discarded_pending.decision_date == end
    assert any(f.action == "buy" for f in result.fills)


def test_decision_every_controls_call_count(
    sample_prices: pl.DataFrame,
) -> None:
    market = HistoricalMarket(sample_prices)
    start, end = date(2023, 1, 1), date(2023, 1, 20)
    sessions = len(market.session_dates(start, end))

    daily = ScriptedAgent([TradeDecision.hold()])
    SimulationSession(
        markets=market,
        agent=daily,
        symbols="TEST.KS",
        capital=10_000.0,
        target=12_000.0,
        decision_every=1,
    ).run(start, end)
    assert daily.calls == sessions

    weekly = ScriptedAgent([TradeDecision.hold()])
    SimulationSession(
        markets=market,
        agent=weekly,
        symbols="TEST.KS",
        capital=10_000.0,
        target=12_000.0,
        decision_every=5,
    ).run(start, end)
    expected = sum(1 for i in range(sessions) if i % 5 == 0)
    assert weekly.calls == expected


def test_invalid_queue_demotes_decision_record(
    sample_prices: pl.DataFrame,
) -> None:
    market = HistoricalMarket(sample_prices)
    start, end = date(2023, 1, 1), date(2023, 1, 5)
    agent = ScriptedAgent(
        [TradeDecision(action="sell", size=1.0, reason="no shares yet")]
    )
    result = SimulationSession(
        markets=market,
        agent=agent,
        symbols="TEST.KS",
        capital=10_000.0,
        target=12_000.0,
        decision_every=1,
    ).run(start, end)
    first = result.decisions[0]
    assert first.requested.action == "sell"
    assert first.applied.action == "hold"
    assert first.queued is False
    assert first.detail == "sell_zero_qty"
    assert result.fills == []


def test_observation_never_sees_future(sample_prices: pl.DataFrame) -> None:
    market = HistoricalMarket(sample_prices)
    seen_max: list[date] = []

    class CaptureAgent(TradingAgent):
        def decide(self, observation: AgentObservation) -> TradeDecision:
            seen_max.append(
                max(date.fromisoformat(str(b["date"])) for b in observation.recent_bars)
            )
            assert observation.as_of >= seen_max[-1]
            return TradeDecision.hold()

    start, end = date(2023, 2, 1), date(2023, 2, 28)
    SimulationSession(
        markets=market,
        agent=CaptureAgent(),
        symbols="TEST.KS",
        capital=10_000.0,
        target=12_000.0,
        decision_every=5,
    ).run(start, end)
    assert seen_max
    assert max(seen_max) <= end


def test_llm_agent_sell_without_reason_falls_back_to_hold() -> None:
    llm = FakeLLM(['{"action":"sell","size":1.0,"reason":""}'])
    agent = LlmTradingAgent(llm, max_retries=0)
    decision = agent.decide(_obs(cash=0.0, holdings={"TEST.KS": 10}, equity=1010.0))
    assert decision.action == "hold"
    assert llm.calls == 1


def test_llm_agent_connection_error_holds() -> None:
    llm = FakeLLM([], fail=True)
    agent = LlmTradingAgent(llm, max_retries=0)
    decision = agent.decide(_obs(cash=1000.0))
    assert decision.action == "hold"
    assert decision.reason == "llm_unavailable"


def test_llm_agent_retries_then_succeeds() -> None:
    llm = FakeLLM(
        [
            "not json",
            '{"action":"buy","size":0.25,"reason":"dip"}',
        ]
    )
    agent = LlmTradingAgent(llm, max_retries=1, options={"seed": 7, "temperature": 0.2})
    decision = agent.decide(_obs(cash=1000.0))
    assert decision.action == "buy"
    assert decision.size == 0.25
    assert llm.calls == 2
    assert llm.last_options == {"seed": 7, "temperature": 0.2}


def test_buy_and_hold_benchmark(sample_prices: pl.DataFrame) -> None:
    market = HistoricalMarket(sample_prices)
    start, end = date(2023, 1, 1), date(2023, 1, 30)
    equity = buy_and_hold_final_equity(
        market, start=start, end=end, capital=10_000.0
    )
    first_open = float(market.bar(market.session_dates(start, end)[0])["open"])
    last_close = float(market.bar(market.session_dates(start, end)[-1])["close"])
    qty = int(10_000.0 // first_open)
    expected = (10_000.0 - qty * first_open) + qty * last_close
    assert equity == expected


def test_multi_symbol_session_intersection_and_symbol_required(
    sample_prices: pl.DataFrame,
) -> None:
    other = sample_prices.with_columns((pl.col("close") * 0.5).alias("close"))
    markets = {
        "A.KS": HistoricalMarket(sample_prices),
        "B.KS": HistoricalMarket(other),
    }
    start, end = date(2023, 1, 1), date(2023, 1, 10)
    agent = ScriptedAgent(
        [
            TradeDecision(action="buy", size=1.0, reason="enter", symbol="B.KS"),
            TradeDecision(action="sell", size=1.0, reason="exit"),  # missing symbol
            TradeDecision.hold(),
        ]
    )
    result = SimulationSession(
        markets=markets,
        agent=agent,
        symbols=["A.KS", "B.KS"],
        capital=10_000.0,
        target=12_000.0,
        decision_every=1,
    ).run(start, end)
    assert any(f.symbol == "B.KS" and f.action == "buy" for f in result.fills)
    demoted = [d for d in result.decisions if d.requested.action == "sell"]
    assert demoted
    assert demoted[0].applied.action == "hold"
    assert demoted[0].applied.reason == "symbol_required"
