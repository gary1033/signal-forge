from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from signal_forge.market_data import Bar, validate_bars
from signal_forge.strategy import Strategy


Decision = Literal["pass", "fail"]
ProfitFactorStatus = Literal["finite", "infinite", "undefined"]


@dataclass(frozen=True)
class EntryEdgeConfig:
    initial_equity: float = 10_000.0
    commission_bps: float = 1.0
    slippage_bps: float = 1.0
    hold_bars_per_day: int = 1
    pass_profit_factor: float = 1.2


@dataclass(frozen=True)
class EntryEdgeTrade:
    signal_index: int
    signal_timestamp: str
    entry_index: int
    entry_timestamp: str
    exit_index: int
    exit_timestamp: str
    entry_price: float
    exit_price: float
    gross_pnl: float
    cost: float
    net_pnl: float
    return_pct: float
    signal_reason: str
    signal_score: float


@dataclass(frozen=True)
class EntryEdgeEquityPoint:
    timestamp: str
    equity: float


@dataclass(frozen=True)
class EntryEdgeResult:
    strategy_name: str
    config: EntryEdgeConfig
    decision: Decision
    failure_reason: str | None
    profit_factor: float | None
    profit_factor_status: ProfitFactorStatus
    sample_risk: str | None
    gross_profit: float
    gross_loss: float
    trade_count: int
    ignored_short_count: int
    unclosed_signal_count: int
    overlapping_signal_count: int
    win_rate: float
    average_net_pnl: float
    max_drawdown: float
    start_equity: float
    end_equity: float
    trades: list[EntryEdgeTrade]
    equity_curve: list[EntryEdgeEquityPoint]


class EntryEdgeEvaluator:
    """Evaluate pure long entry edge with a fixed one-day holding contract."""

    def __init__(self, config: EntryEdgeConfig | None = None) -> None:
        self.config = config or EntryEdgeConfig()
        if self.config.hold_bars_per_day <= 0:
            raise ValueError("hold_bars_per_day must be positive")

    def run(self, strategy: Strategy, bars: list[Bar]) -> EntryEdgeResult:
        validation = validate_bars(bars, min_bars=self.config.hold_bars_per_day + 1)
        if not validation.is_valid:
            raise ValueError("; ".join(validation.errors))

        signals = strategy.generate_signals(bars)
        if len(signals) != len(bars):
            raise ValueError("strategy must return exactly one signal per bar")

        equity = self.config.initial_equity
        trades: list[EntryEdgeTrade] = []
        equity_curve = [EntryEdgeEquityPoint(bars[0].timestamp, equity)]
        total_cost_rate = (self.config.commission_bps + self.config.slippage_bps) / 10_000.0
        previous_target = 0.0
        last_exit_index = -1
        ignored_short_count = 0
        unclosed_signal_count = 0
        overlapping_signal_count = 0

        for signal in signals:
            target = signal.target_position
            if target < 0:
                ignored_short_count += 1

            is_long_entry = target > 0 and previous_target <= 0
            previous_target = target
            if not is_long_entry:
                continue

            entry_index = signal.index + 1
            exit_index = entry_index + self.config.hold_bars_per_day - 1
            if exit_index >= len(bars):
                unclosed_signal_count += 1
                continue
            if entry_index <= last_exit_index:
                overlapping_signal_count += 1
                continue

            entry_bar = bars[entry_index]
            exit_bar = bars[exit_index]
            entry_notional = equity
            gross_pnl = entry_notional * ((exit_bar.close / entry_bar.open) - 1.0)
            exit_notional = entry_notional + gross_pnl
            cost = (entry_notional * total_cost_rate) + (max(exit_notional, 0.0) * total_cost_rate)
            net_pnl = gross_pnl - cost
            equity += net_pnl
            last_exit_index = exit_index

            trades.append(
                EntryEdgeTrade(
                    signal_index=signal.index,
                    signal_timestamp=signal.timestamp,
                    entry_index=entry_index,
                    entry_timestamp=entry_bar.timestamp,
                    exit_index=exit_index,
                    exit_timestamp=exit_bar.timestamp,
                    entry_price=entry_bar.open,
                    exit_price=exit_bar.close,
                    gross_pnl=gross_pnl,
                    cost=cost,
                    net_pnl=net_pnl,
                    return_pct=net_pnl / entry_notional,
                    signal_reason=signal.reason,
                    signal_score=signal.score,
                )
            )
            equity_curve.append(EntryEdgeEquityPoint(exit_bar.timestamp, equity))

        return _build_result(
            strategy_name=strategy.name,
            config=self.config,
            trades=trades,
            equity_curve=equity_curve,
            ignored_short_count=ignored_short_count,
            unclosed_signal_count=unclosed_signal_count,
            overlapping_signal_count=overlapping_signal_count,
        )


def _build_result(
    *,
    strategy_name: str,
    config: EntryEdgeConfig,
    trades: list[EntryEdgeTrade],
    equity_curve: list[EntryEdgeEquityPoint],
    ignored_short_count: int,
    unclosed_signal_count: int,
    overlapping_signal_count: int,
) -> EntryEdgeResult:
    gross_profit = sum(trade.net_pnl for trade in trades if trade.net_pnl > 0)
    gross_loss = sum(trade.net_pnl for trade in trades if trade.net_pnl < 0)
    trade_count = len(trades)
    winning_trades = sum(1 for trade in trades if trade.net_pnl > 0)
    win_rate = winning_trades / trade_count if trade_count else 0.0
    average_net_pnl = sum(trade.net_pnl for trade in trades) / trade_count if trade_count else 0.0
    sample_risk: str | None = None
    failure_reason: str | None = None

    if not trades:
        profit_factor = None
        profit_factor_status: ProfitFactorStatus = "undefined"
        decision: Decision = "fail"
        failure_reason = "沒有可關閉的純多進場交易"
    elif gross_loss == 0 and gross_profit > 0:
        profit_factor = None
        profit_factor_status = "infinite"
        decision = "pass"
        sample_risk = "沒有虧損交易；PF 為無限大，需人工檢查樣本數與代表性"
    elif gross_loss == 0:
        profit_factor = None
        profit_factor_status = "undefined"
        decision = "fail"
        failure_reason = "沒有正報酬的已關閉交易"
    else:
        profit_factor = gross_profit / abs(gross_loss)
        profit_factor_status = "finite"
        if profit_factor > config.pass_profit_factor:
            decision = "pass"
        else:
            decision = "fail"
            failure_reason = (
                f"Profit Factor {profit_factor:.3f} 未高於 "
                f"{config.pass_profit_factor:.3f}"
            )

    equity_values = [point.equity for point in equity_curve]
    return EntryEdgeResult(
        strategy_name=strategy_name,
        config=config,
        decision=decision,
        failure_reason=failure_reason,
        profit_factor=profit_factor,
        profit_factor_status=profit_factor_status,
        sample_risk=sample_risk,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        trade_count=trade_count,
        ignored_short_count=ignored_short_count,
        unclosed_signal_count=unclosed_signal_count,
        overlapping_signal_count=overlapping_signal_count,
        win_rate=win_rate,
        average_net_pnl=average_net_pnl,
        max_drawdown=_max_drawdown(equity_values),
        start_equity=config.initial_equity,
        end_equity=equity_curve[-1].equity,
        trades=trades,
        equity_curve=equity_curve,
    )


def _max_drawdown(equity_values: list[float]) -> float:
    peak = equity_values[0]
    max_drawdown = 0.0
    for equity in equity_values:
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = min(max_drawdown, (equity / peak) - 1.0)
    return max_drawdown
