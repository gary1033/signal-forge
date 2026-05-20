"""SignalForge 核心資料型別、指標與 strategy contract。"""

from signal_forge.core.indicators import ema, rolling_std, rolling_vwap, rsi, sma
from signal_forge.core.market_data import (
    Bar,
    BarValidationResult,
    MarketDataValidationError,
    closes,
    load_bars_from_csv,
    validate_bars,
    volumes,
)
from signal_forge.core.signals import (
    SignalDigest,
    build_signal_digests,
    generate_validated_signals,
    normalize_signal_reason,
)
from signal_forge.core.strategy import BarByBarStrategy, Signal, Strategy, StrategyDecision

__all__ = [
    "Bar",
    "BarByBarStrategy",
    "BarValidationResult",
    "MarketDataValidationError",
    "Signal",
    "SignalDigest",
    "Strategy",
    "StrategyDecision",
    "build_signal_digests",
    "closes",
    "ema",
    "generate_validated_signals",
    "load_bars_from_csv",
    "normalize_signal_reason",
    "rolling_std",
    "rolling_vwap",
    "rsi",
    "sma",
    "validate_bars",
    "volumes",
]
