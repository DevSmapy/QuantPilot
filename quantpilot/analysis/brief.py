"""Agent-ready analysis brief schema (JSON-friendly research context)."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any

BRIEF_SCHEMA_VERSION = "1"

DEFAULT_BRIEF_NOTES: tuple[str, ...] = (
    "Long-only event signals; costs are equity haircuts.",
    "Brief is research context, not an order.",
)


@dataclass(frozen=True)
class AnalysisBriefWindow:
    """Inclusive research window for the backtest."""

    start: str
    end: str


@dataclass(frozen=True)
class AnalysisBriefStrategy:
    """Strategy identity and fixed parameters."""

    name: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnalysisBriefMetrics:
    """Scalar backtest metrics (JSON-friendly; infinite PF becomes null)."""

    total_return: float
    cagr: float
    mdd: float
    sharpe: float
    sortino: float
    profit_factor: float | None
    win_rate: float
    trades_count: int


@dataclass(frozen=True)
class AnalysisBriefSignalsSummary:
    """Compact signal counts and last event."""

    last_signal: int
    buy_count: int
    sell_count: int


@dataclass(frozen=True)
class AnalysisBrief:
    """Flat research pack for LLM prompt injection (later wiring)."""

    schema_version: str
    symbol: str
    as_of: str
    window: AnalysisBriefWindow
    strategy: AnalysisBriefStrategy
    metrics: AnalysisBriefMetrics
    indicators_snapshot: dict[str, float | None]
    signals_summary: AnalysisBriefSignalsSummary
    monthly_returns: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=lambda: list(DEFAULT_BRIEF_NOTES))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-friendly plain dict."""
        return asdict(self)

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialize to JSON text."""
        return json.dumps(self.to_dict(), indent=indent, allow_nan=False)


def json_safe_float(value: float) -> float | None:
    """Convert non-finite floats to ``None`` for JSON."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return float(value)


def brief_to_prompt_block(brief: AnalysisBrief) -> str:
    """Render a compact prompt section (agent wiring is a follow-up)."""
    payload = brief.to_json(indent=2)
    return (
        "### Research brief (AnalysisBrief)\n"
        "Use the following structured research context. "
        "It is not an order.\n"
        f"```json\n{payload}\n```"
    )
