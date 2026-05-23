from __future__ import annotations

import unittest

from signal_forge import Bar, Signal, SignalCooldownStrategy, Strategy


class StaticStrategy(Strategy):
    name = "static"

    def __init__(self, targets: list[float]) -> None:
        """
        用途與流程：保存測試指定的 target_position 序列，讓冷卻 wrapper 測試不依賴真實策略。
        參數：targets 是每根 bar 對應的目標部位，長度需足以覆蓋測試 bars。
        回傳與錯誤：回傳 None；若後續 bars 長度超過 targets，generate_signals 會由索引存取拋出 IndexError。
        """
        self.targets = targets

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        """
        用途與流程：依 targets 產生與 bars 對齊的 deterministic Signal 清單。
        參數：bars 是測試 fixture K 線；self.targets[index] 代表該 bar 的 target_position。
        回傳與錯誤：回傳 list[Signal]；若 targets 長度不足，會拋出 IndexError。
        """
        return [
            Signal(index, bar.timestamp, self.targets[index], f"target_{self.targets[index]}", 2.0)
            for index, bar in enumerate(bars)
        ]


class ShortSignalStrategy(Strategy):
    name = "short_static"

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        """
        用途與流程：產生一組含 short 與 long 的固定訊號，驗證冷卻 wrapper 只處理新的 long entry。
        參數：bars 是測試 fixture K 線，至少需要三根。
        回傳與錯誤：回傳 list[Signal]；若 bars 較短，zip 會自然只回傳可對齊部分。
        """
        targets = [-1.0, 0.0, 1.0]
        return [
            Signal(index, bar.timestamp, target, f"target_{target}", 1.0)
            for index, (bar, target) in enumerate(zip(bars, targets))
        ]


class MismatchedStrategy(Strategy):
    name = "mismatched"

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        """
        用途與流程：故意回傳少於 bars 的 Signal 清單，測試 wrapper 會拒絕破壞逐 bar contract 的底層策略。
        參數：bars 是測試 fixture K 線，此替身不使用完整內容。
        回傳與錯誤：回傳單一 Signal；不主動拋錯。
        """
        return [Signal(0, bars[0].timestamp, 1.0, "entry")]


def bars(count: int) -> list[Bar]:
    """
    用途與流程：建立指定長度的簡單日線 Bar fixture，讓冷卻測試只關注 index 與 target_position。
    參數：count 是要建立的 bar 數，必須是非負整數。
    回傳與錯誤：回傳 list[Bar]；此 helper 不主動拋錯。
    """
    return [
        Bar(f"2026-01-{index + 1:02d}", 10, 11, 9, 10, 100)
        for index in range(count)
    ]


class SignalCooldownStrategyTests(unittest.TestCase):
    def test_blocks_new_long_entries_inside_cooldown(self) -> None:
        """
        用途與流程：驗證接受第一個 long entry 後，冷卻期內重新由 flat 切回 long 的訊號會被封鎖。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        strategy = SignalCooldownStrategy(
            StaticStrategy([1.0, 0.0, 1.0, 0.0, 1.0]),
            cooldown_bars=2,
        )

        signals = strategy.generate_signals(bars(5))

        self.assertEqual(
            [signal.target_position for signal in signals],
            [1.0, 0.0, 0.0, 0.0, 1.0],
        )
        self.assertEqual(signals[2].reason, "signal_cooldown_blocked")
        self.assertEqual(signals[2].score, 2.0)

    def test_keeps_existing_long_hold_without_force_flatten(self) -> None:
        """
        用途與流程：驗證冷卻期只封鎖新的 entry，不會把已接受後延續的 long 持倉強制改成 flat。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        strategy = SignalCooldownStrategy(
            StaticStrategy([1.0, 1.0, 0.0, 1.0]),
            cooldown_bars=2,
        )

        signals = strategy.generate_signals(bars(4))

        self.assertEqual(
            [signal.target_position for signal in signals],
            [1.0, 1.0, 0.0, 1.0],
        )

    def test_preserves_short_and_flat_signals(self) -> None:
        """
        用途與流程：驗證 wrapper 不處理 short/flat 訊號，只有新的 long entry 會啟動冷卻判斷。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        strategy = SignalCooldownStrategy(ShortSignalStrategy(), cooldown_bars=2)

        signals = strategy.generate_signals(bars(3))

        self.assertEqual(
            [signal.target_position for signal in signals],
            [-1.0, 0.0, 1.0],
        )

    def test_rejects_invalid_cooldown(self) -> None:
        """
        用途與流程：驗證 cooldown_bars 必須是正整數，避免 wrapper 被設定成無效防抖。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        with self.assertRaisesRegex(ValueError, "cooldown_bars must be positive"):
            SignalCooldownStrategy(StaticStrategy([1.0]), cooldown_bars=0)

    def test_rejects_mismatched_base_signal_count(self) -> None:
        """
        用途與流程：驗證底層策略若沒有回傳一根 bar 一個 signal，冷卻 wrapper 會拒絕產生不可靠結果。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        strategy = SignalCooldownStrategy(MismatchedStrategy(), cooldown_bars=2)

        with self.assertRaisesRegex(
            ValueError, "base strategy must return exactly one signal per bar"
        ):
            strategy.generate_signals(bars(2))

    def test_name_is_stable(self) -> None:
        """
        用途與流程：驗證 wrapper name 會穩定包含冷卻 bar 數與底層策略名稱，方便 artifact 追蹤。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        strategy = SignalCooldownStrategy(StaticStrategy([1.0]), cooldown_bars=10)

        self.assertEqual(strategy.name, "signal_cooldown_b10__static")


if __name__ == "__main__":
    unittest.main()
