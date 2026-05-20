from __future__ import annotations

import unittest

from signal_forge.indicators import rolling_vwap, rsi, sma


class IndicatorTests(unittest.TestCase):
    def test_sma_returns_none_until_window_is_ready(self) -> None:
        """
        用途與流程：驗證 sma returns none until window is ready 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        self.assertEqual(sma([1, 2, 3, 4], 3), [None, None, 2.0, 3.0])

    def test_rolling_vwap_uses_volume_weights(self) -> None:
        """
        用途與流程：驗證 rolling vwap uses volume weights 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        values = rolling_vwap([10, 20, 30], [1, 3, 1], 2)
        self.assertEqual(values[0], None)
        self.assertAlmostEqual(values[1], 17.5)
        self.assertAlmostEqual(values[2], 22.5)

    def test_rsi_reaches_100_when_there_are_no_losses(self) -> None:
        """
        用途與流程：驗證 rsi reaches 100 when there are no losses 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        values = rsi([1, 2, 3, 4, 5], 3)
        self.assertEqual(values[:2], [None, None])
        self.assertEqual(values[-1], 100.0)


if __name__ == "__main__":
    unittest.main()

