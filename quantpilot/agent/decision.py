"""TradeDecision parsing and sell-reason validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal


Action = Literal["buy", "sell", "hold"]


@dataclass(frozen=True)
class TradeDecision:
    """Agent action for the next open fill."""

    action: Action
    size: float
    reason: str

    @staticmethod
    def hold(reason: str = "hold") -> TradeDecision:
        return TradeDecision(action="hold", size=0.0, reason=reason)


def parse_trade_decision(raw: str) -> TradeDecision | None:
    """Parse model JSON into TradeDecision. Return None if invalid."""
    payload = _extract_json_object(raw)
    if payload is None:
        return None
    return validate_trade_decision(payload)


def validate_trade_decision(payload: dict[str, Any]) -> TradeDecision | None:
    """Validate a decision dict. Sell requires a non-empty reason."""
    action = payload.get("action")
    if action not in ("buy", "sell", "hold"):
        return None

    reason = str(payload.get("reason", "") or "").strip()

    if action == "hold":
        return TradeDecision(action="hold", size=0.0, reason=reason or "hold")

    try:
        size = float(payload.get("size", 0))
    except (TypeError, ValueError):
        return None
    if size <= 0 or size > 1:
        return None

    if action == "sell" and not reason:
        return None

    return TradeDecision(action=action, size=size, reason=reason)


def normalize_decision(decision: TradeDecision) -> TradeDecision:
    """Enforce sell-reason and size rules for any agent implementation."""
    if decision.action == "hold":
        return TradeDecision.hold(reason=decision.reason or "hold")

    if decision.size <= 0 or decision.size > 1:
        return TradeDecision.hold(reason="invalid_size")

    if decision.action == "sell" and not str(decision.reason).strip():
        return TradeDecision.hold(reason="sell_requires_reason")

    return TradeDecision(
        action=decision.action,
        size=decision.size,
        reason=str(decision.reason).strip(),
    )


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    """Parse the first JSON object in text (non-greedy via raw_decode)."""
    text = raw.strip()
    if not text:
        return None

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    if start < 0:
        return None

    decoder = json.JSONDecoder()
    try:
        data, _end = decoder.raw_decode(text[start:])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
