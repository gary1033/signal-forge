from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REQUIRED_OHLCV_FIELDS = ("timestamp", "open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class Bar:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class BarValidationResult:
    bar_count: int
    start_timestamp: str | None
    end_timestamp: str | None
    errors: list[str]
    warnings: list[str]

    @property
    def is_valid(self) -> bool:
        """
        用途與流程：執行此模組定義的業務流程，依輸入資料產生後續 reporting、策略或測試所需結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 bool；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        return not self.errors


class MarketDataValidationError(ValueError):
    """Raised when OHLCV input cannot be used for first-phase research."""


def load_bars_from_csv(path: str | Path, *, validate: bool = True) -> list[Bar]:
    """
    用途與流程：讀取 SignalForge OHLCV CSV，轉成 Bar 清單並可選擇立即驗證資料 contract。
    參數：path（str | Path）由呼叫端傳入，需符合函式 contract；validate（bool）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 list[Bar]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    bars: list[Bar] = []
    with Path(path).open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        missing_fields = [
            field for field in REQUIRED_OHLCV_FIELDS if field not in (reader.fieldnames or [])
        ]
        if missing_fields:
            raise MarketDataValidationError(
                "CSV is missing required columns: " + ", ".join(missing_fields)
            )

        for row in reader:
            row_number = reader.line_num
            try:
                bars.append(
                    Bar(
                        timestamp=row["timestamp"],
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row["volume"]),
                    )
                )
            except (TypeError, ValueError) as exc:
                raise MarketDataValidationError(
                    f"CSV row {row_number} contains a non-numeric OHLCV value"
                ) from exc

    if validate:
        result = validate_bars(bars)
        if not result.is_valid:
            raise MarketDataValidationError("; ".join(result.errors))

    return bars


def validate_bars(bars: list[Bar], *, min_bars: int = 2) -> BarValidationResult:
    """
    用途與流程：檢查 K 線資料的排序、唯一性、OHLC 合理性與基本樣本數。
    參數：bars（list[Bar]）由呼叫端傳入，需符合函式 contract；min_bars（int）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 BarValidationResult；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not bars:
        return BarValidationResult(0, None, None, ["no bars were loaded"], warnings)

    if len(bars) < min_bars:
        errors.append(f"at least {min_bars} bars are required, got {len(bars)}")

    previous_timestamp: str | None = None
    seen_timestamps: set[str] = set()

    for index, bar in enumerate(bars):
        row_label = f"bar {index}"
        if not bar.timestamp:
            errors.append(f"{row_label} has an empty timestamp")

        if bar.timestamp in seen_timestamps:
            errors.append(f"{row_label} duplicates timestamp {bar.timestamp}")
        seen_timestamps.add(bar.timestamp)

        if previous_timestamp is not None and bar.timestamp <= previous_timestamp:
            errors.append(
                f"{row_label} timestamp {bar.timestamp} is not after {previous_timestamp}"
            )
        previous_timestamp = bar.timestamp

        if bar.high < max(bar.open, bar.close):
            errors.append(f"{row_label} high is below open or close")
        if bar.low > min(bar.open, bar.close):
            errors.append(f"{row_label} low is above open or close")
        if bar.high < bar.low:
            errors.append(f"{row_label} high is below low")
        if bar.volume < 0:
            errors.append(f"{row_label} volume is negative")
        if bar.open <= 0 or bar.high <= 0 or bar.low <= 0 or bar.close <= 0:
            errors.append(f"{row_label} contains a non-positive price")

    if len(bars) < 30:
        warnings.append("Sample has fewer than 30 bars; profit factor may be unstable.")

    return BarValidationResult(
        bar_count=len(bars),
        start_timestamp=bars[0].timestamp,
        end_timestamp=bars[-1].timestamp,
        errors=errors,
        warnings=warnings,
    )


def closes(bars: Iterable[Bar]) -> list[float]:
    """
    用途與流程：從 Bar iterable 擷取 close 序列，供指標與策略計算使用。
    參數：bars（Iterable[Bar]）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 list[float]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    return [bar.close for bar in bars]


def volumes(bars: Iterable[Bar]) -> list[float]:
    """
    用途與流程：從 Bar iterable 擷取 volume 序列，供成交量指標與濾網使用。
    參數：bars（Iterable[Bar]）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 list[float]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    return [bar.volume for bar in bars]
