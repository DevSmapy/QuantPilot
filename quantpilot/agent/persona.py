"""Structured trading personas and hard decision guards."""

from __future__ import annotations

from dataclasses import dataclass

from quantpilot.agent.decision import TradeDecision
from quantpilot.environment.observation import AgentObservation

PERSONA_IDS = ("conservative", "balanced", "aggressive")


@dataclass(frozen=True)
class TradingPersona:
    """Investment-style policy applied via prompt + hard guards."""

    id: str
    label: str
    primary_objective: str
    max_buy_size: float
    max_sell_size: float
    min_cash_fraction: float
    loss_response: str
    opportunity_bias: str
    target_pressure: str
    preferred_hold_when: str
    example_decision_json: str


_PERSONAS: dict[str, TradingPersona] = {
    "conservative": TradingPersona(
        id="conservative",
        label="Conservative",
        primary_objective="capital_preservation",
        max_buy_size=0.20,
        max_sell_size=0.40,
        min_cash_fraction=0.40,
        loss_response=(
            "Prefer hold on small unrealized losses; trim only with clear "
            "trend/RSI deterioration, not panic."
        ),
        opportunity_bias="Favor patience and small adds over chasing moves.",
        target_pressure=(
            "Do not chase the equity target with large buys; preserve cash buffer."
        ),
        preferred_hold_when=(
            "Signals are mixed, cash floor would be breached, or thesis is unclear."
        ),
        example_decision_json=(
            '{"action":"hold","size":0,"reason":'
            '"Mixed RSI and thin cash buffer; wait for clearer trend."}'
        ),
    ),
    "balanced": TradingPersona(
        id="balanced",
        label="Balanced",
        primary_objective="balanced_growth",
        max_buy_size=0.50,
        max_sell_size=0.75,
        min_cash_fraction=0.15,
        loss_response=(
            "Weigh drawdown against thesis; partial trims when trend breaks."
        ),
        opportunity_bias="Take moderate sizes when momentum and RSI align.",
        target_pressure=(
            "Progress toward target with measured buys; avoid all-in bets."
        ),
        preferred_hold_when="No edge vs staying in cash or current holdings.",
        example_decision_json=(
            '{"action":"buy","size":0.35,"reason":'
            '"SMA20 above SMA60 and RSI mid-range; moderate add toward target."}'
        ),
    ),
    "aggressive": TradingPersona(
        id="aggressive",
        label="Aggressive",
        primary_objective="maximize_growth",
        max_buy_size=1.00,
        max_sell_size=1.00,
        min_cash_fraction=0.00,
        loss_response=(
            "Tolerate unrealized loss if thesis intact; "
            "cut or rotate when thesis fails."
        ),
        opportunity_bias=(
            "Use larger sizes when momentum/RSI supportive; act on opportunities."
        ),
        target_pressure=(
            "Prioritize closing the gap to target within remaining sessions."
        ),
        preferred_hold_when="Only when no actionable edge across the universe.",
        example_decision_json=(
            '{"action":"buy","size":0.85,"reason":'
            '"Strong momentum and sessions remaining; deploy cash toward target."}'
        ),
    ),
}


def get_persona(name: str) -> TradingPersona:
    """Return a named persona or raise ValueError."""
    key = name.strip().lower()
    if key not in _PERSONAS:
        raise ValueError(
            f"Unknown persona {name!r}; expected one of {', '.join(PERSONA_IDS)}"
        )
    return _PERSONAS[key]


def build_persona_prompt_section(persona: TradingPersona) -> str:
    """Render the persona policy block for the trading prompt."""
    return (
        f"Investor persona: {persona.label} ({persona.id})\n"
        f"Primary objective: {persona.primary_objective}\n"
        f"- Loss response: {persona.loss_response}\n"
        f"- Opportunity bias: {persona.opportunity_bias}\n"
        f"- Target pressure: {persona.target_pressure}\n"
        f"- Prefer hold when: {persona.preferred_hold_when}\n"
        f"- Hard limits: max_buy_size={persona.max_buy_size}, "
        f"max_sell_size={persona.max_sell_size}, "
        f"min_cash_fraction={persona.min_cash_fraction}\n"
        f"Example decision JSON for this persona:\n{persona.example_decision_json}\n"
    )


def apply_persona_guards(
    decision: TradeDecision,
    observation: AgentObservation,
    persona: TradingPersona,
) -> TradeDecision:
    """Clamp sizes and enforce cash floor; demote impossible buys to hold."""
    if decision.action == "hold":
        return decision

    if decision.action == "sell":
        size = min(decision.size, persona.max_sell_size)
        if size <= 0:
            return TradeDecision.hold(reason="persona_invalid_sell_size")
        if size == decision.size:
            return decision
        return TradeDecision(
            action="sell",
            size=size,
            reason=decision.reason,
            symbol=decision.symbol,
        )

    # buy
    size = min(decision.size, persona.max_buy_size)
    cash = observation.portfolio.cash
    equity = observation.portfolio.equity
    if cash <= 0 or equity <= 0:
        return TradeDecision.hold(reason="persona_cash_floor")

    # After spending size*cash, remaining cash / equity >= min_cash_fraction
    # (equity approximately unchanged when converting cash to stock).
    max_by_floor = 1.0 - (persona.min_cash_fraction * equity / cash)
    if max_by_floor <= 0:
        return TradeDecision.hold(reason="persona_cash_floor")
    size = min(size, max_by_floor)
    if size <= 0:
        return TradeDecision.hold(reason="persona_cash_floor")
    if size == decision.size:
        return decision
    return TradeDecision(
        action="buy",
        size=size,
        reason=decision.reason,
        symbol=decision.symbol,
    )
