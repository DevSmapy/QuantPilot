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
