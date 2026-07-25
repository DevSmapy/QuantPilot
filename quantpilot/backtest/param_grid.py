"""Small fixed-parameter grid runner (not an optimizer)."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import polars as pl

from quantpilot.backtest.engine import BacktestEngine, BacktestResult
from quantpilot.environment.costs import TradingCosts
from quantpilot.strategy.base import Strategy


@dataclass(frozen=True)
class ParamGridRow:
    """One fixed-parameter backtest within a small grid."""

    params: dict[str, Any]
    result: BacktestResult


def run_param_grid(
    prices: pl.DataFrame,
    *,
    strategy_factory: Callable[..., Strategy],
    param_grid: Sequence[Mapping[str, Any]],
    costs: TradingCosts | None = None,
) -> list[ParamGridRow]:
    """Run the same prices through a small list of fixed parameter sets.

    ``strategy_factory`` is called as ``strategy_factory(**params)`` for each
    mapping in ``param_grid``. This is an exhaustive fixed grid, not a search
    or optimizer.

    **Overfitting warning:** results are **full-sample** on ``prices``. Do not
    pick the best row here and feed those params into ``run_walk_forward`` as
    if they were out-of-sample. For OOS selection, grid only inside each fold's
    train window (nested) and evaluate on that fold's test slice.
    """
    if not param_grid:
        raise ValueError("param_grid must not be empty")

    engine = BacktestEngine()
    rows: list[ParamGridRow] = []
    for raw in param_grid:
        params = dict(raw)
        strategy = strategy_factory(**params)
        signals = strategy.run(prices)
        result = engine.run(prices, signals, costs=costs)
        rows.append(ParamGridRow(params=params, result=result))
    return rows
