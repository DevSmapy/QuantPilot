"""Backtesting engine."""

from quantpilot.backtest.engine import BacktestEngine, BacktestResult
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
=======
from quantpilot.backtest.param_grid import ParamGridRow, run_param_grid
>>>>>>> fda29b5 (feat(backtest): small fixed parameter grid helper)
from quantpilot.backtest.walk_forward import WalkForwardFold, run_walk_forward

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "ParamGridRow",
    "WalkForwardFold",
    "run_param_grid",
    "run_walk_forward",
]
=======

__all__ = ["BacktestEngine", "BacktestResult"]
>>>>>>> f860d31 (feat(backtest): metrics, richer result, TradingCosts)
=======
from quantpilot.backtest.walk_forward import WalkForwardFold, run_walk_forward

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "WalkForwardFold",
    "run_walk_forward",
]
>>>>>>> 90d13fb (feat(backtest): rolling OOS walk-forward helper)
