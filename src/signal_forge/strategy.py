from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from signal_forge.market_data import Bar


@dataclass(frozen=True)
class Signal:
    index: int
    timestamp: str
    target_position: float
    reason: str
    score: float = 0.0


class Strategy(ABC):
    name: str

    @abstractmethod
    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        """Return one target-position signal for every input bar."""

