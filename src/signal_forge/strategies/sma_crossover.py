from __future__ import annotations

from dataclasses import dataclass

from signal_forge.indicators import sma
from signal_forge.market_data import Bar, closes
from signal_forge.strategy import BarByBarStrategy, StrategyDecision


@dataclass(frozen=True)
class SmaCrossoverContext:
    fast: list[float | None]
    slow: list[float | None]


@dataclass(frozen=True)
class SmaCrossoverStrategy(BarByBarStrategy[SmaCrossoverContext]):
    fast_window: int = 20
    slow_window: int = 200
    allow_short: bool = False

    @property
    def name(self) -> str:
        """
        用途與流程：組合穩定的策略名稱，讓 CLI、artifact 與測試可追蹤實際參數與 wrapper。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        side = "long_short" if self.allow_short else "long_only"
        return f"sma_{self.fast_window}_{self.slow_window}_{side}"

    def prepare_context(self, bars: list[Bar]) -> SmaCrossoverContext:
        """
        用途與流程：預先計算策略決策會重複使用的技術指標或中介資料，避免逐 bar 重複計算。
        參數：self 表示目前物件實例；bars（list[Bar]）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 SmaCrossoverContext；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        close_values = closes(bars)
        return SmaCrossoverContext(
            fast=sma(close_values, self.fast_window),
            slow=sma(close_values, self.slow_window),
        )

    def decide_bar(
        self,
        *,
        index: int,
        bar: Bar,
        bars: list[Bar],
        context: SmaCrossoverContext,
        previous_target_position: float,
    ) -> StrategyDecision:
        """
        用途與流程：針對單一 bar 與前一根目標部位做策略判斷，輸出 target position、reason 與 score。
        參數：self 表示目前物件實例；index（int）由呼叫端傳入，需符合函式 contract；bar（Bar）由呼叫端傳入，需符合函式 contract；bars（list[Bar]）由呼叫端傳入，需符合函式 contract；context（SmaCrossoverContext）由呼叫端傳入，需符合函式 contract；previous_target_position（float）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 StrategyDecision；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        fast = context.fast[index]
        slow = context.slow[index]
        if fast is None or slow is None:
            return StrategyDecision(0.0, "warmup")
        if fast > slow:
            return StrategyDecision(1.0, "fast_sma_above_slow_sma")
        if self.allow_short:
            return StrategyDecision(-1.0, "fast_sma_below_slow_sma")
        return StrategyDecision(0.0, "fast_sma_below_slow_sma_flat")
