from __future__ import annotations

from dataclasses import dataclass

from signal_forge.indicators import rolling_std, rolling_vwap
from signal_forge.market_data import Bar, closes, volumes
from signal_forge.strategy import BarByBarStrategy, StrategyDecision


@dataclass(frozen=True)
class VwapReversionContext:
    vwap: list[float | None]
    std: list[float | None]


@dataclass(frozen=True)
class VwapReversionStrategy(BarByBarStrategy[VwapReversionContext]):
    window: int = 20
    entry_z: float = 1.5
    exit_z: float = 0.25
    allow_short: bool = True

    @property
    def name(self) -> str:
        side = "long_short" if self.allow_short else "long_only"
        return f"vwap_reversion_{self.window}_{side}"

    def prepare_context(self, bars: list[Bar]) -> VwapReversionContext:
        close_values = closes(bars)
        return VwapReversionContext(
            vwap=rolling_vwap(close_values, volumes(bars), self.window),
            std=rolling_std(close_values, self.window),
        )

    def decide_bar(
        self,
        *,
        index: int,
        bar: Bar,
        bars: list[Bar],
        context: VwapReversionContext,
        previous_target_position: float,
    ) -> StrategyDecision:
        vwap = context.vwap[index]
        std = context.std[index]
        if vwap is None or std is None or std == 0:
            return StrategyDecision(0.0, "warmup", 0.0)

        z_score = (bar.close - vwap) / std
        score = -z_score
        if z_score <= -self.entry_z:
            return StrategyDecision(1.0, "price_below_vwap_band", score)
        if self.allow_short and z_score >= self.entry_z:
            return StrategyDecision(-1.0, "price_above_vwap_band", score)
        if abs(z_score) <= self.exit_z:
            return StrategyDecision(0.0, "price_reverted_to_vwap", score)
        return StrategyDecision(previous_target_position, "hold", score)
