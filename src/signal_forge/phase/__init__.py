"""Phase mode、adapter 與 runner 的 public API。"""

from signal_forge.core.signals import SignalDigest, normalize_signal_reason
from signal_forge.phase.adapters import BacktestExecutionAdapter, LiveExecutionAdapter
from signal_forge.phase.config import PhaseConfig, PhaseMode, parse_phase_mode
from signal_forge.phase.intents import OrderIntent, OrderSide
from signal_forge.phase.results import PhaseExecutionResult
from signal_forge.phase.runner import PhaseRunner

__all__ = [
    "BacktestExecutionAdapter",
    "LiveExecutionAdapter",
    "OrderIntent",
    "OrderSide",
    "PhaseConfig",
    "PhaseExecutionResult",
    "PhaseMode",
    "PhaseRunner",
    "SignalDigest",
    "normalize_signal_reason",
    "parse_phase_mode",
]
