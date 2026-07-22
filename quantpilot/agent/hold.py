"""Always-hold agent for smoke tests and baselines."""

from __future__ import annotations

from quantpilot.agent.base import TradingAgent
from quantpilot.agent.decision import TradeDecision
from quantpilot.environment.observation import AgentObservation


class HoldAgent(TradingAgent):
    """Never trade."""

    def decide(self, observation: AgentObservation) -> TradeDecision:
        return TradeDecision.hold(reason="hold_agent")
