from __future__ import annotations

import unittest

from signal_forge import Bar, Signal, Strategy, VolumeFilteredStrategy


class StaticStrategy(Strategy):
    name = "static"

    def __init__(self, targets: list[float]) -> None:
        self.targets = targets

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        return [
            Signal(index, bar.timestamp, self.targets[index], f"target_{self.targets[index]}")
            for index, bar in enumerate(bars)
        ]


def bars_with_volumes(volumes: list[float]) -> list[Bar]:
    return [
        Bar(f"2026-01-{index + 1:02d}", 10, 11, 9, 10, volume)
        for index, volume in enumerate(volumes)
    ]


class VolumeFilteredStrategyTests(unittest.TestCase):
    def test_blocks_long_signal_during_volume_warmup(self) -> None:
        strategy = VolumeFilteredStrategy(StaticStrategy([1.0, 0.0]), volume_window=3)

        signals = strategy.generate_signals(bars_with_volumes([100, 100]))

        self.assertEqual(signals[0].target_position, 0.0)
        self.assertEqual(signals[0].reason, "volume_filter_warmup")
        self.assertEqual(signals[0].index, 0)
        self.assertEqual(signals[0].timestamp, "2026-01-01")

    def test_blocks_long_signal_below_relative_volume_threshold(self) -> None:
        strategy = VolumeFilteredStrategy(
            StaticStrategy([0.0, 1.0, 0.0]),
            volume_window=2,
            volume_multiplier=1.2,
        )

        signals = strategy.generate_signals(bars_with_volumes([100, 100, 100]))

        self.assertEqual(signals[1].target_position, 0.0)
        self.assertEqual(signals[1].reason, "volume_filter_blocked")

    def test_keeps_long_signal_when_volume_passes_threshold(self) -> None:
        strategy = VolumeFilteredStrategy(
            StaticStrategy([0.0, 1.0, 0.0]),
            volume_window=2,
            volume_multiplier=1.2,
        )

        signals = strategy.generate_signals(bars_with_volumes([100, 200, 100]))

        self.assertEqual(signals[1].target_position, 1.0)
        self.assertEqual(signals[1].reason, "target_1.0")

    def test_keeps_flat_signal_flat(self) -> None:
        strategy = VolumeFilteredStrategy(
            StaticStrategy([0.0, 0.0, 0.0]),
            volume_window=2,
            volume_multiplier=1.2,
        )

        signals = strategy.generate_signals(bars_with_volumes([100, 200, 100]))

        self.assertEqual([signal.target_position for signal in signals], [0.0, 0.0, 0.0])
        self.assertEqual([signal.reason for signal in signals], ["target_0.0"] * 3)

    def test_preserves_signal_count_and_alignment(self) -> None:
        strategy = VolumeFilteredStrategy(
            StaticStrategy([0.0, 1.0, 0.0]),
            volume_window=2,
            volume_multiplier=1.2,
        )
        bars = bars_with_volumes([100, 200, 100])

        signals = strategy.generate_signals(bars)

        self.assertEqual(len(signals), len(bars))
        self.assertEqual([signal.index for signal in signals], [0, 1, 2])
        self.assertEqual([signal.timestamp for signal in signals], [bar.timestamp for bar in bars])

    def test_rejects_invalid_parameters(self) -> None:
        with self.assertRaisesRegex(ValueError, "volume_window must be positive"):
            VolumeFilteredStrategy(StaticStrategy([1.0]), volume_window=0)

        with self.assertRaisesRegex(ValueError, "volume_multiplier must be positive"):
            VolumeFilteredStrategy(StaticStrategy([1.0]), volume_multiplier=0)

    def test_name_is_stable(self) -> None:
        strategy = VolumeFilteredStrategy(
            StaticStrategy([1.0]),
            volume_window=20,
            volume_multiplier=1.2,
        )

        self.assertEqual(strategy.name, "volume_filter_w20_m1.20__static")


if __name__ == "__main__":
    unittest.main()
