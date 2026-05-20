from __future__ import annotations

from dataclasses import dataclass

from signal_forge.backtesting.entry_edge import EntryEdgeResult
from signal_forge.core.signals import SignalDigest
from signal_forge.phase.config import PhaseMode
from signal_forge.phase.intents import OrderIntent


@dataclass(frozen=True)
class PhaseExecutionResult:
    mode: PhaseMode
    adapter_name: str
    dry_run: bool
    entry_edge_result: EntryEdgeResult | None = None
    order_intents: list[OrderIntent] | None = None
    signal_digests: list[SignalDigest] | None = None
