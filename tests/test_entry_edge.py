from __future__ import annotations

import unittest

from signal_forge import (
    Bar,
    EntryEdgeConfig,
    EntryEdgeEvaluator,
    Signal,
    Strategy,
    run_entry_edge_hold_comparison,
)


class StaticSignalStrategy(Strategy):
    name = "static_signal"

    def __init__(self, targets: list[float]) -> None:
        """
        用途與流程：初始化測試替身物件，保存 fixture 或測試案例需要的輸入資料。
        參數：self 表示目前物件實例；targets（list[float]）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        self.targets = targets

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        """
        用途與流程：在測試替身策略中產生固定 Signal 序列，讓測試可聚焦於被測流程而非策略細節。
        參數：self 表示目前物件實例；bars（list[Bar]）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 list[Signal]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        return [
            Signal(index, bar.timestamp, self.targets[index], f"target_{self.targets[index]}")
            for index, bar in enumerate(bars)
        ]


def bars_with_prices(prices: list[tuple[float, float]]) -> list[Bar]:
    """
    用途與流程：依測試案例建立帶有指定價格路徑的 Bar fixture，方便驗證進出場計算。
    參數：prices（list[tuple[float, float]]）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 list[Bar]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
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
        """
        用途與流程：驗證 enters next bar and exits after fixed hold 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
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
        """
        用途與流程：驗證 ignores short signals in pure long mode 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = bars_with_prices([(10, 10), (10, 11), (11, 11)])
        strategy = StaticSignalStrategy([-1.0, 0.0, 0.0])
        result = EntryEdgeEvaluator().run(strategy, bars)
        self.assertEqual(result.ignored_short_count, 1)
        self.assertEqual(result.trade_count, 0)
        self.assertEqual(result.decision, "fail")

    def test_finite_profit_factor_can_fail_threshold(self) -> None:
        """
        用途與流程：驗證 finite profit factor can fail threshold 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
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
        """
        用途與流程：驗證 all losing trades have zero profit factor 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = bars_with_prices([(10, 10), (10, 9), (9, 9)])
        strategy = StaticSignalStrategy([1.0, 0.0, 0.0])
        result = EntryEdgeEvaluator(
            EntryEdgeConfig(commission_bps=0, slippage_bps=0)
        ).run(strategy, bars)
        self.assertEqual(result.profit_factor, 0.0)
        self.assertEqual(result.profit_factor_status, "finite")
        self.assertEqual(result.decision, "fail")

    def test_transaction_tax_is_charged_on_exit_notional(self) -> None:
        """
        用途與流程：驗證 entry-edge 成本模型會把 commission/slippage 套用在進出場兩側，
        並把 transaction_tax_bps 額外套用在出場端 notional。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        bars = bars_with_prices([(10, 10), (10, 11), (11, 11)])
        strategy = StaticSignalStrategy([1.0, 0.0, 0.0])

        result = EntryEdgeEvaluator(
            EntryEdgeConfig(
                commission_bps=10,
                slippage_bps=5,
                transaction_tax_bps=30,
            )
        ).run(strategy, bars)

        self.assertEqual(result.trade_count, 1)
        self.assertAlmostEqual(result.trades[0].gross_pnl, 1000.0)
        self.assertAlmostEqual(result.trades[0].cost, 64.5)
        self.assertAlmostEqual(result.trades[0].net_pnl, 935.5)

    def test_result_includes_risk_adjusted_and_benchmark_metrics(self) -> None:
        """
        用途與流程：驗證 EntryEdgeResult 會固定輸出策略總報酬、風險調整指標與
        buy-and-hold benchmark 對照欄位，讓報表不用在下游重新計算。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        bars = bars_with_prices(
            [
                (10, 10),
                (10, 11),
                (11, 11),
                (10, 9),
                (10, 9),
                (10, 12),
                (10, 12),
            ]
        )
        strategy = StaticSignalStrategy([1.0, 0.0, 0.0, 1.0, 0.0, 1.0, 0.0])

        result = EntryEdgeEvaluator(
            EntryEdgeConfig(commission_bps=0, slippage_bps=0)
        ).run(strategy, bars)

        self.assertAlmostEqual(result.total_return, result.end_equity / 10000.0 - 1.0)
        self.assertIsNotNone(result.sharpe_ratio)
        self.assertIsNotNone(result.sortino_ratio)
        self.assertIn("2026-01", result.monthly_returns)
        self.assertIn("2026", result.yearly_returns)
        self.assertAlmostEqual(
            result.benchmark_excess_return,
            result.total_return - result.benchmark_total_return,
        )

    def test_failure_reason_is_ascii_and_deterministic(self) -> None:
        """
        用途與流程：驗證 failure reason is ascii and deterministic 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = bars_with_prices([(10, 10), (10, 11), (11, 11)])
        strategy = StaticSignalStrategy([-1.0, 0.0, 0.0])
        result = EntryEdgeEvaluator(EntryEdgeConfig(commission_bps=0, slippage_bps=0)).run(
            strategy, bars
        )
        self.assertEqual(result.decision, "fail")
        self.assertEqual(result.failure_reason, "No closed long-entry trades to evaluate.")

        flat_bars = bars_with_prices([(10, 10), (10, 10), (10, 10)])
        flat_strategy = StaticSignalStrategy([1.0, 0.0, 0.0])
        flat_result = EntryEdgeEvaluator(
            EntryEdgeConfig(commission_bps=0, slippage_bps=0)
        ).run(flat_strategy, flat_bars)
        self.assertEqual(flat_result.decision, "fail")
        self.assertEqual(flat_result.failure_reason, "No profitable closed trades.")

    def test_hold_comparison_preserves_requested_order(self) -> None:
        """
        用途與流程：驗證 hold comparison preserves requested order 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = bars_with_prices([(10, 10), (10, 12), (12, 15), (15, 15)])
        strategy = StaticSignalStrategy([1.0, 0.0, 0.0, 0.0])

        comparison = run_entry_edge_hold_comparison(
            strategy,
            bars,
            EntryEdgeConfig(commission_bps=0, slippage_bps=0),
            [2, 1],
        )

        self.assertEqual(comparison.strategy_name, "static_signal")
        self.assertEqual(comparison.hold_bars_per_day, (2, 1))
        self.assertEqual(
            [result.config.hold_bars_per_day for result in comparison.results],
            [2, 1],
        )
        self.assertEqual([result.trade_count for result in comparison.results], [1, 1])
        self.assertEqual([result.end_equity for result in comparison.results], [15000.0, 12000.0])


if __name__ == "__main__":
    unittest.main()
