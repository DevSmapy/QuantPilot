"""Tests for TradeDecision parsing and sell-reason rules."""

from __future__ import annotations

from quantpilot.agent.decision import (
    TradeDecision,
    normalize_decision,
    parse_trade_decision,
    validate_trade_decision,
)


def test_parse_buy_decision() -> None:
    decision = parse_trade_decision(
        '{"action":"buy","size":0.5,"reason":"momentum"}'
    )
    assert decision is not None
    assert decision.action == "buy"
    assert decision.size == 0.5


def test_sell_requires_reason() -> None:
    assert validate_trade_decision({"action": "sell", "size": 1.0, "reason": ""}) is None
    assert validate_trade_decision({"action": "sell", "size": 1.0, "reason": "   "}) is None
    ok = validate_trade_decision(
        {"action": "sell", "size": 0.5, "reason": "take profit"}
    )
    assert ok is not None
    assert ok.action == "sell"


def test_parse_first_json_object_not_greedy() -> None:
    raw = (
        'Sure.\n{"action":"hold","size":0,"reason":"wait"}\n'
        'ignore {"action":"buy","size":1,"reason":"no"}\n'
    )
    decision = parse_trade_decision(raw)
    assert decision is not None
    assert decision.action == "hold"


def test_invalid_size_rejected() -> None:
    assert validate_trade_decision({"action": "buy", "size": 0, "reason": "x"}) is None
    assert validate_trade_decision({"action": "buy", "size": 1.5, "reason": "x"}) is None


def test_normalize_sell_without_reason_becomes_hold() -> None:
    demoted = normalize_decision(
        TradeDecision(action="sell", size=1.0, reason="")
    )
    assert demoted.action == "hold"
    assert demoted.reason == "sell_requires_reason"
