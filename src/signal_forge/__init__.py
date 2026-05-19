"""SignalForge research toolkit."""

from signal_forge.backtester import Backtester, BacktestConfig, BacktestResult
from signal_forge.entry_edge import EntryEdgeConfig, EntryEdgeEvaluator, EntryEdgeResult
from signal_forge.market_data import (
    Bar,
    BarValidationResult,
    MarketDataValidationError,
    load_bars_from_csv,
    validate_bars,
)
from signal_forge.phase import (
    BacktestExecutionAdapter,
    LiveExecutionAdapter,
    OrderIntent,
    PhaseConfig,
    PhaseExecutionResult,
    PhaseMode,
    PhaseRunner,
    parse_phase_mode,
)
from signal_forge.strategy import Signal, Strategy

__all__ = [
    "Backtester",
    "BacktestConfig",
    "BacktestExecutionAdapter",
    "BacktestResult",
    "Bar",
    "BarValidationResult",
    "EntryEdgeConfig",
    "EntryEdgeEvaluator",
    "EntryEdgeResult",
    "LiveExecutionAdapter",
    "MarketDataValidationError",
    "OrderIntent",
    "PhaseConfig",
    "PhaseExecutionResult",
    "PhaseMode",
    "PhaseRunner",
    "Signal",
    "Strategy",
    "load_bars_from_csv",
    "parse_phase_mode",
    "validate_bars",
]
