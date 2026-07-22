"""Trading agent interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from quantpilot.agent.decision import TradeDecision
from quantpilot.environment.observation import AgentObservation


class TradingAgent(ABC):
    """Decide an action from a look-ahead-safe observation."""

    @abstractmethod
    def decide(self, observation: AgentObservation) -> TradeDecision:
        """Return buy / sell / hold for the next open."""
