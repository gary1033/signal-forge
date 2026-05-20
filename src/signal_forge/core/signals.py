from __future__ import annotations

from dataclasses import dataclass

from signal_forge.core.market_data import Bar
from signal_forge.core.strategy import Signal, Strategy


@dataclass(frozen=True)
class SignalDigest:
    index: int
    timestamp: str
    target_position: float
    position_change: float
    reason: str
    score: float
    is_long_entry: bool
    is_flatten: bool


def normalize_signal_reason(value: str) -> str:
    """
    用途與流程：把 strategy reason 正規化成 deterministic、單行、ASCII-only 的 artifact 欄位。
    參數：value 是策略輸出的 reason 字串；允許空白、換行、tab 或非 ASCII 字元。
    回傳與錯誤：回傳最多 120 字元的 ASCII 字串；空字串會回傳 unknown，不會因非 ASCII 字元丟錯。
    """
    max_len = 120
    normalized = value.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    normalized = " ".join(normalized.split())
    if not normalized:
        return "unknown"

    out: list[str] = []
    for ch in normalized:
        if ch.isascii():
            out.append(ch)
            continue
        out.append(f"u{ord(ch):04x}")

    normalized = "".join(out).strip()
    if len(normalized) > max_len:
        normalized = normalized[:max_len].rstrip()
    return normalized or "unknown"


def generate_validated_signals(strategy: Strategy, bars: list[Bar]) -> list[Signal]:
    """
    用途與流程：集中呼叫 strategy.generate_signals(...) 並驗證一根 bar 對齊一筆 Signal。
    參數：strategy 是符合 SignalForge Strategy contract 的策略；bars 是已載入的 OHLCV Bar 清單。
    回傳與錯誤：回傳原始 Signal 清單；若筆數與 bars 不一致，拋出 ValueError。
    """
    signals = strategy.generate_signals(bars)
    if len(signals) != len(bars):
        raise ValueError("strategy must return exactly one signal per bar")
    return signals


def build_signal_digests(signals: list[Signal]) -> list[SignalDigest]:
    """
    用途與流程：把 strategy 原始 Signal 序列轉成 reporting 使用的 SignalDigest，補上部位變化與 entry/flatten flags。
    參數：signals 是已通過長度驗證、按 index/time 遞增排列的 Signal 清單。
    回傳與錯誤：回傳 SignalDigest 清單；此函式只做 deterministic 轉換，不額外讀取市場資料。
    """
    previous_target = 0.0
    epsilon = 1e-12
    digests: list[SignalDigest] = []
    for signal in signals:
        is_long_entry = signal.target_position > epsilon and previous_target <= epsilon
        is_flatten = signal.target_position <= epsilon and previous_target > epsilon
        position_change = signal.target_position - previous_target
        previous_target = signal.target_position
        digests.append(
            SignalDigest(
                index=signal.index,
                timestamp=signal.timestamp,
                target_position=signal.target_position,
                position_change=position_change,
                reason=normalize_signal_reason(signal.reason),
                score=signal.score,
                is_long_entry=is_long_entry,
                is_flatten=is_flatten,
            )
        )
    return digests
