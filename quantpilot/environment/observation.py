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
class SymbolView:
    """Look-ahead-safe summary for one symbol."""

    symbol: str
    recent_bars: list[dict[str, float | str]]
    sma_20: float | None
    sma_60: float | None
    rsi_14: float | None


@dataclass(frozen=True)
class AgentObservation:
    """What an agent may see at as_of (no future bars)."""

    as_of: date
    symbols: list[str]
    legs: list[SymbolView]
    portfolio: PortfolioSnapshot
    capital: float
    target: float
    remaining_sessions: int
    session_index: int
    session_count: int

    @property
    def symbol(self) -> str:
        """Primary symbol (first in universe) for single-leg prompts/tests."""
        return self.symbols[0]

    @property
    def recent_bars(self) -> list[dict[str, float | str]]:
        return self.legs[0].recent_bars if self.legs else []

    @property
    def sma_20(self) -> float | None:
        return self.legs[0].sma_20 if self.legs else None

    @property
    def sma_60(self) -> float | None:
        return self.legs[0].sma_60 if self.legs else None

    @property
    def rsi_14(self) -> float | None:
        return self.legs[0].rsi_14 if self.legs else None


class ObservationBuilder:
    """Assemble AgentObservation from visible price slices."""

    def __init__(self, recent_bars: int = 20) -> None:
        if recent_bars < 1:
            raise ValueError("recent_bars must be >= 1")
        self._recent_bars = recent_bars

    def build(
        self,
        *,
        symbols: list[str],
        visibles: dict[str, pl.DataFrame],
        as_of: date,
        portfolio: PortfolioSnapshot,
        capital: float,
        target: float,
        remaining_sessions: int,
        session_index: int,
        session_count: int,
    ) -> AgentObservation:
        if not symbols:
            raise ValueError("symbols must not be empty")
        legs: list[SymbolView] = []
        for symbol in symbols:
            visible = visibles.get(symbol)
            if visible is None:
                raise ValueError(f"Missing visible frame for {symbol}")
            legs.append(self._build_leg(symbol=symbol, visible=visible, as_of=as_of))

        return AgentObservation(
            as_of=as_of,
            symbols=list(symbols),
            legs=legs,
            portfolio=portfolio,
            capital=capital,
            target=target,
            remaining_sessions=remaining_sessions,
            session_index=session_index,
            session_count=session_count,
        )

    def _build_leg(
        self,
        *,
        symbol: str,
        visible: pl.DataFrame,
        as_of: date,
    ) -> SymbolView:
        visible = visible.filter(pl.col(QP_DATE) <= as_of).sort(QP_DATE)
        if visible.is_empty():
            raise ValueError(f"No visible bars at as_of={as_of} for {symbol}")

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

        return SymbolView(
            symbol=symbol,
            recent_bars=recent,
            sma_20=_last(sma20_s),
            sma_60=_last(sma60_s),
            rsi_14=_last(rsi_s),
        )
