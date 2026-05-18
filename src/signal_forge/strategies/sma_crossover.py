from __future__ import annotations

from dataclasses import dataclass

from signal_forge.indicators import sma
from signal_forge.market_data import Bar, closes
from signal_forge.strategy import Signal, Strategy


@dataclass(frozen=True)
class SmaCrossoverStrategy(Strategy):
    fast_window: int = 20
    slow_window: int = 200
    allow_short: bool = False

    @property
    def name(self) -> str:
        side = "long_short" if self.allow_short else "long_only"
        return f"sma_{self.fast_window}_{self.slow_window}_{side}"

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        close_values = closes(bars)
        fast = sma(close_values, self.fast_window)
        slow = sma(close_values, self.slow_window)
        signals: list[Signal] = []

        for index, bar in enumerate(bars):
            if fast[index] is None or slow[index] is None:
                target = 0.0
                reason = "warmup"
            elif fast[index] > slow[index]:
                target = 1.0
                reason = "fast_sma_above_slow_sma"
            elif self.allow_short:
                target = -1.0
                reason = "fast_sma_below_slow_sma"
            else:
                target = 0.0
                reason = "fast_sma_below_slow_sma_flat"

            signals.append(Signal(index, bar.timestamp, target, reason))

        return signals

