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
        return not self.errors


class MarketDataValidationError(ValueError):
    """Raised when OHLCV input cannot be used for first-phase research."""


def load_bars_from_csv(path: str | Path, *, validate: bool = True) -> list[Bar]:
    """Load OHLCV bars from a CSV with timestamp,open,high,low,close,volume."""
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
    return [bar.close for bar in bars]


def volumes(bars: Iterable[Bar]) -> list[float]:
    return [bar.volume for bar in bars]
