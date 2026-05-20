from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar

from signal_forge.market_data import Bar


ContextT = TypeVar("ContextT")


@dataclass(frozen=True)
class Signal:
    index: int
    timestamp: str
    target_position: float
    reason: str
    score: float = 0.0


@dataclass(frozen=True)
class StrategyDecision:
    target_position: float
    reason: str
    score: float = 0.0


class Strategy(ABC):
    name: str

    @abstractmethod
    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        """Return one target-position signal for every input bar."""


class BarByBarStrategy(Strategy, Generic[ContextT]):
    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        context = self.prepare_context(bars)
        previous_target_position = 0.0
        signals: list[Signal] = []

        for index, bar in enumerate(bars):
            decision = self.decide_bar(
                index=index,
                bar=bar,
                bars=bars,
                context=context,
                previous_target_position=previous_target_position,
            )
            signals.append(
                Signal(
                    index=index,
                    timestamp=bar.timestamp,
                    target_position=decision.target_position,
                    reason=decision.reason,
                    score=decision.score,
                )
            )
            previous_target_position = decision.target_position

        return signals

    @abstractmethod
    def prepare_context(self, bars: list[Bar]) -> ContextT:
        """Precompute indicator values or shared state for bar-by-bar decisions."""

    @abstractmethod
    def decide_bar(
        self,
        *,
        index: int,
        bar: Bar,
        bars: list[Bar],
        context: ContextT,
        previous_target_position: float,
    ) -> StrategyDecision:
        """Return the target-position decision for one bar."""
