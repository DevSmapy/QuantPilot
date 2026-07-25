"""Performance metrics for equity curves and round-trip trades."""

from __future__ import annotations

import math
from datetime import date


def period_returns(equity_curve: list[float]) -> list[float]:
    """Convert an equity curve into per-bar simple returns."""
    if len(equity_curve) < 2:
        return []
    returns: list[float] = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1]
        if prev == 0:
            continue
        returns.append((equity_curve[i] / prev) - 1.0)
    return returns


def max_drawdown(equity_curve: list[float]) -> float:
    """Maximum drawdown as a non-positive fraction of peak equity."""
    if not equity_curve:
        return 0.0

    peak = equity_curve[0]
    max_dd = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            drawdown = (value / peak) - 1.0
            max_dd = min(max_dd, drawdown)
    return max_dd


def sharpe_ratio(equity_curve: list[float]) -> float:
    """Annualized Sharpe ratio from daily equity returns (sqrt(252))."""
    returns = period_returns(equity_curve)
    if not returns:
        return 0.0

    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    std_dev = math.sqrt(variance)
    if std_dev == 0:
        return 0.0

    return (mean_return / std_dev) * math.sqrt(252)


def sortino_ratio(equity_curve: list[float]) -> float:
    """Annualized Sortino ratio using downside deviation of daily returns."""
    returns = period_returns(equity_curve)
    if not returns:
        return 0.0

    mean_return = sum(returns) / len(returns)
    downside = [min(r, 0.0) for r in returns]
    downside_variance = sum(r * r for r in downside) / len(returns)
    downside_dev = math.sqrt(downside_variance)
    if downside_dev == 0:
        return 0.0

    return (mean_return / downside_dev) * math.sqrt(252)


def cagr(equity: float, start: date, end: date) -> float:
    """Compound annual growth rate from start equity 1.0 to ``equity``."""
    years = max((end - start).days / 365.25, 1 / 365.25)
    if equity <= 0:
        return -1.0
    return float((equity ** (1 / years)) - 1.0)


def profit_factor(trade_pnls: list[float]) -> float:
    """Gross profits divided by absolute gross losses (trade PnL list)."""
    gains = sum(p for p in trade_pnls if p > 0)
    losses = sum(p for p in trade_pnls if p < 0)
    if not trade_pnls:
        return 0.0
    if losses == 0:
        return float("inf") if gains > 0 else 0.0
    return gains / abs(losses)


def win_rate(trade_pnls: list[float]) -> float:
    """Fraction of round-trip trades with positive PnL."""
    if not trade_pnls:
        return 0.0
    wins = sum(1 for p in trade_pnls if p > 0)
    return wins / len(trade_pnls)


def _parse_year_month(key: str) -> tuple[int, int]:
    year_s, month_s = key.split("-", maxsplit=1)
    return int(year_s), int(month_s)


def _month_delta(prev: tuple[int, int], curr: tuple[int, int]) -> int:
    return (curr[0] - prev[0]) * 12 + (curr[1] - prev[1])


def monthly_returns(
    dates: list[date],
    equity_curve: list[float],
) -> dict[str, float]:
    """Calendar-month simple returns from month-end equity levels.

    Sorts by date, groups by YYYY-MM using the last equity observation in each
    month, then returns ``(e_m / e_{m-1}) - 1`` keyed by the later month label
    **only when months are consecutive**. Gaps (e.g. missing February) are
    skipped so a multi-month move is never labeled as a single month. The first
    observed month is omitted (no prior month-end baseline).
    """
    if len(dates) != len(equity_curve):
        raise ValueError("dates and equity_curve must have the same length")
    if not dates:
        return {}

    ordered = sorted(zip(dates, equity_curve, strict=True), key=lambda row: row[0])
    month_end: dict[str, float] = {}
    for d, equity in ordered:
        key = f"{d.year:04d}-{d.month:02d}"
        month_end[key] = float(equity)

    keys = sorted(month_end.keys())
    if len(keys) < 2:
        return {}

    out: dict[str, float] = {}
    for i in range(1, len(keys)):
        prev_key = keys[i - 1]
        curr_key = keys[i]
        if _month_delta(_parse_year_month(prev_key), _parse_year_month(curr_key)) != 1:
            continue
        prev = month_end[prev_key]
        curr = month_end[curr_key]
        if prev == 0:
            continue
        out[curr_key] = (curr / prev) - 1.0
    return out


def metrics_from_equity(
    dates: list[date],
    equity_curve: list[float],
    *,
    trade_pnls: list[float] | None = None,
    trades_count: int | None = None,
) -> dict[str, float | int | dict[str, float]]:
    """Build the standard metric bundle from a dated equity curve."""
    if not dates or not equity_curve:
        raise ValueError("dates and equity_curve must be non-empty")
    if len(dates) != len(equity_curve):
        raise ValueError("dates and equity_curve must have the same length")
    pnls = list(trade_pnls or [])
    equity = equity_curve[-1]
    return {
        "total_return": equity - 1.0,
        "cagr": cagr(equity, dates[0], dates[-1]),
        "mdd": max_drawdown(equity_curve),
        "sharpe": sharpe_ratio(equity_curve),
        "sortino": sortino_ratio(equity_curve),
        "profit_factor": profit_factor(pnls),
        "win_rate": win_rate(pnls),
        "trades_count": int(trades_count if trades_count is not None else 0),
        "monthly_returns": monthly_returns(dates, equity_curve),
    }
