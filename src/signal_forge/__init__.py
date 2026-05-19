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
from signal_forge.strategy import Signal, Strategy

__all__ = [
    "Backtester",
    "BacktestConfig",
    "BacktestResult",
    "Bar",
    "BarValidationResult",
    "EntryEdgeConfig",
    "EntryEdgeEvaluator",
    "EntryEdgeResult",
    "MarketDataValidationError",
    "Signal",
    "Strategy",
    "load_bars_from_csv",
    "validate_bars",
]
