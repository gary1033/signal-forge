from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


METRIC_KEYS = (
    "total_return",
    "benchmark_excess_return",
    "information_ratio",
    "max_drawdown",
    "active_max_drawdown",
    "top3_symbol_abs_contribution_share",
    "top3_group_abs_contribution_share",
)


@dataclass(frozen=True)
class PortfolioCompareRow:
    """raw 與 adjusted portfolio rotation 指標對照列。"""

    scope: str
    cost_label: str
    raw_label: str
    adjusted_label: str
    raw_total_return: float | None
    adjusted_total_return: float | None
    delta_total_return: float | None
    raw_benchmark_excess_return: float | None
    adjusted_benchmark_excess_return: float | None
    delta_benchmark_excess_return: float | None
    raw_information_ratio: float | None
    adjusted_information_ratio: float | None
    delta_information_ratio: float | None
    raw_max_drawdown: float | None
    adjusted_max_drawdown: float | None
    delta_max_drawdown: float | None
    raw_active_max_drawdown: float | None
    adjusted_active_max_drawdown: float | None
    delta_active_max_drawdown: float | None
    raw_top3_symbol_abs_contribution_share: float | None
    adjusted_top3_symbol_abs_contribution_share: float | None
    delta_top3_symbol_abs_contribution_share: float | None
    raw_top3_group_abs_contribution_share: float | None
    adjusted_top3_group_abs_contribution_share: float | None
    delta_top3_group_abs_contribution_share: float | None


@dataclass(frozen=True)
class RollingCompareRow:
    """指定 rolling window 與成本倍率下的 raw / adjusted 對照列。"""

    window_label: str
    start: str
    end: str
    comparison: PortfolioCompareRow


@dataclass(frozen=True)
class PortfolioReportComparison:
    """portfolio rotation raw / adjusted 比較結果與 manifest metadata。"""

    schema_version: str
    raw_summary_json: Path
    adjusted_summary_json: Path
    raw_label: str
    adjusted_label: str
    adjusted_batch_manifest_json: Path | None
    adjusted_manifest_summary: dict[str, Any] | None
    full_window: list[PortfolioCompareRow]
    rolling_cost_label: str
    rolling_windows: list[RollingCompareRow]
    adjusted_weakest_rolling_window: dict[str, Any] | None


def build_parser() -> argparse.ArgumentParser:
    """
    用途與流程：建立 raw / adjusted portfolio rotation 比較工具的 CLI parser，集中定義兩份 summary 與 manifest 輸入。
    參數：無。
    回傳與錯誤：回傳 argparse.ArgumentParser；實際檔案存在性與 JSON schema 由後續流程驗證。
    """
    parser = argparse.ArgumentParser(
        description=(
            "Compare raw and adjusted portfolio rotation summary JSON files "
            "and write deterministic comparison artifacts."
        )
    )
    parser.add_argument("--raw-summary-json", required=True, type=Path)
    parser.add_argument("--adjusted-summary-json", required=True, type=Path)
    parser.add_argument("--raw-label", default="raw")
    parser.add_argument("--adjusted-label", default="adjusted-ratio")
    parser.add_argument(
        "--adjusted-batch-manifest-json",
        type=Path,
        help="Optional adjusted OHLCV batch manifest used to build the adjusted report.",
    )
    parser.add_argument(
        "--rolling-cost-label",
        default="1x",
        help="Cost label used for rolling-window comparison rows.",
    )
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    return parser


def compare_portfolio_rotation_reports(
    *,
    raw_summary_json: Path,
    adjusted_summary_json: Path,
    raw_label: str = "raw",
    adjusted_label: str = "adjusted-ratio",
    adjusted_batch_manifest_json: Path | None = None,
    rolling_cost_label: str = "1x",
) -> PortfolioReportComparison:
    """
    用途與流程：讀取 raw 與 adjusted portfolio rotation summary JSON，依成本倍率與 rolling window 對齊後計算 adjusted-minus-raw 差異。
    參數：raw_summary_json/adjusted_summary_json 是 portfolio_rotation_sweep 輸出的 summary JSON；raw_label/adjusted_label 是報表顯示名稱；adjusted_batch_manifest_json 可提供 adjusted 資料批次來源；rolling_cost_label 指定 rolling 比較使用的成本倍率。
    回傳與錯誤：回傳 PortfolioReportComparison；缺少 `results`、成本倍率不一致、rolling window 無法對齊或 manifest 無效時拋出 ValueError。
    """
    raw_summary = _load_summary(raw_summary_json)
    adjusted_summary = _load_summary(adjusted_summary_json)
    raw_results = _results_by_cost(raw_summary)
    adjusted_results = _results_by_cost(adjusted_summary)
    missing_costs = sorted(set(raw_results) - set(adjusted_results))
    if missing_costs:
        raise ValueError("adjusted summary is missing costs: " + ", ".join(missing_costs))

    full_window = [
        _build_compare_row(
            scope="full",
            cost_label=cost_label,
            raw_label=raw_label,
            adjusted_label=adjusted_label,
            raw_result=raw_result,
            adjusted_result=adjusted_results[cost_label],
        )
        for cost_label, raw_result in raw_results.items()
    ]

    rolling_windows = _build_rolling_compare_rows(
        raw_summary=raw_summary,
        adjusted_summary=adjusted_summary,
        raw_label=raw_label,
        adjusted_label=adjusted_label,
        rolling_cost_label=rolling_cost_label,
    )
    adjusted_weakest = _find_weakest_adjusted_rolling(rolling_windows)
    manifest_summary = (
        _load_adjusted_manifest_summary(adjusted_batch_manifest_json)
        if adjusted_batch_manifest_json is not None
        else None
    )
    return PortfolioReportComparison(
        schema_version="portfolio_rotation_raw_adjusted_compare.v1",
        raw_summary_json=raw_summary_json,
        adjusted_summary_json=adjusted_summary_json,
        raw_label=raw_label,
        adjusted_label=adjusted_label,
        adjusted_batch_manifest_json=adjusted_batch_manifest_json,
        adjusted_manifest_summary=manifest_summary,
        full_window=full_window,
        rolling_cost_label=rolling_cost_label,
        rolling_windows=rolling_windows,
        adjusted_weakest_rolling_window=adjusted_weakest,
    )


def write_comparison_json(comparison: PortfolioReportComparison, output_json: Path) -> None:
    """
    用途與流程：將 raw / adjusted 比較結果寫成 deterministic JSON，供後續筆記與自動化驗證引用。
    參數：comparison 是 compare_portfolio_rotation_reports 的結果；output_json 是輸出路徑。
    回傳與錯誤：回傳 None；寫檔失敗時由 pathlib 拋出例外。
    """
    payload = _comparison_to_json_payload(comparison)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="",
    )


def format_comparison_markdown(comparison: PortfolioReportComparison) -> str:
    """
    用途與流程：把比較結果轉成 Markdown，先列資料來源與 manifest，再列 full-window 與 rolling-window 風險差異。
    參數：comparison 是 compare_portfolio_rotation_reports 的結果。
    回傳與錯誤：回傳 Markdown 字串；此函式不做 I/O。
    """
    lines = [
        "# Portfolio Rotation Raw vs Adjusted Comparison",
        "",
        f"- Raw summary: `{comparison.raw_summary_json.as_posix()}`",
        f"- Adjusted summary: `{comparison.adjusted_summary_json.as_posix()}`",
    ]
    if comparison.adjusted_batch_manifest_json is not None:
        lines.append(
            "- Adjusted batch manifest: "
            f"`{comparison.adjusted_batch_manifest_json.as_posix()}`"
        )
    if comparison.adjusted_manifest_summary is not None:
        manifest = comparison.adjusted_manifest_summary
        lines.extend(
            [
                "- Adjusted manifest rows: "
                f"`{manifest.get('row_count_total')}`",
                "- Adjusted manifest missing ratios: "
                f"`{manifest.get('missing_adjustment_count_total')}`",
                "- Adjusted manifest skipped rows: "
                f"`{manifest.get('skipped_row_count_total')}`",
            ]
        )
    if comparison.adjusted_weakest_rolling_window is not None:
        weakest = comparison.adjusted_weakest_rolling_window
        lines.append(
            "- Weakest adjusted rolling IR: "
            f"`{weakest['window_label']}` = `{_format_decimal(weakest['information_ratio'])}`"
        )

    lines.extend(
        [
            "",
            "## Full Window",
            "",
            "| Cost | Raw return | Adjusted return | Delta return | Raw excess | Adjusted excess | Delta excess | Raw IR | Adjusted IR | Delta IR | Raw MDD | Adjusted MDD | Delta MDD | Raw top3 group | Adjusted top3 group |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in comparison.full_window:
        lines.append(_format_compare_row_markdown(row))

    if comparison.rolling_windows:
        lines.extend(
            [
                "",
                f"## Rolling Windows ({comparison.rolling_cost_label})",
                "",
                "| Window | Range | Raw excess | Adjusted excess | Delta excess | Raw IR | Adjusted IR | Delta IR | Raw MDD | Adjusted MDD | Adjusted top3 group |",
                "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in comparison.rolling_windows:
            comp = row.comparison
            lines.append(
                "| "
                f"`{row.window_label}` | `{row.start} to {row.end}` | "
                f"{_format_percent(comp.raw_benchmark_excess_return)} | "
                f"{_format_percent(comp.adjusted_benchmark_excess_return)} | "
                f"{_format_percent(comp.delta_benchmark_excess_return)} | "
                f"{_format_decimal(comp.raw_information_ratio)} | "
                f"{_format_decimal(comp.adjusted_information_ratio)} | "
                f"{_format_decimal(comp.delta_information_ratio)} | "
                f"{_format_percent(comp.raw_max_drawdown)} | "
                f"{_format_percent(comp.adjusted_max_drawdown)} | "
                f"{_format_percent(comp.adjusted_top3_group_abs_contribution_share)} |"
            )
    lines.append("")
    return "\n".join(lines)


def write_comparison_markdown(
    comparison: PortfolioReportComparison,
    output_md: Path,
) -> None:
    """
    用途與流程：將 raw / adjusted 比較結果寫成 Markdown artifact。
    參數：comparison 是比較結果；output_md 是輸出 Markdown 路徑。
    回傳與錯誤：回傳 None；寫檔失敗時由 pathlib 拋出例外。
    """
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(
        format_comparison_markdown(comparison),
        encoding="utf-8",
        newline="",
    )


def main(argv: list[str] | None = None) -> int:
    """
    用途與流程：CLI 入口，讀取 raw / adjusted summary 與可選 manifest，輸出 JSON / Markdown 或直接印出 Markdown。
    參數：argv 是可選命令列參數清單；None 時使用系統命令列。
    回傳與錯誤：成功回傳 0；輸入 JSON 或對齊驗證失敗時讓 ValueError 往外傳。
    """
    args = build_parser().parse_args(argv)
    comparison = compare_portfolio_rotation_reports(
        raw_summary_json=args.raw_summary_json,
        adjusted_summary_json=args.adjusted_summary_json,
        raw_label=args.raw_label,
        adjusted_label=args.adjusted_label,
        adjusted_batch_manifest_json=args.adjusted_batch_manifest_json,
        rolling_cost_label=args.rolling_cost_label,
    )
    if args.output_json:
        write_comparison_json(comparison, args.output_json)
    markdown = format_comparison_markdown(comparison)
    if args.output_md:
        write_comparison_markdown(comparison, args.output_md)
    print(markdown, end="")
    return 0


def _load_summary(path: Path) -> dict[str, Any]:
    """
    用途與流程：讀取 portfolio rotation summary JSON 並確認至少包含 results list。
    參數：path 是 JSON 檔案路徑。
    回傳與錯誤：回傳 dict；JSON 不是物件或缺少 results list 時拋出 ValueError。
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"summary must be a JSON object: {path}")
    if not isinstance(payload.get("results"), list):
        raise ValueError(f"summary must contain a results list: {path}")
    return payload


def _results_by_cost(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """
    用途與流程：把 summary results 依 cost_label 排序成 dict，讓 raw 與 adjusted 可穩定對齊。
    參數：summary 是 portfolio rotation summary JSON 物件。
    回傳與錯誤：回傳 cost_label 到 result dict；缺少或重複 cost_label 時拋出 ValueError。
    """
    by_cost: dict[str, dict[str, Any]] = {}
    for result in summary["results"]:
        if not isinstance(result, dict):
            raise ValueError("each result must be an object")
        cost_label = result.get("cost_label")
        if not isinstance(cost_label, str) or not cost_label:
            raise ValueError("each result must contain cost_label")
        if cost_label in by_cost:
            raise ValueError(f"duplicate cost_label in summary: {cost_label}")
        by_cost[cost_label] = result
    return by_cost


def _build_compare_row(
    *,
    scope: str,
    cost_label: str,
    raw_label: str,
    adjusted_label: str,
    raw_result: dict[str, Any],
    adjusted_result: dict[str, Any],
) -> PortfolioCompareRow:
    """
    用途與流程：從一組 raw / adjusted result 建立對照列，對固定指標計算 adjusted-minus-raw。
    參數：scope 是 full 或 rolling 標籤；cost_label 是成本倍率；raw/adjusted label 是顯示名稱；raw_result/adjusted_result 是 summary result dict。
    回傳與錯誤：回傳 PortfolioCompareRow；數值欄位若非數字或 None 會拋出 ValueError。
    """
    raw_values = {key: _optional_float(raw_result.get(key), key=key) for key in METRIC_KEYS}
    adjusted_values = {
        key: _optional_float(adjusted_result.get(key), key=key) for key in METRIC_KEYS
    }
    deltas = {
        key: _delta(adjusted_values[key], raw_values[key])
        for key in METRIC_KEYS
    }
    return PortfolioCompareRow(
        scope=scope,
        cost_label=cost_label,
        raw_label=raw_label,
        adjusted_label=adjusted_label,
        raw_total_return=raw_values["total_return"],
        adjusted_total_return=adjusted_values["total_return"],
        delta_total_return=deltas["total_return"],
        raw_benchmark_excess_return=raw_values["benchmark_excess_return"],
        adjusted_benchmark_excess_return=adjusted_values["benchmark_excess_return"],
        delta_benchmark_excess_return=deltas["benchmark_excess_return"],
        raw_information_ratio=raw_values["information_ratio"],
        adjusted_information_ratio=adjusted_values["information_ratio"],
        delta_information_ratio=deltas["information_ratio"],
        raw_max_drawdown=raw_values["max_drawdown"],
        adjusted_max_drawdown=adjusted_values["max_drawdown"],
        delta_max_drawdown=deltas["max_drawdown"],
        raw_active_max_drawdown=raw_values["active_max_drawdown"],
        adjusted_active_max_drawdown=adjusted_values["active_max_drawdown"],
        delta_active_max_drawdown=deltas["active_max_drawdown"],
        raw_top3_symbol_abs_contribution_share=raw_values[
            "top3_symbol_abs_contribution_share"
        ],
        adjusted_top3_symbol_abs_contribution_share=adjusted_values[
            "top3_symbol_abs_contribution_share"
        ],
        delta_top3_symbol_abs_contribution_share=deltas[
            "top3_symbol_abs_contribution_share"
        ],
        raw_top3_group_abs_contribution_share=raw_values[
            "top3_group_abs_contribution_share"
        ],
        adjusted_top3_group_abs_contribution_share=adjusted_values[
            "top3_group_abs_contribution_share"
        ],
        delta_top3_group_abs_contribution_share=deltas[
            "top3_group_abs_contribution_share"
        ],
    )


def _build_rolling_compare_rows(
    *,
    raw_summary: dict[str, Any],
    adjusted_summary: dict[str, Any],
    raw_label: str,
    adjusted_label: str,
    rolling_cost_label: str,
) -> list[RollingCompareRow]:
    """
    用途與流程：依 rolling window label 與 cost_label 對齊 raw / adjusted walk-forward result，產生 rolling 對照列。
    參數：raw_summary/adjusted_summary 是 summary JSON；raw_label/adjusted_label 是顯示名稱；rolling_cost_label 是要比較的成本倍率。
    回傳與錯誤：回傳 RollingCompareRow list；沒有 rolling 結果時回傳空 list，window 缺漏時拋出 ValueError。
    """
    raw_windows = _rolling_results_by_window(raw_summary, rolling_cost_label)
    adjusted_windows = _rolling_results_by_window(adjusted_summary, rolling_cost_label)
    if not raw_windows and not adjusted_windows:
        return []
    missing = sorted(set(raw_windows) - set(adjusted_windows))
    if missing:
        raise ValueError("adjusted summary is missing rolling windows: " + ", ".join(missing))

    rows: list[RollingCompareRow] = []
    for window_label, raw_window in raw_windows.items():
        adjusted_window = adjusted_windows[window_label]
        raw_meta = raw_window["window"]
        adjusted_meta = adjusted_window["window"]
        raw_range = (raw_meta.get("start"), raw_meta.get("end"))
        adjusted_range = (adjusted_meta.get("start"), adjusted_meta.get("end"))
        if raw_range != adjusted_range:
            raise ValueError(f"rolling window range mismatch: {window_label}")
        rows.append(
            RollingCompareRow(
                window_label=window_label,
                start=str(raw_meta.get("start")),
                end=str(raw_meta.get("end")),
                comparison=_build_compare_row(
                    scope=f"rolling:{window_label}",
                    cost_label=rolling_cost_label,
                    raw_label=raw_label,
                    adjusted_label=adjusted_label,
                    raw_result=raw_window["result"],
                    adjusted_result=adjusted_window["result"],
                ),
            )
        )
    return rows


def _rolling_results_by_window(
    summary: dict[str, Any],
    cost_label: str,
) -> dict[str, dict[str, Any]]:
    """
    用途與流程：從 walk_forward_results 取出指定成本倍率的每個 rolling window result。
    參數：summary 是 portfolio summary；cost_label 是目標成本倍率。
    回傳與錯誤：回傳 window label 到 window/result dict；window 結構不合法或找不到成本倍率時拋出 ValueError。
    """
    by_window: dict[str, dict[str, Any]] = {}
    for window_payload in summary.get("walk_forward_results") or []:
        if not isinstance(window_payload, dict):
            raise ValueError("each walk_forward_result must be an object")
        window = window_payload.get("window")
        results = window_payload.get("results")
        if not isinstance(window, dict) or not isinstance(results, list):
            raise ValueError("walk_forward_result must contain window and results")
        label = window.get("label")
        if not isinstance(label, str) or not label:
            raise ValueError("walk_forward window must contain label")
        result = _find_result_for_cost(results, cost_label)
        by_window[label] = {"window": window, "result": result}
    return by_window


def _find_result_for_cost(results: list[Any], cost_label: str) -> dict[str, Any]:
    """
    用途與流程：在一個 rolling window 的 result list 中找出指定成本倍率。
    參數：results 是 walk_forward window 內的結果清單；cost_label 是成本倍率標籤。
    回傳與錯誤：找到時回傳 result dict；找不到或結果不是物件時拋出 ValueError。
    """
    for result in results:
        if not isinstance(result, dict):
            raise ValueError("rolling result must be an object")
        if result.get("cost_label") == cost_label:
            return result
    raise ValueError(f"rolling window is missing cost label: {cost_label}")


def _load_adjusted_manifest_summary(path: Path) -> dict[str, Any]:
    """
    用途與流程：讀取 adjusted batch manifest 並抽出比較報表需要的資料來源摘要。
    參數：path 是 batch manifest JSON 路徑。
    回傳與錯誤：回傳 summary dict；manifest 缺少必要彙總欄位時拋出 ValueError。
    """
    manifest = json.loads(path.read_text(encoding="utf-8"))
    required = (
        "result_count",
        "row_count_total",
        "missing_adjustment_count_total",
        "skipped_row_count_total",
        "symbols",
        "adjustment_method",
        "volume_source",
    )
    missing = [key for key in required if key not in manifest]
    if missing:
        raise ValueError("adjusted batch manifest is missing: " + ", ".join(missing))
    return {key: manifest[key] for key in required}


def _find_weakest_adjusted_rolling(
    rolling_windows: list[RollingCompareRow],
) -> dict[str, Any] | None:
    """
    用途與流程：找出 adjusted rolling windows 中 Information Ratio 最弱的一段，方便筆記直接定位風險版本。
    參數：rolling_windows 是已對齊的 rolling 比較列。
    回傳與錯誤：若沒有可比較 IR 回傳 None；否則回傳 window label、日期與 adjusted 指標。
    """
    candidates = [
        row
        for row in rolling_windows
        if row.comparison.adjusted_information_ratio is not None
    ]
    if not candidates:
        return None
    weakest = min(candidates, key=lambda row: row.comparison.adjusted_information_ratio or 0.0)
    return {
        "window_label": weakest.window_label,
        "start": weakest.start,
        "end": weakest.end,
        "information_ratio": weakest.comparison.adjusted_information_ratio,
        "benchmark_excess_return": weakest.comparison.adjusted_benchmark_excess_return,
        "max_drawdown": weakest.comparison.adjusted_max_drawdown,
        "top3_group_abs_contribution_share": (
            weakest.comparison.adjusted_top3_group_abs_contribution_share
        ),
    }


def _comparison_to_json_payload(comparison: PortfolioReportComparison) -> dict[str, Any]:
    """
    用途與流程：把 dataclass 比較結果轉成可 JSON 序列化且路徑固定為 POSIX 字串的 dict。
    參數：comparison 是 PortfolioReportComparison。
    回傳與錯誤：回傳 dict；此函式不做 I/O。
    """
    return {
        "adjusted_batch_manifest_json": (
            comparison.adjusted_batch_manifest_json.as_posix()
            if comparison.adjusted_batch_manifest_json is not None
            else None
        ),
        "adjusted_label": comparison.adjusted_label,
        "adjusted_manifest_summary": comparison.adjusted_manifest_summary,
        "adjusted_summary_json": comparison.adjusted_summary_json.as_posix(),
        "adjusted_weakest_rolling_window": comparison.adjusted_weakest_rolling_window,
        "full_window": [asdict(row) for row in comparison.full_window],
        "raw_label": comparison.raw_label,
        "raw_summary_json": comparison.raw_summary_json.as_posix(),
        "rolling_cost_label": comparison.rolling_cost_label,
        "rolling_windows": [
            {
                "window_label": row.window_label,
                "start": row.start,
                "end": row.end,
                "comparison": asdict(row.comparison),
            }
            for row in comparison.rolling_windows
        ],
        "schema_version": comparison.schema_version,
    }


def _optional_float(value: Any, *, key: str) -> float | None:
    """
    用途與流程：將 JSON 數值欄位轉成 float，允許 None 代表該指標無法計算。
    參數：value 是 JSON 欄位值；key 是錯誤訊息用欄位名稱。
    回傳與錯誤：回傳 float 或 None；非數值型別時拋出 ValueError。
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"metric must be numeric or null: {key}")
    return float(value)


def _delta(adjusted: float | None, raw: float | None) -> float | None:
    """
    用途與流程：計算 adjusted-minus-raw 差異，若任一側缺值則保持 None。
    參數：adjusted/raw 是兩側指標值。
    回傳與錯誤：回傳差異或 None；此函式不主動拋錯。
    """
    if adjusted is None or raw is None:
        return None
    return adjusted - raw


def _format_compare_row_markdown(row: PortfolioCompareRow) -> str:
    """
    用途與流程：將 full-window compare row 格式化成 Markdown 表格列。
    參數：row 是 PortfolioCompareRow。
    回傳與錯誤：回傳 Markdown row 字串。
    """
    return (
        "| "
        f"{row.cost_label} | "
        f"{_format_percent(row.raw_total_return)} | "
        f"{_format_percent(row.adjusted_total_return)} | "
        f"{_format_percent(row.delta_total_return)} | "
        f"{_format_percent(row.raw_benchmark_excess_return)} | "
        f"{_format_percent(row.adjusted_benchmark_excess_return)} | "
        f"{_format_percent(row.delta_benchmark_excess_return)} | "
        f"{_format_decimal(row.raw_information_ratio)} | "
        f"{_format_decimal(row.adjusted_information_ratio)} | "
        f"{_format_decimal(row.delta_information_ratio)} | "
        f"{_format_percent(row.raw_max_drawdown)} | "
        f"{_format_percent(row.adjusted_max_drawdown)} | "
        f"{_format_percent(row.delta_max_drawdown)} | "
        f"{_format_percent(row.raw_top3_group_abs_contribution_share)} | "
        f"{_format_percent(row.adjusted_top3_group_abs_contribution_share)} |"
    )


def _format_percent(value: float | None) -> str:
    """
    用途與流程：將小數形式報酬、回撤或占比格式化為百分比。
    參數：value 是小數形式數值或 None。
    回傳與錯誤：回傳百分比字串；None 回傳 `n/a`。
    """
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def _format_decimal(value: float | None) -> str:
    """
    用途與流程：將 Information Ratio 這類非百分比數值格式化成三位小數。
    參數：value 是數值或 None。
    回傳與錯誤：回傳字串；None 回傳 `n/a`。
    """
    if value is None:
        return "n/a"
    return f"{value:.3f}"


if __name__ == "__main__":
    raise SystemExit(main())
