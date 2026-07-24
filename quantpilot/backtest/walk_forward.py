"""Rolling out-of-sample backtest helper (fixed parameters)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import polars as pl

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
    pre-test history, then only test-period signals are backtested. Train
    dates remain metadata (no in-sample optimization).
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
        test_signals = context_signals.filter(pl.col(QP_DATE) >= test_start_date)
        result = engine.run(test_slice, test_signals, costs=costs)

        train_dates = train_slice[QP_DATE].to_list()
        test_dates = test_slice[QP_DATE].to_list()
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
