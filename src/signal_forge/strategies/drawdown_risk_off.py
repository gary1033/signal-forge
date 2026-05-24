from __future__ import annotations

from dataclasses import dataclass

from signal_forge.core.market_data import Bar
from signal_forge.core.strategy import Signal, Strategy


@dataclass(frozen=True)
class DrawdownRiskOffStrategy(Strategy):
    """
    用途與流程：包裝既有 target-state 策略，用策略層 proxy equity 追蹤單檔回撤，
    當高點回撤超過門檻時把非零 target_position 暫時降為 0，等待固定 bar 數後
    重新允許底層策略進場。這個 wrapper 用來驗證 per-symbol drawdown-state
    risk-off 是否能改善 Absolute Momentum 類策略的最大回撤。
    參數：base_strategy 是原始策略；drawdown_threshold 是觸發 risk-off 的高點回撤
    小數，例如 0.20 表示 -20%；risk_off_bars 是觸發後維持 flat 的 bar 數。
    回傳與錯誤：generate_signals 回傳與 bars 等長的 Signal 清單；門檻或 bar 數不合法、
    或底層策略未遵守一根 bar 一筆 signal contract 時拋出 ValueError。
    """

    base_strategy: Strategy
    drawdown_threshold: float = 0.20
    risk_off_bars: int = 60

    def __post_init__(self) -> None:
        """
        用途與流程：建立 wrapper 後先驗證 drawdown risk-off 參數，避免回測中途才暴露
        不可解釋的風控狀態。
        參數：self 是目前 DrawdownRiskOffStrategy 實例。
        回傳與錯誤：回傳 None；drawdown_threshold 不在 0 到 1 之間、或
        risk_off_bars 非正數時拋出 ValueError。
        """
        if self.drawdown_threshold <= 0 or self.drawdown_threshold >= 1:
            raise ValueError("drawdown_threshold must be between 0 and 1")
        if self.risk_off_bars <= 0:
            raise ValueError("risk_off_bars must be positive")

    @property
    def name(self) -> str:
        """
        用途與流程：產生包含回撤門檻、risk-off bar 數與底層策略名稱的穩定名稱，
        讓 target-state 報表可辨識這輪是否套用 drawdown-state 風控。
        參數：self 是目前 wrapper 實例。
        回傳與錯誤：回傳 ASCII 策略名稱；不會主動拋錯。
        """
        threshold_label = _format_percent_label(self.drawdown_threshold)
        return (
            f"drawdown_risk_off_d{threshold_label}_b{self.risk_off_bars}"
            f"__{self.base_strategy.name}"
        )

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        """
        用途與流程：先取得底層策略 signals，再以 Backtester 相同的 close-to-close
        target exposure 語意維護 proxy equity；若 proxy equity 自本地高點回撤超過
        drawdown_threshold，就在目前與後續 risk_off_bars 根 bar 將非零 target 改成 0。
        Risk-off 結束後會以當下 proxy equity 重設本地 high-water mark，避免 flat 期間
        因舊高點造成永久停用。
        參數：bars 是依時間排序的 OHLCV 序列；只使用目前 index 以前的 close 與已調整
        target，不讀未來資料。
        回傳與錯誤：回傳調整後 Signal 清單；若底層策略輸出長度與 bars 不一致，拋出
        ValueError。
        """
        base_signals = self.base_strategy.generate_signals(bars)
        if len(base_signals) != len(bars):
            raise ValueError("base strategy must return exactly one signal per bar")

        adjusted_signals: list[Signal] = []
        proxy_equity = 1.0
        peak_equity = 1.0
        proxy_position = 0.0
        risk_off_until_index = -1
        was_in_risk_off = False

        for index, signal in enumerate(base_signals):
            if index > 0:
                proxy_equity *= 1.0 + (
                    proxy_position * _close_to_close_return(bars, index)
                )

            if was_in_risk_off and index > risk_off_until_index:
                peak_equity = proxy_equity
                was_in_risk_off = False
            else:
                peak_equity = max(peak_equity, proxy_equity)

            drawdown = 0.0
            if peak_equity > 0:
                drawdown = (proxy_equity / peak_equity) - 1.0

            if drawdown <= -self.drawdown_threshold and index > risk_off_until_index:
                risk_off_until_index = index + self.risk_off_bars
                was_in_risk_off = True

            is_risk_off_active = index <= risk_off_until_index
            if is_risk_off_active and abs(signal.target_position) > 1e-12:
                adjusted = Signal(
                    signal.index,
                    signal.timestamp,
                    0.0,
                    "drawdown_risk_off",
                    signal.score,
                )
            else:
                adjusted = signal

            adjusted_signals.append(adjusted)
            if index > 0:
                proxy_position = adjusted.target_position

        return adjusted_signals


def _close_to_close_return(bars: list[Bar], index: int) -> float:
    """
    用途與流程：計算指定 index 的 close-to-close 報酬，對齊 Backtester 在第 index
    根 bar 先用既有 position 承擔前一根 close 到目前 close 的報酬，再套用目前 signal。
    參數：bars 是 OHLCV 序列；index 必須大於 0 且小於 bars 長度。
    回傳與錯誤：回傳浮點報酬；若前一根 close 非正數，回傳 0 以避免除零。
    """
    previous_close = bars[index - 1].close
    if previous_close <= 0:
        return 0.0
    return (bars[index].close / previous_close) - 1.0


def _format_percent_label(value: float) -> str:
    """
    用途與流程：把小數百分比轉成適合 strategy name 的短標籤，例如 0.20 轉成 20。
    參數：value 是 0 到 1 之間的小數。
    回傳與錯誤：回傳去除多餘 0 的 ASCII 字串；不會主動拋錯。
    """
    return f"{value * 100:.4f}".rstrip("0").rstrip(".")
