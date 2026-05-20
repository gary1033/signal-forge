from __future__ import annotations

import unittest

from helpers import bars_from_closes
from signal_forge import BarByBarStrategy
from signal_forge.strategies import (
    ConfluenceScoreStrategy,
    SmaCrossoverStrategy,
    VwapReversionStrategy,
)


class StrategyRegressionTests(unittest.TestCase):
    def test_sma_crossover_contract_after_template_refactor(self) -> None:
        """
        用途與流程：驗證 sma crossover contract after template refactor 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = SmaCrossoverStrategy(fast_window=2, slow_window=3, allow_short=False)

        self.assertIsInstance(strategy, BarByBarStrategy)
        signals = strategy.generate_signals(bars_from_closes([10, 11, 12, 13, 14, 15]))

        self.assertEqual([signal.target_position for signal in signals], [0.0, 0.0, 1.0, 1.0, 1.0, 1.0])
        self.assertEqual(
            [signal.reason for signal in signals],
            [
                "warmup",
                "warmup",
                "fast_sma_above_slow_sma",
                "fast_sma_above_slow_sma",
                "fast_sma_above_slow_sma",
                "fast_sma_above_slow_sma",
            ],
        )
        self.assertEqual([signal.score for signal in signals], [0.0] * 6)

    def test_vwap_reversion_hold_state_survives_template_refactor(self) -> None:
        """
        用途與流程：驗證 vwap reversion hold state survives template refactor 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = VwapReversionStrategy(
            window=3,
            entry_z=0.5,
            exit_z=0.25,
            allow_short=False,
        )

        self.assertIsInstance(strategy, BarByBarStrategy)
        signals = strategy.generate_signals(bars_from_closes([10, 11, 12, 8, 9]))

        self.assertEqual(
            [signal.reason for signal in signals],
            [
                "warmup",
                "warmup",
                "hold",
                "price_below_vwap_band",
                "hold",
            ],
        )
        self.assertEqual(
            [signal.target_position for signal in signals],
            [0.0, 0.0, 0.0, 1.0, 1.0],
        )
        self.assertGreater(signals[3].score, 0.0)
        self.assertGreater(signals[4].score, 0.0)

    def test_vwap_regime_filter_blocks_new_long_entry_below_regime_sma(self) -> None:
        """
        用途與流程：驗證 VWAP regime filter 在 close 低於 regime SMA 時只阻擋新的 long entry。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = VwapReversionStrategy(
            window=3,
            entry_z=0.5,
            exit_z=0.25,
            allow_short=False,
            regime_filter=True,
            regime_window=3,
        )

        signals = strategy.generate_signals(bars_from_closes([10, 20, 8]))

        self.assertEqual(signals[2].target_position, 0.0)
        self.assertEqual(signals[2].reason, "regime_downtrend_blocked")
        self.assertGreater(signals[2].score, 0.0)

    def test_vwap_regime_filter_allows_long_entry_above_regime_sma(self) -> None:
        """
        用途與流程：驗證 VWAP regime filter 在 close 不低於 regime SMA 時保留原本跌深進場 reason。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = VwapReversionStrategy(
            window=3,
            entry_z=0.5,
            exit_z=0.25,
            allow_short=False,
            regime_filter=True,
            regime_window=3,
        )

        signals = strategy.generate_signals(
            bars_from_closes([20, 10, 15], volumes=[100, 1, 1])
        )

        self.assertEqual(signals[2].target_position, 1.0)
        self.assertEqual(signals[2].reason, "price_below_vwap_band")
        self.assertGreater(signals[2].score, 0.0)

    def test_vwap_regime_filter_does_not_force_exit_existing_long(self) -> None:
        """
        用途與流程：驗證 VWAP regime filter 只處理 entry，不會在已持有時因 close 低於 regime SMA 強制歸零。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = VwapReversionStrategy(
            window=3,
            entry_z=0.5,
            exit_z=0.25,
            allow_short=False,
            regime_filter=True,
            regime_window=3,
        )

        signals = strategy.generate_signals(
            bars_from_closes([20, 10, 15, 8], volumes=[100, 1, 1, 1])
        )

        self.assertEqual(signals[2].target_position, 1.0)
        self.assertEqual(signals[3].target_position, 1.0)
        self.assertEqual(signals[3].reason, "price_below_vwap_band")

    def test_confluence_score_contract_after_template_refactor(self) -> None:
        """
        用途與流程：驗證 confluence score contract after template refactor 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = ConfluenceScoreStrategy(
            fast_window=2,
            slow_window=3,
            rsi_window=2,
            vwap_window=2,
            threshold=3.0,
            allow_short=False,
        )

        signals = strategy.generate_signals(
            bars_from_closes([10, 11, 12], volumes=[100, 120, 150])
        )

        self.assertEqual([signal.target_position for signal in signals], [0.0, 0.0, 1.0])
        self.assertEqual(
            signals[2].reason,
            "trend_up+above_slow_sma+above_vwap+momentum_positive+volume_confirms_up",
        )
        self.assertEqual(signals[2].score, 5.0)


if __name__ == "__main__":
    unittest.main()
