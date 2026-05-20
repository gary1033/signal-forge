"""SignalForge 回測引擎與 entry-edge 評估工具。"""

from signal_forge.backtesting.backtester import BacktestConfig, BacktestResult, Backtester
from signal_forge.backtesting.entry_edge import (
    EntryEdgeComparisonResult,
    EntryEdgeConfig,
    EntryEdgeEvaluator,
    EntryEdgeResult,
    run_entry_edge_hold_comparison,
)

__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "Backtester",
    "EntryEdgeComparisonResult",
    "EntryEdgeConfig",
    "EntryEdgeEvaluator",
    "EntryEdgeResult",
    "run_entry_edge_hold_comparison",
]
