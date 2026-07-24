"""Backtesting engine."""

from quantpilot.backtest.engine import BacktestEngine, BacktestResult
<<<<<<< HEAD
<<<<<<< HEAD
from quantpilot.backtest.walk_forward import WalkForwardFold, run_walk_forward

__all__ = [
    "BacktestEngine",
    "BacktestResult",
    "WalkForwardFold",
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
