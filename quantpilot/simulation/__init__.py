"""Simulation orchestration: session loop, results, benchmarks."""

from quantpilot.simulation.benchmark import buy_and_hold_final_equity
from quantpilot.simulation.result import (
    DecisionRecord,
    EquityPoint,
    FillReject,
    SimResult,
)
from quantpilot.simulation.session import ProgressEvent, SimulationSession

__all__ = [
    "DecisionRecord",
    "EquityPoint",
    "FillReject",
    "ProgressEvent",
    "SimResult",
    "SimulationSession",
    "buy_and_hold_final_equity",
]
