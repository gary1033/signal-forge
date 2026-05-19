from __future__ import annotations

import unittest

from signal_forge import Bar, EntryEdgeConfig, EntryEdgeEvaluator, Signal, Strategy


class StaticSignalStrategy(Strategy):
    name = "static_signal"

    def __init__(self, targets: list[float]) -> None:
        self.targets = targets

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        return [
            Signal(index, bar.timestamp, self.targets[index], f"target_{self.targets[index]}")
            for index, bar in enumerate(bars)
        ]


def bars_with_prices(prices: list[tuple[float, float]]) -> list[Bar]:
    return [
        Bar(
            f"2026-01-{index + 1:02d}",
            open_price,
            max(open_price, close_price) + 0.5,
            min(open_price, close_price) - 0.5,
            close_price,
            100,
        )
        for index, (open_price, close_price) in enumerate(prices)
    ]


class EntryEdgeTests(unittest.TestCase):
    def test_enters_next_bar_and_exits_after_fixed_hold(self) -> None:
        bars = bars_with_prices([(10, 10), (10, 12), (12, 12)])
        strategy = StaticSignalStrategy([1.0, 1.0, 0.0])
        result = EntryEdgeEvaluator(
            EntryEdgeConfig(commission_bps=0, slippage_bps=0)
        ).run(strategy, bars)
        self.assertEqual(result.trade_count, 1)
        self.assertEqual(result.trades[0].entry_timestamp, "2026-01-02")
        self.assertEqual(result.trades[0].exit_timestamp, "2026-01-02")
        self.assertGreater(result.trades[0].net_pnl, 0)
        self.assertEqual(result.decision, "pass")
        self.assertEqual(result.profit_factor_status, "infinite")

    def test_ignores_short_signals_in_pure_long_mode(self) -> None:
        bars = bars_with_prices([(10, 10), (10, 11), (11, 11)])
        strategy = StaticSignalStrategy([-1.0, 0.0, 0.0])
        result = EntryEdgeEvaluator().run(strategy, bars)
        self.assertEqual(result.ignored_short_count, 1)
        self.assertEqual(result.trade_count, 0)
        self.assertEqual(result.decision, "fail")

    def test_finite_profit_factor_can_fail_threshold(self) -> None:
        bars = bars_with_prices(
            [
                (10, 10),
                (10, 11),
                (11, 11),
                (10, 10),
                (10, 9),
                (9, 9),
            ]
        )
        strategy = StaticSignalStrategy([1.0, 0.0, 0.0, 1.0, 0.0, 0.0])
        result = EntryEdgeEvaluator(
            EntryEdgeConfig(commission_bps=0, slippage_bps=0, pass_profit_factor=1.2)
        ).run(strategy, bars)
        self.assertEqual(result.trade_count, 2)
        self.assertEqual(result.profit_factor_status, "finite")
        self.assertLess(result.profit_factor or 0.0, 1.2)
        self.assertEqual(result.decision, "fail")

    def test_all_losing_trades_have_zero_profit_factor(self) -> None:
        bars = bars_with_prices([(10, 10), (10, 9), (9, 9)])
        strategy = StaticSignalStrategy([1.0, 0.0, 0.0])
        result = EntryEdgeEvaluator(
            EntryEdgeConfig(commission_bps=0, slippage_bps=0)
        ).run(strategy, bars)
        self.assertEqual(result.profit_factor, 0.0)
        self.assertEqual(result.profit_factor_status, "finite")
        self.assertEqual(result.decision, "fail")


if __name__ == "__main__":
    unittest.main()
