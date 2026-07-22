"""Build look-ahead-safe observations for trading agents."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import polars as pl

from quantpilot.environment.types import PortfolioSnapshot
from quantpilot.indicators.rsi import rsi
from quantpilot.indicators.sma import sma
from quantpilot.providers.qseed_schema import QP_CLOSE, QP_DATE, QP_OPEN, QP_VOLUME


@dataclass(frozen=True)
class AgentObservation:
    """What an agent may see at as_of (no future bars)."""

    as_of: date
    symbol: str
    recent_bars: list[dict[str, float | str]]
    sma_20: float | None
    sma_60: float | None
    rsi_14: float | None
    portfolio: PortfolioSnapshot
    capital: float
    target: float
    remaining_sessions: int
    session_index: int
    session_count: int


class ObservationBuilder:
    """Assemble AgentObservation from a visible price slice."""

    def __init__(self, recent_bars: int = 20) -> None:
        if recent_bars < 1:
            raise ValueError("recent_bars must be >= 1")
        self._recent_bars = recent_bars

    def build(
        self,
        *,
        symbol: str,
        visible: pl.DataFrame,
        as_of: date,
        portfolio: PortfolioSnapshot,
        capital: float,
        target: float,
        remaining_sessions: int,
        session_index: int,
        session_count: int,
    ) -> AgentObservation:
        visible = visible.filter(pl.col(QP_DATE) <= as_of).sort(QP_DATE)
        if visible.is_empty():
            raise ValueError(f"No visible bars at as_of={as_of}")

        closes = visible[QP_CLOSE].cast(pl.Float64)
        sma20_s = sma(closes, 20)
        sma60_s = sma(closes, 60)
        rsi_s = rsi(closes, 14)

        def _last(series: pl.Series) -> float | None:
            value = series[-1]
            if value is None:
                return None
            try:
                if value != value:  # NaN
                    return None
            except TypeError:
                pass
            return float(value)

        tail = visible.tail(self._recent_bars)
        recent: list[dict[str, float | str]] = []
        for row in tail.iter_rows(named=True):
            recent.append(
                {
                    "date": str(row[QP_DATE]),
                    "open": float(row[QP_OPEN]),
                    "close": float(row[QP_CLOSE]),
                    "volume": float(row[QP_VOLUME]),
                }
            )

        return AgentObservation(
            as_of=as_of,
            symbol=symbol,
            recent_bars=recent,
            sma_20=_last(sma20_s),
            sma_60=_last(sma60_s),
            rsi_14=_last(rsi_s),
            portfolio=portfolio,
            capital=capital,
            target=target,
            remaining_sessions=remaining_sessions,
            session_index=session_index,
            session_count=session_count,
        )
