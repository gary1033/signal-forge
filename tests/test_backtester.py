from __future__ import annotations

import unittest

from signal_forge import Backtester, Bar, Signal, Strategy
from signal_forge.strategies import SmaCrossoverStrategy, VwapReversionStrategy


class AlwaysLongStrategy(Strategy):
    name = "always_long"

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        return [
            Signal(index, bar.timestamp, 1.0 if index > 0 else 0.0, "test")
            for index, bar in enumerate(bars)
        ]


def sample_bars() -> list[Bar]:
    return [
        Bar("2026-01-01", 10, 11, 9, 10, 100),
        Bar("2026-01-02", 11, 12, 10, 11, 100),
        Bar("2026-01-03", 12, 13, 11, 12, 100),
        Bar("2026-01-04", 13, 14, 12, 13, 100),
        Bar("2026-01-05", 14, 15, 13, 14, 100),
        Bar("2026-01-06", 15, 16, 14, 15, 100),
    ]


class BacktesterTests(unittest.TestCase):
    def test_backtester_records_trades_and_equity_curve(self) -> None:
        result = Backtester().run(AlwaysLongStrategy(), sample_bars())
        self.assertEqual(result.strategy_name, "always_long")
        self.assertEqual(len(result.equity_curve), len(sample_bars()))
        self.assertEqual(result.trade_count, 1)
        self.assertGreater(result.end_equity, result.start_equity)

    def test_sma_strategy_returns_one_signal_per_bar(self) -> None:
        strategy = SmaCrossoverStrategy(fast_window=2, slow_window=3)
        signals = strategy.generate_signals(sample_bars())
        self.assertEqual(len(signals), len(sample_bars()))
        self.assertEqual(signals[0].reason, "warmup")
        self.assertEqual(signals[-1].target_position, 1.0)

    def test_vwap_strategy_can_emit_reversion_signal(self) -> None:
        bars = sample_bars() + [Bar("2026-01-07", 8, 9, 7, 8, 100)]
        strategy = VwapReversionStrategy(window=3, entry_z=0.5, allow_short=False)
        signals = strategy.generate_signals(bars)
        self.assertEqual(len(signals), len(bars))
        self.assertEqual(signals[-1].target_position, 1.0)


if __name__ == "__main__":
    unittest.main()

