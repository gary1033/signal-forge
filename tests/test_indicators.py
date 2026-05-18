from __future__ import annotations

import unittest

from signal_forge.indicators import rolling_vwap, rsi, sma


class IndicatorTests(unittest.TestCase):
    def test_sma_returns_none_until_window_is_ready(self) -> None:
        self.assertEqual(sma([1, 2, 3, 4], 3), [None, None, 2.0, 3.0])

    def test_rolling_vwap_uses_volume_weights(self) -> None:
        values = rolling_vwap([10, 20, 30], [1, 3, 1], 2)
        self.assertEqual(values[0], None)
        self.assertAlmostEqual(values[1], 17.5)
        self.assertAlmostEqual(values[2], 22.5)

    def test_rsi_reaches_100_when_there_are_no_losses(self) -> None:
        values = rsi([1, 2, 3, 4, 5], 3)
        self.assertEqual(values[:2], [None, None])
        self.assertEqual(values[-1], 100.0)


if __name__ == "__main__":
    unittest.main()

