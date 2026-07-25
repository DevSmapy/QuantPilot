"""Rolling out-of-sample backtest helper (fixed parameters)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import polars as pl

from quantpilot.backtest import metrics as metrics_mod
from quantpilot.backtest.engine import BacktestEngine, BacktestResult
from quantpilot.environment.costs import TradingCosts
from quantpilot.providers.qseed_schema import QP_DATE
from quantpilot.strategy.base import Strategy


@dataclass(frozen=True)
class WalkForwardFold:
    """One rolling window: train dates are metadata only; test is executed."""

    train_start: date
    train_end: date
    test_start: date
    test_end: date
    result: BacktestResult


def _metric_float(
    bundle: dict[str, float | int | dict[str, float]],
    key: str,
) -> float:
    value = bundle[key]
    if isinstance(value, dict):
        raise TypeError(f"{key} must be numeric")
    return float(value)


def _metric_int(
    bundle: dict[str, float | int | dict[str, float]],
    key: str,
) -> int:
    value = bundle[key]
    if isinstance(value, dict):
        raise TypeError(f"{key} must be numeric")
    return int(value)


def _oos_result_from_extended(
    extended: BacktestResult,
    *,
    oos_dates: list[date],
) -> BacktestResult:
    """Drop the prepended continuity bar and renormalize OOS equity to 1.0."""
    if len(extended.equity_curve) != len(oos_dates) + 1:
        raise ValueError("extended equity curve length must be len(oos_dates) + 1")
    base = extended.equity_curve[0]
    if base == 0:
        raise ValueError("continuity equity base must be non-zero")
    equity = [value / base for value in extended.equity_curve[1:]]
    bundle = metrics_mod.metrics_from_equity(
        oos_dates,
        equity,
        trade_pnls=extended.trade_pnls,
        trades_count=extended.trades_count,
    )
    monthly = bundle["monthly_returns"]
    if not isinstance(monthly, dict):
        raise TypeError("monthly_returns must be a dict")
    return BacktestResult(
        total_return=_metric_float(bundle, "total_return"),
        cagr=_metric_float(bundle, "cagr"),
        mdd=_metric_float(bundle, "mdd"),
        sharpe=_metric_float(bundle, "sharpe"),
        sortino=_metric_float(bundle, "sortino"),
        profit_factor=_metric_float(bundle, "profit_factor"),
        win_rate=_metric_float(bundle, "win_rate"),
        trades_count=_metric_int(bundle, "trades_count"),
        start_date=str(oos_dates[0]),
        end_date=str(oos_dates[-1]),
        equity_curve=equity,
        trade_pnls=list(extended.trade_pnls),
        monthly_returns={str(k): float(v) for k, v in monthly.items()},
    )


def run_walk_forward(
    prices: pl.DataFrame,
    strategy: Strategy,
    *,
    train_bars: int,
    test_bars: int,
    step_bars: int,
    costs: TradingCosts | None = None,
) -> list[WalkForwardFold]:
    """Run fixed-parameter rolling OOS backtests.

    Signals are generated on train+test context so indicators warm up on
    pre-test history. The last train bar is prepended for **execution
    continuity** so a signal on the final train day can fill on the first
    test bar (prior-bar rule). Reported fold metrics cover the test window
    only (continuity bar stripped / equity renormalized).
    """
    if train_bars < 1 or test_bars < 1 or step_bars < 1:
        raise ValueError("train_bars, test_bars, and step_bars must be >= 1")

    frame = prices.sort(QP_DATE)
    n = frame.height
    engine = BacktestEngine()
    folds: list[WalkForwardFold] = []

    start = 0
    while True:
        train_end = start + train_bars
        test_end = train_end + test_bars
        if test_end > n:
            break

        train_slice = frame.slice(start, train_bars)
        test_slice = frame.slice(train_end, test_bars)
        context = pl.concat([train_slice, test_slice], how="vertical")
        context_signals = strategy.run(context)
        test_start_date = test_slice[QP_DATE][0]
        train_end_date = train_slice[QP_DATE][-1]
        test_signals = context_signals.filter(pl.col(QP_DATE) >= test_start_date)
        continuity_price = train_slice.tail(1)
        continuity_signal = context_signals.filter(pl.col(QP_DATE) == train_end_date)
        if continuity_signal.height != 1:
            raise ValueError("missing train-end signal for walk-forward continuity")

        extended_prices = pl.concat([continuity_price, test_slice], how="vertical")
        extended_signals = pl.concat([continuity_signal, test_signals], how="vertical")
        extended_result = engine.run(extended_prices, extended_signals, costs=costs)

        train_dates = train_slice[QP_DATE].to_list()
        test_dates = test_slice[QP_DATE].to_list()
        result = _oos_result_from_extended(extended_result, oos_dates=test_dates)
        folds.append(
            WalkForwardFold(
                train_start=train_dates[0],
                train_end=train_dates[-1],
                test_start=test_dates[0],
                test_end=test_dates[-1],
                result=result,
            )
        )
        start += step_bars

    return folds
