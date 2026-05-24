from __future__ import annotations

from dataclasses import dataclass

from signal_forge.indicators import sma
from signal_forge.market_data import Bar, closes
from signal_forge.strategy import BarByBarStrategy, StrategyDecision


@dataclass(frozen=True)
class AbsoluteMomentumContext:
    close_values: list[float]
    trend_sma: list[float | None]


@dataclass(frozen=True)
class AbsoluteMomentumStrategy(BarByBarStrategy[AbsoluteMomentumContext]):
    momentum_window: int = 126
    trend_window: int = 200

    def __post_init__(self) -> None:
        """
        用途與流程：在策略建立後驗證動能回看期與趨勢均線視窗，避免回測時才出現不明確的除零或暖機錯誤。
        參數：self 是 dataclass 實例，包含 momentum_window 與 trend_window。
        回傳與錯誤：回傳 None；任一視窗小於等於 0 時拋出 ValueError。
        """
        if self.momentum_window <= 0:
            raise ValueError("momentum_window must be positive")
        if self.trend_window <= 0:
            raise ValueError("trend_window must be positive")

    @property
    def name(self) -> str:
        """
        用途與流程：組合穩定策略名稱，把動能回看期與趨勢均線視窗寫進 artifact，方便跨回測比較。
        參數：self 是目前 AbsoluteMomentumStrategy 實例。
        回傳與錯誤：回傳 str；此 property 不會額外丟錯。
        """
        return (
            f"absolute_momentum_m{self.momentum_window}_"
            f"sma{self.trend_window}_long_only"
        )

    def prepare_context(self, bars: list[Bar]) -> AbsoluteMomentumContext:
        """
        用途與流程：預先擷取 close 序列並計算長期趨勢 SMA，供逐 bar 判斷重複使用。
        參數：bars 是已載入且通過上游 OHLCV 驗證的 K 線清單。
        回傳與錯誤：回傳 AbsoluteMomentumContext；若 trend_window 非正數，會由 sma 拋出 ValueError。
        """
        close_values = closes(bars)
        return AbsoluteMomentumContext(
            close_values=close_values,
            trend_sma=sma(close_values, self.trend_window),
        )

    def decide_bar(
        self,
        *,
        index: int,
        bar: Bar,
        bars: list[Bar],
        context: AbsoluteMomentumContext,
        previous_target_position: float,
    ) -> StrategyDecision:
        """
        用途與流程：用絕對動能與長期趨勢濾網決定單根 bar 的 long-only target position。
        參數：index 是目前 bar 位置；bar 是目前 K 線；bars 保留模板共用介面但此策略不直接使用；context 包含 close 序列與 trend SMA；previous_target_position 保留模板共用介面但本策略由當前狀態直接決定 target。
        回傳與錯誤：回傳 StrategyDecision；暖機期、非正動能或趨勢濾網未通過時 target 為 0，兩條件都通過時 target 為 1。
        """
        trend = context.trend_sma[index]
        if index < self.momentum_window or trend is None:
            return StrategyDecision(0.0, "warmup", 0.0)

        previous_close = context.close_values[index - self.momentum_window]
        if previous_close <= 0:
            return StrategyDecision(0.0, "invalid_momentum_reference", 0.0)

        momentum_return = (bar.close / previous_close) - 1.0
        if momentum_return <= 0.0:
            return StrategyDecision(0.0, "absolute_momentum_negative", momentum_return)
        if bar.close <= trend:
            return StrategyDecision(0.0, "trend_filter_blocked", momentum_return)
        return StrategyDecision(1.0, "absolute_momentum_long", momentum_return)
