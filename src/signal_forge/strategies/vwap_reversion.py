from __future__ import annotations

from dataclasses import dataclass

from signal_forge.indicators import rolling_std, rolling_vwap
from signal_forge.market_data import Bar, closes, volumes
from signal_forge.strategy import Signal, Strategy


@dataclass(frozen=True)
class VwapReversionStrategy(Strategy):
    window: int = 20
    entry_z: float = 1.5
    exit_z: float = 0.25
    allow_short: bool = True

    @property
    def name(self) -> str:
        side = "long_short" if self.allow_short else "long_only"
        return f"vwap_reversion_{self.window}_{side}"

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        close_values = closes(bars)
        vwap_values = rolling_vwap(close_values, volumes(bars), self.window)
        std_values = rolling_std(close_values, self.window)
        signals: list[Signal] = []
        target = 0.0

        for index, bar in enumerate(bars):
            vwap = vwap_values[index]
            std = std_values[index]
            if vwap is None or std is None or std == 0:
                target = 0.0
                reason = "warmup"
                score = 0.0
            else:
                z_score = (bar.close - vwap) / std
                score = -z_score
                if z_score <= -self.entry_z:
                    target = 1.0
                    reason = "price_below_vwap_band"
                elif self.allow_short and z_score >= self.entry_z:
                    target = -1.0
                    reason = "price_above_vwap_band"
                elif abs(z_score) <= self.exit_z:
                    target = 0.0
                    reason = "price_reverted_to_vwap"
                else:
                    reason = "hold"

            signals.append(Signal(index, bar.timestamp, target, reason, score))

        return signals

