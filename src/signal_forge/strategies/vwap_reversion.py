from __future__ import annotations

from dataclasses import dataclass

from signal_forge.indicators import rolling_std, rolling_vwap
from signal_forge.market_data import Bar, closes, volumes
from signal_forge.strategy import BarByBarStrategy, StrategyDecision


@dataclass(frozen=True)
class VwapReversionContext:
    vwap: list[float | None]
    std: list[float | None]


@dataclass(frozen=True)
class VwapReversionStrategy(BarByBarStrategy[VwapReversionContext]):
    window: int = 20
    entry_z: float = 1.5
    exit_z: float = 0.25
    allow_short: bool = True

    @property
    def name(self) -> str:
        """
        用途與流程：組合穩定的策略名稱，讓 CLI、artifact 與測試可追蹤實際參數與 wrapper。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        side = "long_short" if self.allow_short else "long_only"
        return f"vwap_reversion_{self.window}_{side}"

    def prepare_context(self, bars: list[Bar]) -> VwapReversionContext:
        """
        用途與流程：預先計算策略決策會重複使用的技術指標或中介資料，避免逐 bar 重複計算。
        參數：self 表示目前物件實例；bars（list[Bar]）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 VwapReversionContext；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        close_values = closes(bars)
        return VwapReversionContext(
            vwap=rolling_vwap(close_values, volumes(bars), self.window),
            std=rolling_std(close_values, self.window),
        )

    def decide_bar(
        self,
        *,
        index: int,
        bar: Bar,
        bars: list[Bar],
        context: VwapReversionContext,
        previous_target_position: float,
    ) -> StrategyDecision:
        """
        用途與流程：針對單一 bar 與前一根目標部位做策略判斷，輸出 target position、reason 與 score。
        參數：self 表示目前物件實例；index（int）由呼叫端傳入，需符合函式 contract；bar（Bar）由呼叫端傳入，需符合函式 contract；bars（list[Bar]）由呼叫端傳入，需符合函式 contract；context（VwapReversionContext）由呼叫端傳入，需符合函式 contract；previous_target_position（float）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 StrategyDecision；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        vwap = context.vwap[index]
        std = context.std[index]
        if vwap is None or std is None or std == 0:
            return StrategyDecision(0.0, "warmup", 0.0)

        z_score = (bar.close - vwap) / std
        score = -z_score
        if z_score <= -self.entry_z:
            return StrategyDecision(1.0, "price_below_vwap_band", score)
        if self.allow_short and z_score >= self.entry_z:
            return StrategyDecision(-1.0, "price_above_vwap_band", score)
        if abs(z_score) <= self.exit_z:
            return StrategyDecision(0.0, "price_reverted_to_vwap", score)
        return StrategyDecision(previous_target_position, "hold", score)
