from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from signal_forge import build_phase1_strategy, load_bars_from_csv
from signal_forge.backtesting.entry_edge import EntryEdgeConfig, EntryEdgeEvaluator
from signal_forge.core.market_data import Bar
from signal_forge.strategies import SUPPORTED_STRATEGY_NAMES


DEFAULT_STRATEGIES = ("sma-crossover", "vwap-reversion", "confluence-score")


@dataclass(frozen=True)
class SweepRow:
    symbol: str
    csv_path: str
    strategy: str
    hold_bars: int
    decision: str
    profit_factor_status: str
    profit_factor: float | None
    trade_count: int
    win_rate: float
    average_net_pnl: float
    max_drawdown: float
    gross_profit: float
    gross_loss: float
    end_equity: float
    overlapping_signal_count: int


@dataclass(frozen=True)
class SweepAggregate:
    strategy: str
    hold_bars: int
    stock_count: int
    pass_count: int
    aggregate_profit_factor_status: str
    aggregate_profit_factor: float | None
    total_trades: int
    average_win_rate: float
    worst_max_drawdown: float
    total_gross_profit: float
    total_gross_loss: float


def parse_hold_bars_list(value: str) -> tuple[int, ...]:
    """
    用途與流程：解析命令列傳入的逗號分隔持有期，讓批次 sweep 可以用同一組 hold bars
    跑所有股票與策略。
    參數：value 是逗號分隔字串，例如 `1,3,5,10`；每個欄位都必須是正整數。
    回傳與錯誤：回傳 tuple[int, ...]；若欄位空白、非整數或小於等於 0，拋出 ValueError。
    """
    parts = [part.strip() for part in value.split(",")]
    if not parts or any(part == "" for part in parts):
        raise ValueError("--hold-bars-list must be a comma-separated list of positive integers")
    try:
        hold_values = tuple(int(part) for part in parts)
    except ValueError as exc:
        raise ValueError(
            "--hold-bars-list must be a comma-separated list of positive integers"
        ) from exc
    if any(hold <= 0 for hold in hold_values):
        raise ValueError("--hold-bars-list values must be positive integers")
    return hold_values


def infer_symbol_from_path(path: Path) -> str:
    """
    用途與流程：從 SignalForge 慣用檔名推導股票代號，讓輸出摘要可讀性更高。
    參數：path 是 OHLCV CSV 路徑，檔名通常像 `TWSE_2330_1D.csv`。
    回傳與錯誤：若符合 `MARKET_SYMBOL_TIMEFRAME` 命名，回傳中間的 symbol；否則回傳 stem。
    """
    parts = path.stem.split("_")
    if len(parts) >= 3 and parts[0].isalpha():
        return parts[1]
    return path.stem


def load_filtered_bars(path: Path, *, start: str | None, end: str | None) -> list[Bar]:
    """
    用途與流程：載入單一 OHLCV CSV，並用 ISO 日期字串做 common-window 過濾，避免多檔股票
    因資料起訖不同而讓比較偏掉。
    參數：path 是 CSV 檔案路徑；start/end 是可選 `YYYY-MM-DD` 邊界，None 表示不限制該端。
    回傳與錯誤：回傳過濾後的 Bar list；若沒有任何資料落在區間內，拋出 ValueError。
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
    hold_bars_values: tuple[int, ...],
    start: str | None,
    end: str | None,
    pass_profit_factor: float,
    initial_equity: float,
    commission_bps: float,
    slippage_bps: float,
) -> tuple[list[SweepRow], list[SweepAggregate]]:
    """
    用途與流程：對多個股票 CSV、策略與固定持有期做笛卡兒積回測，並另外彙總每個
    strategy/hold 的跨股票 aggregate PF。
    參數：csv_paths 是待比較股票資料；strategies 是 SignalForge registry 策略名稱；
    hold_bars_values 是固定持有期清單；start/end 控制共同回測區間；pass_profit_factor、
    initial_equity、commission_bps、slippage_bps 會傳入 EntryEdgeConfig。
    回傳與錯誤：回傳逐檔 SweepRow 與聚合 SweepAggregate；若策略名稱不支援、資料不足
    或 entry-edge contract 不合法，底層會拋出 ValueError。
    """
    rows: list[SweepRow] = []
    loaded = [
        (infer_symbol_from_path(path), path, load_filtered_bars(path, start=start, end=end))
        for path in csv_paths
    ]

    for symbol, path, bars in loaded:
        for strategy_name in strategies:
            for hold_bars in hold_bars_values:
                config = EntryEdgeConfig(
                    initial_equity=initial_equity,
                    commission_bps=commission_bps,
                    slippage_bps=slippage_bps,
                    hold_bars_per_day=hold_bars,
                    pass_profit_factor=pass_profit_factor,
                )
                strategy = build_phase1_strategy(strategy_name)
                result = EntryEdgeEvaluator(config).run(strategy, bars)
                rows.append(
                    SweepRow(
                        symbol=symbol,
                        csv_path=str(path),
                        strategy=strategy_name,
                        hold_bars=hold_bars,
                        decision=result.decision,
                        profit_factor_status=result.profit_factor_status,
                        profit_factor=result.profit_factor,
                        trade_count=result.trade_count,
                        win_rate=result.win_rate,
                        average_net_pnl=result.average_net_pnl,
                        max_drawdown=result.max_drawdown,
                        gross_profit=result.gross_profit,
                        gross_loss=result.gross_loss,
                        end_equity=result.end_equity,
                        overlapping_signal_count=result.overlapping_signal_count,
                    )
                )

    return rows, build_aggregates(rows)


def build_aggregates(rows: list[SweepRow]) -> list[SweepAggregate]:
    """
    用途與流程：把逐檔 sweep 結果依 strategy/hold 分組，計算跨股票總損益後的 aggregate PF，
    讓判斷不只依賴單一股票的漂亮結果。
    參數：rows 是 run_sweep 產生的逐檔結果。
    回傳與錯誤：回傳依 aggregate PF、通過數與交易數排序的摘要；若某組沒有交易，PF 會標成
    undefined。
    """
    groups: dict[tuple[str, int], list[SweepRow]] = {}
    for row in rows:
        groups.setdefault((row.strategy, row.hold_bars), []).append(row)

    aggregates: list[SweepAggregate] = []
    for (strategy, hold_bars), group_rows in groups.items():
        total_gross_profit = sum(row.gross_profit for row in group_rows)
        total_gross_loss = sum(row.gross_loss for row in group_rows)
        total_trades = sum(row.trade_count for row in group_rows)
        if total_trades == 0:
            pf_status = "undefined"
            aggregate_pf = None
        elif total_gross_loss == 0 and total_gross_profit > 0:
            pf_status = "infinite"
            aggregate_pf = None
        elif total_gross_loss == 0:
            pf_status = "undefined"
            aggregate_pf = None
        else:
            pf_status = "finite"
            aggregate_pf = total_gross_profit / abs(total_gross_loss)
        aggregates.append(
            SweepAggregate(
                strategy=strategy,
                hold_bars=hold_bars,
                stock_count=len(group_rows),
                pass_count=sum(1 for row in group_rows if row.decision == "pass"),
                aggregate_profit_factor_status=pf_status,
                aggregate_profit_factor=aggregate_pf,
                total_trades=total_trades,
                average_win_rate=(
                    sum(row.win_rate for row in group_rows) / len(group_rows)
                    if group_rows
                    else 0.0
                ),
                worst_max_drawdown=min((row.max_drawdown for row in group_rows), default=0.0),
                total_gross_profit=total_gross_profit,
                total_gross_loss=total_gross_loss,
            )
        )

    return sorted(
        aggregates,
        key=lambda item: (
            -1.0
            if item.aggregate_profit_factor is None
            else -item.aggregate_profit_factor,
            -item.pass_count,
            item.strategy,
            item.hold_bars,
        ),
    )


def format_markdown(
    rows: list[SweepRow],
    aggregates: list[SweepAggregate],
    *,
    start: str | None,
    end: str | None,
    pass_profit_factor: float,
) -> str:
    """
    用途與流程：把批次 sweep 結果整理成人可讀 Markdown，分成 aggregate ranking 與逐檔明細。
    參數：rows 與 aggregates 是回測結果；start/end 與 pass_profit_factor 用來標明本次評估邊界。
    回傳與錯誤：回傳 Markdown 字串；此函式只格式化已計算資料，不做額外 I/O。
    """
    window = f"{start or 'earliest'} to {end or 'latest'}"
    lines = [
        "# Multi-stock Entry Edge Sweep",
        "",
        f"- Window: `{window}`",
        f"- Pass threshold PF: `>{pass_profit_factor:.2f}`",
        "",
        "## Aggregate",
        "",
        "| Strategy | Hold | Stocks passed | Aggregate PF | Trades | Avg win rate | Worst max drawdown |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in aggregates:
        lines.append(
            "| "
            f"{item.strategy} | {item.hold_bars} | "
            f"{item.pass_count}/{item.stock_count} | "
            f"{_format_pf(item.aggregate_profit_factor_status, item.aggregate_profit_factor)} | "
            f"{item.total_trades} | {item.average_win_rate:.2%} | "
            f"{item.worst_max_drawdown:.2%} |"
        )
    lines.extend(
        [
            "",
            "## Per Stock",
            "",
            "| Symbol | Strategy | Hold | Decision | PF | Trades | Win rate | Avg net PnL | Max drawdown | Overlap |",
            "|---|---|---:|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in sorted(rows, key=lambda item: (item.symbol, item.strategy, item.hold_bars)):
        lines.append(
            "| "
            f"{row.symbol} | {row.strategy} | {row.hold_bars} | {row.decision} | "
            f"{_format_pf(row.profit_factor_status, row.profit_factor)} | "
            f"{row.trade_count} | {row.win_rate:.2%} | {row.average_net_pnl:.2f} | "
            f"{row.max_drawdown:.2%} | {row.overlapping_signal_count} |"
        )
    return "\n".join(lines) + "\n"


def _format_pf(status: str, value: float | None) -> str:
    """
    用途與流程：將 EntryEdge 的 PF status/value 轉成 Markdown 與 CLI 穩定顯示格式。
    參數：status 是 finite/infinite/undefined；value 是 finite PF 數值或 None。
    回傳與錯誤：回傳格式化字串；未知 status 會保留 status 文字以利排查。
    """
    if status == "infinite":
        return "Infinity"
    if value is None:
        return status
    return f"{value:.3f}"


def build_parser() -> argparse.ArgumentParser:
    """
    用途與流程：建立批次 entry-edge sweep 的命令列 parser。
    參數：無。
    回傳與錯誤：回傳 argparse.ArgumentParser；解析錯誤由 argparse 處理。
    """
    parser = argparse.ArgumentParser(
        description="Run EntryEdge across multiple stock CSV files."
    )
    parser.add_argument("--csv", action="append", required=True, help="OHLCV CSV path")
    parser.add_argument(
        "--strategy",
        action="append",
        choices=SUPPORTED_STRATEGY_NAMES,
        help="strategy to include; defaults to daily strategies",
    )
    parser.add_argument("--hold-bars-list", default="1,3,5,10")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--pass-profit-factor", type=float, default=1.5)
    parser.add_argument("--initial-equity", type=float, default=10_000.0)
    parser.add_argument("--commission-bps", type=float, default=1.0)
    parser.add_argument("--slippage-bps", type=float, default=1.0)
    parser.add_argument("--summary-json")
    parser.add_argument("--summary-md")
    return parser


def main(argv: list[str] | None = None) -> int:
    """
    用途與流程：命令列入口，解析多股票 sweep 參數、執行回測、列印 Markdown，並可選擇寫出
    JSON/Markdown 摘要檔。
    參數：argv 是可選命令列參數清單；None 表示使用 sys.argv。
    回傳與錯誤：成功回傳 0；參數、資料或回測錯誤會由 argparse 或底層函式拋出。
    """
    args = build_parser().parse_args(argv)
    strategies = tuple(args.strategy or DEFAULT_STRATEGIES)
    hold_bars_values = parse_hold_bars_list(args.hold_bars_list)
    rows, aggregates = run_sweep(
        csv_paths=[Path(path) for path in args.csv],
        strategies=strategies,
        hold_bars_values=hold_bars_values,
        start=args.start,
        end=args.end,
        pass_profit_factor=args.pass_profit_factor,
        initial_equity=args.initial_equity,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
    )
    markdown = format_markdown(
        rows,
        aggregates,
        start=args.start,
        end=args.end,
        pass_profit_factor=args.pass_profit_factor,
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


if __name__ == "__main__":
    raise SystemExit(main())
