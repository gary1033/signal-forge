"""SignalForge research toolkit."""

from signal_forge.backtester import Backtester, BacktestConfig, BacktestResult
from signal_forge.data_fetch import FetchDataResult, fetch_market_data
from signal_forge.entry_edge import (
    EntryEdgeComparisonResult,
    EntryEdgeConfig,
    EntryEdgeEvaluator,
    EntryEdgeResult,
    run_entry_edge_hold_comparison,
)
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
from signal_forge.strategy import BarByBarStrategy, Signal, Strategy, StrategyDecision
from signal_forge.strategies import (
    SUPPORTED_STRATEGY_NAMES,
    SignalCooldownStrategy,
    VolumeFilteredStrategy,
    build_phase1_strategy,
    build_strategy,
)

__all__ = [
    "Backtester",
    "BacktestConfig",
    "BacktestExecutionAdapter",
    "BacktestResult",
    "BarByBarStrategy",
    "Bar",
    "BarValidationResult",
    "EntryEdgeConfig",
    "EntryEdgeComparisonResult",
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
    "SUPPORTED_STRATEGY_NAMES",
    "Signal",
    "SignalCooldownStrategy",
    "Strategy",
    "StrategyDecision",
    "VolumeFilteredStrategy",
    "build_phase1_strategy",
    "build_strategy",
    "fetch_market_data",
    "load_bars_from_csv",
    "normalize_signal_reason",
    "parse_phase_mode",
    "run_entry_edge_hold_comparison",
    "validate_bars",
]
