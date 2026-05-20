from __future__ import annotations

from dataclasses import dataclass

from signal_forge.indicators import rolling_std, rolling_vwap, sma
from signal_forge.market_data import Bar, closes, volumes
from signal_forge.strategy import BarByBarStrategy, StrategyDecision


@dataclass(frozen=True)
class VwapReversionContext:
    vwap: list[float | None]
    std: list[float | None]
    regime_sma: list[float | None]


@dataclass(frozen=True)
class VwapReversionStrategy(BarByBarStrategy[VwapReversionContext]):
    window: int = 20
    entry_z: float = 1.5
    exit_z: float = 0.25
    allow_short: bool = True
    regime_filter: bool = False
    regime_window: int = 50

    @property
    def name(self) -> str:
        """
        用途與流程：組合穩定的策略名稱，讓 CLI、artifact 與測試可追蹤實際參數與 wrapper。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        side = "long_short" if self.allow_short else "long_only"
        if self.regime_filter:
            return f"vwap_reversion_{self.window}_regime_sma{self.regime_window}_{side}"
        return f"vwap_reversion_{self.window}_{side}"

    def prepare_context(self, bars: list[Bar]) -> VwapReversionContext:
        """
        用途與流程：預先計算 rolling VWAP、rolling standard deviation 與可選 regime SMA，供逐 bar hook 判斷均值回歸訊號與趨勢環境。
        參數：self 表示目前物件實例；bars（list[Bar]）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 VwapReversionContext；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        close_values = closes(bars)
        return VwapReversionContext(
            vwap=rolling_vwap(close_values, volumes(bars), self.window),
            std=rolling_std(close_values, self.window),
            regime_sma=sma(close_values, self.regime_window),
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
        用途與流程：針對單一 bar 與前一根目標部位做策略判斷；可選 regime filter 只阻擋新 long entry，不強制平掉既有持倉。
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
            if self.regime_filter and previous_target_position <= 0:
                regime_sma = context.regime_sma[index]
                if regime_sma is None:
                    return StrategyDecision(0.0, "regime_warmup", score)
                if bar.close < regime_sma:
                    return StrategyDecision(0.0, "regime_downtrend_blocked", score)
            return StrategyDecision(1.0, "price_below_vwap_band", score)
        if self.allow_short and z_score >= self.entry_z:
            return StrategyDecision(-1.0, "price_above_vwap_band", score)
        if abs(z_score) <= self.exit_z:
            return StrategyDecision(0.0, "price_reverted_to_vwap", score)
        return StrategyDecision(previous_target_position, "hold", score)
