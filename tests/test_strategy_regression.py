from __future__ import annotations

import unittest

from signal_forge import Bar, BarByBarStrategy
from signal_forge.strategies import (
    ConfluenceScoreStrategy,
    SmaCrossoverStrategy,
    VwapReversionStrategy,
)


def bars_from_closes(closes: list[float], volumes: list[float] | None = None) -> list[Bar]:
    """
    用途與流程：依 close 價格序列建立一致的 Bar fixture，讓策略 regression 聚焦在訊號語意。
    參數：closes（list[float]）由呼叫端傳入，需符合函式 contract；volumes（list[float] | None）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 list[Bar]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    if volumes is None:
        volumes = [100.0 for _ in closes]
    return [
        Bar(
            f"2026-01-{index + 1:02d}",
            close,
            close + 1.0,
            close - 1.0,
            close,
            volumes[index],
        )
        for index, close in enumerate(closes)
    ]


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
