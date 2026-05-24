from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Iterable

from signal_forge import (
    BacktestConfig,
    Backtester,
    build_phase1_strategy,
    load_bars_from_csv,
)
from signal_forge.backtesting.backtester import BacktestResult
from signal_forge.core.market_data import Bar
from signal_forge.strategies import SUPPORTED_STRATEGY_NAMES


DEFAULT_TARGET_STATE_STRATEGIES = (
    "sma-crossover",
    "vwap-reversion",
    "confluence-score",
    "absolute-momentum",
)


@dataclass(frozen=True)
class TargetStateRow:
    symbol: str
    csv_path: str
    strategy: str
    strategy_impl: str
    cost_multiplier: float
    cost_label: str
    commission_bps: float
    slippage_bps: float
    transaction_tax_bps: float
    total_return: float
    cagr: float | None
    sharpe_ratio: float | None
    sortino_ratio: float | None
    calmar_ratio: float | None
    max_drawdown: float
    benchmark_total_return: float
    benchmark_cagr: float | None
    benchmark_max_drawdown: float
    benchmark_excess_return: float
    benchmark_excess_cagr: float | None
    trade_count: int
    total_cost: float
    turnover: float
    time_in_market: float
    end_equity: float


@dataclass(frozen=True)
class TargetStateAggregate:
    strategy: str
    cost_multiplier: float
    cost_label: str
    stock_count: int
    positive_return_count: int
    outperform_benchmark_count: int
    lower_drawdown_than_benchmark_count: int
    average_total_return: float
    average_cagr: float | None
    average_sharpe_ratio: float | None
    average_sortino_ratio: float | None
    average_calmar_ratio: float | None
    worst_max_drawdown: float
    average_benchmark_total_return: float
    average_benchmark_cagr: float | None
    worst_benchmark_max_drawdown: float
    average_benchmark_excess_return: float
    average_benchmark_excess_cagr: float | None
    total_trades: int
    total_cost: float
    average_turnover: float
    average_time_in_market: float
    average_end_equity: float


def parse_cost_multipliers_list(value: str) -> tuple[float, ...]:
    """
    用途與流程：解析 CLI 的成本壓力倍率清單，讓同一批策略可同時跑 1x、2x、3x 成本情境。
    參數：value 是逗號分隔字串，例如 `1,2,3`；每個欄位都必須是正浮點數。
    回傳與錯誤：回傳 tuple[float, ...]；若欄位空白、非數字或小於等於 0，拋出 ValueError。
    """
    parts = [part.strip() for part in value.split(",")]
    if not parts or any(part == "" for part in parts):
        raise ValueError(
            "--cost-multipliers-list must be a comma-separated list of positive numbers"
        )
    try:
        multipliers = tuple(float(part) for part in parts)
    except ValueError as exc:
        raise ValueError(
            "--cost-multipliers-list must be a comma-separated list of positive numbers"
        ) from exc
    if any(multiplier <= 0 for multiplier in multipliers):
        raise ValueError("--cost-multipliers-list values must be positive")
    return multipliers


def infer_symbol_from_path(path: Path) -> str:
    """
    用途與流程：從 SignalForge 慣用 CSV 檔名推導股票代號，讓多股票報表不需要額外輸入 symbol。
    參數：path 是 OHLCV CSV 路徑，常見格式為 `TWSE_2330_1D.csv`。
    回傳與錯誤：若檔名符合 market_symbol_timeframe 形狀，回傳中間代號；否則回傳 stem。
    """
    parts = path.stem.split("_")
    if len(parts) >= 3 and parts[0].isalpha():
        return parts[1]
    return path.stem


def load_filtered_bars(path: Path, *, start: str | None, end: str | None) -> list[Bar]:
    """
    用途與流程：載入 OHLCV CSV 並套用共同日期窗，避免不同股票資料起訖不一造成比較偏差。
    參數：path 是 CSV 路徑；start/end 是可選 `YYYY-MM-DD` 邊界，None 表示不限制該端。
    回傳與錯誤：回傳篩選後的 Bar 清單；若指定區間內沒有資料，拋出 ValueError。
    """
    bars = [
        bar
        for bar in load_bars_from_csv(path)
        if (start is None or bar.timestamp[:10] >= start)
        and (end is None or bar.timestamp[:10] <= end)
    ]
    if not bars:
        raise ValueError(f"{path} has no bars in the requested date window")
    return bars


def run_sweep(
    *,
    csv_paths: list[Path],
    strategies: tuple[str, ...],
    cost_multipliers: tuple[float, ...],
    start: str | None,
    end: str | None,
    initial_equity: float,
    commission_bps: float,
    slippage_bps: float,
    transaction_tax_bps: float,
    periods_per_year: int,
    signal_cooldown_bars: int | None = None,
) -> tuple[list[TargetStateRow], list[TargetStateAggregate]]:
    """
    用途與流程：對多個股票、策略與成本倍率執行完整 target-state 回測，並彙總跨股票風險指標。
    參數：csv_paths 是股票 CSV；strategies 是 strategy registry 名稱；cost_multipliers 會等比例放大 commission/slippage/tax；start/end 控制 common window；initial_equity 與成本欄位傳給 Backtester；periods_per_year 用於日線風險年化；signal_cooldown_bars 可沿用 Phase 1 進場冷卻 wrapper。
    回傳與錯誤：回傳逐檔 TargetStateRow 與 aggregate；策略名稱、資料或成本不合法時由底層拋出 ValueError。
    """
    rows: list[TargetStateRow] = []
    loaded = [
        (infer_symbol_from_path(path), path, load_filtered_bars(path, start=start, end=end))
        for path in csv_paths
    ]

    for strategy_name in strategies:
        for cost_multiplier in cost_multipliers:
            config = BacktestConfig(
                initial_equity=initial_equity,
                commission_bps=commission_bps * cost_multiplier,
                slippage_bps=slippage_bps * cost_multiplier,
                transaction_tax_bps=transaction_tax_bps * cost_multiplier,
            )
            backtester = Backtester(config)
            for symbol, path, bars in loaded:
                strategy = build_phase1_strategy(
                    strategy_name,
                    signal_cooldown_bars=signal_cooldown_bars,
                )
                result = backtester.run(strategy, bars)
                rows.append(
                    _build_row(
                        symbol=symbol,
                        path=path,
                        strategy=strategy_name,
                        result=result,
                        bars=bars,
                        config=config,
                        cost_multiplier=cost_multiplier,
                        periods_per_year=periods_per_year,
                    )
                )

    return rows, build_aggregates(rows)


def build_aggregates(rows: list[TargetStateRow]) -> list[TargetStateAggregate]:
    """
    用途與流程：把逐檔 target-state 結果依 strategy/cost 分組，計算平均報酬、相對 benchmark 與最差回撤。
    參數：rows 是 run_sweep 產生的逐檔結果。
    回傳與錯誤：回傳依平均 excess return、worst MDD、策略名排序的 aggregate 清單；空輸入回傳空清單。
    """
    groups: dict[tuple[str, float, str], list[TargetStateRow]] = {}
    for row in rows:
        groups.setdefault((row.strategy, row.cost_multiplier, row.cost_label), []).append(row)

    aggregates: list[TargetStateAggregate] = []
    for (strategy, cost_multiplier, cost_label), group_rows in groups.items():
        aggregates.append(
            TargetStateAggregate(
                strategy=strategy,
                cost_multiplier=cost_multiplier,
                cost_label=cost_label,
                stock_count=len(group_rows),
                positive_return_count=sum(1 for row in group_rows if row.total_return > 0),
                outperform_benchmark_count=sum(
                    1 for row in group_rows if row.benchmark_excess_return > 0
                ),
                lower_drawdown_than_benchmark_count=sum(
                    1
                    for row in group_rows
                    if row.max_drawdown > row.benchmark_max_drawdown
                ),
                average_total_return=_average(row.total_return for row in group_rows),
                average_cagr=_average_optional(row.cagr for row in group_rows),
                average_sharpe_ratio=_average_optional(
                    row.sharpe_ratio for row in group_rows
                ),
                average_sortino_ratio=_average_optional(
                    row.sortino_ratio for row in group_rows
                ),
                average_calmar_ratio=_average_optional(
                    row.calmar_ratio for row in group_rows
                ),
                worst_max_drawdown=min(
                    (row.max_drawdown for row in group_rows),
                    default=0.0,
                ),
                average_benchmark_total_return=_average(
                    row.benchmark_total_return for row in group_rows
                ),
                average_benchmark_cagr=_average_optional(
                    row.benchmark_cagr for row in group_rows
                ),
                worst_benchmark_max_drawdown=min(
                    (row.benchmark_max_drawdown for row in group_rows),
                    default=0.0,
                ),
                average_benchmark_excess_return=_average(
                    row.benchmark_excess_return for row in group_rows
                ),
                average_benchmark_excess_cagr=_average_optional(
                    row.benchmark_excess_cagr for row in group_rows
                ),
                total_trades=sum(row.trade_count for row in group_rows),
                total_cost=sum(row.total_cost for row in group_rows),
                average_turnover=_average(row.turnover for row in group_rows),
                average_time_in_market=_average(row.time_in_market for row in group_rows),
                average_end_equity=_average(row.end_equity for row in group_rows),
            )
        )

    return sorted(
        aggregates,
        key=lambda item: (
            -item.average_benchmark_excess_return,
            item.worst_max_drawdown,
            item.strategy,
            item.cost_multiplier,
        ),
    )


def format_markdown(
    rows: list[TargetStateRow],
    aggregates: list[TargetStateAggregate],
    *,
    start: str | None,
    end: str | None,
    periods_per_year: int,
) -> str:
    """
    用途與流程：把 target-state 多股票回測結果格式化為 Markdown，供筆記與報表人工檢查。
    參數：rows 是逐檔結果；aggregates 是跨股票彙總；start/end/periods_per_year 標明評估邊界。
    回傳與錯誤：回傳 Markdown 字串；此函式不做 I/O，也不主動拋錯。
    """
    window = f"{start or 'earliest'} to {end or 'latest'}"
    lines = [
        "# Multi-stock Target-state Sweep",
        "",
        f"- Window: `{window}`",
        f"- Periods per year: `{periods_per_year}`",
        "",
        "## Aggregate",
        "",
        "| Strategy | Cost | Stocks | Positive | Beat B&H | Lower MDD | Avg return | Avg CAGR | Avg excess | Worst MDD | Worst B&H MDD | Trades | Avg time in market |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in aggregates:
        lines.append(
            "| "
            f"{item.strategy} | {item.cost_label} | {item.stock_count} | "
            f"{item.positive_return_count}/{item.stock_count} | "
            f"{item.outperform_benchmark_count}/{item.stock_count} | "
            f"{item.lower_drawdown_than_benchmark_count}/{item.stock_count} | "
            f"{item.average_total_return:.2%} | "
            f"{_format_optional_percent(item.average_cagr)} | "
            f"{item.average_benchmark_excess_return:.2%} | "
            f"{item.worst_max_drawdown:.2%} | "
            f"{item.worst_benchmark_max_drawdown:.2%} | "
            f"{item.total_trades} | {item.average_time_in_market:.2%} |"
        )
    lines.extend(
        [
            "",
            "## Risk Adjusted Aggregate",
            "",
            "| Strategy | Cost | Avg Sharpe | Avg Sortino | Avg Calmar | Avg turnover | Total cost | Avg end equity | Avg B&H return | Avg B&H CAGR | Avg excess CAGR |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for item in aggregates:
        lines.append(
            "| "
            f"{item.strategy} | {item.cost_label} | "
            f"{_format_optional_ratio(item.average_sharpe_ratio)} | "
            f"{_format_optional_ratio(item.average_sortino_ratio)} | "
            f"{_format_optional_ratio(item.average_calmar_ratio)} | "
            f"{item.average_turnover:.2f} | "
            f"{item.total_cost:.2f} | "
            f"{item.average_end_equity:.2f} | "
            f"{item.average_benchmark_total_return:.2%} | "
            f"{_format_optional_percent(item.average_benchmark_cagr)} | "
            f"{_format_optional_percent(item.average_benchmark_excess_cagr)} |"
        )
    lines.extend(
        [
            "",
            "## Per Stock",
            "",
            "| Symbol | Strategy | Cost | Return | CAGR | Sharpe | Sortino | Calmar | B&H return | Excess | MDD | B&H MDD | Trades | Turnover | Time in market |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in sorted(
        rows,
        key=lambda item: (item.symbol, item.strategy, item.cost_multiplier),
    ):
        lines.append(
            "| "
            f"{row.symbol} | {row.strategy} | {row.cost_label} | "
            f"{row.total_return:.2%} | "
            f"{_format_optional_percent(row.cagr)} | "
            f"{_format_optional_ratio(row.sharpe_ratio)} | "
            f"{_format_optional_ratio(row.sortino_ratio)} | "
            f"{_format_optional_ratio(row.calmar_ratio)} | "
            f"{row.benchmark_total_return:.2%} | "
            f"{row.benchmark_excess_return:.2%} | "
            f"{row.max_drawdown:.2%} | "
            f"{row.benchmark_max_drawdown:.2%} | "
            f"{row.trade_count} | {row.turnover:.2f} | {row.time_in_market:.2%} |"
        )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    """
    用途與流程：建立 target-state 多股票 sweep 的命令列 parser，支援多 CSV、多策略與多成本壓力。
    參數：無。
    回傳與錯誤：回傳 argparse.ArgumentParser；解析錯誤由 argparse 處理。
    """
    parser = argparse.ArgumentParser(
        description="Run target-state Backtester across multiple stock CSV files."
    )
    parser.add_argument("--csv", action="append", required=True, help="OHLCV CSV path")
    parser.add_argument(
        "--strategy",
        action="append",
        choices=SUPPORTED_STRATEGY_NAMES,
        help="strategy to include; defaults to daily target-state strategies",
    )
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--initial-equity", type=float, default=10_000.0)
    parser.add_argument("--commission-bps", type=float, default=1.0)
    parser.add_argument("--slippage-bps", type=float, default=1.0)
    parser.add_argument(
        "--transaction-tax-bps",
        type=float,
        default=0.0,
        help="sell-side transaction tax in basis points",
    )
    parser.add_argument(
        "--cost-multipliers-list",
        default="1",
        help="comma-separated cost stress multipliers, for example 1,2,3",
    )
    parser.add_argument(
        "--periods-per-year",
        type=int,
        default=252,
        help="annualization periods for equity-curve Sharpe and Sortino",
    )
    parser.add_argument(
        "--signal-cooldown-bars",
        type=int,
        help="block new long entries for this many bars after an accepted long entry",
    )
    parser.add_argument("--summary-json")
    parser.add_argument("--summary-md")
    return parser


def main(argv: list[str] | None = None) -> int:
    """
    用途與流程：CLI 入口，解析 target-state sweep 參數、執行回測、列印 Markdown，並可寫出 JSON/Markdown 摘要。
    參數：argv 是可選命令列參數清單；None 時使用 sys.argv。
    回傳與錯誤：成功回傳 0；參數、資料或回測錯誤會由 argparse 或底層函式拋出。
    """
    args = build_parser().parse_args(argv)
    strategies = tuple(args.strategy or DEFAULT_TARGET_STATE_STRATEGIES)
    cost_multipliers = parse_cost_multipliers_list(args.cost_multipliers_list)
    rows, aggregates = run_sweep(
        csv_paths=[Path(path) for path in args.csv],
        strategies=strategies,
        cost_multipliers=cost_multipliers,
        start=args.start,
        end=args.end,
        initial_equity=args.initial_equity,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
        transaction_tax_bps=args.transaction_tax_bps,
        periods_per_year=args.periods_per_year,
        signal_cooldown_bars=args.signal_cooldown_bars,
    )
    markdown = format_markdown(
        rows,
        aggregates,
        start=args.start,
        end=args.end,
        periods_per_year=args.periods_per_year,
    )
    if args.summary_json:
        Path(args.summary_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.summary_json).write_text(
            json.dumps(
                {
                    "rows": [asdict(row) for row in rows],
                    "aggregates": [asdict(item) for item in aggregates],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    if args.summary_md:
        Path(args.summary_md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.summary_md).write_text(markdown, encoding="utf-8", newline="")
    print(markdown, end="")
    return 0


def _build_row(
    *,
    symbol: str,
    path: Path,
    strategy: str,
    result: BacktestResult,
    bars: list[Bar],
    config: BacktestConfig,
    cost_multiplier: float,
    periods_per_year: int,
) -> TargetStateRow:
    """
    用途與流程：把單一 BacktestResult 補齊 benchmark、風險調整與持倉統計後轉成報表列。
    參數：symbol/path/strategy 標示資料來源；result 是 Backtester 輸出；bars 用來計算 benchmark 與年化；config 是實際成本設定；cost_multiplier 是成本壓力倍率；periods_per_year 用於 Sharpe/Sortino。
    回傳與錯誤：回傳 TargetStateRow；若 bars 過短或價格不合法，底層 benchmark 計算可能拋出 ValueError。
    """
    equity_values = [point.equity for point in result.equity_curve]
    equity_returns = _equity_returns(equity_values)
    years = _elapsed_years(bars)
    cagr = _compound_annual_growth_rate(
        result.start_equity,
        result.end_equity,
        years,
    )
    benchmark = _buy_and_hold_benchmark(bars, config=config)
    return TargetStateRow(
        symbol=symbol,
        csv_path=str(path),
        strategy=strategy,
        strategy_impl=result.strategy_name,
        cost_multiplier=cost_multiplier,
        cost_label=_format_cost_label(cost_multiplier),
        commission_bps=config.commission_bps,
        slippage_bps=config.slippage_bps,
        transaction_tax_bps=config.transaction_tax_bps,
        total_return=result.total_return,
        cagr=cagr,
        sharpe_ratio=_annualized_sharpe_ratio(equity_returns, periods_per_year),
        sortino_ratio=_annualized_sortino_ratio(equity_returns, periods_per_year),
        calmar_ratio=_calmar_ratio(cagr, result.max_drawdown),
        max_drawdown=result.max_drawdown,
        benchmark_total_return=benchmark["total_return"],
        benchmark_cagr=benchmark["cagr"],
        benchmark_max_drawdown=benchmark["max_drawdown"],
        benchmark_excess_return=result.total_return - benchmark["total_return"],
        benchmark_excess_cagr=_subtract_optional(cagr, benchmark["cagr"]),
        trade_count=result.trade_count,
        total_cost=sum(trade.cost for trade in result.trades),
        turnover=sum(
            abs(trade.to_position - trade.from_position) for trade in result.trades
        ),
        time_in_market=_time_in_market(result),
        end_equity=result.end_equity,
    )


def _buy_and_hold_benchmark(
    bars: list[Bar],
    *,
    config: BacktestConfig,
) -> dict[str, float | None]:
    """
    用途與流程：用第一根 open 買入、最後一根 close 賣出建立 buy-and-hold benchmark，並套用同一成本設定。
    參數：bars 是共同日期窗的 OHLCV 序列；config 提供 initial_equity、commission、slippage 與賣出端交易稅。
    回傳與錯誤：回傳 total_return、cagr 與 max_drawdown；若 bars 為空或價格非正，拋出 ValueError。
    """
    if not bars:
        raise ValueError("buy-and-hold benchmark requires at least one bar")
    if bars[0].open <= 0:
        raise ValueError("buy-and-hold benchmark requires positive first open")
    entry_cost_rate = (config.commission_bps + config.slippage_bps) / 10_000.0
    exit_cost_rate = (
        config.commission_bps + config.slippage_bps + config.transaction_tax_bps
    ) / 10_000.0
    entry_price = bars[0].open * (1.0 + entry_cost_rate)
    shares = config.initial_equity / entry_price
    equity_values = [shares * bar.close for bar in bars]
    end_equity = shares * bars[-1].close * (1.0 - exit_cost_rate)
    equity_values[-1] = end_equity
    years = _elapsed_years(bars)
    return {
        "total_return": (end_equity / config.initial_equity) - 1.0,
        "cagr": _compound_annual_growth_rate(
            config.initial_equity,
            end_equity,
            years,
        ),
        "max_drawdown": _max_drawdown(equity_values),
    }


def _equity_returns(equity_values: list[float]) -> list[float]:
    """
    用途與流程：把 equity curve 轉成相鄰期間報酬，供 Sharpe 與 Sortino 使用。
    參數：equity_values 是按時間排序的權益序列。
    回傳與錯誤：回傳相鄰報酬清單；若前一期權益小於等於 0，該段回傳 0 避免除零。
    """
    returns: list[float] = []
    for previous, current in zip(equity_values, equity_values[1:]):
        if previous <= 0:
            returns.append(0.0)
        else:
            returns.append((current / previous) - 1.0)
    return returns


def _annualized_sharpe_ratio(
    returns: list[float],
    periods_per_year: int,
) -> float | None:
    """
    用途與流程：用 equity return 序列估算年化 Sharpe，讓 target-state 報表能比較日線波動風險。
    參數：returns 是相鄰 equity returns；periods_per_year 是年化期數，日線預設 252。
    回傳與錯誤：樣本不足、標準差為 0 或年化期數非正時回傳 None；否則回傳 Sharpe。
    """
    if len(returns) < 2 or periods_per_year <= 0:
        return None
    mean_return = sum(returns) / len(returns)
    variance = sum((value - mean_return) ** 2 for value in returns) / (
        len(returns) - 1
    )
    if variance <= 0:
        return None
    return (mean_return / sqrt(variance)) * sqrt(periods_per_year)


def _annualized_sortino_ratio(
    returns: list[float],
    periods_per_year: int,
) -> float | None:
    """
    用途與流程：用 equity return 的 downside deviation 估算年化 Sortino，避免把上行波動當成風險。
    參數：returns 是相鄰 equity returns；periods_per_year 是年化期數，日線預設 252。
    回傳與錯誤：樣本不足、沒有 downside deviation 或年化期數非正時回傳 None；否則回傳 Sortino。
    """
    if len(returns) < 2 or periods_per_year <= 0:
        return None
    mean_return = sum(returns) / len(returns)
    downside = [min(0.0, value) for value in returns]
    downside_variance = sum(value * value for value in downside) / len(returns)
    if downside_variance <= 0:
        return None
    return (mean_return / sqrt(downside_variance)) * sqrt(periods_per_year)


def _calmar_ratio(cagr: float | None, max_drawdown: float) -> float | None:
    """
    用途與流程：計算 CAGR / abs(max_drawdown)，補足總報酬看不到的回撤承受度。
    參數：cagr 是年化報酬；max_drawdown 是小於等於 0 的最大回撤。
    回傳與錯誤：缺 CAGR 或最大回撤為 0 時回傳 None；否則回傳 Calmar ratio。
    """
    if cagr is None or max_drawdown == 0:
        return None
    return cagr / abs(max_drawdown)


def _compound_annual_growth_rate(
    start_equity: float,
    end_equity: float,
    years: float,
) -> float | None:
    """
    用途與流程：用起訖權益與樣本年數計算 CAGR，避免不同長度樣本只比較總報酬。
    參數：start_equity 是期初資金；end_equity 是期末權益；years 是樣本期間年數。
    回傳與錯誤：起訖資金或年數不合法時回傳 None；否則回傳 CAGR。
    """
    if start_equity <= 0 or end_equity <= 0 or years < (30.0 / 365.25):
        return None
    try:
        return (end_equity / start_equity) ** (1.0 / years) - 1.0
    except OverflowError:
        return None


def _elapsed_years(bars: list[Bar]) -> float:
    """
    用途與流程：由第一根與最後一根 bar timestamp 推估樣本年數，供 CAGR 計算。
    參數：bars 是按時間排序的 OHLCV 序列。
    回傳與錯誤：回傳正浮點年數；timestamp 無法解析或期間非正時退回 bar 數 / 252。
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
    用途與流程：將 SignalForge timestamp 轉成 datetime，支援 YYYY-MM-DD、ISO datetime 與 Z 結尾格式。
    參數：timestamp 是 Bar.timestamp 字串。
    回傳與錯誤：回傳 datetime；格式不合法時拋出 ValueError。
    """
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def _max_drawdown(equity_values: list[float]) -> float:
    """
    用途與流程：從權益序列計算最大回撤，供策略與 buy-and-hold benchmark 使用。
    參數：equity_values 是按時間排序的權益值。
    回傳與錯誤：回傳小於等於 0 的最大回撤；空清單回傳 0。
    """
    if not equity_values:
        return 0.0
    peak = equity_values[0]
    max_drawdown = 0.0
    for equity in equity_values:
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = min(max_drawdown, (equity / peak) - 1.0)
    return max_drawdown


def _time_in_market(result: BacktestResult) -> float:
    """
    用途與流程：計算完整回測期間平均絕對曝險，用來判斷策略是否長時間滿倉或多數時間空手。
    參數：result 是 Backtester 的回測結果，equity_curve 每點包含 position。
    回傳與錯誤：回傳 0 到 1 附近的平均曝險；若 equity_curve 為空則回傳 0。
    """
    if not result.equity_curve:
        return 0.0
    return sum(abs(point.position) for point in result.equity_curve) / len(
        result.equity_curve
    )


def _subtract_optional(left: float | None, right: float | None) -> float | None:
    """
    用途與流程：安全計算兩個可選數值的差，用於 excess CAGR。
    參數：left/right 是可為 None 的浮點數。
    回傳與錯誤：任一側為 None 時回傳 None；否則回傳 left - right。
    """
    if left is None or right is None:
        return None
    return left - right


def _average(values: Iterable[float]) -> float:
    """
    用途與流程：計算非空數值 iterable 的平均，供 aggregate 欄位使用。
    參數：values 是 float iterable。
    回傳與錯誤：若沒有有效值回傳 0；否則回傳平均。
    """
    items = list(values)
    if not items:
        return 0.0
    return sum(items) / len(items)


def _average_optional(values: Iterable[float | None]) -> float | None:
    """
    用途與流程：計算可選浮點欄位的平均，忽略 None。
    參數：values 是 float 或 None 的 iterable。
    回傳與錯誤：若沒有有效值回傳 None；否則回傳平均。
    """
    valid = [value for value in values if value is not None]
    if not valid:
        return None
    return sum(valid) / len(valid)


def _format_cost_label(multiplier: float) -> str:
    """
    用途與流程：把成本倍率轉成穩定短標籤，供 Markdown 與 JSON aggregate 分組閱讀。
    參數：multiplier 是正浮點倍率。
    回傳與錯誤：整數倍率輸出如 `2x`；非整數保留兩位有效小數並去除多餘 0。
    """
    if multiplier.is_integer():
        return f"{int(multiplier)}x"
    return f"{multiplier:.2f}".rstrip("0").rstrip(".") + "x"


def _format_optional_percent(value: float | None) -> str:
    """
    用途與流程：將可選百分比數值格式化為 Markdown 表格文字。
    參數：value 是 None 或小數形式百分比。
    回傳與錯誤：None 回傳 `undefined`；否則回傳兩位百分比。
    """
    if value is None:
        return "undefined"
    return f"{value:.2%}"


def _format_optional_ratio(value: float | None) -> str:
    """
    用途與流程：將可選比率格式化為 Markdown 表格文字。
    參數：value 是 None 或浮點比率。
    回傳與錯誤：None 回傳 `undefined`；否則回傳三位小數。
    """
    if value is None:
        return "undefined"
    return f"{value:.3f}"


if __name__ == "__main__":
    raise SystemExit(main())
