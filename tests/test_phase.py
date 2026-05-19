from __future__ import annotations

import unittest

from signal_forge import (
    Bar,
    PhaseConfig,
    PhaseRunner,
    Signal,
    Strategy,
    normalize_signal_reason,
    parse_phase_mode,
)


class OneEntryStrategy(Strategy):
    name = "one_entry"

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        return [
            Signal(index, bar.timestamp, 1.0 if index == 0 else 0.0, "entry")
            for index, bar in enumerate(bars)
        ]


class MessyReasonStrategy(Strategy):
    name = "messy_reason"

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        messy = "  \u9032\u5834\t\n  alpha  "
        return [
            Signal(index, bar.timestamp, 1.0 if index == 0 else 0.0, messy)
            for index, bar in enumerate(bars)
        ]


def sample_bars() -> list[Bar]:
    return [
        Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
        Bar("2026-01-02", 10, 11.5, 9.5, 11, 100),
    ]


class PhaseConfigTests(unittest.TestCase):
    def test_normalize_signal_reason_is_ascii_trimmed_single_line(self) -> None:
        self.assertEqual(normalize_signal_reason(""), "unknown")
        self.assertEqual(normalize_signal_reason("\r\n\t"), "unknown")
        self.assertEqual(
            normalize_signal_reason("  \u9032\u5834\t\n  alpha  "), "u9032u5834 alpha"
        )

    def test_normalize_signal_reason_truncates_long_input(self) -> None:
        self.assertEqual(normalize_signal_reason("a" * 200), "a" * 120)

    def test_backtest_mode_is_default(self) -> None:
        config = PhaseConfig()
        self.assertTrue(config.is_backtest)
        self.assertFalse(config.is_live)
        self.assertFalse(config.dry_run)

    def test_live_mode_is_dry_run_only(self) -> None:
        with self.assertRaises(ValueError):
            PhaseConfig(mode="live", dry_run=False)

    def test_backtest_mode_rejects_dry_run_true(self) -> None:
        with self.assertRaises(ValueError):
            PhaseConfig(mode="backtest", dry_run=True)

    def test_rejects_unknown_mode(self) -> None:
        with self.assertRaises(ValueError):
            PhaseConfig(mode="paper")  # type: ignore[arg-type]

    def test_rejects_invalid_hold_period(self) -> None:
        with self.assertRaises(ValueError):
            PhaseConfig(hold_bars_per_day=0)

    def test_parse_phase_mode_normalizes_valid_values(self) -> None:
        self.assertEqual(parse_phase_mode(" BACKTEST "), "backtest")
        self.assertEqual(parse_phase_mode("live"), "live")

    def test_parse_phase_mode_rejects_unknown_value(self) -> None:
        with self.assertRaises(ValueError):
            parse_phase_mode("paper")

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

    def test_phase_runner_normalizes_reasons_for_digest_and_intent(self) -> None:
        backtest = PhaseRunner().run(
            PhaseConfig(mode="backtest"),
            MessyReasonStrategy(),
            sample_bars(),
        )
        self.assertEqual(backtest.mode, "backtest")
        self.assertEqual(
            backtest.signal_digests[0].reason, "u9032u5834 alpha"  # type: ignore[index]
        )

        live = PhaseRunner().run(
            PhaseConfig(mode="live"),
            MessyReasonStrategy(),
            sample_bars(),
        )
        self.assertEqual(live.mode, "live")
        self.assertEqual(
            live.order_intents[0].reason, "u9032u5834 alpha"  # type: ignore[index]
        )

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
        self.assertIn("LIVE_DRY_RUN_ONLY", intent.safety_note)
        self.assertIn("no broker", intent.safety_note)
        self.assertIn("no api keys", intent.safety_note)
        self.assertIn("submitted=False", intent.safety_note)

    def test_phase_runner_rejects_missing_data_before_live_adapter(self) -> None:
        with self.assertRaisesRegex(ValueError, "no bars were loaded"):
            PhaseRunner().run(
                PhaseConfig(mode="live"),
                OneEntryStrategy(),
                [],
            )

    def test_phase_runner_rejects_insufficient_data_for_hold_period(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 3 bars are required"):
            PhaseRunner().run(
                PhaseConfig(mode="backtest", hold_bars_per_day=2),
                OneEntryStrategy(),
                sample_bars(),
            )


if __name__ == "__main__":
    unittest.main()
