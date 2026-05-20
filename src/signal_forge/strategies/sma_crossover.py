from __future__ import annotations

from dataclasses import dataclass

from signal_forge.indicators import sma
from signal_forge.market_data import Bar, closes
from signal_forge.strategy import BarByBarStrategy, StrategyDecision


@dataclass(frozen=True)
class SmaCrossoverContext:
    fast: list[float | None]
    slow: list[float | None]


@dataclass(frozen=True)
class SmaCrossoverStrategy(BarByBarStrategy[SmaCrossoverContext]):
    fast_window: int = 20
    slow_window: int = 200
    allow_short: bool = False

    @property
    def name(self) -> str:
        side = "long_short" if self.allow_short else "long_only"
        return f"sma_{self.fast_window}_{self.slow_window}_{side}"

    def prepare_context(self, bars: list[Bar]) -> SmaCrossoverContext:
        close_values = closes(bars)
        return SmaCrossoverContext(
            fast=sma(close_values, self.fast_window),
            slow=sma(close_values, self.slow_window),
        )

    def decide_bar(
        self,
        *,
        index: int,
        bar: Bar,
        bars: list[Bar],
        context: SmaCrossoverContext,
        previous_target_position: float,
    ) -> StrategyDecision:
        fast = context.fast[index]
        slow = context.slow[index]
        if fast is None or slow is None:
            return StrategyDecision(0.0, "warmup")
        if fast > slow:
            return StrategyDecision(1.0, "fast_sma_above_slow_sma")
        if self.allow_short:
            return StrategyDecision(-1.0, "fast_sma_below_slow_sma")
        return StrategyDecision(0.0, "fast_sma_below_slow_sma_flat")
