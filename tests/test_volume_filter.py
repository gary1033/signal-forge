from __future__ import annotations

import unittest

from signal_forge import Bar, Signal, Strategy, VolumeFilteredStrategy


class StaticStrategy(Strategy):
    name = "static"

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


def bars_with_volumes(volumes: list[float]) -> list[Bar]:
    """
    用途與流程：建立帶有指定成交量路徑的 Bar fixture，方便驗證 volume filter 邊界。
    參數：volumes（list[float]）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 list[Bar]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    return [
        Bar(f"2026-01-{index + 1:02d}", 10, 11, 9, 10, volume)
        for index, volume in enumerate(volumes)
    ]


class VolumeFilteredStrategyTests(unittest.TestCase):
    def test_blocks_long_signal_during_volume_warmup(self) -> None:
        """
        用途與流程：驗證 blocks long signal during volume warmup 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = VolumeFilteredStrategy(StaticStrategy([1.0, 0.0]), volume_window=3)

        signals = strategy.generate_signals(bars_with_volumes([100, 100]))

        self.assertEqual(signals[0].target_position, 0.0)
        self.assertEqual(signals[0].reason, "volume_filter_warmup")
        self.assertEqual(signals[0].index, 0)
        self.assertEqual(signals[0].timestamp, "2026-01-01")

    def test_blocks_long_signal_below_relative_volume_threshold(self) -> None:
        """
        用途與流程：驗證 blocks long signal below relative volume threshold 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = VolumeFilteredStrategy(
            StaticStrategy([0.0, 1.0, 0.0]),
            volume_window=2,
            volume_multiplier=1.2,
        )

        signals = strategy.generate_signals(bars_with_volumes([100, 100, 100]))

        self.assertEqual(signals[1].target_position, 0.0)
        self.assertEqual(signals[1].reason, "volume_filter_blocked")

    def test_keeps_long_signal_when_volume_passes_threshold(self) -> None:
        """
        用途與流程：驗證 keeps long signal when volume passes threshold 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = VolumeFilteredStrategy(
            StaticStrategy([0.0, 1.0, 0.0]),
            volume_window=2,
            volume_multiplier=1.2,
        )

        signals = strategy.generate_signals(bars_with_volumes([100, 200, 100]))

        self.assertEqual(signals[1].target_position, 1.0)
        self.assertEqual(signals[1].reason, "target_1.0")

    def test_keeps_flat_signal_flat(self) -> None:
        """
        用途與流程：驗證 keeps flat signal flat 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = VolumeFilteredStrategy(
            StaticStrategy([0.0, 0.0, 0.0]),
            volume_window=2,
            volume_multiplier=1.2,
        )

        signals = strategy.generate_signals(bars_with_volumes([100, 200, 100]))

        self.assertEqual([signal.target_position for signal in signals], [0.0, 0.0, 0.0])
        self.assertEqual([signal.reason for signal in signals], ["target_0.0"] * 3)

    def test_preserves_signal_count_and_alignment(self) -> None:
        """
        用途與流程：驗證 preserves signal count and alignment 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = VolumeFilteredStrategy(
            StaticStrategy([0.0, 1.0, 0.0]),
            volume_window=2,
            volume_multiplier=1.2,
        )
        bars = bars_with_volumes([100, 200, 100])

        signals = strategy.generate_signals(bars)

        self.assertEqual(len(signals), len(bars))
        self.assertEqual([signal.index for signal in signals], [0, 1, 2])
        self.assertEqual([signal.timestamp for signal in signals], [bar.timestamp for bar in bars])

    def test_rejects_invalid_parameters(self) -> None:
        """
        用途與流程：驗證 rejects invalid parameters 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with self.assertRaisesRegex(ValueError, "volume_window must be positive"):
            VolumeFilteredStrategy(StaticStrategy([1.0]), volume_window=0)

        with self.assertRaisesRegex(ValueError, "volume_multiplier must be positive"):
            VolumeFilteredStrategy(StaticStrategy([1.0]), volume_multiplier=0)

    def test_name_is_stable(self) -> None:
        """
        用途與流程：驗證 name is stable 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = VolumeFilteredStrategy(
            StaticStrategy([1.0]),
            volume_window=20,
            volume_multiplier=1.2,
        )

        self.assertEqual(strategy.name, "volume_filter_w20_m1.20__static")


if __name__ == "__main__":
    unittest.main()
