from __future__ import annotations

from dataclasses import dataclass

from signal_forge.market_data import Bar
from signal_forge.strategy import Signal, Strategy


@dataclass(frozen=True)
class SignalCooldownStrategy(Strategy):
    base_strategy: Strategy
    cooldown_bars: int

    def __post_init__(self) -> None:
        """
        用途與流程：在 wrapper 建立後驗證冷卻期設定，避免 0 或負數讓進場防抖語意失效。
        參數：self 表示目前 SignalCooldownStrategy 實例，其中 cooldown_bars 必須是正整數 bar 數。
        回傳與錯誤：回傳 None；若 cooldown_bars 小於等於 0，拋出 ValueError。
        """
        if self.cooldown_bars <= 0:
            raise ValueError("cooldown_bars must be positive")

    @property
    def name(self) -> str:
        """
        用途與流程：組合包含冷卻期與底層策略名稱的穩定 strategy implementation 名稱。
        參數：self 表示目前 wrapper 實例，會讀取 cooldown_bars 與 base_strategy.name。
        回傳與錯誤：回傳 str；若底層策略名稱屬性不可用，會由 Python 屬性存取拋出例外。
        """
        return f"signal_cooldown_b{self.cooldown_bars}__{self.base_strategy.name}"

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        """
        用途與流程：先取得底層策略逐 bar 訊號，再只針對新的 long entry 加上冷卻期；已接受
        的持倉延續不會被強制平倉，flat/short 訊號也維持原狀。每次接受一個由非多單切換到
        long 的訊號後，後續 cooldown_bars 根 bar 內的新 long entry 會被改成 flat，藉此降低
        同一段行情反覆觸發 entry-edge 的 overlap。
        參數：bars 是已驗證並依時間排序的 OHLCV Bar 清單；self.base_strategy 必須回傳與 bars
        等長、index/timestamp 對齊的 Signal 清單；cooldown_bars 是接受 entry 後要封鎖的新進場
        bar 數。
        回傳與錯誤：回傳與 bars 等長的 Signal 清單；若底層策略輸出長度不等於 bars，拋出
        ValueError。
        """
        base_signals = self.base_strategy.generate_signals(bars)
        if len(base_signals) != len(bars):
            raise ValueError("base strategy must return exactly one signal per bar")

        cooled: list[Signal] = []
        cooldown_until_index = -1
        previous_adjusted_target = 0.0

        for signal in base_signals:
            is_new_long_entry = (
                signal.target_position > 0 and previous_adjusted_target <= 0
            )
            if is_new_long_entry and signal.index <= cooldown_until_index:
                adjusted = Signal(
                    signal.index,
                    signal.timestamp,
                    0.0,
                    "signal_cooldown_blocked",
                    signal.score,
                )
            else:
                adjusted = signal
                if is_new_long_entry:
                    cooldown_until_index = signal.index + self.cooldown_bars

            cooled.append(adjusted)
            previous_adjusted_target = adjusted.target_position

        return cooled
