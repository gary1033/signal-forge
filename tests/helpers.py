from __future__ import annotations

from signal_forge import Bar, Signal, Strategy


class OneEntryStrategy(Strategy):
    name = "one_entry"

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        """
        用途與流程：在測試替身策略中產生第一根 bar 進場、後續歸零的 deterministic Signal 序列。
        參數：bars 是測試提供的 OHLCV fixture，需與輸出 signals 一對一對齊。
        回傳與錯誤：回傳 list[Signal]；此測試替身不主動丟錯。
        """
        return [
            Signal(index, bar.timestamp, 1.0 if index == 0 else 0.0, "entry")
            for index, bar in enumerate(bars)
        ]


class MessyReasonStrategy(Strategy):
    name = "messy_reason"

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        """
        用途與流程：產生含中文、tab 與換行的 reason，專門測試 reason normalization contract。
        參數：bars 是測試提供的 OHLCV fixture，需與輸出 signals 一對一對齊。
        回傳與錯誤：回傳 list[Signal]；此測試替身不主動丟錯。
        """
        messy = "  \u9032\u5834\t\n  alpha  "
        return [
            Signal(index, bar.timestamp, 1.0 if index == 0 else 0.0, messy)
            for index, bar in enumerate(bars)
        ]


class StatefulOneEntryStrategy(Strategy):
    name = "stateful_one_entry"

    def __init__(self) -> None:
        """
        用途與流程：初始化測試替身的呼叫計數，用來驗證 Phase backtest 不會重複呼叫 strategy。
        參數：無參數。
        回傳與錯誤：回傳 None；不會主動丟錯。
        """
        self.call_count = 0

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        """
        用途與流程：每次呼叫都把 call_count 寫入 reason，讓測試能偵測 artifacts 是否來自同一份 signals。
        參數：bars 是測試提供的 OHLCV fixture，需與輸出 signals 一對一對齊。
        回傳與錯誤：回傳 list[Signal]；此測試替身不主動丟錯。
        """
        self.call_count += 1
        reason = f"entry_call_{self.call_count}"
        return [
            Signal(index, bar.timestamp, 1.0 if index == 0 else 0.0, reason)
            for index, bar in enumerate(bars)
        ]


def sample_bars() -> list[Bar]:
    """
    用途與流程：建立通用 deterministic Bar 清單，供 phase、backtester 與 reporting 測試共用。
    參數：無參數。
    回傳與錯誤：回傳兩根 Bar；此 fixture 不會主動丟錯。
    """
    return [
        Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
        Bar("2026-01-02", 10, 11.5, 9.5, 11, 100),
    ]


def bars_from_closes(closes: list[float], volumes: list[float] | None = None) -> list[Bar]:
    """
    用途與流程：依 close 價格序列建立一致的 Bar fixture，讓策略 regression 聚焦在訊號語意。
    參數：closes 是收盤價序列；volumes 可選，None 時全部使用 100.0。
    回傳與錯誤：回傳 list[Bar]；volumes 長度不足時會由 list index 取值自然拋出 IndexError。
    """
    if volumes is None:
        volumes = [100.0 for _ in closes]
    return [
        Bar(
            f"2026-01-{index + 1:02d}",
            close,
            close + 1.0,
            close - 1.0,
            close,
            volumes[index],
        )
        for index, close in enumerate(closes)
    ]
