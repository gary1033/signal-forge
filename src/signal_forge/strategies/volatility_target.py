from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from signal_forge.core.market_data import Bar
from signal_forge.core.strategy import Signal, Strategy


@dataclass(frozen=True)
class VolatilityTargetStrategy(Strategy):
    """
    用途與流程：包裝既有策略，使用最近 close-to-close realized volatility 將非零 target_position 縮放到目標年化波動附近。
    參數：base_strategy 是原始策略；lookback_bars 是計算 realized volatility 的日數；target_annual_volatility 是目標年化波動小數；periods_per_year 是年化期數；min_observations 是啟用縮放前需要的最少報酬筆數；max_scale 是曝險上限，預設 1 表示只降曝險、不加槓桿。
    回傳與錯誤：generate_signals 回傳與 bars 等長的 Signal 清單；初始化參數不合法時拋出 ValueError。
    """

    base_strategy: Strategy
    lookback_bars: int = 20
    target_annual_volatility: float = 0.20
    periods_per_year: int = 252
    min_observations: int | None = None
    max_scale: float = 1.0

    def __post_init__(self) -> None:
        """
        用途與流程：在 wrapper 建立時驗證波動目標參數，避免回測期間才出現難追蹤的無效縮放。
        參數：self 是目前 VolatilityTargetStrategy 實例。
        回傳與錯誤：回傳 None；lookback、目標波動、年化期數、最少樣本或曝險上限不合法時拋出 ValueError。
        """
        if self.lookback_bars <= 1:
            raise ValueError("lookback_bars must be greater than 1")
        if self.target_annual_volatility <= 0:
            raise ValueError("target_annual_volatility must be positive")
        if self.periods_per_year <= 0:
            raise ValueError("periods_per_year must be positive")
        if self.max_scale <= 0 or self.max_scale > 1:
            raise ValueError("max_scale must be greater than 0 and no more than 1")
        if self.min_observations is not None:
            if self.min_observations <= 1:
                raise ValueError("min_observations must be greater than 1")
            if self.min_observations > self.lookback_bars:
                raise ValueError("min_observations must be <= lookback_bars")

    @property
    def name(self) -> str:
        """
        用途與流程：產生包含縮放參數與底層策略名稱的 deterministic 策略名稱，方便報表辨識同一策略是否套用風控。
        參數：self 是目前 wrapper 實例。
        回傳與錯誤：回傳 ASCII 策略名稱；不會額外拋錯。
        """
        target_label = _format_decimal_label(self.target_annual_volatility)
        scale_label = _format_decimal_label(self.max_scale)
        return (
            f"vol_target_l{self.lookback_bars}_t{target_label}_max{scale_label}"
            f"__{self.base_strategy.name}"
        )

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        """
        用途與流程：先取得底層策略 signals，再逐 bar 用已知 close-to-close 報酬估算 realized volatility，將非零曝險縮小到目標年化波動對應的 scale。
        參數：bars 是按時間排序的 OHLCV 序列；只使用 index 當下以前含當根 close 的歷史報酬，不讀未來資料。
        回傳與錯誤：回傳縮放後 Signal 清單；若底層策略輸出長度與 bars 不一致，拋出 ValueError。
        """
        base_signals = self.base_strategy.generate_signals(bars)
        if len(base_signals) != len(bars):
            raise ValueError("base strategy must return exactly one signal per bar")

        scaled_signals: list[Signal] = []
        for index, signal in enumerate(base_signals):
            if abs(signal.target_position) <= 1e-12:
                scaled_signals.append(signal)
                continue

            scale = self._scale_for_bar(bars, index)
            if scale is None:
                scaled_signals.append(
                    Signal(
                        signal.index,
                        signal.timestamp,
                        0.0,
                        "vol_target_warmup",
                        signal.score,
                    )
                )
                continue

            target_position = signal.target_position * scale
            scaled_signals.append(
                Signal(
                    signal.index,
                    signal.timestamp,
                    target_position,
                    _scaled_reason(signal.reason, scale, self.max_scale),
                    signal.score,
                )
            )
        return scaled_signals

    def _scale_for_bar(self, bars: list[Bar], index: int) -> float | None:
        """
        用途與流程：計算指定 bar 的曝險縮放倍率；樣本不足時回傳 None，已足夠時以 target annual volatility / realized annual volatility 取得 scale。
        參數：bars 是 OHLCV 序列；index 是目前 signal 所在位置，縮放只使用 index 當下以前的 close-to-close returns。
        回傳與錯誤：回傳 0 到 max_scale 的浮點倍率；樣本不足回傳 None；若 realized volatility 為 0，回傳 max_scale。
        """
        returns = _rolling_close_returns(bars, index, self.lookback_bars)
        required_observations = self.min_observations or self.lookback_bars
        if len(returns) < required_observations:
            return None

        daily_volatility = _sample_standard_deviation(returns)
        if daily_volatility <= 0:
            return self.max_scale
        annualized_volatility = daily_volatility * sqrt(self.periods_per_year)
        if annualized_volatility <= 0:
            return self.max_scale
        return min(self.max_scale, self.target_annual_volatility / annualized_volatility)


def _rolling_close_returns(
    bars: list[Bar],
    index: int,
    lookback_bars: int,
) -> list[float]:
    """
    用途與流程：擷取指定 index 前後界線內已知的 close-to-close 報酬，作為 realized volatility 的輸入。
    參數：bars 是 OHLCV 序列；index 是目前 signal 位置；lookback_bars 是最多使用的報酬筆數。
    回傳與錯誤：回傳報酬清單；若前一根 close 非正，該段略過以避免除零。
    """
    if index <= 0:
        return []
    start = max(1, index - lookback_bars + 1)
    returns: list[float] = []
    for position in range(start, index + 1):
        previous_close = bars[position - 1].close
        current_close = bars[position].close
        if previous_close <= 0:
            continue
        returns.append((current_close / previous_close) - 1.0)
    return returns


def _sample_standard_deviation(values: list[float]) -> float:
    """
    用途與流程：計算樣本標準差，供 realized volatility 年化使用。
    參數：values 是浮點報酬清單，至少需要兩筆才有樣本變異。
    回傳與錯誤：樣本不足時回傳 0；否則回傳樣本標準差。
    """
    if len(values) < 2:
        return 0.0
    mean_value = sum(values) / len(values)
    variance = sum((value - mean_value) ** 2 for value in values) / (
        len(values) - 1
    )
    if variance <= 0:
        return 0.0
    return sqrt(variance)


def _scaled_reason(reason: str, scale: float, max_scale: float) -> str:
    """
    用途與流程：把底層策略 reason 轉成穩定分類，避免每個浮點 scale 都製造一種新的 reason count。
    參數：reason 是底層策略 reason；scale 是本 bar 計算出的縮放倍率；max_scale 是 wrapper 的最高曝險倍率。
    回傳與錯誤：回傳 ASCII reason 字串；不會主動拋錯。
    """
    suffix = "vol_target_full" if abs(scale - max_scale) <= 1e-9 else "vol_target_scaled"
    return f"{reason}_{suffix}"


def _format_decimal_label(value: float) -> str:
    """
    用途與流程：把小數參數轉成檔名與 strategy name 可讀的短標籤。
    參數：value 是正浮點數。
    回傳與錯誤：回傳去除多餘 0 的字串，例如 0.20 轉成 0.2。
    """
    return f"{value:.4f}".rstrip("0").rstrip(".")
