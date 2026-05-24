from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.multi_stock_target_state_sweep import parse_cost_multipliers_list
from tools.portfolio_rotation_sweep import (
    PortfolioRotationResult,
    PortfolioWalkForwardResult,
    build_rolling_windows,
    parse_symbol_group_assignments,
    run_portfolio_rotation_sweep,
    run_walk_forward_rotation,
)


@dataclass(frozen=True)
class PortfolioRotationGridCandidate:
    """portfolio rotation 參數掃描中的單一候選設定。"""

    top_n: int
    breadth_min_positive_count: int
    max_consecutive_selections_per_symbol: int | None
    min_average_traded_value: float | None


@dataclass(frozen=True)
class PortfolioRotationGridRow:
    """單一候選設定的 full-window、cost-stress 與 rolling stability 摘要。"""

    rank: int
    decision: str
    gate_pass: bool
    failure_reasons: list[str]
    top_n: int
    breadth_min_positive_count: int
    max_consecutive_selections_per_symbol: int | None
    min_average_traded_value: float | None
    primary_cost_label: str
    total_return: float
    benchmark_excess_return: float
    information_ratio: float | None
    max_drawdown: float
    active_max_drawdown: float
    top3_symbol_abs_contribution_share: float
    top3_group_abs_contribution_share: float
    stress_cost_label: str | None
    stress_benchmark_excess_return: float | None
    stress_information_ratio: float | None
    rolling_window_count: int
    weakest_rolling_window: str | None
    min_rolling_information_ratio: float | None
    min_rolling_benchmark_excess_return: float | None
    worst_rolling_max_drawdown: float | None
    max_rolling_top3_symbol_abs_contribution_share: float | None
    max_rolling_top3_group_abs_contribution_share: float | None


@dataclass(frozen=True)
class PortfolioRotationGridSearch:
    """portfolio rotation 參數掃描輸出 payload。"""

    schema_version: str
    csv_paths: list[str]
    start: str | None
    end: str | None
    candidate_count: int
    primary_cost_label: str
    stress_cost_label: str | None
    thresholds: dict[str, float]
    rows: list[PortfolioRotationGridRow]


def build_parser() -> argparse.ArgumentParser:
    """
    用途與流程：建立 adjusted portfolio rotation grid search CLI parser，集中管理參數網格、成本與 gate 門檻。
    參數：無。
    回傳與錯誤：回傳 argparse.ArgumentParser；命令列格式錯誤由 argparse 處理，語意驗證由 main 與 helper 負責。
    """
    parser = argparse.ArgumentParser(
        description=(
            "Grid-search portfolio rotation parameters and rank candidates "
            "with full-window, cost-stress, and rolling stability metrics."
        )
    )
    parser.add_argument("--csv", action="append", required=True, help="OHLCV CSV path")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--initial-equity", type=float, default=10_000.0)
    parser.add_argument("--commission-bps", type=float, default=1.0)
    parser.add_argument("--slippage-bps", type=float, default=1.0)
    parser.add_argument("--transaction-tax-bps", type=float, default=0.0)
    parser.add_argument("--cost-multipliers-list", default="1,3")
    parser.add_argument("--primary-cost-label", default="1x")
    parser.add_argument("--stress-cost-label", default="3x")
    parser.add_argument(
        "--rebalance-frequency",
        choices=("daily", "weekly", "monthly"),
        default="monthly",
    )
    parser.add_argument("--lookback-bars", type=int, default=21)
    parser.add_argument("--min-return", type=float, default=0.0)
    parser.add_argument("--periods-per-year", type=int, default=252)
    parser.add_argument("--top-n-list", default="3,4,5")
    parser.add_argument("--breadth-lookback-bars", type=int, default=42)
    parser.add_argument("--breadth-min-positive-count-list", default="2,3,4,5")
    parser.add_argument("--breadth-positive-threshold", type=float, default=0.0)
    parser.add_argument("--liquidity-lookback-bars", type=int, default=20)
    parser.add_argument("--min-average-traded-value-list", default="500000000")
    parser.add_argument("--max-consecutive-selections-list", default="4,5,6")
    parser.add_argument("--symbol-group", action="append")
    parser.add_argument("--rolling-window-months", type=int, default=24)
    parser.add_argument("--rolling-step-months", type=int, default=12)
    parser.add_argument("--rolling-min-months", type=int, default=12)
    parser.add_argument("--min-full-ir", type=float, default=1.0)
    parser.add_argument("--min-rolling-ir", type=float, default=0.20)
    parser.add_argument("--min-rolling-excess-return", type=float, default=0.0)
    parser.add_argument("--max-drawdown-abs", type=float, default=0.30)
    parser.add_argument("--max-top3-group-share", type=float, default=0.90)
    parser.add_argument("--summary-json", type=Path)
    parser.add_argument("--summary-md", type=Path)
    return parser


def run_portfolio_rotation_grid_search(
    *,
    csv_paths: list[Path],
    start: str | None,
    end: str | None,
    cost_multipliers: tuple[float, ...],
    primary_cost_label: str,
    stress_cost_label: str | None,
    initial_equity: float,
    commission_bps: float,
    slippage_bps: float,
    transaction_tax_bps: float,
    rebalance_frequency: str,
    lookback_bars: int,
    min_return: float,
    periods_per_year: int,
    top_n_values: list[int],
    breadth_lookback_bars: int,
    breadth_min_positive_count_values: list[int],
    breadth_positive_threshold: float,
    liquidity_lookback_bars: int,
    min_average_traded_value_values: list[float | None],
    max_consecutive_selection_values: list[int | None],
    symbol_groups: dict[str, str] | None,
    rolling_window_months: int,
    rolling_step_months: int,
    rolling_min_months: int,
    thresholds: dict[str, float],
) -> PortfolioRotationGridSearch:
    """
    用途與流程：對 portfolio rotation 的 top-N、breadth、連續入選上限與 liquidity gate 做 deterministic grid search，並依 adjusted stability 指標排序。
    參數：csv_paths/start/end 定義資料；cost_multipliers 與成本標籤定義 full/stress 比較；top/breadth/liquidity/max-consecutive lists 定義參數網格；symbol_groups 是可選產業分組；rolling window 參數定義穩健性檢查；thresholds 定義 gate。
    回傳與錯誤：回傳 PortfolioRotationGridSearch；日期窗、成本標籤、參數或回測資料不合法時拋出 ValueError。
    """
    windows = build_rolling_windows(
        start=start,
        end=end,
        window_months=rolling_window_months,
        step_months=rolling_step_months,
        min_window_months=rolling_min_months,
    )
    candidates = _build_candidates(
        top_n_values=top_n_values,
        breadth_min_positive_count_values=breadth_min_positive_count_values,
        min_average_traded_value_values=min_average_traded_value_values,
        max_consecutive_selection_values=max_consecutive_selection_values,
    )
    rows: list[PortfolioRotationGridRow] = []
    for candidate in candidates:
        full_results = run_portfolio_rotation_sweep(
            csv_paths=csv_paths,
            start=start,
            end=end,
            cost_multipliers=cost_multipliers,
            initial_equity=initial_equity,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            transaction_tax_bps=transaction_tax_bps,
            rebalance_frequency=rebalance_frequency,
            lookback_bars=lookback_bars,
            top_n=candidate.top_n,
            min_return=min_return,
            periods_per_year=periods_per_year,
            breadth_filter=True,
            breadth_lookback_bars=breadth_lookback_bars,
            breadth_min_positive_count=candidate.breadth_min_positive_count,
            breadth_positive_threshold=breadth_positive_threshold,
            liquidity_lookback_bars=liquidity_lookback_bars,
            min_average_traded_value=candidate.min_average_traded_value,
            symbol_groups=symbol_groups,
            max_consecutive_selections_per_symbol=(
                candidate.max_consecutive_selections_per_symbol
            ),
        )
        walk_forward_results, _retention_rows = run_walk_forward_rotation(
            windows=windows,
            csv_paths=csv_paths,
            cost_multipliers=cost_multipliers,
            initial_equity=initial_equity,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            transaction_tax_bps=transaction_tax_bps,
            rebalance_frequency=rebalance_frequency,
            lookback_bars=lookback_bars,
            top_n=candidate.top_n,
            min_return=min_return,
            periods_per_year=periods_per_year,
            breadth_filter=True,
            breadth_lookback_bars=breadth_lookback_bars,
            breadth_min_positive_count=candidate.breadth_min_positive_count,
            breadth_positive_threshold=breadth_positive_threshold,
            liquidity_lookback_bars=liquidity_lookback_bars,
            min_average_traded_value=candidate.min_average_traded_value,
            symbol_groups=symbol_groups,
            max_consecutive_selections_per_symbol=(
                candidate.max_consecutive_selections_per_symbol
            ),
        )
        rows.append(
            _build_grid_row(
                candidate=candidate,
                full_results=full_results,
                walk_forward_results=walk_forward_results,
                primary_cost_label=primary_cost_label,
                stress_cost_label=stress_cost_label,
                thresholds=thresholds,
            )
        )

    ranked_rows = [
        _replace_rank(row, rank=index + 1)
        for index, row in enumerate(sorted(rows, key=_ranking_key))
    ]
    return PortfolioRotationGridSearch(
        schema_version="portfolio_rotation_grid_search.v1",
        csv_paths=[path.as_posix() for path in csv_paths],
        start=start,
        end=end,
        candidate_count=len(ranked_rows),
        primary_cost_label=primary_cost_label,
        stress_cost_label=stress_cost_label,
        thresholds=thresholds,
        rows=ranked_rows,
    )


def write_grid_search_json(search: PortfolioRotationGridSearch, output_json: Path) -> None:
    """
    用途與流程：將 grid search 結果寫成 deterministic JSON，供後續筆記與自動化比較引用。
    參數：search 是 run_portfolio_rotation_grid_search 的結果；output_json 是輸出路徑。
    回傳與錯誤：回傳 None；寫檔失敗時由 pathlib 拋出例外。
    """
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(asdict(search), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="",
    )


def format_grid_search_markdown(search: PortfolioRotationGridSearch) -> str:
    """
    用途與流程：把 grid search 排名轉成 Markdown，優先呈現 gate 狀態、full-window 指標與 rolling 弱點。
    參數：search 是 run_portfolio_rotation_grid_search 的結果。
    回傳與錯誤：回傳 Markdown 字串；此函式不做 I/O。
    """
    lines = [
        "# Portfolio Rotation Grid Search",
        "",
        f"- Schema: `{search.schema_version}`",
        f"- Candidates: `{search.candidate_count}`",
        f"- Primary cost: `{search.primary_cost_label}`",
    ]
    if search.stress_cost_label is not None:
        lines.append(f"- Stress cost: `{search.stress_cost_label}`")
    lines.extend(
        [
            "",
            "## Ranking",
            "",
            "| Rank | Decision | Top N | Breadth min | Max consecutive | Liquidity min | Full IR | Full excess | MDD | Stress IR | Min rolling IR | Min rolling excess | Weakest window | Max rolling top3 group | Failure reasons |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|",
        ]
    )
    for row in search.rows:
        lines.append(
            "| "
            f"{row.rank} | {row.decision} | {row.top_n} | "
            f"{row.breadth_min_positive_count} | "
            f"{_format_optional_int(row.max_consecutive_selections_per_symbol)} | "
            f"{_format_optional_float(row.min_average_traded_value)} | "
            f"{_format_decimal(row.information_ratio)} | "
            f"{_format_percent(row.benchmark_excess_return)} | "
            f"{_format_percent(row.max_drawdown)} | "
            f"{_format_decimal(row.stress_information_ratio)} | "
            f"{_format_decimal(row.min_rolling_information_ratio)} | "
            f"{_format_percent(row.min_rolling_benchmark_excess_return)} | "
            f"{row.weakest_rolling_window or 'n/a'} | "
            f"{_format_percent(row.max_rolling_top3_group_abs_contribution_share)} | "
            f"{'; '.join(row.failure_reasons) or 'none'} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_grid_search_markdown(search: PortfolioRotationGridSearch, output_md: Path) -> None:
    """
    用途與流程：將 grid search 結果寫成 Markdown artifact。
    參數：search 是掃描結果；output_md 是輸出 Markdown 路徑。
    回傳與錯誤：回傳 None；寫檔失敗時由 pathlib 拋出例外。
    """
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(
        format_grid_search_markdown(search),
        encoding="utf-8",
        newline="",
    )


def main(argv: list[str] | None = None) -> int:
    """
    用途與流程：CLI 入口，解析參數網格、執行 portfolio rotation grid search，並輸出 Markdown/JSON。
    參數：argv 是可選命令列參數清單；None 時使用系統命令列。
    回傳與錯誤：成功回傳 0；輸入資料、成本標籤或參數網格不合法時拋出 ValueError。
    """
    args = build_parser().parse_args(argv)
    thresholds = {
        "min_full_ir": args.min_full_ir,
        "min_rolling_ir": args.min_rolling_ir,
        "min_rolling_excess_return": args.min_rolling_excess_return,
        "max_drawdown_abs": args.max_drawdown_abs,
        "max_top3_group_share": args.max_top3_group_share,
    }
    search = run_portfolio_rotation_grid_search(
        csv_paths=[Path(path) for path in args.csv],
        start=args.start,
        end=args.end,
        cost_multipliers=parse_cost_multipliers_list(args.cost_multipliers_list),
        primary_cost_label=args.primary_cost_label,
        stress_cost_label=args.stress_cost_label or None,
        initial_equity=args.initial_equity,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
        transaction_tax_bps=args.transaction_tax_bps,
        rebalance_frequency=args.rebalance_frequency,
        lookback_bars=args.lookback_bars,
        min_return=args.min_return,
        periods_per_year=args.periods_per_year,
        top_n_values=_parse_int_list(args.top_n_list, option_name="--top-n-list"),
        breadth_lookback_bars=args.breadth_lookback_bars,
        breadth_min_positive_count_values=_parse_int_list(
            args.breadth_min_positive_count_list,
            option_name="--breadth-min-positive-count-list",
        ),
        breadth_positive_threshold=args.breadth_positive_threshold,
        liquidity_lookback_bars=args.liquidity_lookback_bars,
        min_average_traded_value_values=_parse_optional_float_list(
            args.min_average_traded_value_list,
            option_name="--min-average-traded-value-list",
        ),
        max_consecutive_selection_values=_parse_optional_int_list(
            args.max_consecutive_selections_list,
            option_name="--max-consecutive-selections-list",
        ),
        symbol_groups=parse_symbol_group_assignments(args.symbol_group),
        rolling_window_months=args.rolling_window_months,
        rolling_step_months=args.rolling_step_months,
        rolling_min_months=args.rolling_min_months,
        thresholds=thresholds,
    )
    markdown = format_grid_search_markdown(search)
    if args.summary_json is not None:
        write_grid_search_json(search, args.summary_json)
    if args.summary_md is not None:
        write_grid_search_markdown(search, args.summary_md)
    print(markdown, end="")
    return 0


def _build_candidates(
    *,
    top_n_values: list[int],
    breadth_min_positive_count_values: list[int],
    min_average_traded_value_values: list[float | None],
    max_consecutive_selection_values: list[int | None],
) -> list[PortfolioRotationGridCandidate]:
    """
    用途與流程：展開 CLI 傳入的參數清單，形成 deterministic candidate 網格。
    參數：四個 list 分別代表 top-N、breadth min、liquidity threshold 與單檔連續入選上限。
    回傳與錯誤：回傳候選設定清單；若清單為空或參數非正，拋出 ValueError。
    """
    if not top_n_values:
        raise ValueError("top-n list cannot be empty")
    if not breadth_min_positive_count_values:
        raise ValueError("breadth min list cannot be empty")
    if not min_average_traded_value_values:
        raise ValueError("liquidity list cannot be empty")
    if not max_consecutive_selection_values:
        raise ValueError("max consecutive list cannot be empty")
    candidates = [
        PortfolioRotationGridCandidate(
            top_n=top_n,
            breadth_min_positive_count=breadth_min,
            max_consecutive_selections_per_symbol=max_consecutive,
            min_average_traded_value=liquidity,
        )
        for top_n, breadth_min, max_consecutive, liquidity in product(
            top_n_values,
            breadth_min_positive_count_values,
            max_consecutive_selection_values,
            min_average_traded_value_values,
        )
    ]
    return candidates


def _build_grid_row(
    *,
    candidate: PortfolioRotationGridCandidate,
    full_results: list[PortfolioRotationResult],
    walk_forward_results: list[PortfolioWalkForwardResult],
    primary_cost_label: str,
    stress_cost_label: str | None,
    thresholds: dict[str, float],
) -> PortfolioRotationGridRow:
    """
    用途與流程：從單一候選的 full-window 與 rolling 回測結果建立排名列，並套用策略品質 gate。
    參數：candidate 是參數設定；full_results 是多成本 full-window 結果；walk_forward_results 是 rolling 結果；成本標籤定義主排序與壓力成本；thresholds 定義 gate。
    回傳與錯誤：回傳 PortfolioRotationGridRow；指定成本標籤不存在時拋出 ValueError。
    """
    primary = _find_result_by_cost(full_results, primary_cost_label)
    stress = (
        _find_result_by_cost(full_results, stress_cost_label)
        if stress_cost_label is not None
        else None
    )
    rolling_results = [
        _find_result_by_cost(window_result.results, primary_cost_label)
        for window_result in walk_forward_results
    ]
    weakest = _weakest_rolling_result(walk_forward_results, primary_cost_label)
    min_rolling_ir = _min_optional(
        result.information_ratio for result in rolling_results
    )
    min_rolling_excess = min(
        (result.benchmark_excess_return for result in rolling_results),
        default=None,
    )
    worst_rolling_mdd = min((result.max_drawdown for result in rolling_results), default=None)
    max_rolling_top3_symbol = max(
        (result.top3_symbol_abs_contribution_share for result in rolling_results),
        default=None,
    )
    max_rolling_top3_group = max(
        (result.top3_group_abs_contribution_share for result in rolling_results),
        default=None,
    )
    failure_reasons = _gate_failure_reasons(
        primary=primary,
        min_rolling_ir=min_rolling_ir,
        min_rolling_excess=min_rolling_excess,
        max_rolling_top3_group=max_rolling_top3_group,
        thresholds=thresholds,
    )
    return PortfolioRotationGridRow(
        rank=0,
        decision="candidate" if not failure_reasons else "compare-only",
        gate_pass=not failure_reasons,
        failure_reasons=failure_reasons,
        top_n=candidate.top_n,
        breadth_min_positive_count=candidate.breadth_min_positive_count,
        max_consecutive_selections_per_symbol=(
            candidate.max_consecutive_selections_per_symbol
        ),
        min_average_traded_value=candidate.min_average_traded_value,
        primary_cost_label=primary.cost_label,
        total_return=primary.total_return,
        benchmark_excess_return=primary.benchmark_excess_return,
        information_ratio=primary.information_ratio,
        max_drawdown=primary.max_drawdown,
        active_max_drawdown=primary.active_max_drawdown,
        top3_symbol_abs_contribution_share=primary.top3_symbol_abs_contribution_share,
        top3_group_abs_contribution_share=primary.top3_group_abs_contribution_share,
        stress_cost_label=stress.cost_label if stress is not None else None,
        stress_benchmark_excess_return=(
            stress.benchmark_excess_return if stress is not None else None
        ),
        stress_information_ratio=stress.information_ratio if stress is not None else None,
        rolling_window_count=len(rolling_results),
        weakest_rolling_window=weakest[0],
        min_rolling_information_ratio=min_rolling_ir,
        min_rolling_benchmark_excess_return=min_rolling_excess,
        worst_rolling_max_drawdown=worst_rolling_mdd,
        max_rolling_top3_symbol_abs_contribution_share=max_rolling_top3_symbol,
        max_rolling_top3_group_abs_contribution_share=max_rolling_top3_group,
    )


def _gate_failure_reasons(
    *,
    primary: PortfolioRotationResult,
    min_rolling_ir: float | None,
    min_rolling_excess: float | None,
    max_rolling_top3_group: float | None,
    thresholds: dict[str, float],
) -> list[str]:
    """
    用途與流程：依策略評估 gate 產生 failure reason，讓排名不只看單一 IR。
    參數：primary 是 full-window 主要成本結果；min_rolling_ir/min_rolling_excess/max_rolling_top3_group 是 rolling 摘要；thresholds 是 gate 門檻。
    回傳與錯誤：回傳 failure reason list；缺值視為失敗但不拋錯。
    """
    reasons: list[str] = []
    full_ir = primary.information_ratio
    if full_ir is None or full_ir < thresholds["min_full_ir"]:
        reasons.append("full_ir_below_threshold")
    if min_rolling_ir is None or min_rolling_ir < thresholds["min_rolling_ir"]:
        reasons.append("rolling_ir_below_threshold")
    if (
        min_rolling_excess is None
        or min_rolling_excess < thresholds["min_rolling_excess_return"]
    ):
        reasons.append("rolling_excess_below_threshold")
    if abs(primary.max_drawdown) > thresholds["max_drawdown_abs"]:
        reasons.append("drawdown_above_threshold")
    if (
        max_rolling_top3_group is None
        or max_rolling_top3_group > thresholds["max_top3_group_share"]
    ):
        reasons.append("group_concentration_above_threshold")
    return reasons


def _ranking_key(row: PortfolioRotationGridRow) -> tuple[Any, ...]:
    """
    用途與流程：定義 grid search 排名順序，先看 gate，再看 rolling stability，最後看 full-window edge 與集中度。
    參數：row 是已建立但 rank 尚未重編的掃描列。
    回傳與錯誤：回傳可排序 tuple；此函式不主動拋錯。
    """
    return (
        0 if row.gate_pass else 1,
        len(row.failure_reasons),
        -_none_to_negative_inf(row.min_rolling_information_ratio),
        -_none_to_negative_inf(row.information_ratio),
        abs(row.worst_rolling_max_drawdown)
        if row.worst_rolling_max_drawdown is not None
        else float("inf"),
        _none_to_positive_inf(row.max_rolling_top3_group_abs_contribution_share),
        _none_to_positive_inf(row.max_rolling_top3_symbol_abs_contribution_share),
        -row.benchmark_excess_return,
    )


def _replace_rank(row: PortfolioRotationGridRow, *, rank: int) -> PortfolioRotationGridRow:
    """
    用途與流程：用 dataclass 欄位建立相同內容但更新 rank 的 row。
    參數：row 是原始排名列；rank 是新的 1-based 排名。
    回傳與錯誤：回傳 PortfolioRotationGridRow；此函式不做 I/O。
    """
    payload = asdict(row)
    payload["rank"] = rank
    return PortfolioRotationGridRow(**payload)


def _find_result_by_cost(
    results: list[PortfolioRotationResult],
    cost_label: str,
) -> PortfolioRotationResult:
    """
    用途與流程：從多成本結果中找出指定 cost_label 的 portfolio rotation result。
    參數：results 是 full 或 rolling 的結果清單；cost_label 是目標成本標籤。
    回傳與錯誤：找到時回傳 PortfolioRotationResult；找不到時拋出 ValueError。
    """
    for result in results:
        if result.cost_label == cost_label:
            return result
    raise ValueError(f"missing cost label: {cost_label}")


def _weakest_rolling_result(
    walk_forward_results: list[PortfolioWalkForwardResult],
    cost_label: str,
) -> tuple[str | None, PortfolioRotationResult | None]:
    """
    用途與流程：找出指定成本下 rolling IR 最弱的 window，方便報表定位穩健性破口。
    參數：walk_forward_results 是 rolling 結果；cost_label 是目標成本標籤。
    回傳與錯誤：回傳 `(window label, result)`；沒有可比較 IR 時回傳 `(None, None)`。
    """
    candidates: list[tuple[str, PortfolioRotationResult]] = []
    for window_result in walk_forward_results:
        result = _find_result_by_cost(window_result.results, cost_label)
        if result.information_ratio is not None:
            candidates.append((window_result.window.label, result))
    if not candidates:
        return None, None
    return min(candidates, key=lambda item: item[1].information_ratio or 0.0)


def _parse_int_list(raw: str, *, option_name: str) -> list[int]:
    """
    用途與流程：解析逗號分隔正整數清單，供 top-N 與 breadth-min 參數網格使用。
    參數：raw 是 CLI 字串；option_name 是錯誤訊息中的參數名稱。
    回傳與錯誤：回傳 int list；空清單、非整數或非正數時拋出 ValueError。
    """
    values: list[int] = []
    for token in _split_tokens(raw):
        try:
            value = int(token)
        except ValueError as exc:
            raise ValueError(f"{option_name} must contain integers") from exc
        if value <= 0:
            raise ValueError(f"{option_name} values must be positive")
        values.append(value)
    if not values:
        raise ValueError(f"{option_name} cannot be empty")
    return values


def _parse_optional_int_list(raw: str, *, option_name: str) -> list[int | None]:
    """
    用途與流程：解析逗號分隔正整數或 none 清單，供可停用的 max-consecutive 網格使用。
    參數：raw 是 CLI 字串；option_name 是錯誤訊息中的參數名稱。
    回傳與錯誤：回傳 int/None list；格式不合法時拋出 ValueError。
    """
    values: list[int | None] = []
    for token in _split_tokens(raw):
        if token.lower() == "none":
            values.append(None)
            continue
        try:
            value = int(token)
        except ValueError as exc:
            raise ValueError(f"{option_name} must contain integers or none") from exc
        if value <= 0:
            raise ValueError(f"{option_name} values must be positive")
        values.append(value)
    if not values:
        raise ValueError(f"{option_name} cannot be empty")
    return values


def _parse_optional_float_list(raw: str, *, option_name: str) -> list[float | None]:
    """
    用途與流程：解析逗號分隔正浮點數或 none 清單，供 liquidity gate 網格使用。
    參數：raw 是 CLI 字串；option_name 是錯誤訊息中的參數名稱。
    回傳與錯誤：回傳 float/None list；格式不合法時拋出 ValueError。
    """
    values: list[float | None] = []
    for token in _split_tokens(raw):
        if token.lower() == "none":
            values.append(None)
            continue
        try:
            value = float(token)
        except ValueError as exc:
            raise ValueError(f"{option_name} must contain numbers or none") from exc
        if value <= 0:
            raise ValueError(f"{option_name} values must be positive")
        values.append(value)
    if not values:
        raise ValueError(f"{option_name} cannot be empty")
    return values


def _split_tokens(raw: str) -> list[str]:
    """
    用途與流程：拆分逗號分隔 CLI 清單並移除空白。
    參數：raw 是原始 CLI 字串。
    回傳與錯誤：回傳非空 token list；此函式不主動拋錯。
    """
    return [token.strip() for token in raw.split(",") if token.strip()]


def _min_optional(values: Any) -> float | None:
    """
    用途與流程：計算可選浮點迭代器中的最小值，忽略 None。
    參數：values 是可能包含 None 的可迭代物件。
    回傳與錯誤：若有數值回傳最小值，否則回傳 None。
    """
    filtered = [value for value in values if value is not None]
    if not filtered:
        return None
    return min(filtered)


def _none_to_negative_inf(value: float | None) -> float:
    """
    用途與流程：排序時把 None 視為負無限，避免缺值候選排在有效結果之前。
    參數：value 是可選浮點值。
    回傳與錯誤：回傳 float；此函式不主動拋錯。
    """
    return value if value is not None else float("-inf")


def _none_to_positive_inf(value: float | None) -> float:
    """
    用途與流程：排序時把 None 視為正無限，讓缺少集中度資訊的候選保守排後。
    參數：value 是可選浮點值。
    回傳與錯誤：回傳 float；此函式不主動拋錯。
    """
    return value if value is not None else float("inf")


def _format_percent(value: float | None) -> str:
    """
    用途與流程：將小數形式報酬、回撤或占比格式化為百分比。
    參數：value 是小數值或 None。
    回傳與錯誤：回傳字串；None 回傳 `n/a`。
    """
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def _format_decimal(value: float | None) -> str:
    """
    用途與流程：將 Information Ratio 等小數指標格式化為三位小數。
    參數：value 是小數值或 None。
    回傳與錯誤：回傳字串；None 回傳 `n/a`。
    """
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def _format_optional_int(value: int | None) -> str:
    """
    用途與流程：格式化可選整數，讓 Markdown 表格對 disabled gate 顯示 none。
    參數：value 是 int 或 None。
    回傳與錯誤：回傳字串；此函式不主動拋錯。
    """
    return str(value) if value is not None else "none"


def _format_optional_float(value: float | None) -> str:
    """
    用途與流程：格式化可選浮點數，讓 Markdown 表格對 disabled liquidity gate 顯示 none。
    參數：value 是 float 或 None。
    回傳與錯誤：回傳字串；此函式不主動拋錯。
    """
    if value is None:
        return "none"
    if value.is_integer():
        return str(int(value))
    return f"{value:.6g}"


if __name__ == "__main__":
    raise SystemExit(main())
