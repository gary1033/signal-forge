from __future__ import annotations

import unittest

from signal_forge import Bar, BarByBarStrategy, StrategyDecision


class CapturingStrategy(BarByBarStrategy[str]):
    name = "capturing"

    def __init__(self) -> None:
        self.previous_targets: list[float] = []
        self.contexts: list[str] = []

    def prepare_context(self, bars: list[Bar]) -> str:
        return "prepared"

    def decide_bar(
        self,
        *,
        index: int,
        bar: Bar,
        bars: list[Bar],
        context: str,
        previous_target_position: float,
    ) -> StrategyDecision:
        self.previous_targets.append(previous_target_position)
        self.contexts.append(context)
        return StrategyDecision(float(index + 1), f"bar_{index}", float(index) / 10.0)


def sample_bars() -> list[Bar]:
    return [
        Bar("2026-01-01", 10, 11, 9, 10, 100),
        Bar("2026-01-02", 11, 12, 10, 11, 100),
        Bar("2026-01-03", 12, 13, 11, 12, 100),
    ]


class StrategyTemplateTests(unittest.TestCase):
    def test_bar_by_bar_strategy_returns_one_aligned_signal_per_bar(self) -> None:
        strategy = CapturingStrategy()

        signals = strategy.generate_signals(sample_bars())

        self.assertEqual(len(signals), 3)
        self.assertEqual([signal.index for signal in signals], [0, 1, 2])
        self.assertEqual(
            [signal.timestamp for signal in signals],
            ["2026-01-01", "2026-01-02", "2026-01-03"],
        )
        self.assertEqual([signal.reason for signal in signals], ["bar_0", "bar_1", "bar_2"])
        self.assertEqual([signal.target_position for signal in signals], [1.0, 2.0, 3.0])
        self.assertEqual([signal.score for signal in signals], [0.0, 0.1, 0.2])

    def test_bar_by_bar_strategy_passes_previous_target_position_to_hook(self) -> None:
        strategy = CapturingStrategy()

        strategy.generate_signals(sample_bars())

        self.assertEqual(strategy.previous_targets, [0.0, 1.0, 2.0])
        self.assertEqual(strategy.contexts, ["prepared", "prepared", "prepared"])


if __name__ == "__main__":
    unittest.main()
