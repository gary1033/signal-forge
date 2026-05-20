from __future__ import annotations

import unittest

from signal_forge import Bar, BarByBarStrategy, StrategyDecision


class CapturingStrategy(BarByBarStrategy[str]):
    name = "capturing"

    def __init__(self) -> None:
        """
        用途與流程：初始化測試替身物件，保存 fixture 或測試案例需要的輸入資料。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        self.previous_targets: list[float] = []
        self.contexts: list[str] = []

    def prepare_context(self, bars: list[Bar]) -> str:
        """
        用途與流程：預先計算策略決策會重複使用的技術指標或中介資料，避免逐 bar 重複計算。
        參數：self 表示目前物件實例；bars（list[Bar]）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        return "prepared"

    def decide_bar(
        self,
        *,
        index: int,
        bar: Bar,
        bars: list[Bar],
        context: str,
        previous_target_position: float,
    ) -> StrategyDecision:
        """
        用途與流程：針對單一 bar 與前一根目標部位做策略判斷，輸出 target position、reason 與 score。
        參數：self 表示目前物件實例；index（int）由呼叫端傳入，需符合函式 contract；bar（Bar）由呼叫端傳入，需符合函式 contract；bars（list[Bar]）由呼叫端傳入，需符合函式 contract；context（str）由呼叫端傳入，需符合函式 contract；previous_target_position（float）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 StrategyDecision；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        self.previous_targets.append(previous_target_position)
        self.contexts.append(context)
        return StrategyDecision(float(index + 1), f"bar_{index}", float(index) / 10.0)


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
    ]


class StrategyTemplateTests(unittest.TestCase):
    def test_bar_by_bar_strategy_returns_one_aligned_signal_per_bar(self) -> None:
        """
        用途與流程：驗證 bar by bar strategy returns one aligned signal per bar 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = CapturingStrategy()

        signals = strategy.generate_signals(sample_bars())

        self.assertEqual(len(signals), 3)
        self.assertEqual([signal.index for signal in signals], [0, 1, 2])
        self.assertEqual(
            [signal.timestamp for signal in signals],
            ["2026-01-01", "2026-01-02", "2026-01-03"],
        )
        self.assertEqual([signal.reason for signal in signals], ["bar_0", "bar_1", "bar_2"])
        self.assertEqual([signal.target_position for signal in signals], [1.0, 2.0, 3.0])
        self.assertEqual([signal.score for signal in signals], [0.0, 0.1, 0.2])

    def test_bar_by_bar_strategy_passes_previous_target_position_to_hook(self) -> None:
        """
        用途與流程：驗證 bar by bar strategy passes previous target position to hook 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = CapturingStrategy()

        strategy.generate_signals(sample_bars())

        self.assertEqual(strategy.previous_targets, [0.0, 1.0, 2.0])
        self.assertEqual(strategy.contexts, ["prepared", "prepared", "prepared"])


if __name__ == "__main__":
    unittest.main()
