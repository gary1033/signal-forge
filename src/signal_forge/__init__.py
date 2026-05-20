"""SignalForge research toolkit."""

from signal_forge.backtester import Backtester, BacktestConfig, BacktestResult
from signal_forge.data_fetch import FetchDataResult, fetch_market_data
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
    normalize_signal_reason,
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
    "FetchDataResult",
    "LiveExecutionAdapter",
    "MarketDataValidationError",
    "OrderIntent",
    "PhaseConfig",
    "PhaseExecutionResult",
    "PhaseMode",
    "PhaseRunner",
    "Signal",
    "Strategy",
    "fetch_market_data",
    "load_bars_from_csv",
    "normalize_signal_reason",
    "parse_phase_mode",
    "validate_bars",
]
