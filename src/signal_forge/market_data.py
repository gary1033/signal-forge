from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class Bar:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


def load_bars_from_csv(path: str | Path) -> list[Bar]:
    """Load OHLCV bars from a CSV with timestamp,open,high,low,close,volume."""
    bars: list[Bar] = []
    with Path(path).open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
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
    return bars


def closes(bars: Iterable[Bar]) -> list[float]:
    return [bar.close for bar in bars]


def volumes(bars: Iterable[Bar]) -> list[float]:
    return [bar.volume for bar in bars]

