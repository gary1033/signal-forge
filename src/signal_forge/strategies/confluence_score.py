from __future__ import annotations

from dataclasses import dataclass

from signal_forge.indicators import rolling_vwap, rsi, sma
from signal_forge.market_data import Bar, closes, volumes
from signal_forge.strategy import BarByBarStrategy, StrategyDecision


@dataclass(frozen=True)
class ConfluenceScoreContext:
    fast: list[float | None]
    slow: list[float | None]
    rsi: list[float | None]
    vwap: list[float | None]
    avg_volume: list[float | None]
    volume: list[float]


@dataclass(frozen=True)
class ConfluenceScoreStrategy(BarByBarStrategy[ConfluenceScoreContext]):
    fast_window: int = 20
    slow_window: int = 50
    rsi_window: int = 14
    vwap_window: int = 20
    threshold: float = 3.0
    allow_short: bool = True

    @property
    def name(self) -> str:
        """
        用途與流程：組合穩定的策略名稱，讓 CLI、artifact 與測試可追蹤實際參數與 wrapper。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        side = "long_short" if self.allow_short else "long_only"
        return f"confluence_score_{side}"

    def prepare_context(self, bars: list[Bar]) -> ConfluenceScoreContext:
        """
        用途與流程：預先計算策略決策會重複使用的技術指標或中介資料，避免逐 bar 重複計算。
        參數：self 表示目前物件實例；bars（list[Bar]）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 ConfluenceScoreContext；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        close_values = closes(bars)
        volume_values = volumes(bars)
        return ConfluenceScoreContext(
            fast=sma(close_values, self.fast_window),
            slow=sma(close_values, self.slow_window),
            rsi=rsi(close_values, self.rsi_window),
            vwap=rolling_vwap(close_values, volume_values, self.vwap_window),
            avg_volume=sma(volume_values, self.fast_window),
            volume=volume_values,
        )

    def decide_bar(
        self,
        *,
        index: int,
        bar: Bar,
        bars: list[Bar],
        context: ConfluenceScoreContext,
        previous_target_position: float,
    ) -> StrategyDecision:
        """
        用途與流程：針對單一 bar 與前一根目標部位做策略判斷，輸出 target position、reason 與 score。
        參數：self 表示目前物件實例；index（int）由呼叫端傳入，需符合函式 contract；bar（Bar）由呼叫端傳入，需符合函式 contract；bars（list[Bar]）由呼叫端傳入，需符合函式 contract；context（ConfluenceScoreContext）由呼叫端傳入，需符合函式 contract；previous_target_position（float）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 StrategyDecision；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        fast = context.fast[index]
        slow = context.slow[index]
        rsi_value = context.rsi[index]
        vwap = context.vwap[index]
        avg_volume = context.avg_volume[index]
        if (
            fast is None
            or slow is None
            or rsi_value is None
            or vwap is None
            or avg_volume is None
        ):
            return StrategyDecision(0.0, "warmup", 0.0)

        score = 0.0
        reasons: list[str] = []

        if fast > slow:
            score += 1.0
            reasons.append("trend_up")
        else:
            score -= 1.0
            reasons.append("trend_down")

        if bar.close > slow:
            score += 1.0
            reasons.append("above_slow_sma")
        else:
            score -= 1.0
            reasons.append("below_slow_sma")

        if bar.close > vwap:
            score += 1.0
            reasons.append("above_vwap")
        else:
            score -= 1.0
            reasons.append("below_vwap")

        if rsi_value >= 55:
            score += 1.0
            reasons.append("momentum_positive")
        elif rsi_value <= 45:
            score -= 1.0
            reasons.append("momentum_negative")

        if index > 0 and context.volume[index] > avg_volume:
            if bar.close >= bars[index - 1].close:
                score += 1.0
                reasons.append("volume_confirms_up")
            else:
                score -= 1.0
                reasons.append("volume_confirms_down")

        if score >= self.threshold:
            target = 1.0
        elif self.allow_short and score <= -self.threshold:
            target = -1.0
        else:
            target = 0.0

        reason = "+".join(reasons) if reasons else "neutral"
        return StrategyDecision(target, reason, score)
