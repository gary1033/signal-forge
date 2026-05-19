from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


PhaseMode = Literal["backtest", "live"]


@dataclass(frozen=True)
class PhaseConfig:
    """Shared phase configuration for backtest and live dry-run modes."""

    mode: PhaseMode = "backtest"
    strategy: str = "sma-crossover"
    csv_path: str | Path | None = None
    output_dir: str | Path = "reports/generated"
    hold_bars_per_day: int = 1
    dry_run: bool = True

    def __post_init__(self) -> None:
        if self.mode not in {"backtest", "live"}:
            raise ValueError("mode must be either 'backtest' or 'live'")
        if self.hold_bars_per_day <= 0:
            raise ValueError("hold_bars_per_day must be positive")
        if self.mode == "live" and not self.dry_run:
            raise ValueError("live mode is dry-run only until backtests are stable")

    @property
    def is_backtest(self) -> bool:
        return self.mode == "backtest"

    @property
    def is_live(self) -> bool:
        return self.mode == "live"


def parse_phase_mode(value: str) -> PhaseMode:
    normalized = value.strip().lower()
    if normalized not in {"backtest", "live"}:
        raise ValueError("mode must be either 'backtest' or 'live'")
    return normalized  # type: ignore[return-value]
