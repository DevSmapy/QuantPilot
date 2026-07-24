"""Simple long-only event-driven backtest engine."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import polars as pl

from quantpilot.environment.costs import TradingCosts
from quantpilot.providers.qseed_schema import QP_CLOSE, QP_DATE

from . import metrics


@dataclass(frozen=True)
class BacktestResult:
    """Summary metrics for a backtest run."""

    total_return: float
    cagr: float
    mdd: float
    sharpe: float
    sortino: float
    profit_factor: float
    win_rate: float
    trades_count: int
    start_date: str
    end_date: str
    equity_curve: list[float] = field(default_factory=list)
    trade_pnls: list[float] = field(default_factory=list)


class BacktestEngine:
    """Run a basic long-only backtest from price data and discrete signals."""

    def run(
        self,
        prices: pl.DataFrame,
        signals: pl.DataFrame,
        costs: TradingCosts | None = None,
    ) -> BacktestResult:
        """Compute performance metrics.

        Costs are a proportional equity haircut on entry and exit
        (``commission_rate + slippage_bps / 10_000``), not share-level fills.
        Prior-bar signals are executed to avoid same-bar look-ahead.
        """
        trading_costs = costs or TradingCosts()
        cost_rate = (
            trading_costs.commission_rate + trading_costs.slippage_bps / 10_000.0
        )
        if not math.isfinite(cost_rate) or cost_rate >= 1.0:
            raise ValueError(
                "combined cost_rate must be finite and < 1 "
                f"(got {cost_rate!r} from commission_rate + slippage_bps/1e4)"
            )

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
        trade_pnls: list[float] = []
        entry_basis: float | None = None

        for idx in range(1, len(closes)):
            # Execute prior-bar signals to avoid same-bar look-ahead.
            sig = signal_values[idx - 1]
            if sig == 1 and position == 0:
                position = 1
                trades_count += 1
                entry_basis = equity
                equity *= 1.0 - cost_rate
            elif sig == -1 and position == 1:
                position = 0
                trades_count += 1
                equity *= 1.0 - cost_rate
                if entry_basis is not None and entry_basis != 0:
                    trade_pnls.append((equity / entry_basis) - 1.0)
                entry_basis = None

            if position == 1 and closes[idx - 1] != 0:
                equity *= closes[idx] / closes[idx - 1]

            equity_curve.append(equity)

        total_return = equity - 1.0
        return BacktestResult(
            total_return=total_return,
            cagr=metrics.cagr(equity, dates[0], dates[-1]),
            mdd=metrics.max_drawdown(equity_curve),
            sharpe=metrics.sharpe_ratio(equity_curve),
            sortino=metrics.sortino_ratio(equity_curve),
            profit_factor=metrics.profit_factor(trade_pnls),
            win_rate=metrics.win_rate(trade_pnls),
            trades_count=trades_count,
            start_date=str(dates[0]),
            end_date=str(dates[-1]),
            equity_curve=equity_curve,
            trade_pnls=trade_pnls,
        )
