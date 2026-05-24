from __future__ import annotations

import unittest

from signal_forge import Bar, Signal, Strategy
from signal_forge.strategies import VolatilityTargetStrategy


class AlwaysLongFromStartStrategy(Strategy):
    name = "always_long_from_start"

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        """
        用途與流程：測試替身策略，從第一根 bar 起固定輸出 full long，讓 volatility target 測試只關注曝險縮放。
        參數：bars 是測試用 OHLCV 序列。
        回傳與錯誤：回傳與 bars 等長的 full-long Signal 清單；此替身不主動拋錯。
        """
        return [
            Signal(index, bar.timestamp, 1.0, "base_long", 1.0)
            for index, bar in enumerate(bars)
        ]


class BadLengthStrategy(Strategy):
    name = "bad_length"

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        """
        用途與流程：測試替身策略，刻意回傳空 signals 以驗證 wrapper 會拒絕違反 Strategy contract 的底層策略。
        參數：bars 是測試用 OHLCV 序列。
        回傳與錯誤：永遠回傳空清單；不主動拋錯，錯誤應由被測 wrapper 偵測。
        """
        return []


def volatile_bars() -> list[Bar]:
    """
    用途與流程：建立含正負 10% close-to-close 報酬的 deterministic bar fixture，讓樣本波動與縮放倍率可手算。
    參數：無。
    回傳與錯誤：回傳四根 OHLCV Bar；不主動拋錯。
    """
    return [
        Bar("2026-01-01", 100, 101, 99, 100, 100),
        Bar("2026-01-02", 110, 111, 109, 110, 100),
        Bar("2026-01-03", 99, 100, 98, 99, 100),
        Bar("2026-01-04", 108.9, 110, 108, 108.9, 100),
    ]


class VolatilityTargetStrategyTests(unittest.TestCase):
    def test_scales_down_nonzero_target_after_realized_volatility_warmup(self) -> None:
        """
        用途與流程：驗證 wrapper 在樣本不足時維持 flat，樣本足夠後用 target volatility / realized volatility 把 long exposure 降到預期倍率。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；target position 或 reason contract 漂移時 assertion 失敗。
        """
        strategy = VolatilityTargetStrategy(
            AlwaysLongFromStartStrategy(),
            lookback_bars=2,
            target_annual_volatility=0.07071067811865475,
            periods_per_year=1,
            min_observations=2,
        )

        signals = strategy.generate_signals(volatile_bars())

        self.assertEqual([signal.target_position for signal in signals[:2]], [0.0, 0.0])
        self.assertEqual(signals[0].reason, "vol_target_warmup")
        self.assertAlmostEqual(signals[2].target_position, 0.5)
        self.assertEqual(signals[2].reason, "base_long_vol_target_scaled")

    def test_preserves_full_exposure_when_realized_volatility_is_below_target(self) -> None:
        """
        用途與流程：驗證 realized volatility 低於目標時 wrapper 不會超過 max_scale，也就是不加槓桿。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；若 wrapper 放大超過 1 或 reason 分類錯誤，assertion 失敗。
        """
        strategy = VolatilityTargetStrategy(
            AlwaysLongFromStartStrategy(),
            lookback_bars=2,
            target_annual_volatility=1.0,
            periods_per_year=1,
            min_observations=2,
            max_scale=1.0,
        )

        signals = strategy.generate_signals(volatile_bars())

        self.assertEqual(signals[2].target_position, 1.0)
        self.assertEqual(signals[2].reason, "base_long_vol_target_full")

    def test_rejects_invalid_parameters_and_bad_base_signal_length(self) -> None:
        """
        用途與流程：驗證 wrapper 會在建立時拒絕不合法風控參數，並在執行時拒絕違反 signal 對齊 contract 的底層策略。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；預期 ValueError 未發生時 assertion 失敗。
        """
        with self.assertRaisesRegex(ValueError, "max_scale"):
            VolatilityTargetStrategy(AlwaysLongFromStartStrategy(), max_scale=1.5)

        with self.assertRaisesRegex(ValueError, "exactly one signal per bar"):
            VolatilityTargetStrategy(BadLengthStrategy()).generate_signals(volatile_bars())


if __name__ == "__main__":
    unittest.main()
