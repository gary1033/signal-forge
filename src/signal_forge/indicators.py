from __future__ import annotations

import math
from collections.abc import Sequence


Number = float | int


def sma(values: Sequence[Number], window: int) -> list[float | None]:
    _require_window(window)
    result: list[float | None] = []
    rolling_sum = 0.0
    for index, value in enumerate(values):
        rolling_sum += float(value)
        if index >= window:
            rolling_sum -= float(values[index - window])
        if index + 1 < window:
            result.append(None)
        else:
            result.append(rolling_sum / window)
    return result


def ema(values: Sequence[Number], window: int) -> list[float | None]:
    _require_window(window)
    if not values:
        return []

    result: list[float | None] = []
    multiplier = 2.0 / (window + 1)
    current: float | None = None

    for index, value in enumerate(values):
        value = float(value)
        if index + 1 < window:
            result.append(None)
            continue
        if current is None:
            current = sum(float(item) for item in values[index + 1 - window : index + 1]) / window
        else:
            current = (value - current) * multiplier + current
        result.append(current)
    return result


def rolling_std(values: Sequence[Number], window: int) -> list[float | None]:
    _require_window(window)
    result: list[float | None] = []
    for index in range(len(values)):
        if index + 1 < window:
            result.append(None)
            continue
        sample = [float(item) for item in values[index + 1 - window : index + 1]]
        mean = sum(sample) / window
        variance = sum((item - mean) ** 2 for item in sample) / window
        result.append(math.sqrt(variance))
    return result


def rsi(values: Sequence[Number], window: int = 14) -> list[float | None]:
    _require_window(window)
    if len(values) < 2:
        return [None for _ in values]

    gains = [0.0]
    losses = [0.0]
    for index in range(1, len(values)):
        change = float(values[index]) - float(values[index - 1])
        gains.append(max(change, 0.0))
        losses.append(abs(min(change, 0.0)))

    avg_gains = sma(gains, window)
    avg_losses = sma(losses, window)
    result: list[float | None] = []

    for gain, loss in zip(avg_gains, avg_losses):
        if gain is None or loss is None:
            result.append(None)
        elif loss == 0:
            result.append(100.0)
        else:
            relative_strength = gain / loss
            result.append(100.0 - (100.0 / (1.0 + relative_strength)))
    return result


def rolling_vwap(
    close_values: Sequence[Number], volume_values: Sequence[Number], window: int
) -> list[float | None]:
    _require_window(window)
    if len(close_values) != len(volume_values):
        raise ValueError("close_values and volume_values must have the same length")

    result: list[float | None] = []
    price_volume_sum = 0.0
    volume_sum = 0.0

    for index, (close, volume) in enumerate(zip(close_values, volume_values)):
        close = float(close)
        volume = float(volume)
        price_volume_sum += close * volume
        volume_sum += volume

        if index >= window:
            old_close = float(close_values[index - window])
            old_volume = float(volume_values[index - window])
            price_volume_sum -= old_close * old_volume
            volume_sum -= old_volume

        if index + 1 < window or volume_sum == 0:
            result.append(None)
        else:
            result.append(price_volume_sum / volume_sum)
    return result


def _require_window(window: int) -> None:
    if window <= 0:
        raise ValueError("window must be positive")

