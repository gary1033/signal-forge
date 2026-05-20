from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


OrderSide = Literal["buy"]


@dataclass(frozen=True)
class OrderIntent:
    timestamp: str
    side: OrderSide
    target_position: float
    reason: str
    dry_run: bool = True
    submitted: bool = False
    safety_note: str = (
        "LIVE_DRY_RUN_ONLY: dry_run order intent only; no broker; no api keys; submitted=False"
    )
