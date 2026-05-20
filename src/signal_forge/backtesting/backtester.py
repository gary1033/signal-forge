from __future__ import annotations

from dataclasses import dataclass

from signal_forge.core.market_data import Bar
from signal_forge.core.strategy import Signal, Strategy


@dataclass(frozen=True)
class BacktestConfig:
    initial_equity: float = 10_000.0
    commission_bps: float = 1.0
    slippage_bps: float = 1.0


@dataclass(frozen=True)
class Trade:
    timestamp: str
    price: float
    from_position: float
    to_position: float
    cost: float
    reason: str


@dataclass(frozen=True)
class EquityPoint:
    timestamp: str
    equity: float
    position: float


@dataclass(frozen=True)
class BacktestResult:
    strategy_name: str
    start_equity: float
    end_equity: float
    total_return: float
    max_drawdown: float
    trade_count: int
    equity_curve: list[EquityPoint]
    trades: list[Trade]


class Backtester:
    """Simple close-to-close target-exposure backtester."""

    def __init__(self, config: BacktestConfig | None = None) -> None:
        """
        用途與流程：初始化物件狀態，保存後續執行所需的設定或 adapter 相依物件。
        參數：self 表示目前物件實例；config（BacktestConfig | None）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        self.config = config or BacktestConfig()

    def run(self, strategy: Strategy, bars: list[Bar]) -> BacktestResult:
        """
        用途與流程：執行主要工作流程，先驗證輸入 contract，再產生結果物件供 reporting 或測試使用。
        參數：self 表示目前物件實例；strategy（Strategy）由呼叫端傳入，需符合函式 contract；bars（list[Bar]）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 BacktestResult；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        if len(bars) < 2:
            raise ValueError("at least two bars are required")

        signals = strategy.generate_signals(bars)
        if len(signals) != len(bars):
            raise ValueError("strategy must return exactly one signal per bar")

        equity = self.config.initial_equity
        position = 0.0
        equity_curve = [EquityPoint(bars[0].timestamp, equity, position)]
        trades: list[Trade] = []
        total_cost_bps = (self.config.commission_bps + self.config.slippage_bps) / 10_000.0

        for index in range(1, len(bars)):
            previous_close = bars[index - 1].close
            current_close = bars[index].close
            price_return = (current_close / previous_close) - 1.0
            equity *= 1.0 + (position * price_return)

            signal = signals[index]
            target = _clamp(signal.target_position, -1.0, 1.0)
            delta = target - position
            if abs(delta) > 1e-12:
                cost = abs(delta) * equity * total_cost_bps
                equity -= cost
                trades.append(
                    Trade(
                        timestamp=bars[index].timestamp,
                        price=current_close,
                        from_position=position,
                        to_position=target,
                        cost=cost,
                        reason=signal.reason,
                    )
                )
                position = target

            equity_curve.append(EquityPoint(bars[index].timestamp, equity, position))

        return BacktestResult(
            strategy_name=strategy.name,
            start_equity=self.config.initial_equity,
            end_equity=equity,
            total_return=(equity / self.config.initial_equity) - 1.0,
            max_drawdown=_max_drawdown([point.equity for point in equity_curve]),
            trade_count=len(trades),
            equity_curve=equity_curve,
            trades=trades,
        )


def _max_drawdown(equity_values: list[float]) -> float:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：equity_values（list[float]）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 float；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    peak = equity_values[0]
    max_drawdown = 0.0
    for equity in equity_values:
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = min(max_drawdown, (equity / peak) - 1.0)
    return max_drawdown


def _clamp(value: float, lower: float, upper: float) -> float:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：value（float）由呼叫端傳入，需符合函式 contract；lower（float）由呼叫端傳入，需符合函式 contract；upper（float）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 float；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    return min(max(value, lower), upper)
