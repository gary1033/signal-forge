from __future__ import annotations

import unittest

from signal_forge import Bar, PhaseConfig, PhaseRunner, Signal, Strategy, parse_phase_mode


class OneEntryStrategy(Strategy):
    name = "one_entry"

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        return [
            Signal(index, bar.timestamp, 1.0 if index == 0 else 0.0, "entry")
            for index, bar in enumerate(bars)
        ]


def sample_bars() -> list[Bar]:
    return [
        Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
        Bar("2026-01-02", 10, 11.5, 9.5, 11, 100),
    ]


class PhaseConfigTests(unittest.TestCase):
    def test_backtest_mode_is_default(self) -> None:
        config = PhaseConfig()
        self.assertTrue(config.is_backtest)
        self.assertFalse(config.is_live)
        self.assertTrue(config.dry_run)

    def test_live_mode_is_dry_run_only(self) -> None:
        with self.assertRaises(ValueError):
            PhaseConfig(mode="live", dry_run=False)

    def test_rejects_unknown_mode(self) -> None:
        with self.assertRaises(ValueError):
            PhaseConfig(mode="paper")  # type: ignore[arg-type]

    def test_parse_phase_mode_normalizes_valid_values(self) -> None:
        self.assertEqual(parse_phase_mode(" BACKTEST "), "backtest")
        self.assertEqual(parse_phase_mode("live"), "live")

    def test_phase_runner_routes_backtest_to_entry_edge_adapter(self) -> None:
        result = PhaseRunner().run(
            PhaseConfig(mode="backtest"),
            OneEntryStrategy(),
            sample_bars(),
        )

        self.assertEqual(result.mode, "backtest")
        self.assertEqual(result.adapter_name, "backtest")
        self.assertFalse(result.dry_run)
        self.assertIsNotNone(result.entry_edge_result)
        self.assertEqual(result.entry_edge_result.trade_count, 1)

    def test_phase_runner_routes_live_to_dry_run_order_intent_only(self) -> None:
        result = PhaseRunner().run(
            PhaseConfig(mode="live"),
            OneEntryStrategy(),
            sample_bars(),
        )

        self.assertEqual(result.mode, "live")
        self.assertEqual(result.adapter_name, "live")
        self.assertTrue(result.dry_run)
        self.assertIsNone(result.entry_edge_result)
        self.assertEqual(len(result.order_intents or []), 1)
        intent = (result.order_intents or [])[0]
        self.assertTrue(intent.dry_run)
        self.assertFalse(intent.submitted)
        self.assertIn("不送單", intent.safety_note)


if __name__ == "__main__":
    unittest.main()
