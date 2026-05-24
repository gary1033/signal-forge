from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from math import sqrt
from typing import Literal, Sequence

from signal_forge.core.market_data import Bar, validate_bars
from signal_forge.core.signals import generate_validated_signals
from signal_forge.core.strategy import Signal, Strategy


Decision = Literal["pass", "fail"]
ProfitFactorStatus = Literal["finite", "infinite", "undefined"]


@dataclass(frozen=True)
class EntryEdgeConfig:
    initial_equity: float = 10_000.0
    commission_bps: float = 1.0
    slippage_bps: float = 1.0
    transaction_tax_bps: float = 0.0
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
    total_return: float
    cagr: float | None
    sharpe_ratio: float | None
    sortino_ratio: float | None
    calmar_ratio: float | None
    max_drawdown: float
    start_equity: float
    end_equity: float
    benchmark_end_equity: float
    benchmark_total_return: float
    benchmark_cagr: float | None
    benchmark_max_drawdown: float
    benchmark_excess_return: float
    benchmark_excess_cagr: float | None
    monthly_returns: dict[str, float]
    yearly_returns: dict[str, float]
    trades: list[EntryEdgeTrade]
    equity_curve: list[EntryEdgeEquityPoint]


@dataclass(frozen=True)
class EntryEdgeComparisonResult:
    strategy_name: str
    hold_bars_per_day: tuple[int, ...]
    results: list[EntryEdgeResult]


class EntryEdgeEvaluator:
    """Evaluate pure long entry edge with a fixed one-day holding contract."""

    def __init__(self, config: EntryEdgeConfig | None = None) -> None:
        """
        用途與流程：初始化 entry-edge evaluator，保存回測資金、成本、固定持有期與 PF
        門檻，並在執行前先拒絕不合法設定。
        參數：config 可為 None 或 EntryEdgeConfig；None 時使用預設初始資金、commission、
        slippage、賣出端 transaction tax 與持有期。
        回傳與錯誤：回傳 None；若資金非正、成本為負或持有期非正，拋出 ValueError。
        """
        self.config = config or EntryEdgeConfig()
        if self.config.hold_bars_per_day <= 0:
            raise ValueError("hold_bars_per_day must be positive")
        if self.config.initial_equity <= 0:
            raise ValueError("initial_equity must be positive")
        if self.config.commission_bps < 0:
            raise ValueError("commission_bps must be non-negative")
        if self.config.slippage_bps < 0:
            raise ValueError("slippage_bps must be non-negative")
        if self.config.transaction_tax_bps < 0:
            raise ValueError("transaction_tax_bps must be non-negative")

    def run(self, strategy: Strategy, bars: list[Bar]) -> EntryEdgeResult:
        """
        用途與流程：執行主要工作流程，先驗證輸入 contract，再產生結果物件供 reporting 或測試使用。
        參數：self 表示目前物件實例；strategy（Strategy）由呼叫端傳入，需符合函式 contract；bars（list[Bar]）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 EntryEdgeResult；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        signals = generate_validated_signals(strategy, bars)
        return self.run_from_signals(strategy.name, bars, signals)

    def run_from_signals(
        self,
        strategy_name: str,
        bars: list[Bar],
        signals: list[Signal],
    ) -> EntryEdgeResult:
        """
        用途與流程：以呼叫端已產生且已固定的 Signal 序列評估 entry-edge，避免 Phase 同一輪回測重複呼叫 strategy。
        參數：strategy_name 是報表使用的策略名稱；bars 是同一批 OHLCV Bar；signals 必須與 bars 一對一對齊。
        回傳與錯誤：回傳 EntryEdgeResult；若 bars 驗證失敗或 signals 筆數不一致，拋出 ValueError。
        """
        validation = validate_bars(bars, min_bars=self.config.hold_bars_per_day + 1)
        if not validation.is_valid:
            raise ValueError("; ".join(validation.errors))
        if len(signals) != len(bars):
            raise ValueError("strategy must return exactly one signal per bar")

        equity = self.config.initial_equity
        trades: list[EntryEdgeTrade] = []
        equity_curve = [EntryEdgeEquityPoint(bars[0].timestamp, equity)]
        entry_cost_rate = (self.config.commission_bps + self.config.slippage_bps) / 10_000.0
        exit_cost_rate = (
            self.config.commission_bps
            + self.config.slippage_bps
            + self.config.transaction_tax_bps
        ) / 10_000.0
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
            cost = (entry_notional * entry_cost_rate) + (max(exit_notional, 0.0) * exit_cost_rate)
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
            strategy_name=strategy_name,
            config=self.config,
            bars=bars,
            trades=trades,
            equity_curve=equity_curve,
            ignored_short_count=ignored_short_count,
            unclosed_signal_count=unclosed_signal_count,
            overlapping_signal_count=overlapping_signal_count,
        )


def run_entry_edge_hold_comparison(
    strategy: Strategy,
    bars: list[Bar],
    base_config: EntryEdgeConfig,
    hold_bars_per_day: Sequence[int],
) -> EntryEdgeComparisonResult:
    """
    用途與流程：用同一策略與資料依序跑多個固定持有期，產生可比較的 Entry Edge 結果。
    參數：strategy（Strategy）由呼叫端傳入，需符合函式 contract；bars（list[Bar]）由呼叫端傳入，需符合函式 contract；base_config（EntryEdgeConfig）由呼叫端傳入，需符合函式 contract；hold_bars_per_day（Sequence[int]）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 EntryEdgeComparisonResult；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    hold_values = tuple(hold_bars_per_day)
    if not hold_values:
        raise ValueError("hold_bars_per_day comparison list must not be empty")
    invalid_values = [value for value in hold_values if value <= 0]
    if invalid_values:
        raise ValueError("hold_bars_per_day comparison values must be positive")

    results = [
        EntryEdgeEvaluator(replace(base_config, hold_bars_per_day=value)).run(
            strategy,
            bars,
        )
        for value in hold_values
    ]
    return EntryEdgeComparisonResult(
        strategy_name=strategy.name,
        hold_bars_per_day=hold_values,
        results=results,
    )


def _build_result(
    *,
    strategy_name: str,
    config: EntryEdgeConfig,
    bars: list[Bar],
    trades: list[EntryEdgeTrade],
    equity_curve: list[EntryEdgeEquityPoint],
    ignored_short_count: int,
    unclosed_signal_count: int,
    overlapping_signal_count: int,
) -> EntryEdgeResult:
    """
    用途與流程：依 registry 或 reporting 需求組合內部資料結構，集中維護建構規則。
    參數：strategy_name 是報表使用的策略名稱；config 是 entry-edge 成本、資金與持有期設定；bars 是完整 OHLCV 樣本，用來計算年化期間與 buy-and-hold benchmark；trades 是已完成交易；equity_curve 是交易後權益曲線；ignored_short_count、unclosed_signal_count、overlapping_signal_count 是訊號處理統計。
    回傳與錯誤：回傳 EntryEdgeResult；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
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
        failure_reason = "No closed long-entry trades to evaluate."
    elif gross_loss == 0 and gross_profit > 0:
        profit_factor = None
        profit_factor_status = "infinite"
        decision = "pass"
        sample_risk = (
            "No losing trades; PF is infinite. Manually inspect sample size and representativeness."
        )
    elif gross_loss == 0:
        profit_factor = None
        profit_factor_status = "undefined"
        decision = "fail"
        failure_reason = "No profitable closed trades."
    else:
        profit_factor = gross_profit / abs(gross_loss)
        profit_factor_status = "finite"
        if profit_factor > config.pass_profit_factor:
            decision = "pass"
        else:
            decision = "fail"
            failure_reason = (
                f"Profit Factor {profit_factor:.3f} did not exceed "
                f"{config.pass_profit_factor:.3f}"
            )

    equity_values = [point.equity for point in equity_curve]
    end_equity = equity_curve[-1].equity
    total_return = (end_equity / config.initial_equity) - 1.0
    years = _elapsed_years(bars)
    trade_returns = [trade.return_pct for trade in trades]
    benchmark = _buy_and_hold_benchmark(
        bars,
        initial_equity=config.initial_equity,
        commission_bps=config.commission_bps,
        slippage_bps=config.slippage_bps,
        transaction_tax_bps=config.transaction_tax_bps,
    )
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
        total_return=total_return,
        cagr=_compound_annual_growth_rate(config.initial_equity, end_equity, years),
        sharpe_ratio=_annualized_sharpe_ratio(trade_returns, years),
        sortino_ratio=_annualized_sortino_ratio(trade_returns, years),
        calmar_ratio=_calmar_ratio(
            _compound_annual_growth_rate(config.initial_equity, end_equity, years),
            _max_drawdown(equity_values),
        ),
        max_drawdown=_max_drawdown(equity_values),
        start_equity=config.initial_equity,
        end_equity=end_equity,
        benchmark_end_equity=benchmark["end_equity"],
        benchmark_total_return=benchmark["total_return"],
        benchmark_cagr=benchmark["cagr"],
        benchmark_max_drawdown=benchmark["max_drawdown"],
        benchmark_excess_return=total_return - benchmark["total_return"],
        benchmark_excess_cagr=_subtract_optional(
            _compound_annual_growth_rate(config.initial_equity, end_equity, years),
            benchmark["cagr"],
        ),
        monthly_returns=_period_returns(equity_curve, key_length=7),
        yearly_returns=_period_returns(equity_curve, key_length=4),
        trades=trades,
        equity_curve=equity_curve,
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


def _elapsed_years(bars: list[Bar]) -> float:
    """
    用途與流程：由回測樣本第一根與最後一根 bar 的 timestamp 推估年化期間，供 CAGR、
    Sharpe、Sortino 與 Calmar 使用。
    參數：bars 是已通過 validate_bars 的 OHLCV 序列，timestamp 可為 YYYY-MM-DD 或 ISO datetime。
    回傳與錯誤：回傳正浮點年數；若無法解析或期間為 0，退回用 bar 數除以 252 的近似值。
    """
    if len(bars) < 2:
        return 0.0
    try:
        start = _parse_timestamp(bars[0].timestamp)
        end = _parse_timestamp(bars[-1].timestamp)
    except ValueError:
        return len(bars) / 252.0
    elapsed_days = (end - start).total_seconds() / 86_400.0
    if elapsed_days <= 0:
        return len(bars) / 252.0
    return elapsed_days / 365.25


def _parse_timestamp(timestamp: str) -> datetime:
    """
    用途與流程：將 SignalForge bar timestamp 轉成 datetime，支援日期與含時區的 ISO datetime。
    參數：timestamp 是 Bar.timestamp 字串，可為 YYYY-MM-DD、ISO datetime 或 Z 結尾 UTC 格式。
    回傳與錯誤：回傳 datetime；若格式不合法，拋出 ValueError。
    """
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def _compound_annual_growth_rate(
    start_equity: float,
    end_equity: float,
    years: float,
) -> float | None:
    """
    用途與流程：用起訖權益與年數計算 CAGR，避免報表只呈現未年化總報酬。
    參數：start_equity 是期初資金；end_equity 是期末權益；years 是樣本期間年數。
    回傳與錯誤：若起訖資金或年數不適合年化，回傳 None；否則回傳 CAGR 小數。
    """
    if start_equity <= 0 or end_equity <= 0 or years < (30.0 / 365.25):
        return None
    try:
        return (end_equity / start_equity) ** (1.0 / years) - 1.0
    except OverflowError:
        return None


def _annualized_sharpe_ratio(returns: list[float], years: float) -> float | None:
    """
    用途與流程：以每筆已完成交易的 net return 序列估算年化 Sharpe ratio，作為 entry-edge
    階段的交易級風險調整報酬。
    參數：returns 是每筆交易 net_pnl / entry_notional；years 是完整樣本年數，用來估算年化交易頻率。
    回傳與錯誤：樣本不足、年數不合法或標準差為 0 時回傳 None；否則回傳 Sharpe。
    """
    if len(returns) < 2 or years <= 0:
        return None
    mean_return = sum(returns) / len(returns)
    variance = sum((value - mean_return) ** 2 for value in returns) / (len(returns) - 1)
    if variance <= 0:
        return None
    trades_per_year = len(returns) / years
    return (mean_return / sqrt(variance)) * sqrt(trades_per_year)


def _annualized_sortino_ratio(returns: list[float], years: float) -> float | None:
    """
    用途與流程：以負報酬交易的 downside deviation 估算年化 Sortino ratio，避免把上行波動也當成風險。
    參數：returns 是每筆交易 net return；years 是樣本年數，用來估算年化交易頻率。
    回傳與錯誤：樣本不足、沒有 downside deviation 或年數不合法時回傳 None；否則回傳 Sortino。
    """
    if len(returns) < 2 or years <= 0:
        return None
    mean_return = sum(returns) / len(returns)
    downside = [min(0.0, value) for value in returns]
    downside_variance = sum(value * value for value in downside) / len(returns)
    if downside_variance <= 0:
        return None
    trades_per_year = len(returns) / years
    return (mean_return / sqrt(downside_variance)) * sqrt(trades_per_year)


def _calmar_ratio(cagr: float | None, max_drawdown: float) -> float | None:
    """
    用途與流程：計算 Calmar ratio，也就是 CAGR 除以最大回撤絕對值，用來衡量報酬是否足以補償回撤。
    參數：cagr 是策略年化報酬；max_drawdown 是負數或 0 的最大回撤。
    回傳與錯誤：若 CAGR 不存在或最大回撤為 0，回傳 None；否則回傳 Calmar。
    """
    if cagr is None or max_drawdown == 0:
        return None
    return cagr / abs(max_drawdown)


def _subtract_optional(left: float | None, right: float | None) -> float | None:
    """
    用途與流程：安全計算兩個可選浮點數差值，供 excess CAGR 類欄位使用。
    參數：left 與 right 是可為 None 的數值。
    回傳與錯誤：任一側為 None 時回傳 None；否則回傳 left - right。
    """
    if left is None or right is None:
        return None
    return left - right


def _buy_and_hold_benchmark(
    bars: list[Bar],
    *,
    initial_equity: float,
    commission_bps: float,
    slippage_bps: float,
    transaction_tax_bps: float,
) -> dict[str, float | None]:
    """
    用途與流程：用同一份 bars 建立 buy-and-hold benchmark，第一根 open 買入、最後一根 close
    賣出，並套用與策略相同的進出場成本設定。
    參數：bars 是完整 OHLCV 樣本；initial_equity 是期初資金；commission_bps 與 slippage_bps
    套用於買賣兩側；transaction_tax_bps 只套用於賣出端。
    回傳與錯誤：回傳 end_equity、total_return、cagr、max_drawdown；若資料不足則回傳初始資金與 0 報酬。
    """
    if not bars:
        return {
            "end_equity": initial_equity,
            "total_return": 0.0,
            "cagr": None,
            "max_drawdown": 0.0,
        }
    entry_cost_rate = (commission_bps + slippage_bps) / 10_000.0
    exit_cost_rate = (commission_bps + slippage_bps + transaction_tax_bps) / 10_000.0
    entry_price = bars[0].open * (1.0 + entry_cost_rate)
    shares = initial_equity / entry_price if entry_price > 0 else 0.0
    equity_values = [shares * bar.close for bar in bars]
    end_equity = shares * bars[-1].close * (1.0 - exit_cost_rate)
    equity_values[-1] = end_equity
    years = _elapsed_years(bars)
    return {
        "end_equity": end_equity,
        "total_return": (end_equity / initial_equity) - 1.0
        if initial_equity > 0
        else 0.0,
        "cagr": _compound_annual_growth_rate(initial_equity, end_equity, years),
        "max_drawdown": _max_drawdown(equity_values),
    }


def _period_returns(
    equity_curve: list[EntryEdgeEquityPoint],
    *,
    key_length: int,
) -> dict[str, float]:
    """
    用途與流程：把交易後 equity curve 聚合成月或年報酬，讓報表可以檢查績效是否集中於少數期間。
    參數：equity_curve 是 EntryEdgeEquityPoint 序列；key_length 為 7 時取 YYYY-MM，為 4 時取 YYYY。
    回傳與錯誤：回傳 period -> return 的 deterministic dict；若 period 內沒有權益變化則報酬為 0。
    """
    if not equity_curve:
        return {}
    period_start: dict[str, float] = {}
    period_end: dict[str, float] = {}
    previous_equity = equity_curve[0].equity
    for point in equity_curve:
        key = point.timestamp[:key_length]
        period_start.setdefault(key, previous_equity)
        period_end[key] = point.equity
        previous_equity = point.equity
    return {
        key: (period_end[key] / start_equity) - 1.0 if start_equity else 0.0
        for key, start_equity in sorted(period_start.items())
    }
