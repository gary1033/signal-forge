from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from signal_forge.entry_edge import EntryEdgeConfig, EntryEdgeEvaluator, EntryEdgeResult
from signal_forge.market_data import Bar, validate_bars
from signal_forge.strategy import Strategy


PhaseMode = Literal["backtest", "live"]
OrderSide = Literal["buy"]


@dataclass(frozen=True)
class PhaseConfig:
    """Shared phase configuration for backtest and live dry-run modes."""

    mode: PhaseMode = "backtest"
    strategy: str = "sma-crossover"
    csv_path: str | Path | None = None
    output_dir: str | Path = "reports/generated"
    hold_bars_per_day: int = 1
    dry_run: bool = True

    def __post_init__(self) -> None:
        if self.mode not in {"backtest", "live"}:
            raise ValueError("mode must be either 'backtest' or 'live'")
        if self.hold_bars_per_day <= 0:
            raise ValueError("hold_bars_per_day must be positive")
        if self.mode == "live" and not self.dry_run:
            raise ValueError("live mode is dry-run only until backtests are stable")

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
    safety_note: str = "LIVE_DRY_RUN_ONLY: dry_run order intent only; 不送單"


@dataclass(frozen=True)
class PhaseExecutionResult:
    mode: PhaseMode
    adapter_name: str
    dry_run: bool
    entry_edge_result: EntryEdgeResult | None = None
    order_intents: list[OrderIntent] | None = None


class BacktestExecutionAdapter:
    name = "backtest"

    def run(
        self, config: PhaseConfig, strategy: Strategy, bars: list[Bar]
    ) -> PhaseExecutionResult:
        result = EntryEdgeEvaluator(
            EntryEdgeConfig(hold_bars_per_day=config.hold_bars_per_day)
        ).run(strategy, bars)
        return PhaseExecutionResult(
            mode="backtest",
            adapter_name=self.name,
            dry_run=False,
            entry_edge_result=result,
            order_intents=[],
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
        for signal in signals:
            is_long_entry = signal.target_position > 0 and previous_target <= 0
            previous_target = signal.target_position
            if not is_long_entry:
                continue
            order_intents.append(
                OrderIntent(
                    timestamp=signal.timestamp,
                    side="buy",
                    target_position=signal.target_position,
                    reason=signal.reason,
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
