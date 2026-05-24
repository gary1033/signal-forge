from __future__ import annotations

import unittest

from signal_forge import BacktestConfig, Backtester, Bar, Signal, Strategy
from signal_forge.strategies import SmaCrossoverStrategy, VwapReversionStrategy


class AlwaysLongStrategy(Strategy):
    name = "always_long"

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        """
        用途與流程：在測試替身策略中產生固定 Signal 序列，讓測試可聚焦於被測流程而非策略細節。
        參數：self 表示目前物件實例；bars（list[Bar]）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 list[Signal]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        return [
            Signal(index, bar.timestamp, 1.0 if index > 0 else 0.0, "test")
            for index, bar in enumerate(bars)
        ]


class EnterThenExitStrategy(Strategy):
    name = "enter_then_exit"

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        """
        用途與流程：產生先進場再出場的固定 target 序列，專門驗證 Backtester 的賣出端交易稅。
        參數：bars 是測試用 OHLCV 序列，至少需要三根。
        回傳與錯誤：回傳 list[Signal]；此測試替身不主動拋錯。
        """
        targets = [0.0, 1.0, 0.0]
        return [
            Signal(index, bar.timestamp, targets[index], "target")
            for index, bar in enumerate(bars)
        ]


def sample_bars() -> list[Bar]:
    """
    用途與流程：建立測試用 deterministic Bar 清單，讓不同測試共用穩定 OHLCV fixture。
    參數：無參數。
    回傳與錯誤：回傳 list[Bar]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
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
        """
        用途與流程：驗證 backtester records trades and equity curve 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        result = Backtester().run(AlwaysLongStrategy(), sample_bars())
        self.assertEqual(result.strategy_name, "always_long")
        self.assertEqual(len(result.equity_curve), len(sample_bars()))
        self.assertEqual(result.trade_count, 1)
        self.assertGreater(result.end_equity, result.start_equity)

    def test_backtester_applies_transaction_tax_when_reducing_exposure(self) -> None:
        """
        用途與流程：驗證一般 Backtester 在降低多單曝險時，會把 transaction_tax_bps 加到賣出端成本。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        result = Backtester(
            BacktestConfig(
                commission_bps=10,
                slippage_bps=5,
                transaction_tax_bps=30,
            )
        ).run(EnterThenExitStrategy(), sample_bars()[:3])

        self.assertEqual(result.trade_count, 2)
        self.assertAlmostEqual(result.trades[0].cost, 15.0)
        self.assertAlmostEqual(result.trades[1].cost, 49.0173, places=4)

    def test_sma_strategy_returns_one_signal_per_bar(self) -> None:
        """
        用途與流程：驗證 sma strategy returns one signal per bar 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = SmaCrossoverStrategy(fast_window=2, slow_window=3)
        signals = strategy.generate_signals(sample_bars())
        self.assertEqual(len(signals), len(sample_bars()))
        self.assertEqual(signals[0].reason, "warmup")
        self.assertEqual(signals[-1].target_position, 1.0)

    def test_vwap_strategy_can_emit_reversion_signal(self) -> None:
        """
        用途與流程：驗證 vwap strategy can emit reversion signal 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = sample_bars() + [Bar("2026-01-07", 8, 9, 7, 8, 100)]
        strategy = VwapReversionStrategy(window=3, entry_z=0.5, allow_short=False)
        signals = strategy.generate_signals(bars)
        self.assertEqual(len(signals), len(bars))
        self.assertEqual(signals[-1].target_position, 1.0)


if __name__ == "__main__":
    unittest.main()
