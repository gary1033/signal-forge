from __future__ import annotations

from dataclasses import dataclass

from signal_forge.indicators import rolling_vwap, rsi, sma
from signal_forge.market_data import Bar, closes, volumes
from signal_forge.strategy import Signal, Strategy


@dataclass(frozen=True)
class ConfluenceScoreStrategy(Strategy):
    fast_window: int = 20
    slow_window: int = 50
    rsi_window: int = 14
    vwap_window: int = 20
    threshold: float = 3.0
    allow_short: bool = True

    @property
    def name(self) -> str:
        side = "long_short" if self.allow_short else "long_only"
        return f"confluence_score_{side}"

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        close_values = closes(bars)
        volume_values = volumes(bars)
        fast = sma(close_values, self.fast_window)
        slow = sma(close_values, self.slow_window)
        rsi_values = rsi(close_values, self.rsi_window)
        vwap_values = rolling_vwap(close_values, volume_values, self.vwap_window)
        avg_volume = sma(volume_values, self.fast_window)
        signals: list[Signal] = []

        for index, bar in enumerate(bars):
            if (
                fast[index] is None
                or slow[index] is None
                or rsi_values[index] is None
                or vwap_values[index] is None
                or avg_volume[index] is None
            ):
                signals.append(Signal(index, bar.timestamp, 0.0, "warmup", 0.0))
                continue

            score = 0.0
            reasons: list[str] = []

            if fast[index] > slow[index]:
                score += 1.0
                reasons.append("trend_up")
            else:
                score -= 1.0
                reasons.append("trend_down")

            if bar.close > slow[index]:
                score += 1.0
                reasons.append("above_slow_sma")
            else:
                score -= 1.0
                reasons.append("below_slow_sma")

            if bar.close > vwap_values[index]:
                score += 1.0
                reasons.append("above_vwap")
            else:
                score -= 1.0
                reasons.append("below_vwap")

            if rsi_values[index] >= 55:
                score += 1.0
                reasons.append("momentum_positive")
            elif rsi_values[index] <= 45:
                score -= 1.0
                reasons.append("momentum_negative")

            if index > 0 and volume_values[index] > avg_volume[index]:
                if bar.close >= bars[index - 1].close:
                    score += 1.0
                    reasons.append("volume_confirms_up")
                else:
                    score -= 1.0
                    reasons.append("volume_confirms_down")

            if score >= self.threshold:
                target = 1.0
            elif self.allow_short and score <= -self.threshold:
                target = -1.0
            else:
                target = 0.0

            reason = "+".join(reasons) if reasons else "neutral"
            signals.append(Signal(index, bar.timestamp, target, reason, score))

        return signals

