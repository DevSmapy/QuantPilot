"""Build AnalysisBrief from prices, signals, and a BacktestResult."""

from __future__ import annotations

from datetime import date
from typing import Any

import polars as pl

from quantpilot.analysis.brief import (
    BRIEF_SCHEMA_VERSION,
    DEFAULT_BRIEF_NOTES,
    AnalysisBrief,
    AnalysisBriefMetrics,
    AnalysisBriefSignalsSummary,
    AnalysisBriefStrategy,
    AnalysisBriefWindow,
    json_safe_float,
)
from quantpilot.backtest.engine import BacktestResult
from quantpilot.indicators.atr import atr
from quantpilot.indicators.bollinger import bollinger
from quantpilot.indicators.ema import ema
from quantpilot.indicators.macd import macd
from quantpilot.indicators.rsi import rsi
from quantpilot.indicators.sma import sma
from quantpilot.providers.qseed_schema import (
    QP_CLOSE,
    QP_DATE,
    QP_HIGH,
    QP_LOW,
    QP_SYMBOL,
)


def _as_of_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _last_finite(series: pl.Series) -> float | None:
    if series.len() == 0:
        return None
    value = series[-1]
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN
        return None
    return f


def _indicators_at_as_of(prices: pl.DataFrame, as_of: date) -> dict[str, float | None]:
    visible = prices.filter(pl.col(QP_DATE) <= as_of).sort(QP_DATE)
    empty: dict[str, float | None] = {
        "sma_20": None,
        "sma_60": None,
        "rsi_14": None,
        "ema_20": None,
        "macd": None,
        "macd_signal": None,
        "bb_mid": None,
        "atr_14": None,
    }
    if visible.is_empty():
        return empty
    closes = visible[QP_CLOSE].cast(pl.Float64)
    macd_frame = macd(closes)
    bb = bollinger(closes)
    snapshot: dict[str, float | None] = {
        "sma_20": _last_finite(sma(closes, 20)),
        "sma_60": _last_finite(sma(closes, 60)),
        "rsi_14": _last_finite(rsi(closes, 14)),
        "ema_20": _last_finite(ema(closes, 20)),
        "macd": _last_finite(macd_frame["macd"]),
        "macd_signal": _last_finite(macd_frame["signal"]),
        "bb_mid": _last_finite(bb["mid"]),
        "atr_14": None,
    }
    if QP_HIGH in visible.columns and QP_LOW in visible.columns:
        snapshot["atr_14"] = _last_finite(
            atr(visible[QP_HIGH], visible[QP_LOW], closes, 14)
        )
    return snapshot


def _signals_summary(signals: pl.DataFrame, as_of: date) -> AnalysisBriefSignalsSummary:
    frame = signals.filter(pl.col(QP_DATE) <= as_of).sort(QP_DATE)
    if frame.is_empty():
        return AnalysisBriefSignalsSummary(last_signal=0, buy_count=0, sell_count=0)
    signal_col = frame["signal"]
    last = int(signal_col[-1])
    buy_count = int(signal_col.eq(1).sum())
    sell_count = int(signal_col.eq(-1).sum())
    return AnalysisBriefSignalsSummary(
        last_signal=last,
        buy_count=buy_count,
        sell_count=sell_count,
    )


def _resolve_symbol(prices: pl.DataFrame, symbol: str | None) -> str:
    if symbol is not None:
        return symbol
    if QP_SYMBOL in prices.columns and prices.height > 0:
        return str(prices[QP_SYMBOL][0])
    return "UNKNOWN"


def build_analysis_brief(
    *,
    prices: pl.DataFrame,
    signals: pl.DataFrame,
    result: BacktestResult,
    strategy_name: str,
    strategy_params: dict[str, Any] | None = None,
    symbol: str | None = None,
    as_of: date | str | None = None,
    notes: list[str] | None = None,
) -> AnalysisBrief:
    """Assemble a look-ahead-safe AnalysisBrief from a completed backtest."""
    if QP_DATE not in prices.columns or QP_CLOSE not in prices.columns:
        raise ValueError(f"prices must contain '{QP_DATE}' and '{QP_CLOSE}'")
    if QP_DATE not in signals.columns or "signal" not in signals.columns:
        raise ValueError("signals must contain 'date' and 'signal'")

    as_of_d = _as_of_date(as_of if as_of is not None else result.end_date)
    pf = json_safe_float(result.profit_factor)
    brief_notes = list(notes) if notes is not None else list(DEFAULT_BRIEF_NOTES)
    if pf is None and result.profit_factor == float("inf"):
        brief_notes.append(
            "profit_factor was infinite (no losing trades); emitted as null."
        )

    return AnalysisBrief(
        schema_version=BRIEF_SCHEMA_VERSION,
        symbol=_resolve_symbol(prices, symbol),
        as_of=as_of_d.isoformat(),
        window=AnalysisBriefWindow(start=result.start_date, end=result.end_date),
        strategy=AnalysisBriefStrategy(
            name=strategy_name,
            params=dict(strategy_params or {}),
        ),
        metrics=AnalysisBriefMetrics(
            total_return=float(result.total_return),
            cagr=float(result.cagr),
            mdd=float(result.mdd),
            sharpe=float(result.sharpe),
            sortino=float(result.sortino),
            profit_factor=pf,
            win_rate=float(result.win_rate),
            trades_count=int(result.trades_count),
        ),
        indicators_snapshot=_indicators_at_as_of(prices, as_of_d),
        signals_summary=_signals_summary(signals, as_of_d),
        monthly_returns=dict(result.monthly_returns),
        notes=brief_notes,
    )
