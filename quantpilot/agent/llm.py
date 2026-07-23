"""LLM-backed trading agent with sell-reason enforcement."""

from __future__ import annotations

from typing import Any, Protocol

from quantpilot.agent.base import TradingAgent
from quantpilot.agent.decision import TradeDecision, parse_trade_decision
from quantpilot.environment.observation import AgentObservation


class SupportsGenerate(Protocol):
    def generate(
        self,
        prompt: str,
        *,
        format_json: bool = False,
        options: dict[str, Any] | None = None,
    ) -> str: ...


class LlmTradingAgent(TradingAgent):
    """Ask an LLM for JSON trade decisions; invalid/unavailable → hold."""

    def __init__(
        self,
        llm: SupportsGenerate,
        *,
        max_retries: int = 1,
        options: dict[str, Any] | None = None,
    ) -> None:
        self._llm = llm
        self._max_retries = max(0, max_retries)
        self._options = options

    def decide(self, observation: AgentObservation) -> TradeDecision:
        prompt = _build_prompt(observation)
        attempts = self._max_retries + 1
        for _ in range(attempts):
            try:
                raw = self._llm.generate(
                    prompt,
                    format_json=True,
                    options=self._options,
                )
            except Exception:
                return TradeDecision.hold(reason="llm_unavailable")
            decision = parse_trade_decision(raw, universe=observation.symbols)
            if decision is not None:
                if decision.action == "sell":
                    symbol = decision.symbol or (
                        observation.symbols[0] if len(observation.symbols) == 1 else None
                    )
                    qty = (
                        observation.portfolio.holdings.get(symbol, 0)
                        if symbol is not None
                        else 0
                    )
                    if qty <= 0:
                        return TradeDecision.hold(reason="sell_with_zero_qty")
                return decision
        return TradeDecision.hold(reason="invalid_llm_decision")


def _build_prompt(obs: AgentObservation) -> str:
    port = obs.portfolio
    holdings = ", ".join(
        f"{symbol}:{qty}" for symbol, qty in sorted(port.holdings.items())
    ) or "(none)"
    multi = len(obs.symbols) > 1
    schema = (
        '{"action":"buy"|"sell"|"hold","size":number,"reason":string,"symbol":string}'
        if multi
        else '{"action":"buy"|"sell"|"hold","size":number,"reason":string}'
    )
    symbol_rule = (
        "- For buy/sell, symbol MUST be one of the universe tickers.\n"
        if multi
        else ""
    )
    legs_text: list[str] = []
    for leg in obs.legs:
        bars = "\n".join(
            f"  - {b['date']}: open={b['open']}, close={b['close']}, volume={b['volume']}"
            for b in leg.recent_bars
        )
        legs_text.append(
            f"Symbol {leg.symbol}:\n"
            f"  SMA20={leg.sma_20} SMA60={leg.sma_60} RSI14={leg.rsi_14}\n"
            f"  Recent bars:\n{bars}"
        )
    return (
        "You are a long-only paper trader. Reply with ONLY one JSON object.\n"
        f"Schema: {schema}\n"
        "- buy size: fraction of cash to spend (0 < size <= 1)\n"
        "- sell size: fraction of shares to sell (0 < size <= 1)\n"
        "- hold: size ignored\n"
        "- If action is sell, reason MUST be a non-empty explanation.\n"
        f"{symbol_rule}"
        "- No shorting. You cannot see future prices.\n"
        "- Decisions are end-of-day using today's close; orders fill at the next open.\n\n"
        f"Universe: {', '.join(obs.symbols)}\n"
        f"As of: {obs.as_of}\n"
        f"Session: {obs.session_index + 1}/{obs.session_count} "
        f"(remaining={obs.remaining_sessions})\n"
        f"Capital: {obs.capital:.2f}\n"
        f"Target: {obs.target:.2f}\n"
        f"Cash: {port.cash:.2f}\n"
        f"Holdings: {holdings}\n"
        f"Equity: {port.equity:.2f}\n"
        f"Unrealized PnL: {port.unrealized_pnl:.2f}\n\n"
        + "\n\n".join(legs_text)
        + "\n"
    )
