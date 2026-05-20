from __future__ import annotations

from dataclasses import dataclass

from signal_forge.indicators import sma
from signal_forge.market_data import Bar, volumes
from signal_forge.strategy import Signal, Strategy


@dataclass(frozen=True)
class VolumeFilteredStrategy(Strategy):
    base_strategy: Strategy
    volume_window: int = 20
    volume_multiplier: float = 1.2

    def __post_init__(self) -> None:
        """
        用途與流程：在 dataclass 建立後檢查設定值，將不合法或破壞安全邊界的輸入及早拒絕。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        if self.volume_window <= 0:
            raise ValueError("volume_window must be positive")
        if self.volume_multiplier <= 0:
            raise ValueError("volume_multiplier must be positive")

    @property
    def name(self) -> str:
        """
        用途與流程：組合穩定的策略名稱，讓 CLI、artifact 與測試可追蹤實際參數與 wrapper。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        return (
            f"volume_filter_w{self.volume_window}"
            f"_m{self.volume_multiplier:.2f}__{self.base_strategy.name}"
        )

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        """
        用途與流程：根據輸入 K 線序列產生逐 bar 對齊的 Signal 清單，維持策略輸出 contract。
        參數：self 表示目前物件實例；bars（list[Bar]）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 list[Signal]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        base_signals = self.base_strategy.generate_signals(bars)
        if len(base_signals) != len(bars):
            raise ValueError("base strategy must return exactly one signal per bar")

        average_volume = sma(volumes(bars), self.volume_window)
        filtered: list[Signal] = []

        for signal, bar, avg_volume in zip(base_signals, bars, average_volume):
            if signal.target_position <= 0:
                filtered.append(signal)
                continue

            if avg_volume is None:
                filtered.append(
                    Signal(
                        signal.index,
                        signal.timestamp,
                        0.0,
                        "volume_filter_warmup",
                        signal.score,
                    )
                )
                continue

            required_volume = avg_volume * self.volume_multiplier
            if bar.volume >= required_volume:
                filtered.append(signal)
                continue

            filtered.append(
                Signal(
                    signal.index,
                    signal.timestamp,
                    0.0,
                    "volume_filter_blocked",
                    signal.score,
                )
            )

        return filtered
