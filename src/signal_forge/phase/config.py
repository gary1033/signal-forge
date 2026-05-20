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
    dry_run: bool | None = None

    def __post_init__(self) -> None:
        """
        用途與流程：在 PhaseConfig 建立後統一檢查 mode、hold period 與 live dry-run 安全語意。
        參數：self 是 dataclass 實例，欄位來自 CLI、測試或程式呼叫端。
        回傳與錯誤：回傳 None；mode 不合法、hold period 非正數或破壞 dry-run 邊界時拋出 ValueError。
        """
        if self.mode not in {"backtest", "live"}:
            raise ValueError("mode must be either 'backtest' or 'live'")
        if self.hold_bars_per_day <= 0:
            raise ValueError("hold_bars_per_day must be positive")
        if self.mode == "live":
            if self.dry_run is False:
                raise ValueError(
                    "live mode is dry-run only until backtests are stable"
                )
            object.__setattr__(self, "dry_run", True)
            return

        if self.dry_run is True:
            raise ValueError("backtest mode must set dry_run=False")
        object.__setattr__(self, "dry_run", False)

    @property
    def is_backtest(self) -> bool:
        """
        用途與流程：提供 runner 分派 adapter 的語意捷徑，避免呼叫端自行比較字串。
        參數：self 是目前 PhaseConfig 實例。
        回傳與錯誤：mode 為 backtest 時回傳 True；此 property 不會額外丟錯。
        """
        return self.mode == "backtest"

    @property
    def is_live(self) -> bool:
        """
        用途與流程：提供 runner 分派 adapter 的語意捷徑，明確標示 live dry-run 路徑。
        參數：self 是目前 PhaseConfig 實例。
        回傳與錯誤：mode 為 live 時回傳 True；此 property 不會額外丟錯。
        """
        return self.mode == "live"


def parse_phase_mode(value: str) -> PhaseMode:
    """
    用途與流程：解析 CLI 傳入的 Phase mode 字串，統一大小寫與空白後回傳合法 mode。
    參數：value 是外部輸入字串，例如 backtest、live 或帶空白的同義輸入。
    回傳與錯誤：回傳 PhaseMode；不屬於 backtest/live 時拋出 ValueError。
    """
    normalized = value.strip().lower()
    if normalized not in {"backtest", "live"}:
        raise ValueError("mode must be either 'backtest' or 'live'")
    return normalized  # type: ignore[return-value]
