"""Regression tests for code-review follow-ups."""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from quantpilot.agent.decision import parse_trade_decision
from quantpilot.agent.hold import HoldAgent
from quantpilot.agent.llm import LlmTradingAgent
from quantpilot.environment.broker import PaperBroker
from quantpilot.environment.costs import TradingCosts
from quantpilot.environment.market import HistoricalMarket, intersect_session_dates
from quantpilot.environment.observation import AgentObservation
from quantpilot.environment.types import PortfolioSnapshot
from quantpilot.simulation.benchmark import buy_and_hold_final_equity
from quantpilot.simulation.session import ProgressEvent, SimulationSession


def _prices(
    *,
    start: date,
    days: int,
    open_: float = 100.0,
    close: float = 100.0,
) -> pl.DataFrame:
    rows = []
    for i in range(days):
        d = date.fromordinal(start.toordinal() + i)
        rows.append(
            {
                "date": d,
                "open": open_,
                "high": max(open_, close) + 1.0,
                "low": min(open_, close) - 1.0,
                "close": close,
                "volume": 1_000,
            }
        )
    return pl.DataFrame(rows)


def test_trading_costs_reject_commission_rate_ge_one() -> None:
    with pytest.raises(ValueError, match="commission_rate must be < 1"):
        TradingCosts(commission_rate=1.0)
    with pytest.raises(ValueError, match="commission_rate must be < 1"):
        TradingCosts(commission_rate=1.5)


def test_broker_missing_mark_price_raises() -> None:
    broker = PaperBroker(10_000.0)
    broker.queue("buy", 1.0, "enter", date(2024, 1, 1), symbol="A.KS")
    broker.fill_pending(100.0, date(2024, 1, 2))
    with pytest.raises(KeyError, match="Missing mark prices"):
        broker.mark_to_market({})
    with pytest.raises(KeyError, match="Missing mark prices"):
        broker.snapshot({"B.KS": 50.0})


def test_buy_and_hold_applies_same_costs() -> None:
    market = HistoricalMarket(_prices(start=date(2023, 1, 1), days=5, open_=100.0, close=110.0))
    costs = TradingCosts(commission_rate=0.01, slippage_bps=100.0)
    equity = buy_and_hold_final_equity(
        market,
        start=date(2023, 1, 1),
        end=date(2023, 1, 5),
        capital=10_100.0,
        costs=costs,
    )
    # exec open = 101, fee 1%, max_notional = 10100/1.01 = 10000 → 99 shares @ 101
    qty = 99
    leftover = 10_100.0 - qty * 101.0 - qty * 101.0 * 0.01
    expected = leftover + qty * 110.0
    assert equity == pytest.approx(expected)


def test_parse_trade_decision_respects_universe() -> None:
    assert (
        parse_trade_decision(
            '{"action":"buy","size":0.5,"reason":"x"}',
            universe=["A.KS", "B.KS"],
        )
        is None
    )
    assert (
        parse_trade_decision(
            '{"action":"buy","size":0.5,"reason":"x","symbol":"Z.KS"}',
            universe=["A.KS", "B.KS"],
        )
        is None
    )
    ok = parse_trade_decision(
        '{"action":"buy","size":0.5,"reason":"x","symbol":"A.KS"}',
        universe=["A.KS", "B.KS"],
    )
    assert ok is not None
    assert ok.symbol == "A.KS"


def test_llm_invalid_symbol_retries_as_invalid() -> None:
    class FakeLLM:
        def __init__(self) -> None:
            self.calls = 0

        def generate(
            self,
            prompt: str,
            *,
            format_json: bool = False,
            options: dict | None = None,
        ) -> str:
            self.calls += 1
            return '{"action":"buy","size":0.5,"reason":"x","symbol":"BAD.KS"}'

    llm = FakeLLM()
    agent = LlmTradingAgent(llm, max_retries=0)
    obs = AgentObservation(
        symbols=["A.KS", "B.KS"],
        as_of=date(2024, 1, 2),
        legs=[],
        portfolio=PortfolioSnapshot(
            cash=1_000.0,
            holdings={},
            mark_prices={"A.KS": 10.0, "B.KS": 10.0},
            avg_costs={},
            equity=1_000.0,
            unrealized_pnl=0.0,
        ),
        capital=1_000.0,
        target=1_200.0,
        remaining_sessions=10,
        session_index=0,
        session_count=10,
    )
    decision = agent.decide(obs)
    assert decision.action == "hold"
    assert decision.reason == "invalid_llm_decision"
    assert llm.calls == 1


def test_intersect_session_dates_uses_calendar_intersection() -> None:
    a = HistoricalMarket(
        pl.DataFrame(
            {
                "date": [date(2023, 1, 2), date(2023, 1, 3), date(2023, 1, 4)],
                "open": [1.0, 1.0, 1.0],
                "high": [1.0, 1.0, 1.0],
                "low": [1.0, 1.0, 1.0],
                "close": [1.0, 1.0, 1.0],
                "volume": [1, 1, 1],
            }
        )
    )
    b = HistoricalMarket(
        pl.DataFrame(
            {
                "date": [date(2023, 1, 3), date(2023, 1, 4), date(2023, 1, 5)],
                "open": [1.0, 1.0, 1.0],
                "high": [1.0, 1.0, 1.0],
                "low": [1.0, 1.0, 1.0],
                "close": [1.0, 1.0, 1.0],
                "volume": [1, 1, 1],
            }
        )
    )
    dates = intersect_session_dates(
        {"A.KS": a, "B.KS": b},
        date(2023, 1, 1),
        date(2023, 1, 10),
    )
    assert dates == [date(2023, 1, 3), date(2023, 1, 4)]


def test_progress_event_equity_after_fill_and_holdings() -> None:
    market = HistoricalMarket(
        _prices(start=date(2023, 1, 1), days=8, open_=100.0, close=105.0)
    )
    events: list[ProgressEvent] = []

    class BuyOnce(HoldAgent):
        def __init__(self) -> None:
            self._done = False

        def decide(self, observation):  # type: ignore[no-untyped-def]
            from quantpilot.agent.decision import TradeDecision

            if self._done:
                return TradeDecision.hold()
            self._done = True
            return TradeDecision(action="buy", size=1.0, reason="enter", symbol="A.KS")

    result = SimulationSession(
        markets={"A.KS": market},
        agent=BuyOnce(),
        symbols=["A.KS"],
        capital=10_000.0,
        target=12_000.0,
        decision_every=1,
        on_progress=events.append,
    ).run(date(2023, 1, 1), date(2023, 1, 8))

    filled = [e for e in events if e.fill is not None]
    assert filled
    first = filled[0]
    assert first.equity_after_fill is not None
    # Open MTM after all-in buy ≈ fill notional leftover + shares * open
    assert first.equity_after_fill == pytest.approx(10_000.0)
    assert first.holdings.get("A.KS", 0) > 0
    assert first.qty == first.holdings["A.KS"]

    point = next(p for p in result.equity_curve if p.equity_after_fill is not None)
    assert point.holdings == first.holdings
    assert point.equity_after_fill == first.equity_after_fill


def test_session_bah_matches_costs() -> None:
    market = HistoricalMarket(
        _prices(start=date(2023, 1, 1), days=5, open_=100.0, close=110.0)
    )
    costs = TradingCosts(commission_rate=0.0, slippage_bps=100.0)
    result = SimulationSession(
        markets=market,
        agent=HoldAgent(),
        symbols="A.KS",
        capital=10_100.0,
        target=12_000.0,
        decision_every=5,
        costs=costs,
    ).run(date(2023, 1, 1), date(2023, 1, 5))
    expected = buy_and_hold_final_equity(
        market,
        start=date(2023, 1, 1),
        end=date(2023, 1, 5),
        capital=10_100.0,
        costs=costs,
    )
    assert result.buy_and_hold_equity == pytest.approx(expected)


def test_streamlit_helpers_format_and_csv() -> None:
    pytest.importorskip("streamlit")
    pytest.importorskip("plotly")
    import importlib.util
    import sys
    from pathlib import Path

    from quantpilot.environment.types import Fill
    from quantpilot.simulation.result import EquityPoint, SimResult

    path = Path(__file__).resolve().parents[1] / "scripts" / "streamlit_agent_sim.py"
    spec = importlib.util.spec_from_file_location("streamlit_agent_sim", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    assert mod._format_holdings({"B.KS": 2, "A.KS": 1}) == "A.KS:1;B.KS:2"
    result = SimResult(
        symbol="A.KS",
        start=date(2024, 1, 2),
        end=date(2024, 1, 3),
        capital=10_000.0,
        target=12_000.0,
        final_equity=10_500.0,
        hit_target=False,
        equity_curve=[
            EquityPoint(
                date=date(2024, 1, 2),
                equity=10_000.0,
                cash=0.0,
                qty=100,
                holdings={"A.KS": 100},
                equity_after_fill=9_900.0,
            ),
            EquityPoint(
                date=date(2024, 1, 3),
                equity=10_500.0,
                cash=0.0,
                qty=100,
                holdings={"A.KS": 100},
            ),
        ],
        fills=[
            Fill(
                date=date(2024, 1, 2),
                action="buy",
                qty=100,
                price=99.0,
                fee=0.0,
                reason="enter",
                symbol="A.KS",
            )
        ],
    )
    csv_text = mod._equity_csv(result)
    assert "total_shares" in csv_text
    assert "A.KS:100" in csv_text
    buys, sells = mod._markers_from_result(
        result, closes_by_date={date(2024, 1, 2): 100.0}
    )
    assert buys[0].equity == 9_900.0
    assert not sells
