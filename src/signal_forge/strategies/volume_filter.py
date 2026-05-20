from __future__ import annotations

from dataclasses import dataclass

from signal_forge.indicators import sma
from signal_forge.market_data import Bar, volumes
from signal_forge.strategy import Signal, Strategy


@dataclass(frozen=True)
class VolumeFilteredStrategy(Strategy):
    base_strategy: Strategy
    volume_window: int = 20
    volume_multiplier: float = 1.2

    def __post_init__(self) -> None:
        if self.volume_window <= 0:
            raise ValueError("volume_window must be positive")
        if self.volume_multiplier <= 0:
            raise ValueError("volume_multiplier must be positive")

    @property
    def name(self) -> str:
        return (
            f"volume_filter_w{self.volume_window}"
            f"_m{self.volume_multiplier:.2f}__{self.base_strategy.name}"
        )

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        base_signals = self.base_strategy.generate_signals(bars)
        if len(base_signals) != len(bars):
            raise ValueError("base strategy must return exactly one signal per bar")

        average_volume = sma(volumes(bars), self.volume_window)
        filtered: list[Signal] = []

        for signal, bar, avg_volume in zip(base_signals, bars, average_volume):
            if signal.target_position <= 0:
                filtered.append(signal)
                continue

            if avg_volume is None:
                filtered.append(
                    Signal(
                        signal.index,
                        signal.timestamp,
                        0.0,
                        "volume_filter_warmup",
                        signal.score,
                    )
                )
                continue

            required_volume = avg_volume * self.volume_multiplier
            if bar.volume >= required_volume:
                filtered.append(signal)
                continue

            filtered.append(
                Signal(
                    signal.index,
                    signal.timestamp,
                    0.0,
                    "volume_filter_blocked",
                    signal.score,
                )
            )

        return filtered
