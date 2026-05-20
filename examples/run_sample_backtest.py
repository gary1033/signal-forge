from __future__ import annotations

import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from signal_forge import Backtester, Bar
from signal_forge.strategies import (  # noqa: E402
    ConfluenceScoreStrategy,
    SmaCrossoverStrategy,
    VwapReversionStrategy,
)


def build_sample_bars(count: int = 260) -> list[Bar]:
    """
    用途與流程：執行此模組定義的業務流程，依輸入資料產生後續 reporting、策略或測試所需結果。
    參數：count（int）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 list[Bar]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    bars: list[Bar] = []
    price = 100.0
    for index in range(count):
        drift = 0.035
        cycle = math.sin(index / 9.0) * 0.65
        shock = -2.4 if index in {80, 160, 210} else 0.0
        price = max(1.0, price + drift + cycle * 0.08 + shock)
        volume = 1_000 + (index % 20) * 35 + (500 if abs(cycle) > 0.55 else 0)
        bars.append(
            Bar(
                timestamp=f"2026-01-{(index % 28) + 1:02d}T00:00:00",
                open=price - 0.2,
                high=price + 0.8,
                low=price - 0.8,
                close=price,
                volume=volume,
            )
        )
    return bars


def main() -> None:
    """
    用途與流程：作為命令列或工具入口，解析輸入、呼叫對應流程，最後回傳 process exit code。
    參數：無參數。
    回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
    """
    bars = build_sample_bars()
    strategies = [
        SmaCrossoverStrategy(),
        VwapReversionStrategy(),
        ConfluenceScoreStrategy(),
    ]
    backtester = Backtester()

    for strategy in strategies:
        result = backtester.run(strategy, bars)
        print(
            f"{result.strategy_name}: "
            f"return={result.total_return:.2%}, "
            f"max_dd={result.max_drawdown:.2%}, "
            f"trades={result.trade_count}, "
            f"end_equity={result.end_equity:.2f}"
        )


if __name__ == "__main__":
    main()

