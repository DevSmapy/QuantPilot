"""Tests for sell-reason heuristic and grounding gate."""

from __future__ import annotations

from datetime import date

import pytest

from quantpilot.agent.decision import TradeDecision
from quantpilot.agent.llm import LlmTradingAgent
from quantpilot.agent.persona import get_persona
from quantpilot.agent.sell_judge import (
    assess_sell_reason_heuristic,
    gate_sell_decision,
)
from quantpilot.environment.observation import AgentObservation, SymbolView
from quantpilot.environment.types import PortfolioSnapshot


def _obs_with_shares() -> AgentObservation:
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
                        "close": 90.0,
                        "volume": 1.0,
                    }
                ],
                sma_20=95.0,
                sma_60=100.0,
                rsi_14=30.0,
            )
        ],
        portfolio=PortfolioSnapshot(
            cash=500.0,
            holdings={"TEST.KS": 10},
            mark_prices={"TEST.KS": 90.0},
            avg_costs={"TEST.KS": 100.0},
            equity=1400.0,
            unrealized_pnl=-100.0,
        ),
        capital=1000.0,
        target=1200.0,
        remaining_sessions=5,
        session_index=2,
        session_count=10,
    )


def test_heuristic_rejects_placeholders() -> None:
    assert assess_sell_reason_heuristic("sell") is False
    assert assess_sell_reason_heuristic("n/a") is False
    assert assess_sell_reason_heuristic("short") is False
    assert (
        assess_sell_reason_heuristic(
            "RSI below 30 and price under SMA60; cutting loser"
        )
        is True
    )


def test_gate_heuristic_demotes_to_hold() -> None:
    decision = TradeDecision(action="sell", size=0.5, reason="sell")
    out = gate_sell_decision(
        decision,
        _obs_with_shares(),
        llm=None,
        use_llm_judge=False,
        prefer_instructor=False,
    )
    assert out.action == "hold"
    assert out.reason == "sell_reason_weak"


def test_gate_llm_rejects_ungrounded() -> None:
    class FakeLLM:
        def generate(
            self,
            prompt: str,
            *,
            format_json: bool = False,
            options: dict | None = None,
        ) -> str:
            return '{"ok": false, "critique": "no observation link"}'

    decision = TradeDecision(
        action="sell",
        size=0.5,
        reason="I feel like selling some shares today",
    )
    out = gate_sell_decision(
        decision,
        _obs_with_shares(),
        llm=FakeLLM(),
        use_llm_judge=True,
        prefer_instructor=False,
    )
    assert out.action == "hold"
    assert out.reason == "sell_reason_ungrounded"


def test_gate_llm_accepts_grounded() -> None:
    class FakeLLM:
        def generate(
            self,
            prompt: str,
            *,
            format_json: bool = False,
            options: dict | None = None,
        ) -> str:
            return '{"ok": true, "critique": "cites RSI and SMA"}'

    decision = TradeDecision(
        action="sell",
        size=0.5,
        reason="RSI near 30 and close below SMA60; trim risk",
    )
    out = gate_sell_decision(
        decision,
        _obs_with_shares(),
        llm=FakeLLM(),
        use_llm_judge=True,
        prefer_instructor=False,
    )
    assert out.action == "sell"


def test_agent_sell_judge_unavailable() -> None:
    class BoomLLM:
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
            # Judge prompt only (see sell_judge.judge_sell_reason_with_generate)
            if "You judge whether a sell reason is grounded" in prompt:
                raise ConnectionError("down")
            return (
                '{"action":"sell","size":0.5,'
                '"reason":"RSI near 30 and price under SMA60 trend break"}'
            )

    agent = LlmTradingAgent(
        BoomLLM(),
        persona=get_persona("balanced"),
        judge_sell_reason=True,
    )
    decision = agent.decide(_obs_with_shares())
    assert decision.action == "hold"
    assert decision.reason == "sell_judge_unavailable"


def test_interviewer_fallback_on_bad_extract(monkeypatch: pytest.MonkeyPatch) -> None:
    from quantpilot.agent.risk_profile import interviewer as mod
    from quantpilot.agent.risk_profile.interviewer import (
        ExtractedChoice,
        interview_collect_sheet,
    )
    from quantpilot.agent.risk_profile.questions import load_all_questions

    questions = load_all_questions()

    def fake_extract(question, user_text, *, model=None):  # type: ignore[no-untyped-def]
        return ExtractedChoice(
            question_id=question.id,
            choice_id=question.choices[0].id,
            confidence=0.1,
            needs_clarification=True,
        )

    monkeypatch.setattr(mod, "extract_choice_from_text", fake_extract)

    def ask_free(prompt: str) -> str:
        return "not sure"

    def ask_select(prompt: str, choices: list[str]) -> str:
        return choices[0]

    sheet = interview_collect_sheet(ask_free_text=ask_free, ask_select=ask_select)
    assert len(sheet.answers) == len(questions)
