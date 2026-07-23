"""Trading cost helpers for paper fills."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TradingCosts:
    """Commission as a fraction of notional; slippage in basis points."""

    commission_rate: float = 0.0
    slippage_bps: float = 0.0

    def __post_init__(self) -> None:
        if self.commission_rate < 0:
            raise ValueError("commission_rate must be >= 0")
        if self.slippage_bps < 0:
            raise ValueError("slippage_bps must be >= 0")

    def exec_price(self, open_price: float, *, action: str) -> float:
        """Apply slippage to the session open."""
        bump = self.slippage_bps / 10_000.0
        if action == "buy":
            return open_price * (1.0 + bump)
        if action == "sell":
            return open_price * (1.0 - bump)
        raise ValueError(f"unsupported action: {action}")

    def commission(self, notional: float) -> float:
        """Commission charged on absolute notional."""
        return abs(notional) * self.commission_rate
