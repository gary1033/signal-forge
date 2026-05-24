from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.portfolio_rotation_sweep import (
    align_close_table,
    load_rotation_inputs,
    parse_symbol_group_assignments,
)


@dataclass(frozen=True)
class GroupBreadthStats:
    """單一群組在一個日期窗內的內部動能廣度摘要。"""

    group: str
    member_symbols: tuple[str, ...]
    member_count: int
    rebalance_count: int
    average_positive_member_count: float | None
    average_positive_member_share: float | None
    majority_positive_rebalance_share: float | None
    all_positive_rebalance_share: float | None
    average_member_lookback_return: float | None


@dataclass(frozen=True)
class GroupBreadthWindowRow:
    """單一 full-window 或 rolling window 的 dominant group breadth 驗證列。"""

    scope: str
    window_label: str
    window_start: str
    window_end: str
    cost_label: str
    information_ratio: float | None
    benchmark_excess_return: float
    max_drawdown: float
    active_max_drawdown: float
    max_group_abs_contribution_group: str | None
    max_group_abs_contribution_share: float
    top3_group_abs_contribution_share: float
    dominant_group_member_count: int | None
    dominant_group_rebalance_count: int | None
    dominant_group_average_positive_member_share: float | None
    dominant_group_majority_positive_rebalance_share: float | None
    dominant_group_all_positive_rebalance_share: float | None
    dominant_group_average_member_lookback_return: float | None
    breadth_type: str
    gate_pass: bool
    failure_reasons: list[str]


@dataclass(frozen=True)
class GroupBreadthValidation:
    """portfolio rotation summary 對應 OHLCV 的 dominant group breadth 驗證總結果。"""

    schema_version: str
    source_summary_json: str
    source_csvs: tuple[str, ...]
    cost_label: str
    rebalance_frequency: str
    breadth_lookback_bars: int
    positive_threshold: float
    min_group_member_count: int
    min_average_positive_member_share: float
    min_majority_positive_rebalance_share: float
    min_average_member_return: float
    min_rebalance_count: int
    max_top3_group_share: float
    symbol_groups: dict[str, str]
    row_count: int
    gate_pass: bool
    high_concentration_count: int
    broad_group_momentum_count: int
    narrow_group_momentum_count: int
    single_member_dominant_count: int
    missing_breadth_count: int
    weakest_breadth_window: dict[str, Any] | None
    weakest_ir_window: dict[str, Any] | None
    rows: list[GroupBreadthWindowRow]


def build_parser() -> argparse.ArgumentParser:
    """
    用途與流程：建立 dominant group breadth validation 的 CLI parser，集中定義 summary、CSV、group mapping 與 gate 門檻。
    參數：無。
    回傳與錯誤：回傳 argparse.ArgumentParser；參數型別與必填檢查由 argparse 在 parse_args 階段處理。
    """
    parser = argparse.ArgumentParser(
        description=(
            "Validate whether a portfolio rotation dominant contribution group "
            "is supported by broad member momentum or by narrow/single-member regimes."
        )
    )
    parser.add_argument("--summary-json", type=Path, required=True)
    parser.add_argument("--csv", action="append", required=True, help="OHLCV CSV path")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--cost-label", default="1x")
    parser.add_argument(
        "--rebalance-frequency",
        choices=("daily", "weekly", "monthly"),
        help="Override summary rebalance frequency.",
    )
    parser.add_argument(
        "--breadth-lookback-bars",
        type=int,
        help="Override summary breadth lookback bars.",
    )
    parser.add_argument(
        "--positive-threshold",
        type=float,
        help="Override summary breadth positive threshold.",
    )
    parser.add_argument(
        "--symbol-group",
        action="append",
        help="symbol-to-group mapping, for example 2330:semiconductor",
    )
    parser.add_argument("--min-group-member-count", type=int, default=2)
    parser.add_argument("--min-average-positive-member-share", type=float, default=0.60)
    parser.add_argument(
        "--min-majority-positive-rebalance-share",
        type=float,
        default=0.50,
    )
    parser.add_argument("--min-average-member-return", type=float, default=0.0)
    parser.add_argument("--min-rebalance-count", type=int, default=3)
    parser.add_argument("--max-top3-group-share", type=float, default=0.90)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    return parser


def validate_group_breadth(
    summary_json: Path,
    csv_paths: list[Path],
    *,
    start: str | None = None,
    end: str | None = None,
    cost_label: str = "1x",
    rebalance_frequency: str | None = None,
    breadth_lookback_bars: int | None = None,
    positive_threshold: float | None = None,
    symbol_groups: dict[str, str] | None = None,
    min_group_member_count: int = 2,
    min_average_positive_member_share: float = 0.60,
    min_majority_positive_rebalance_share: float = 0.50,
    min_average_member_return: float = 0.0,
    min_rebalance_count: int = 3,
    max_top3_group_share: float = 0.90,
) -> GroupBreadthValidation:
    """
    用途與流程：讀取 portfolio rotation summary 與 OHLCV CSV，對每個 full/rolling 視窗計算 dominant contribution group 的成員廣度與 gate 結果。
    參數：summary_json 是 portfolio_rotation_sweep 的輸出；csv_paths 是同一股票池 OHLCV；start/end 是載入資料日期窗；cost_label 指定成本倍率；rebalance_frequency、breadth_lookback_bars、positive_threshold 可覆寫 summary 設定；symbol_groups 可覆寫 summary 內的分組；其餘參數是 broad/narrow/single-member gate 門檻。
    回傳與錯誤：回傳 GroupBreadthValidation；summary schema、CSV 資料、日期窗或門檻不合法時拋出 ValueError。
    """
    if min_group_member_count <= 0:
        raise ValueError("min group member count must be positive")
    if min_rebalance_count <= 0:
        raise ValueError("min rebalance count must be positive")
    if not 0.0 <= min_average_positive_member_share <= 1.0:
        raise ValueError("min average positive member share must be between 0 and 1")
    if not 0.0 <= min_majority_positive_rebalance_share <= 1.0:
        raise ValueError("min majority positive rebalance share must be between 0 and 1")
    if not 0.0 <= max_top3_group_share <= 1.0:
        raise ValueError("max top3 group share must be between 0 and 1")

    summary = json.loads(summary_json.read_text(encoding="utf-8"))
    windows = _summary_windows(summary, cost_label=cost_label)
    first_result = windows[0][4]
    effective_frequency = rebalance_frequency or str(
        first_result.get("rebalance_frequency", "monthly")
    )
    if effective_frequency not in {"daily", "weekly", "monthly"}:
        raise ValueError("rebalance frequency must be daily, weekly, or monthly")
    effective_lookback = (
        breadth_lookback_bars
        if breadth_lookback_bars is not None
        else _int_value(first_result, "breadth_lookback_bars")
    )
    if effective_lookback <= 0:
        raise ValueError("breadth lookback bars must be positive")
    effective_threshold = (
        positive_threshold
        if positive_threshold is not None
        else _float_value(first_result, "breadth_positive_threshold")
    )

    loaded = load_rotation_inputs(csv_paths, start=start, end=end)
    timestamps, closes_by_symbol = align_close_table(loaded)
    symbols = sorted(closes_by_symbol)
    effective_groups = _resolve_symbol_groups(
        symbols,
        explicit_groups=symbol_groups or {},
        summary_result=first_result,
    )

    rows: list[GroupBreadthWindowRow] = []
    for scope, label, window_start, window_end, result in windows:
        stats = _group_breadth_stats_for_window(
            timestamps,
            closes_by_symbol,
            symbol_groups=effective_groups,
            window_start=window_start,
            window_end=window_end,
            rebalance_frequency=effective_frequency,
            lookback_bars=effective_lookback,
            positive_threshold=effective_threshold,
        )
        rows.append(
            _build_window_row(
                scope=scope,
                window_label=label,
                window_start=window_start,
                window_end=window_end,
                result=result,
                group_stats=stats,
                min_group_member_count=min_group_member_count,
                min_average_positive_member_share=min_average_positive_member_share,
                min_majority_positive_rebalance_share=(
                    min_majority_positive_rebalance_share
                ),
                min_average_member_return=min_average_member_return,
                min_rebalance_count=min_rebalance_count,
                max_top3_group_share=max_top3_group_share,
            )
        )

    gate_pass = all(row.gate_pass for row in rows)
    return GroupBreadthValidation(
        schema_version="portfolio_rotation_group_breadth_validation.v1",
        source_summary_json=summary_json.as_posix(),
        source_csvs=tuple(path.as_posix() for path in csv_paths),
        cost_label=cost_label,
        rebalance_frequency=effective_frequency,
        breadth_lookback_bars=effective_lookback,
        positive_threshold=effective_threshold,
        min_group_member_count=min_group_member_count,
        min_average_positive_member_share=min_average_positive_member_share,
        min_majority_positive_rebalance_share=min_majority_positive_rebalance_share,
        min_average_member_return=min_average_member_return,
        min_rebalance_count=min_rebalance_count,
        max_top3_group_share=max_top3_group_share,
        symbol_groups=effective_groups,
        row_count=len(rows),
        gate_pass=gate_pass,
        high_concentration_count=sum(
            row.top3_group_abs_contribution_share > max_top3_group_share
            for row in rows
        ),
        broad_group_momentum_count=sum(
            row.breadth_type == "broad_group_momentum" for row in rows
        ),
        narrow_group_momentum_count=sum(
            row.breadth_type == "narrow_group_momentum" for row in rows
        ),
        single_member_dominant_count=sum(
            row.breadth_type == "single_member_group" for row in rows
        ),
        missing_breadth_count=sum(row.breadth_type == "missing_breadth" for row in rows),
        weakest_breadth_window=_weakest_breadth_window(rows),
        weakest_ir_window=_weakest_ir_window(rows),
        rows=rows,
    )


def write_validation_json(validation: GroupBreadthValidation, output_json: Path) -> None:
    """
    用途與流程：將 dominant group breadth validation 寫成 deterministic JSON，供策略 gate 與筆記引用。
    參數：validation 是 validate_group_breadth 回傳結果；output_json 是輸出路徑。
    回傳與錯誤：回傳 None；建立資料夾或寫檔失敗時由 pathlib 拋出例外。
    """
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(asdict(validation), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="",
    )


def format_validation_markdown(validation: GroupBreadthValidation) -> str:
    """
    用途與流程：將 dominant group breadth validation 結果轉成 Markdown，先列 gate 摘要，再列 full/rolling 明細。
    參數：validation 是 validate_group_breadth 回傳結果。
    回傳與錯誤：回傳 Markdown 字串；格式化過程不主動拋錯。
    """
    lines = [
        "# Portfolio Rotation Group Breadth Validation",
        "",
        f"- Source summary: `{validation.source_summary_json}`",
        f"- Cost label: `{validation.cost_label}`",
        f"- Gate pass: `{str(validation.gate_pass).lower()}`",
        f"- Rebalance frequency: `{validation.rebalance_frequency}`",
        f"- Breadth lookback bars: `{validation.breadth_lookback_bars}`",
        f"- Positive threshold: `{_format_percent(validation.positive_threshold)}`",
        (
            "- Min average positive member share: "
            f"`{_format_percent(validation.min_average_positive_member_share)}`"
        ),
        (
            "- Min majority-positive rebalance share: "
            f"`{_format_percent(validation.min_majority_positive_rebalance_share)}`"
        ),
        f"- Min group member count: `{validation.min_group_member_count}`",
        f"- High concentration windows: `{validation.high_concentration_count}`",
        f"- Broad group momentum windows: `{validation.broad_group_momentum_count}`",
        f"- Narrow group momentum windows: `{validation.narrow_group_momentum_count}`",
        f"- Single-member dominant windows: `{validation.single_member_dominant_count}`",
        f"- Missing breadth windows: `{validation.missing_breadth_count}`",
    ]
    if validation.weakest_breadth_window is not None:
        weakest = validation.weakest_breadth_window
        lines.append(
            "- Weakest breadth window: "
            f"`{weakest['window_label']}` = "
            f"`{_format_optional_percent(weakest['average_positive_member_share'])}`"
        )
    if validation.weakest_ir_window is not None:
        weakest_ir = validation.weakest_ir_window
        lines.append(
            "- Weakest IR window: "
            f"`{weakest_ir['window_label']}` = "
            f"`{_format_optional_float(weakest_ir['information_ratio'])}`"
        )
    lines.extend(
        [
            "",
            "## Window Details",
            "",
            (
                "| Scope | Window | Range | IR | Excess | MDD | Active MDD | "
                "Dominant group | Contrib share | Top3 group | Members | Rebalances | "
                "Avg positive share | Majority rebalance | All-positive rebalance | "
                "Avg member return | Breadth type | Gate | Failure reasons |"
            ),
            "|---|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
        ]
    )
    for row in validation.rows:
        lines.append(_format_window_row(row))
    lines.append("")
    return "\n".join(lines)


def write_validation_markdown(
    validation: GroupBreadthValidation, output_md: Path
) -> None:
    """
    用途與流程：將 dominant group breadth validation 結果寫成 Markdown，方便人工審查與同步到策略實驗紀錄。
    參數：validation 是 validate_group_breadth 回傳結果；output_md 是輸出路徑。
    回傳與錯誤：回傳 None；建立資料夾或寫檔失敗時由 pathlib 拋出例外。
    """
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(
        format_validation_markdown(validation), encoding="utf-8", newline=""
    )


def main(argv: list[str] | None = None) -> int:
    """
    用途與流程：CLI 入口，解析參數後執行 dominant group breadth validation，依需求輸出 JSON / Markdown。
    參數：argv 是可選命令列參數；None 時使用 sys.argv。
    回傳與錯誤：成功回傳 0；輸入檔案、summary schema 或 gate 參數不合法時由底層例外回報。
    """
    args = build_parser().parse_args(argv)
    groups = parse_symbol_group_assignments(args.symbol_group)
    validation = validate_group_breadth(
        args.summary_json,
        [Path(path) for path in args.csv],
        start=args.start,
        end=args.end,
        cost_label=args.cost_label,
        rebalance_frequency=args.rebalance_frequency,
        breadth_lookback_bars=args.breadth_lookback_bars,
        positive_threshold=args.positive_threshold,
        symbol_groups=groups,
        min_group_member_count=args.min_group_member_count,
        min_average_positive_member_share=args.min_average_positive_member_share,
        min_majority_positive_rebalance_share=(
            args.min_majority_positive_rebalance_share
        ),
        min_average_member_return=args.min_average_member_return,
        min_rebalance_count=args.min_rebalance_count,
        max_top3_group_share=args.max_top3_group_share,
    )
    if args.output_json:
        write_validation_json(validation, args.output_json)
    markdown = format_validation_markdown(validation)
    if args.output_md:
        write_validation_markdown(validation, args.output_md)
    if not args.output_md:
        print(markdown)
    return 0


def _summary_windows(
    summary: dict[str, Any], *, cost_label: str
) -> list[tuple[str, str, str, str, dict[str, Any]]]:
    """
    用途與流程：從 summary JSON 抽出 full-window 與 rolling-window 的指定成本倍率 result，供後續廣度計算逐窗對齊。
    參數：summary 是 portfolio rotation summary dict；cost_label 是要讀取的成本倍率標籤。
    回傳與錯誤：回傳 `(scope, label, start, end, result)` 清單；缺 result、window 或成本倍率時拋出 ValueError。
    """
    full_result = _find_result_by_cost(_require_list(summary, "results"), cost_label)
    windows = [
        (
            "full",
            "full",
            str(full_result.get("start_timestamp", "")),
            str(full_result.get("end_timestamp", "")),
            full_result,
        )
    ]
    for window_result in _require_list(summary, "walk_forward_results"):
        if not isinstance(window_result, dict):
            raise ValueError("walk_forward_results rows must be objects")
        window = _require_dict(window_result, "window")
        result = _find_result_by_cost(_require_list(window_result, "results"), cost_label)
        windows.append(
            (
                "rolling",
                str(window.get("label", "")),
                str(window.get("start", "")),
                str(window.get("end", "")),
                result,
            )
        )
    return windows


def _resolve_symbol_groups(
    symbols: list[str],
    *,
    explicit_groups: dict[str, str],
    summary_result: dict[str, Any],
) -> dict[str, str]:
    """
    用途與流程：決定本次驗證使用的 symbol -> group mapping；CLI 指定優先，其次採用 summary 內建 mapping，最後補 `ungrouped`。
    參數：symbols 是 CSV 推導出的股票代號；explicit_groups 是 CLI 傳入 mapping；summary_result 是 full-window result。
    回傳與錯誤：回傳依 symbol 排序的 dict；summary mapping 不是文字到文字時拋出 ValueError。
    """
    raw_groups = explicit_groups or summary_result.get("symbol_groups", {})
    if not isinstance(raw_groups, dict):
        raise ValueError("symbol_groups must be an object")
    groups: dict[str, str] = {}
    for symbol in symbols:
        value = raw_groups.get(symbol, "ungrouped")
        if not isinstance(value, str) or not value:
            raise ValueError(f"invalid group for symbol: {symbol}")
        groups[symbol] = value
    return dict(sorted(groups.items()))


def _group_breadth_stats_for_window(
    timestamps: list[str],
    closes_by_symbol: dict[str, list[float]],
    *,
    symbol_groups: dict[str, str],
    window_start: str,
    window_end: str,
    rebalance_frequency: str,
    lookback_bars: int,
    positive_threshold: float,
) -> dict[str, GroupBreadthStats]:
    """
    用途與流程：在單一日期窗內用 window-local rebalance index 計算每個 group 的正動能成員比例與平均 lookback return。
    參數：timestamps/closes_by_symbol 是共同日期矩陣；symbol_groups 定義分組；window_start/window_end 定義日期窗；rebalance_frequency 決定抽樣點；lookback_bars 與 positive_threshold 定義成員正動能。
    回傳與錯誤：回傳 group 到 GroupBreadthStats；日期窗內資料不足時各群組 rebalance_count 會是 0，不主動拋錯。
    """
    local_indices = [
        index
        for index, timestamp in enumerate(timestamps)
        if window_start[:10] <= timestamp[:10] <= window_end[:10]
    ]
    local_timestamps = [timestamps[index] for index in local_indices]
    local_closes = {
        symbol: [values[index] for index in local_indices]
        for symbol, values in closes_by_symbol.items()
    }
    members_by_group: dict[str, list[str]] = {}
    for symbol, group in symbol_groups.items():
        members_by_group.setdefault(group, []).append(symbol)
    for members in members_by_group.values():
        members.sort()

    samples_by_group: dict[str, list[tuple[int, float, float]]] = {
        group: [] for group in members_by_group
    }
    for index in range(1, len(local_timestamps)):
        if index < lookback_bars:
            continue
        if not _is_rebalance_index(
            local_timestamps,
            index=index,
            frequency=rebalance_frequency,
        ):
            continue
        for group, members in members_by_group.items():
            returns = [
                (local_closes[symbol][index] / local_closes[symbol][index - lookback_bars])
                - 1.0
                for symbol in members
            ]
            positive_count = sum(
                member_return > positive_threshold for member_return in returns
            )
            samples_by_group[group].append(
                (
                    positive_count,
                    positive_count / len(members),
                    sum(returns) / len(returns),
                )
            )

    return {
        group: _summarize_group_breadth(group, tuple(members), samples_by_group[group])
        for group, members in sorted(members_by_group.items())
    }


def _summarize_group_breadth(
    group: str,
    member_symbols: tuple[str, ...],
    samples: list[tuple[int, float, float]],
) -> GroupBreadthStats:
    """
    用途與流程：將 rebalance samples 聚合成群組廣度摘要，包含平均正動能成員數、比例與多數成員同向比例。
    參數：group 是群組名稱；member_symbols 是群組成員；samples 每筆為 `(positive_count, positive_share, average_return)`。
    回傳與錯誤：回傳 GroupBreadthStats；samples 為空時相關平均值回傳 None。
    """
    if not samples:
        return GroupBreadthStats(
            group=group,
            member_symbols=member_symbols,
            member_count=len(member_symbols),
            rebalance_count=0,
            average_positive_member_count=None,
            average_positive_member_share=None,
            majority_positive_rebalance_share=None,
            all_positive_rebalance_share=None,
            average_member_lookback_return=None,
        )
    member_count = len(member_symbols)
    return GroupBreadthStats(
        group=group,
        member_symbols=member_symbols,
        member_count=member_count,
        rebalance_count=len(samples),
        average_positive_member_count=sum(sample[0] for sample in samples)
        / len(samples),
        average_positive_member_share=sum(sample[1] for sample in samples)
        / len(samples),
        majority_positive_rebalance_share=sum(
            sample[0] >= ((member_count // 2) + 1) for sample in samples
        )
        / len(samples),
        all_positive_rebalance_share=sum(sample[0] == member_count for sample in samples)
        / len(samples),
        average_member_lookback_return=sum(sample[2] for sample in samples)
        / len(samples),
    )


def _build_window_row(
    *,
    scope: str,
    window_label: str,
    window_start: str,
    window_end: str,
    result: dict[str, Any],
    group_stats: dict[str, GroupBreadthStats],
    min_group_member_count: int,
    min_average_positive_member_share: float,
    min_majority_positive_rebalance_share: float,
    min_average_member_return: float,
    min_rebalance_count: int,
    max_top3_group_share: float,
) -> GroupBreadthWindowRow:
    """
    用途與流程：將單一 portfolio result 與對應 group breadth stats 合併，產生 dominant group gate result。
    參數：scope/window_* 是輸出視窗資訊；result 是 summary 的成本倍率結果；group_stats 是該窗各群組廣度；其餘為 gate 門檻。
    回傳與錯誤：回傳 GroupBreadthWindowRow；必要績效欄位非數字時拋出 ValueError。
    """
    dominant_group = _optional_str(result.get("max_group_abs_contribution_group"))
    stats = group_stats.get(dominant_group or "")
    breadth_type = _classify_breadth(
        stats,
        min_group_member_count=min_group_member_count,
        min_average_positive_member_share=min_average_positive_member_share,
        min_majority_positive_rebalance_share=min_majority_positive_rebalance_share,
        min_average_member_return=min_average_member_return,
        min_rebalance_count=min_rebalance_count,
    )
    failure_reasons = _failure_reasons(
        stats,
        top3_group_share=_float_value(result, "top3_group_abs_contribution_share"),
        breadth_type=breadth_type,
        min_group_member_count=min_group_member_count,
        min_average_positive_member_share=min_average_positive_member_share,
        min_majority_positive_rebalance_share=min_majority_positive_rebalance_share,
        min_average_member_return=min_average_member_return,
        min_rebalance_count=min_rebalance_count,
        max_top3_group_share=max_top3_group_share,
    )
    return GroupBreadthWindowRow(
        scope=scope,
        window_label=window_label,
        window_start=window_start,
        window_end=window_end,
        cost_label=str(result.get("cost_label", "")),
        information_ratio=_optional_float(result.get("information_ratio")),
        benchmark_excess_return=_float_value(result, "benchmark_excess_return"),
        max_drawdown=_float_value(result, "max_drawdown"),
        active_max_drawdown=_float_value(result, "active_max_drawdown"),
        max_group_abs_contribution_group=dominant_group,
        max_group_abs_contribution_share=_float_value(
            result,
            "max_group_abs_contribution_share",
        ),
        top3_group_abs_contribution_share=_float_value(
            result,
            "top3_group_abs_contribution_share",
        ),
        dominant_group_member_count=stats.member_count if stats else None,
        dominant_group_rebalance_count=stats.rebalance_count if stats else None,
        dominant_group_average_positive_member_share=(
            stats.average_positive_member_share if stats else None
        ),
        dominant_group_majority_positive_rebalance_share=(
            stats.majority_positive_rebalance_share if stats else None
        ),
        dominant_group_all_positive_rebalance_share=(
            stats.all_positive_rebalance_share if stats else None
        ),
        dominant_group_average_member_lookback_return=(
            stats.average_member_lookback_return if stats else None
        ),
        breadth_type=breadth_type,
        gate_pass=not failure_reasons,
        failure_reasons=failure_reasons,
    )


def _classify_breadth(
    stats: GroupBreadthStats | None,
    *,
    min_group_member_count: int,
    min_average_positive_member_share: float,
    min_majority_positive_rebalance_share: float,
    min_average_member_return: float,
    min_rebalance_count: int,
) -> str:
    """
    用途與流程：依 dominant group 的成員數、rebalance 樣本數、正動能廣度與平均報酬分類 broad/narrow/single/missing。
    參數：stats 是 dominant group 的廣度摘要；其餘參數為 gate 門檻。
    回傳與錯誤：回傳 `broad_group_momentum`、`narrow_group_momentum`、`single_member_group` 或 `missing_breadth`；不主動拋錯。
    """
    if stats is None or stats.rebalance_count == 0:
        return "missing_breadth"
    if stats.member_count < min_group_member_count:
        return "single_member_group"
    if (
        stats.rebalance_count >= min_rebalance_count
        and (stats.average_positive_member_share or 0.0)
        >= min_average_positive_member_share
        and (stats.majority_positive_rebalance_share or 0.0)
        >= min_majority_positive_rebalance_share
        and (stats.average_member_lookback_return or 0.0) > min_average_member_return
    ):
        return "broad_group_momentum"
    return "narrow_group_momentum"


def _failure_reasons(
    stats: GroupBreadthStats | None,
    *,
    top3_group_share: float,
    breadth_type: str,
    min_group_member_count: int,
    min_average_positive_member_share: float,
    min_majority_positive_rebalance_share: float,
    min_average_member_return: float,
    min_rebalance_count: int,
    max_top3_group_share: float,
) -> list[str]:
    """
    用途與流程：根據 concentration 與 breadth 分類產生 gate failure reasons，讓報表能直接解釋為何不能升級策略。
    參數：stats 是 dominant group 廣度摘要；top3_group_share 與 breadth_type 是已計算指標；其餘是門檻。
    回傳與錯誤：回傳 failure reason list；不主動拋錯。
    """
    reasons: list[str] = []
    if top3_group_share > max_top3_group_share:
        reasons.append("top3_group_contribution_concentration")
    if stats is None or breadth_type == "missing_breadth":
        reasons.append("missing_dominant_group_breadth")
        return reasons
    if stats.member_count < min_group_member_count:
        reasons.append("single_member_dominant_group")
    if stats.rebalance_count < min_rebalance_count:
        reasons.append("insufficient_rebalance_observations")
    if (
        stats.average_positive_member_share is not None
        and stats.average_positive_member_share < min_average_positive_member_share
    ):
        reasons.append("dominant_group_breadth_below_threshold")
    if (
        stats.majority_positive_rebalance_share is not None
        and stats.majority_positive_rebalance_share
        < min_majority_positive_rebalance_share
    ):
        reasons.append("dominant_group_majority_rebalance_below_threshold")
    if (
        stats.average_member_lookback_return is not None
        and stats.average_member_lookback_return <= min_average_member_return
    ):
        reasons.append("dominant_group_return_below_threshold")
    return reasons


def _weakest_breadth_window(rows: list[GroupBreadthWindowRow]) -> dict[str, Any] | None:
    """
    用途與流程：找出 dominant group 平均正動能成員比例最低的視窗，作為人工優先檢查的 breadth bottleneck。
    參數：rows 是 validation 明細列。
    回傳與錯誤：有可比較資料時回傳精簡 dict；全部缺廣度時回傳 None。
    """
    comparable = [
        row
        for row in rows
        if row.dominant_group_average_positive_member_share is not None
    ]
    if not comparable:
        return None
    row = min(
        comparable,
        key=lambda item: item.dominant_group_average_positive_member_share or 0.0,
    )
    return {
        "scope": row.scope,
        "window_label": row.window_label,
        "max_group_abs_contribution_group": row.max_group_abs_contribution_group,
        "average_positive_member_share": (
            row.dominant_group_average_positive_member_share
        ),
        "breadth_type": row.breadth_type,
    }


def _weakest_ir_window(rows: list[GroupBreadthWindowRow]) -> dict[str, Any] | None:
    """
    用途與流程：找出 Information Ratio 最弱的視窗，方便把 breadth bottleneck 和績效低谷對齊。
    參數：rows 是 validation 明細列。
    回傳與錯誤：有可比較 IR 時回傳精簡 dict；全部 IR 為 None 時回傳 None。
    """
    comparable = [row for row in rows if row.information_ratio is not None]
    if not comparable:
        return None
    row = min(comparable, key=lambda item: item.information_ratio or 0.0)
    return {
        "scope": row.scope,
        "window_label": row.window_label,
        "information_ratio": row.information_ratio,
        "benchmark_excess_return": row.benchmark_excess_return,
        "breadth_type": row.breadth_type,
        "average_positive_member_share": (
            row.dominant_group_average_positive_member_share
        ),
    }


def _format_window_row(row: GroupBreadthWindowRow) -> str:
    """
    用途與流程：把單一 validation row 格式化為 Markdown table row，集中處理百分比、None 與 failure reason 顯示。
    參數：row 是 GroupBreadthWindowRow。
    回傳與錯誤：回傳 Markdown 表格列；不主動拋錯。
    """
    failures = ", ".join(row.failure_reasons) if row.failure_reasons else "none"
    return (
        f"| {row.scope} | `{row.window_label}` | `{row.window_start} to {row.window_end}` | "
        f"{_format_optional_float(row.information_ratio)} | "
        f"{_format_percent(row.benchmark_excess_return)} | "
        f"{_format_percent(row.max_drawdown)} | "
        f"{_format_percent(row.active_max_drawdown)} | "
        f"{row.max_group_abs_contribution_group or 'n/a'} | "
        f"{_format_percent(row.max_group_abs_contribution_share)} | "
        f"{_format_percent(row.top3_group_abs_contribution_share)} | "
        f"{_format_optional_int(row.dominant_group_member_count)} | "
        f"{_format_optional_int(row.dominant_group_rebalance_count)} | "
        f"{_format_optional_percent(row.dominant_group_average_positive_member_share)} | "
        f"{_format_optional_percent(row.dominant_group_majority_positive_rebalance_share)} | "
        f"{_format_optional_percent(row.dominant_group_all_positive_rebalance_share)} | "
        f"{_format_optional_percent(row.dominant_group_average_member_lookback_return)} | "
        f"{row.breadth_type} | `{str(row.gate_pass).lower()}` | {failures} |"
    )


def _find_result_by_cost(results: list[Any], cost_label: str) -> dict[str, Any]:
    """
    用途與流程：從 result list 找出指定 cost_label 的 portfolio result，避免 full/rolling 對錯成本倍率。
    參數：results 是 summary JSON 中的 results list；cost_label 是目標成本標籤。
    回傳與錯誤：找到時回傳 dict；row 不是物件或找不到成本倍率時拋出 ValueError。
    """
    for result in results:
        if not isinstance(result, dict):
            raise ValueError("result rows must be objects")
        if result.get("cost_label") == cost_label:
            return result
    raise ValueError(f"missing cost label: {cost_label}")


def _is_rebalance_index(
    timestamps: list[str],
    *,
    index: int,
    frequency: str,
) -> bool:
    """
    用途與流程：判斷 window-local timestamp 是否為 rebalance bar，語意對齊 portfolio_rotation_sweep 的 daily/weekly/monthly 規則。
    參數：timestamps 是日期序列；index 是目前索引且必須大於 0；frequency 可為 daily、weekly 或 monthly。
    回傳與錯誤：符合再平衡點時回傳 True；frequency 不合法時拋出 ValueError。
    """
    if frequency == "daily":
        return True
    current = _parse_timestamp(timestamps[index])
    previous = _parse_timestamp(timestamps[index - 1])
    if frequency == "weekly":
        return current.isocalendar()[:2] != previous.isocalendar()[:2]
    if frequency == "monthly":
        return (current.year, current.month) != (previous.year, previous.month)
    raise ValueError("rebalance frequency must be daily, weekly, or monthly")


def _parse_timestamp(timestamp: str) -> datetime:
    """
    用途與流程：將 SignalForge timestamp 轉成 datetime，供 rebalance frequency 判斷使用。
    參數：timestamp 是 `YYYY-MM-DD` 或 ISO datetime 字串。
    回傳與錯誤：回傳 datetime；格式不合法時由 datetime.fromisoformat 拋出 ValueError。
    """
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def _require_list(payload: dict[str, Any], key: str) -> list[Any]:
    """
    用途與流程：從 JSON object 讀取必要 list 欄位，避免 schema 錯誤時靜默輸出錯誤驗證結果。
    參數：payload 是 JSON dict；key 是欄位名稱。
    回傳與錯誤：欄位存在且為 list 時回傳；否則拋出 ValueError。
    """
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"summary field must be a list: {key}")
    return value


def _require_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    """
    用途與流程：從 JSON object 讀取必要 dict 欄位，供 rolling window metadata 驗證使用。
    參數：payload 是 JSON dict；key 是欄位名稱。
    回傳與錯誤：欄位存在且為 dict 時回傳；否則拋出 ValueError。
    """
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"summary field must be an object: {key}")
    return value


def _int_value(payload: dict[str, Any], key: str) -> int:
    """
    用途與流程：讀取必要整數欄位，避免用錯 summary schema 時仍然產生可疑報表。
    參數：payload 是 JSON dict；key 是欄位名稱。
    回傳與錯誤：成功時回傳 int；缺欄位、bool 或非整數時拋出 ValueError。
    """
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"summary field must be an integer: {key}")
    return value


def _float_value(payload: dict[str, Any], key: str) -> float:
    """
    用途與流程：讀取必要 numeric 欄位並轉成 float，支援 JSON int/float 但拒絕 bool。
    參數：payload 是 JSON dict；key 是欄位名稱。
    回傳與錯誤：成功時回傳 float；缺欄位或非 numeric 時拋出 ValueError。
    """
    value = _optional_float(payload.get(key))
    if value is None:
        raise ValueError(f"summary field must be numeric: {key}")
    return value


def _optional_float(value: Any) -> float | None:
    """
    用途與流程：將可為 null 的 JSON numeric 欄位轉成 float，統一後續計算與 Markdown 格式化。
    參數：value 是任意 JSON 欄位值。
    回傳與錯誤：None 回傳 None；int/float 回傳 float；bool 或其他型別拋出 ValueError。
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"value must be numeric or null: {value!r}")
    return float(value)


def _optional_str(value: Any) -> str | None:
    """
    用途與流程：將可為 null 的 JSON 文字欄位標準化為 str 或 None。
    參數：value 是任意 JSON 欄位值。
    回傳與錯誤：None 回傳 None；str 回傳原值；其他型別拋出 ValueError。
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"value must be string or null: {value!r}")
    return value


def _format_percent(value: float) -> str:
    """
    用途與流程：將比例數值格式化成百分比字串，供 Markdown 報表固定顯示兩位小數。
    參數：value 是比例值。
    回傳與錯誤：回傳百分比字串；不主動拋錯。
    """
    return f"{value:.2%}"


def _format_optional_percent(value: float | None) -> str:
    """
    用途與流程：將可為 None 的比例數值格式化成 Markdown 友善字串。
    參數：value 是比例值或 None。
    回傳與錯誤：None 回傳 `n/a`；數值回傳百分比字串。
    """
    if value is None:
        return "n/a"
    return _format_percent(value)


def _format_optional_float(value: float | None) -> str:
    """
    用途與流程：將可為 None 的浮點數格式化成三位小數，避免 Markdown table 出現過長小數。
    參數：value 是浮點數或 None。
    回傳與錯誤：None 回傳 `n/a`；數值回傳三位小數字串。
    """
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def _format_optional_int(value: int | None) -> str:
    """
    用途與流程：將可為 None 的整數格式化成 Markdown 友善字串。
    參數：value 是整數或 None。
    回傳與錯誤：None 回傳 `n/a`；整數回傳十進位字串。
    """
    if value is None:
        return "n/a"
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
