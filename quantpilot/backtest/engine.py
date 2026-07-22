"""Simple long-only event-driven backtest engine."""

from __future__ import annotations

import math
from dataclasses import dataclass

import polars as pl

from quantpilot.providers.qseed_schema import QP_CLOSE, QP_DATE


@dataclass(frozen=True)
class BacktestResult:
    """Summary metrics for a backtest run."""

    total_return: float
    cagr: float
    mdd: float
    sharpe: float
    trades_count: int
    start_date: str
    end_date: str


class BacktestEngine:
    """Run a basic long-only backtest from price data and discrete signals."""

    def run(self, prices: pl.DataFrame, signals: pl.DataFrame) -> BacktestResult:
        """Compute performance metrics. Fees and slippage are zero in MVP."""
        merged = prices.join(signals.select(QP_DATE, "signal"), on=QP_DATE, how="inner")
        if merged.is_empty():
            raise ValueError("No overlapping dates between prices and signals")

        merged = merged.sort(QP_DATE)
        dates = merged[QP_DATE].to_list()
        closes = merged[QP_CLOSE].cast(pl.Float64).to_list()
        signal_values = merged["signal"].to_list()

        position = 0
        equity = 1.0
        equity_curve: list[float] = [equity]
        trades_count = 0

        for idx in range(1, len(closes)):
            daily_return = 0.0
            if position == 1 and closes[idx - 1] != 0:
                daily_return = (closes[idx] / closes[idx - 1]) - 1.0
                equity *= 1.0 + daily_return

            sig = signal_values[idx]
            if sig == 1 and position == 0:
                position = 1
                trades_count += 1
            elif sig == -1 and position == 1:
                position = 0
                trades_count += 1

            equity_curve.append(equity)

        total_return = equity - 1.0
        years = max((dates[-1] - dates[0]).days / 365.25, 1 / 365.25)
        cagr = (equity ** (1 / years)) - 1.0 if equity > 0 else -1.0
        mdd = _max_drawdown(equity_curve)
        sharpe = _sharpe_ratio(equity_curve)

        return BacktestResult(
            total_return=total_return,
            cagr=cagr,
            mdd=mdd,
            sharpe=sharpe,
            trades_count=trades_count,
            start_date=str(dates[0]),
            end_date=str(dates[-1]),
        )


def _max_drawdown(equity_curve: list[float]) -> float:
    peak = equity_curve[0]
    max_dd = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            drawdown = (value / peak) - 1.0
            max_dd = min(max_dd, drawdown)
    return max_dd


def _sharpe_ratio(equity_curve: list[float]) -> float:
    if len(equity_curve) < 2:
        return 0.0

    returns = [
        (equity_curve[i] / equity_curve[i - 1]) - 1.0
        for i in range(1, len(equity_curve))
        if equity_curve[i - 1] != 0
    ]
    if not returns:
        return 0.0

    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    std_dev = math.sqrt(variance)
    if std_dev == 0:
        return 0.0

    return (mean_return / std_dev) * math.sqrt(252)
