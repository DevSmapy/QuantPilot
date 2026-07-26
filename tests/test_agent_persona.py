"""Tests for TradingPersona prompts and hard guards."""

from __future__ import annotations

from datetime import date

import pytest

from quantpilot.agent.decision import TradeDecision
from quantpilot.agent.llm import LlmTradingAgent
from quantpilot.agent.persona import (
    apply_persona_guards,
    build_persona_prompt_section,
    get_persona,
)
from quantpilot.environment.observation import AgentObservation, SymbolView
from quantpilot.environment.types import PortfolioSnapshot


def _obs(*, cash: float = 1000.0, equity: float = 1000.0) -> AgentObservation:
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
                sma_60=99.0,
                rsi_14=55.0,
            )
        ],
        portfolio=PortfolioSnapshot(
            cash=cash,
            holdings={},
            mark_prices={"TEST.KS": 101.0},
            avg_costs={},
            equity=equity,
            unrealized_pnl=0.0,
        ),
        capital=1000.0,
        target=1200.0,
        remaining_sessions=10,
        session_index=0,
        session_count=20,
    )


def test_get_persona_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown persona"):
        get_persona("yolo")


def test_prompt_includes_persona_fields() -> None:
    persona = get_persona("conservative")
    block = build_persona_prompt_section(persona)
    assert "capital_preservation" in block
    assert "max_buy_size=0.2" in block or "max_buy_size=0.20" in block
    assert persona.example_decision_json in block


def test_conservative_buy_size_clamped() -> None:
    persona = get_persona("conservative")
    # cash==equity so floor allows up to 1-0.4=0.6; max_buy_size=0.20 binds
    decision = TradeDecision(action="buy", size=1.0, reason="all in")
    guarded = apply_persona_guards(decision, _obs(), persona)
    assert guarded.action == "buy"
    assert guarded.size == pytest.approx(0.20)


def test_conservative_cash_floor_hold() -> None:
    persona = get_persona("conservative")
    # Already below cash floor: cash/equity = 0.3 < 0.4
    decision = TradeDecision(action="buy", size=0.1, reason="small add")
    guarded = apply_persona_guards(decision, _obs(cash=300.0, equity=1000.0), persona)
    assert guarded.action == "hold"
    assert guarded.reason == "persona_cash_floor"


def test_aggressive_allows_full_buy() -> None:
    persona = get_persona("aggressive")
    decision = TradeDecision(action="buy", size=1.0, reason="deploy")
    guarded = apply_persona_guards(decision, _obs(), persona)
    assert guarded.action == "buy"
    assert guarded.size == pytest.approx(1.0)


def test_llm_agent_applies_persona_clamp() -> None:
    class FakeLLM:
        def generate(
            self,
            prompt: str,
            *,
            format_json: bool = False,
            options: dict | None = None,
        ) -> str:
            assert "capital_preservation" in prompt
            return '{"action":"buy","size":1.0,"reason":"momentum breakout buy"}'

    agent = LlmTradingAgent(
        FakeLLM(),
        persona=get_persona("conservative"),
        judge_sell_reason=False,
    )
    decision = agent.decide(_obs())
    assert decision.action == "buy"
    assert decision.size == pytest.approx(0.20)
