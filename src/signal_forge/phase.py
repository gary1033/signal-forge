from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from signal_forge.entry_edge import EntryEdgeConfig, EntryEdgeEvaluator, EntryEdgeResult
from signal_forge.market_data import Bar, validate_bars
from signal_forge.strategy import Strategy


PhaseMode = Literal["backtest", "live"]
OrderSide = Literal["buy"]


def normalize_signal_reason(value: str) -> str:
    max_len = 120
    normalized = value.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    normalized = " ".join(normalized.split())
    if not normalized:
        return "unknown"

    out: list[str] = []
    for ch in normalized:
        if ch.isascii():
            out.append(ch)
            continue
        out.append(f"u{ord(ch):04x}")

    normalized = "".join(out).strip()
    if len(normalized) > max_len:
        normalized = normalized[:max_len].rstrip()
    return normalized or "unknown"


@dataclass(frozen=True)
class PhaseConfig:
    """Shared phase configuration for backtest and live dry-run modes."""

    mode: PhaseMode = "backtest"
    strategy: str = "sma-crossover"
    csv_path: str | Path | None = None
    output_dir: str | Path = "reports/generated"
    hold_bars_per_day: int = 1
    dry_run: bool | None = None

    def __post_init__(self) -> None:
        if self.mode not in {"backtest", "live"}:
            raise ValueError("mode must be either 'backtest' or 'live'")
        if self.hold_bars_per_day <= 0:
            raise ValueError("hold_bars_per_day must be positive")
        if self.mode == "live":
            if self.dry_run is False:
                raise ValueError(
                    "live mode is dry-run only until backtests are stable"
                )
            object.__setattr__(self, "dry_run", True)
            return

        if self.dry_run is True:
            raise ValueError("backtest mode must set dry_run=False")
        object.__setattr__(self, "dry_run", False)

    @property
    def is_backtest(self) -> bool:
        return self.mode == "backtest"

    @property
    def is_live(self) -> bool:
        return self.mode == "live"


@dataclass(frozen=True)
class OrderIntent:
    timestamp: str
    side: OrderSide
    target_position: float
    reason: str
    dry_run: bool = True
    submitted: bool = False
    safety_note: str = (
        "LIVE_DRY_RUN_ONLY: dry_run order intent only; no broker; no api keys; submitted=False"
    )


@dataclass(frozen=True)
class SignalDigest:
    index: int
    timestamp: str
    target_position: float
    position_change: float
    reason: str
    score: float
    is_long_entry: bool
    is_flatten: bool


@dataclass(frozen=True)
class PhaseExecutionResult:
    mode: PhaseMode
    adapter_name: str
    dry_run: bool
    entry_edge_result: EntryEdgeResult | None = None
    order_intents: list[OrderIntent] | None = None
    signal_digests: list[SignalDigest] | None = None


class BacktestExecutionAdapter:
    name = "backtest"

    def run(
        self, config: PhaseConfig, strategy: Strategy, bars: list[Bar]
    ) -> PhaseExecutionResult:
        signals = strategy.generate_signals(bars)
        if len(signals) != len(bars):
            raise ValueError("strategy must return exactly one signal per bar")

        result = EntryEdgeEvaluator(
            EntryEdgeConfig(hold_bars_per_day=config.hold_bars_per_day)
        ).run(strategy, bars)

        previous_target = 0.0
        epsilon = 1e-12
        digests: list[SignalDigest] = []
        for signal in signals:
            is_long_entry = signal.target_position > epsilon and previous_target <= epsilon
            is_flatten = signal.target_position <= epsilon and previous_target > epsilon
            position_change = signal.target_position - previous_target
            previous_target = signal.target_position
            digests.append(
                SignalDigest(
                    index=signal.index,
                    timestamp=signal.timestamp,
                    target_position=signal.target_position,
                    position_change=position_change,
                    reason=normalize_signal_reason(signal.reason),
                    score=signal.score,
                    is_long_entry=is_long_entry,
                    is_flatten=is_flatten,
                )
            )
        return PhaseExecutionResult(
            mode="backtest",
            adapter_name=self.name,
            dry_run=False,
            entry_edge_result=result,
            order_intents=[],
            signal_digests=digests,
        )


class LiveExecutionAdapter:
    name = "live"

    def run(
        self, config: PhaseConfig, strategy: Strategy, bars: list[Bar]
    ) -> PhaseExecutionResult:
        if not config.dry_run:
            raise ValueError("live mode is dry-run only until backtests are stable")

        signals = strategy.generate_signals(bars)
        if len(signals) != len(bars):
            raise ValueError("strategy must return exactly one signal per bar")

        order_intents: list[OrderIntent] = []
        previous_target = 0.0
        epsilon = 1e-12
        for signal in signals:
            is_long_entry = signal.target_position > epsilon and previous_target <= epsilon
            previous_target = signal.target_position
            if not is_long_entry:
                continue
            order_intents.append(
                OrderIntent(
                    timestamp=signal.timestamp,
                    side="buy",
                    target_position=signal.target_position,
                    reason=normalize_signal_reason(signal.reason),
                )
            )

        return PhaseExecutionResult(
            mode="live",
            adapter_name=self.name,
            dry_run=True,
            entry_edge_result=None,
            order_intents=order_intents,
        )


class PhaseRunner:
    def __init__(
        self,
        *,
        backtest_adapter: BacktestExecutionAdapter | None = None,
        live_adapter: LiveExecutionAdapter | None = None,
    ) -> None:
        self.backtest_adapter = backtest_adapter or BacktestExecutionAdapter()
        self.live_adapter = live_adapter or LiveExecutionAdapter()

    def run(
        self, config: PhaseConfig, strategy: Strategy, bars: list[Bar]
    ) -> PhaseExecutionResult:
        validation = validate_bars(bars, min_bars=config.hold_bars_per_day + 1)
        if not validation.is_valid:
            errors = "; ".join(validation.errors)
            raise ValueError(f"phase input data invalid: {errors}")

        if config.is_backtest:
            return self.backtest_adapter.run(config, strategy, bars)
        return self.live_adapter.run(config, strategy, bars)


def parse_phase_mode(value: str) -> PhaseMode:
    normalized = value.strip().lower()
    if normalized not in {"backtest", "live"}:
        raise ValueError("mode must be either 'backtest' or 'live'")
    return normalized  # type: ignore[return-value]
