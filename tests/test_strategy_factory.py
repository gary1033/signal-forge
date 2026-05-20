from __future__ import annotations

import unittest

from signal_forge.strategies import (
    SUPPORTED_STRATEGY_NAMES,
    ConfluenceScoreStrategy,
    SmaCrossoverStrategy,
    VolumeFilteredStrategy,
    VwapReversionStrategy,
    build_phase1_strategy,
    build_strategy,
)


class StrategyFactoryTests(unittest.TestCase):
    def test_supported_strategy_names_are_registry_backed(self) -> None:
        self.assertEqual(
            SUPPORTED_STRATEGY_NAMES,
            ("sma-crossover", "vwap-reversion", "confluence-score"),
        )
        self.assertIsInstance(build_phase1_strategy("sma-crossover"), SmaCrossoverStrategy)
        self.assertIsInstance(build_phase1_strategy("vwap-reversion"), VwapReversionStrategy)
        self.assertIsInstance(
            build_phase1_strategy("confluence-score"), ConfluenceScoreStrategy
        )

    def test_phase1_factory_builds_long_only_strategies(self) -> None:
        self.assertEqual(build_phase1_strategy("sma-crossover").name, "sma_20_200_long_only")
        self.assertEqual(
            build_phase1_strategy("vwap-reversion").name,
            "vwap_reversion_20_long_only",
        )
        self.assertEqual(
            build_phase1_strategy("confluence-score").name,
            "confluence_score_long_only",
        )

    def test_direct_factory_preserves_strategy_constructor_defaults(self) -> None:
        self.assertEqual(build_strategy("sma-crossover").name, "sma_20_200_long_only")
        self.assertEqual(
            build_strategy("vwap-reversion").name,
            "vwap_reversion_20_long_short",
        )
        self.assertEqual(
            build_strategy("confluence-score").name,
            "confluence_score_long_short",
        )

    def test_phase1_factory_can_wrap_volume_filter(self) -> None:
        strategy = build_phase1_strategy(
            "sma-crossover",
            fast_window=1,
            slow_window=2,
            volume_filter=True,
            volume_window=1,
            volume_multiplier=1.0,
        )

        self.assertIsInstance(strategy, VolumeFilteredStrategy)
        self.assertEqual(strategy.name, "volume_filter_w1_m1.00__sma_1_2_long_only")

    def test_rejects_unsupported_strategy_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported strategy unknown"):
            build_strategy("unknown")


if __name__ == "__main__":
    unittest.main()
