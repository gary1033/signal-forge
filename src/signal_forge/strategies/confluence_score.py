from __future__ import annotations

from dataclasses import dataclass

from signal_forge.indicators import rolling_vwap, rsi, sma
from signal_forge.market_data import Bar, closes, volumes
from signal_forge.strategy import BarByBarStrategy, StrategyDecision


@dataclass(frozen=True)
class ConfluenceScoreContext:
    fast: list[float | None]
    slow: list[float | None]
    rsi: list[float | None]
    vwap: list[float | None]
    avg_volume: list[float | None]
    volume: list[float]


@dataclass(frozen=True)
class ConfluenceScoreStrategy(BarByBarStrategy[ConfluenceScoreContext]):
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

    def prepare_context(self, bars: list[Bar]) -> ConfluenceScoreContext:
        close_values = closes(bars)
        volume_values = volumes(bars)
        return ConfluenceScoreContext(
            fast=sma(close_values, self.fast_window),
            slow=sma(close_values, self.slow_window),
            rsi=rsi(close_values, self.rsi_window),
            vwap=rolling_vwap(close_values, volume_values, self.vwap_window),
            avg_volume=sma(volume_values, self.fast_window),
            volume=volume_values,
        )

    def decide_bar(
        self,
        *,
        index: int,
        bar: Bar,
        bars: list[Bar],
        context: ConfluenceScoreContext,
        previous_target_position: float,
    ) -> StrategyDecision:
        fast = context.fast[index]
        slow = context.slow[index]
        rsi_value = context.rsi[index]
        vwap = context.vwap[index]
        avg_volume = context.avg_volume[index]
        if (
            fast is None
            or slow is None
            or rsi_value is None
            or vwap is None
            or avg_volume is None
        ):
            return StrategyDecision(0.0, "warmup", 0.0)

        score = 0.0
        reasons: list[str] = []

        if fast > slow:
            score += 1.0
            reasons.append("trend_up")
        else:
            score -= 1.0
            reasons.append("trend_down")

        if bar.close > slow:
            score += 1.0
            reasons.append("above_slow_sma")
        else:
            score -= 1.0
            reasons.append("below_slow_sma")

        if bar.close > vwap:
            score += 1.0
            reasons.append("above_vwap")
        else:
            score -= 1.0
            reasons.append("below_vwap")

        if rsi_value >= 55:
            score += 1.0
            reasons.append("momentum_positive")
        elif rsi_value <= 45:
            score -= 1.0
            reasons.append("momentum_negative")

        if index > 0 and context.volume[index] > avg_volume:
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
        return StrategyDecision(target, reason, score)
