from __future__ import annotations

import unittest

from signal_forge import Bar, Signal, Strategy
from signal_forge.strategies import DrawdownRiskOffStrategy


class AlwaysLongStrategy(Strategy):
    name = "always_long"

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        """
        用途與流程：測試替身策略，對每根 bar 都輸出 full-long，讓 drawdown risk-off
        測試只關注 wrapper 是否在回撤狀態下降曝險。
        參數：bars 是測試用 OHLCV 序列。
        回傳與錯誤：回傳與 bars 等長的 Signal 清單；此替身不主動拋錯。
        """
        return [
            Signal(index, bar.timestamp, 1.0, "base_long", 1.0)
            for index, bar in enumerate(bars)
        ]


class BadLengthStrategy(Strategy):
    name = "bad_length"

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        """
        用途與流程：測試替身策略，刻意回傳空清單以驗證 wrapper 會拒絕未對齊
        bars 的底層策略輸出。
        參數：bars 是測試用 OHLCV 序列。
        回傳與錯誤：永遠回傳空 Signal 清單；錯誤應由被測 wrapper 偵測。
        """
        return []


def drawdown_bars() -> list[Bar]:
    """
    用途與流程：建立 deterministic close 序列，使策略先遭遇超過 10% 的回撤、
    經過 risk-off 期間後重新進場，再因下一段跌幅重新觸發 risk-off。
    參數：無。
    回傳與錯誤：回傳七根 OHLCV Bar；不主動拋錯。
    """
    closes = [100.0, 100.0, 85.0, 70.0, 70.0, 70.0, 60.0]
    return [
        Bar(
            f"2026-01-0{index + 1}",
            close,
            close + 1.0,
            close - 1.0,
            close,
            100,
        )
        for index, close in enumerate(closes)
    ]


class DrawdownRiskOffStrategyTests(unittest.TestCase):
    def test_forces_flat_after_drawdown_then_rearms_after_standdown(self) -> None:
        """
        用途與流程：驗證 wrapper 在 proxy equity 回撤超過門檻時會把 nonzero target
        改為 flat，且 risk-off 結束後會重設本地 high-water mark 讓策略可重新進場。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；target sequence、reason 或名稱 contract 漂移時 assertion 失敗。
        """
        strategy = DrawdownRiskOffStrategy(
            AlwaysLongStrategy(),
            drawdown_threshold=0.10,
            risk_off_bars=2,
        )

        signals = strategy.generate_signals(drawdown_bars())

        self.assertEqual(strategy.name, "drawdown_risk_off_d10_b2__always_long")
        self.assertEqual(
            [signal.target_position for signal in signals],
            [1.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0],
        )
        self.assertEqual(signals[2].reason, "drawdown_risk_off")
        self.assertEqual(signals[5].reason, "base_long")
        self.assertEqual(signals[6].reason, "drawdown_risk_off")

    def test_preserves_flat_base_signals_while_risk_off_is_active(self) -> None:
        """
        用途與流程：驗證底層策略本來就是 flat 時，risk-off 期間不會改寫 reason，
        避免把底層 exit 或 stay-flat 語意誤記為 drawdown 觸發。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；flat signal 被錯誤改寫時 assertion 失敗。
        """

        class FlatAfterDropStrategy(Strategy):
            name = "flat_after_drop"

            def generate_signals(self, bars: list[Bar]) -> list[Signal]:
                """
                用途與流程：測試替身策略，前段維持 full-long，觸發回撤後自行輸出 flat，
                用來確認 wrapper 不會覆蓋既有 flat reason。
                參數：bars 是測試用 OHLCV 序列。
                回傳與錯誤：回傳與 bars 等長的 Signal 清單；不主動拋錯。
                """
                signals: list[Signal] = []
                for index, bar in enumerate(bars):
                    target = 0.0 if index >= 3 else 1.0
                    reason = "base_flat" if target == 0.0 else "base_long"
                    signals.append(Signal(index, bar.timestamp, target, reason, 1.0))
                return signals

        strategy = DrawdownRiskOffStrategy(
            FlatAfterDropStrategy(),
            drawdown_threshold=0.10,
            risk_off_bars=2,
        )

        signals = strategy.generate_signals(drawdown_bars())

        self.assertEqual(signals[2].reason, "drawdown_risk_off")
        self.assertEqual(signals[3].target_position, 0.0)
        self.assertEqual(signals[3].reason, "base_flat")

    def test_rejects_invalid_parameters_and_bad_base_signal_length(self) -> None:
        """
        用途與流程：驗證 wrapper 會拒絕不合法的 drawdown 參數，並拒絕違反 Strategy
        signal 對齊 contract 的底層策略。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；預期 ValueError 未發生時 assertion 失敗。
        """
        with self.assertRaisesRegex(ValueError, "drawdown_threshold"):
            DrawdownRiskOffStrategy(AlwaysLongStrategy(), drawdown_threshold=1.0)

        with self.assertRaisesRegex(ValueError, "risk_off_bars"):
            DrawdownRiskOffStrategy(AlwaysLongStrategy(), risk_off_bars=0)

        with self.assertRaisesRegex(ValueError, "exactly one signal per bar"):
            DrawdownRiskOffStrategy(BadLengthStrategy()).generate_signals(drawdown_bars())


if __name__ == "__main__":
    unittest.main()
