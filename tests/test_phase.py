from __future__ import annotations

import unittest

from signal_forge import PhaseConfig, parse_phase_mode


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


if __name__ == "__main__":
    unittest.main()
