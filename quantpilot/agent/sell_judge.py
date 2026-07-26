"""Sell-reason grounding gate (heuristic + optional LLM judge)."""

from __future__ import annotations

import logging
import re
from typing import Any, Protocol

from pydantic import BaseModel

from quantpilot.agent.decision import TradeDecision
from quantpilot.environment.observation import AgentObservation

logger = logging.getLogger(__name__)

_PLACEHOLDERS = frozenset(
    {
        "sell",
        "n/a",
        "na",
        "none",
        "null",
        "test",
        "asdf",
        "reason",
        "todo",
        "tbd",
        "...",
        "idk",
    }
)


class SellGroundingResult(BaseModel):
    """Whether a sell reason is grounded in the observation."""

    ok: bool
    critique: str = ""


class SupportsGenerate(Protocol):
    def generate(
        self,
        prompt: str,
        *,
        format_json: bool = False,
        options: dict[str, Any] | None = None,
    ) -> str: ...


def assess_sell_reason_heuristic(reason: str) -> bool:
    """Return True if the reason clears cheap placeholder checks."""
    text = reason.strip()
    lowered = text.lower().strip(" .!?")
    if lowered in _PLACEHOLDERS:
        return False
    if len(text) < 12:
        return False
    words = re.findall(r"[a-zA-Z0-9]+", text)
    if len(words) <= 1:
        return False
    return True


def _observation_digest(obs: AgentObservation) -> str:
    port = obs.portfolio
    legs = []
    for leg in obs.legs:
        legs.append(
            f"{leg.symbol}: SMA20={leg.sma_20} SMA60={leg.sma_60} RSI14={leg.rsi_14} "
            f"bars={len(leg.recent_bars)}"
        )
    return (
        f"as_of={obs.as_of} symbols={obs.symbols} "
        f"cash={port.cash:.2f} equity={port.equity:.2f} "
        f"unrealized_pnl={port.unrealized_pnl:.2f} "
        f"target={obs.target:.2f} remaining={obs.remaining_sessions} "
        f"legs=[{'; '.join(legs)}]"
    )


def judge_sell_reason_with_generate(
    llm: SupportsGenerate,
    *,
    observation: AgentObservation,
    reason: str,
    options: dict[str, Any] | None = None,
) -> SellGroundingResult:
    """Ask an LLM (JSON) whether the sell reason cites observation facts."""
    prompt = (
        "You judge whether a sell reason is grounded in the observation.\n"
        'Reply with ONLY JSON: {"ok": true|false, "critique": "..."}\n'
        "ok=true only if the reason cites or clearly implies something present "
        "(price/trend/SMA/RSI/PnL/target/time/holdings).\n"
        "ok=false for empty, vague, or ungrounded reasons.\n\n"
        f"Observation: {_observation_digest(observation)}\n"
        f"Sell reason: {reason}\n"
    )
    raw = llm.generate(prompt, format_json=True, options=options)
    try:
        return SellGroundingResult.model_validate_json(raw)
    except Exception as exc:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            logger.warning(
                "Unparseable sell-judge payload (no JSON object): %s",
                exc,
                exc_info=True,
            )
            return SellGroundingResult(ok=False, critique="unparseable_judge_response")
        try:
            return SellGroundingResult.model_validate_json(raw[start : end + 1])
        except Exception as scrape_exc:
            logger.warning(
                "Unparseable sell-judge payload after scrape: %s",
                scrape_exc,
                exc_info=True,
            )
            return SellGroundingResult(ok=False, critique="unparseable_judge_response")


def judge_sell_reason_structured(
    *,
    observation: AgentObservation,
    reason: str,
    model: str | None = None,
) -> SellGroundingResult:
    """Judge via instructor structured extraction (preferred path)."""
    from quantpilot.ai.structured import extract_structured

    messages = [
        {
            "role": "system",
            "content": (
                "Judge whether a sell reason is grounded in the observation. "
                "ok=true only if it cites or implies price/trend/SMA/RSI/PnL/"
                "target/time/holdings from the observation."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Observation: {_observation_digest(observation)}\n"
                f"Sell reason: {reason}\n"
            ),
        },
    ]
    return extract_structured(
        SellGroundingResult,
        messages=messages,
        model=model,
    )


def gate_sell_decision(
    decision: TradeDecision,
    observation: AgentObservation,
    *,
    llm: SupportsGenerate | None,
    use_llm_judge: bool,
    options: dict[str, Any] | None = None,
    prefer_instructor: bool = True,
) -> TradeDecision:
    """Apply heuristic + optional LLM grounding; demote to hold on failure."""
    if decision.action != "sell":
        return decision

    if not assess_sell_reason_heuristic(decision.reason):
        return TradeDecision.hold(reason="sell_reason_weak")

    if not use_llm_judge:
        return decision

    try:
        if prefer_instructor:
            result = judge_sell_reason_structured(
                observation=observation,
                reason=decision.reason,
            )
        elif llm is not None:
            result = judge_sell_reason_with_generate(
                llm,
                observation=observation,
                reason=decision.reason,
                options=options,
            )
        else:
            return TradeDecision.hold(reason="sell_judge_unavailable")
    except Exception as exc:
        logger.warning("Sell judge unavailable: %s", exc, exc_info=True)
        return TradeDecision.hold(reason="sell_judge_unavailable")

    if not result.ok:
        return TradeDecision.hold(reason="sell_reason_ungrounded")
    return decision
