from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GroupRegimeWindowRow:
    """單一 full-window 或 rolling window 的群組 regime 驗證結果。"""

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
    contribution_group_average_weight: float | None
    max_group_average_weight_group: str | None
    max_group_average_weight: float
    top3_group_abs_contribution_share: float
    top3_group_average_weight: float
    contribution_exposure_gap: float | None
    dominance_type: str
    gate_pass: bool
    failure_reasons: list[str]


@dataclass(frozen=True)
class GroupRegimeValidation:
    """portfolio rotation summary 的群組 regime 驗證總結果。"""

    schema_version: str
    source_summary_json: str
    cost_label: str
    max_top3_group_share: float
    max_contribution_exposure_gap: float
    row_count: int
    gate_pass: bool
    high_concentration_count: int
    return_regime_dominated_count: int
    exposure_dominated_count: int
    mixed_count: int
    worst_top3_group_window: dict[str, Any] | None
    weakest_ir_window: dict[str, Any] | None
    rows: list[GroupRegimeWindowRow]


def build_parser() -> argparse.ArgumentParser:
    """
    用途與流程：建立 group regime validation CLI parser，集中定義 summary JSON、成本倍率、gate 門檻與輸出路徑。
    參數：無。
    回傳與錯誤：回傳 argparse.ArgumentParser；parser 本身不讀檔，參數錯誤由 argparse 在 parse_args 階段處理。
    """
    parser = argparse.ArgumentParser(
        description=(
            "Validate portfolio rotation group contribution concentration "
            "against group exposure in full and rolling windows."
        )
    )
    parser.add_argument("--summary-json", type=Path, required=True)
    parser.add_argument(
        "--cost-label",
        default="1x",
        help="Cost label to validate in full-window and rolling-window rows.",
    )
    parser.add_argument(
        "--max-top3-group-share",
        type=float,
        default=0.90,
        help="Maximum allowed top-3 group absolute contribution share.",
    )
    parser.add_argument(
        "--max-contribution-exposure-gap",
        type=float,
        default=0.30,
        help=(
            "Maximum allowed gap between the dominant contribution group's "
            "absolute contribution share and its average weight."
        ),
    )
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    return parser


def validate_group_regime(
    summary_json: Path,
    *,
    cost_label: str = "1x",
    max_top3_group_share: float = 0.90,
    max_contribution_exposure_gap: float = 0.30,
) -> GroupRegimeValidation:
    """
    用途與流程：讀取 portfolio rotation summary，抽出指定成本倍率的 full-window 與 rolling results，建立群組貢獻相對曝險的 regime 驗證列。
    參數：summary_json 是 portfolio_rotation_sweep 輸出的 JSON；cost_label 指定要檢查的成本倍率；max_top3_group_share 與 max_contribution_exposure_gap 是集中度 gate。
    回傳與錯誤：回傳 GroupRegimeValidation；summary 缺少必要 result、rolling result 或 group attribution 時拋出 ValueError。
    """
    summary = json.loads(summary_json.read_text(encoding="utf-8"))
    rows: list[GroupRegimeWindowRow] = []
    full_result = _find_result_by_cost(_require_list(summary, "results"), cost_label)
    rows.append(
        _build_window_row(
            scope="full",
            window_label="full",
            window_start=str(full_result.get("start_timestamp", "")),
            window_end=str(full_result.get("end_timestamp", "")),
            result=full_result,
            max_top3_group_share=max_top3_group_share,
            max_contribution_exposure_gap=max_contribution_exposure_gap,
        )
    )
    for window_result in _require_list(summary, "walk_forward_results"):
        if not isinstance(window_result, dict):
            raise ValueError("walk_forward_results rows must be objects")
        window = _require_dict(window_result, "window")
        result = _find_result_by_cost(_require_list(window_result, "results"), cost_label)
        rows.append(
            _build_window_row(
                scope="rolling",
                window_label=str(window.get("label", "")),
                window_start=str(window.get("start", "")),
                window_end=str(window.get("end", "")),
                result=result,
                max_top3_group_share=max_top3_group_share,
                max_contribution_exposure_gap=max_contribution_exposure_gap,
            )
        )

    worst_top3 = _worst_top3_group_window(rows)
    weakest_ir = _weakest_ir_window(rows)
    high_concentration_count = sum(
        row.top3_group_abs_contribution_share > max_top3_group_share for row in rows
    )
    return_regime_dominated_count = sum(
        row.dominance_type == "return_regime_dominated" for row in rows
    )
    exposure_dominated_count = sum(
        row.dominance_type == "exposure_dominated" for row in rows
    )
    mixed_count = sum(row.dominance_type == "mixed" for row in rows)
    gate_pass = all(row.gate_pass for row in rows)
    return GroupRegimeValidation(
        schema_version="portfolio_rotation_group_regime_validation.v1",
        source_summary_json=summary_json.as_posix(),
        cost_label=cost_label,
        max_top3_group_share=max_top3_group_share,
        max_contribution_exposure_gap=max_contribution_exposure_gap,
        row_count=len(rows),
        gate_pass=gate_pass,
        high_concentration_count=high_concentration_count,
        return_regime_dominated_count=return_regime_dominated_count,
        exposure_dominated_count=exposure_dominated_count,
        mixed_count=mixed_count,
        worst_top3_group_window=worst_top3,
        weakest_ir_window=weakest_ir,
        rows=rows,
    )


def write_validation_json(validation: GroupRegimeValidation, output_json: Path) -> None:
    """
    用途與流程：將 group regime validation 結果寫成 deterministic JSON，供後續筆記或自動化 gate 引用。
    參數：validation 是 validate_group_regime 回傳結果；output_json 是輸出檔案路徑。
    回傳與錯誤：回傳 None；寫檔失敗時由 Path.write_text 拋出例外。
    """
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(asdict(validation), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="",
    )


def format_validation_markdown(validation: GroupRegimeValidation) -> str:
    """
    用途與流程：把 group regime validation 結果整理成 Markdown，先列 gate 摘要，再列 full/rolling 視窗明細。
    參數：validation 是 validate_group_regime 回傳結果。
    回傳與錯誤：回傳 Markdown 字串；格式化過程不主動拋錯。
    """
    lines = [
        "# Portfolio Rotation Group Regime Validation",
        "",
        f"- Source summary: `{validation.source_summary_json}`",
        f"- Cost label: `{validation.cost_label}`",
        f"- Gate pass: `{str(validation.gate_pass).lower()}`",
        f"- Max top3 group share threshold: `{validation.max_top3_group_share:.2%}`",
        (
            "- Max contribution-exposure gap threshold: "
            f"`{validation.max_contribution_exposure_gap:.2%}`"
        ),
        f"- High concentration windows: `{validation.high_concentration_count}`",
        f"- Return-regime dominated windows: `{validation.return_regime_dominated_count}`",
        f"- Exposure dominated windows: `{validation.exposure_dominated_count}`",
        f"- Mixed windows: `{validation.mixed_count}`",
    ]
    if validation.worst_top3_group_window is not None:
        worst = validation.worst_top3_group_window
        lines.append(
            "- Worst top3 group window: "
            f"`{worst['window_label']}` = `{_format_percent(worst['top3_group_abs_contribution_share'])}`"
        )
    if validation.weakest_ir_window is not None:
        weakest = validation.weakest_ir_window
        lines.append(
            "- Weakest IR window: "
            f"`{weakest['window_label']}` = `{_format_optional_float(weakest['information_ratio'])}`"
        )
    lines.extend(
        [
            "",
            "## Window Details",
            "",
            (
                "| Scope | Window | Range | IR | Excess | MDD | Max contrib group | "
                "Contrib share | Contrib group avg weight | Gap | Max exposure group | "
                "Max exposure | Top3 group | Top3 exposure | Dominance | Gate | Failure reasons |"
            ),
            "|---|---|---|---:|---:|---:|---|---:|---:|---:|---|---:|---:|---:|---|---|---|",
        ]
    )
    for row in validation.rows:
        lines.append(_format_window_row(row))
    lines.append("")
    return "\n".join(lines)


def write_validation_markdown(
    validation: GroupRegimeValidation, output_md: Path
) -> None:
    """
    用途與流程：將 group regime validation 結果寫成 Markdown，方便人工檢查集中度瓶頸。
    參數：validation 是 validate_group_regime 回傳結果；output_md 是輸出檔案路徑。
    回傳與錯誤：回傳 None；寫檔失敗時由 Path.write_text 拋出例外。
    """
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(
        format_validation_markdown(validation), encoding="utf-8", newline=""
    )


def main(argv: list[str] | None = None) -> int:
    """
    用途與流程：CLI 入口，讀取 portfolio rotation summary，輸出 group regime validation JSON / Markdown 或印出 Markdown。
    參數：argv 是可選命令列參數清單；None 時使用 sys.argv。
    回傳與錯誤：成功回傳 0；輸入檔案格式不符或 gate 建構失敗時由底層 ValueError/IOError 呈現。
    """
    args = build_parser().parse_args(argv)
    validation = validate_group_regime(
        args.summary_json,
        cost_label=args.cost_label,
        max_top3_group_share=args.max_top3_group_share,
        max_contribution_exposure_gap=args.max_contribution_exposure_gap,
    )
    if args.output_json:
        write_validation_json(validation, args.output_json)
    markdown = format_validation_markdown(validation)
    if args.output_md:
        write_validation_markdown(validation, args.output_md)
    if not args.output_md:
        print(markdown)
    return 0


def _build_window_row(
    *,
    scope: str,
    window_label: str,
    window_start: str,
    window_end: str,
    result: dict[str, Any],
    max_top3_group_share: float,
    max_contribution_exposure_gap: float,
) -> GroupRegimeWindowRow:
    """
    用途與流程：從單一 portfolio result 建立 group regime row，計算最大貢獻群組的平均曝險、貢獻-曝險 gap 與 dominance 類型。
    參數：scope/window_* 定義輸出列；result 是 portfolio_rotation_sweep 的單一成本結果；兩個 threshold 是 gate 門檻。
    回傳與錯誤：回傳 GroupRegimeWindowRow；若缺少 group_attribution 或必要 numeric 欄位，拋出 ValueError。
    """
    group_attribution = _require_list(result, "group_attribution")
    max_contribution_group = _optional_str(
        result.get("max_group_abs_contribution_group")
    )
    contribution_group_weight = _group_average_weight(
        group_attribution, max_contribution_group
    )
    max_group_share = _float_value(result, "max_group_abs_contribution_share")
    top3_group_share = _float_value(result, "top3_group_abs_contribution_share")
    max_group_weight = _float_value(result, "max_group_average_weight")
    contribution_exposure_gap = (
        max_group_share - contribution_group_weight
        if contribution_group_weight is not None
        else None
    )
    dominance_type = _classify_dominance(
        max_contribution_group=max_contribution_group,
        max_exposure_group=_optional_str(result.get("max_group_average_weight_group")),
        contribution_exposure_gap=contribution_exposure_gap,
        max_contribution_exposure_gap=max_contribution_exposure_gap,
    )
    failure_reasons = _failure_reasons(
        top3_group_share=top3_group_share,
        contribution_exposure_gap=contribution_exposure_gap,
        max_top3_group_share=max_top3_group_share,
        max_contribution_exposure_gap=max_contribution_exposure_gap,
    )
    return GroupRegimeWindowRow(
        scope=scope,
        window_label=window_label,
        window_start=window_start,
        window_end=window_end,
        cost_label=str(result.get("cost_label", "")),
        information_ratio=_optional_float(result.get("information_ratio")),
        benchmark_excess_return=_float_value(result, "benchmark_excess_return"),
        max_drawdown=_float_value(result, "max_drawdown"),
        active_max_drawdown=_float_value(result, "active_max_drawdown"),
        max_group_abs_contribution_group=max_contribution_group,
        max_group_abs_contribution_share=max_group_share,
        contribution_group_average_weight=contribution_group_weight,
        max_group_average_weight_group=_optional_str(
            result.get("max_group_average_weight_group")
        ),
        max_group_average_weight=max_group_weight,
        top3_group_abs_contribution_share=top3_group_share,
        top3_group_average_weight=_float_value(result, "top3_group_average_weight"),
        contribution_exposure_gap=contribution_exposure_gap,
        dominance_type=dominance_type,
        gate_pass=not failure_reasons,
        failure_reasons=failure_reasons,
    )


def _classify_dominance(
    *,
    max_contribution_group: str | None,
    max_exposure_group: str | None,
    contribution_exposure_gap: float | None,
    max_contribution_exposure_gap: float,
) -> str:
    """
    用途與流程：依最大貢獻群組、最大曝險群組與貢獻-曝險 gap 判斷集中度更像 regime return、長期曝險或混合來源。
    參數：max_contribution_group/max_exposure_group 是群組名稱；contribution_exposure_gap 是最大貢獻群組 share 減平均權重；threshold 是 regime return 判定門檻。
    回傳與錯誤：回傳 return_regime_dominated、exposure_dominated 或 mixed；不主動拋錯。
    """
    if contribution_exposure_gap is not None and (
        contribution_exposure_gap > max_contribution_exposure_gap
        or (
            max_contribution_group is not None
            and max_exposure_group is not None
            and max_contribution_group != max_exposure_group
        )
    ):
        return "return_regime_dominated"
    if (
        max_contribution_group is not None
        and max_exposure_group is not None
        and max_contribution_group == max_exposure_group
    ):
        return "exposure_dominated"
    return "mixed"


def _failure_reasons(
    *,
    top3_group_share: float,
    contribution_exposure_gap: float | None,
    max_top3_group_share: float,
    max_contribution_exposure_gap: float,
) -> list[str]:
    """
    用途與流程：依 group concentration 與 contribution-exposure gap 產生 gate failure reason，讓報表能直接解釋不能升級的原因。
    參數：top3_group_share 與 contribution_exposure_gap 是待評估指標；後兩者是門檻。
    回傳與錯誤：回傳 failure reason list；缺 gap 時會加入 missing_contribution_group_exposure，不主動拋錯。
    """
    reasons: list[str] = []
    if top3_group_share > max_top3_group_share:
        reasons.append("top3_group_contribution_concentration")
    if contribution_exposure_gap is None:
        reasons.append("missing_contribution_group_exposure")
    elif contribution_exposure_gap > max_contribution_exposure_gap:
        reasons.append("contribution_exposure_gap")
    return reasons


def _find_result_by_cost(results: list[Any], cost_label: str) -> dict[str, Any]:
    """
    用途與流程：從 result 清單中找出指定 cost_label 的結果列，供 full-window 與 rolling-window 共用。
    參數：results 是 JSON result list；cost_label 是目標成本倍率文字，例如 1x。
    回傳與錯誤：找到時回傳 dict；result 不是物件或找不到 cost_label 時拋出 ValueError。
    """
    for result in results:
        if not isinstance(result, dict):
            raise ValueError("result rows must be objects")
        if result.get("cost_label") == cost_label:
            return result
    raise ValueError(f"missing cost label: {cost_label}")


def _group_average_weight(
    group_attribution: list[Any], group_name: str | None
) -> float | None:
    """
    用途與流程：在 group_attribution 中找出指定群組的 average_weight，用來計算貢獻占比是否明顯高於平均曝險。
    參數：group_attribution 是 summary JSON 的群組 attribution list；group_name 是最大貢獻群組名稱。
    回傳與錯誤：找到時回傳 float；沒有 group_name 或找不到群組時回傳 None；row 不是物件時拋出 ValueError。
    """
    if group_name is None:
        return None
    for row in group_attribution:
        if not isinstance(row, dict):
            raise ValueError("group_attribution rows must be objects")
        if row.get("group") == group_name:
            return _optional_float(row.get("average_weight"))
    return None


def _worst_top3_group_window(rows: list[GroupRegimeWindowRow]) -> dict[str, Any] | None:
    """
    用途與流程：找出 top3 group contribution share 最高的視窗，方便人工優先檢查最嚴重 concentration。
    參數：rows 是 validation 明細列。
    回傳與錯誤：有資料時回傳精簡 dict；rows 為空時回傳 None。
    """
    if not rows:
        return None
    row = max(rows, key=lambda item: item.top3_group_abs_contribution_share)
    return {
        "scope": row.scope,
        "window_label": row.window_label,
        "top3_group_abs_contribution_share": row.top3_group_abs_contribution_share,
        "max_group_abs_contribution_group": row.max_group_abs_contribution_group,
    }


def _weakest_ir_window(rows: list[GroupRegimeWindowRow]) -> dict[str, Any] | None:
    """
    用途與流程：找出 Information Ratio 最弱的視窗，讓 concentration 診斷能和 rolling performance weakness 對齊。
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
        "top3_group_abs_contribution_share": row.top3_group_abs_contribution_share,
    }


def _format_window_row(row: GroupRegimeWindowRow) -> str:
    """
    用途與流程：把單一 GroupRegimeWindowRow 轉成 Markdown table row，集中處理百分比、None 與 failure reason 格式。
    參數：row 是 validation 明細列。
    回傳與錯誤：回傳 Markdown 表格列字串；不主動拋錯。
    """
    failures = ", ".join(row.failure_reasons) if row.failure_reasons else "none"
    return (
        f"| {row.scope} | `{row.window_label}` | `{row.window_start} to {row.window_end}` | "
        f"{_format_optional_float(row.information_ratio)} | "
        f"{_format_percent(row.benchmark_excess_return)} | "
        f"{_format_percent(row.max_drawdown)} | "
        f"{row.max_group_abs_contribution_group or 'n/a'} | "
        f"{_format_percent(row.max_group_abs_contribution_share)} | "
        f"{_format_optional_percent(row.contribution_group_average_weight)} | "
        f"{_format_optional_percent(row.contribution_exposure_gap)} | "
        f"{row.max_group_average_weight_group or 'n/a'} | "
        f"{_format_percent(row.max_group_average_weight)} | "
        f"{_format_percent(row.top3_group_abs_contribution_share)} | "
        f"{_format_percent(row.top3_group_average_weight)} | "
        f"{row.dominance_type} | `{str(row.gate_pass).lower()}` | {failures} |"
    )


def _require_list(payload: dict[str, Any], key: str) -> list[Any]:
    """
    用途與流程：從 JSON 物件讀取必要 list 欄位，避免後續分析在錯誤 schema 上默默輸出誤導結果。
    參數：payload 是 JSON dict；key 是必要欄位名稱。
    回傳與錯誤：欄位存在且為 list 時回傳；否則拋出 ValueError。
    """
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"summary field must be a list: {key}")
    return value


def _require_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    """
    用途與流程：從 JSON 物件讀取必要 object 欄位，供 window metadata 等巢狀結構驗證使用。
    參數：payload 是 JSON dict；key 是必要欄位名稱。
    回傳與錯誤：欄位存在且為 dict 時回傳；否則拋出 ValueError。
    """
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"summary field must be an object: {key}")
    return value


def _float_value(payload: dict[str, Any], key: str) -> float:
    """
    用途與流程：讀取必要 numeric 欄位並轉成 float，讓 JSON int/float 都能進入同一套運算。
    參數：payload 是 JSON dict；key 是必要欄位名稱。
    回傳與錯誤：成功時回傳 float；缺欄位或不能轉數字時拋出 ValueError。
    """
    value = _optional_float(payload.get(key))
    if value is None:
        raise ValueError(f"summary field must be numeric: {key}")
    return value


def _optional_float(value: Any) -> float | None:
    """
    用途與流程：把 JSON 中可為 null 的 numeric 欄位轉成 float，支援 int/float 但拒絕 bool。
    參數：value 是任意 JSON 欄位值。
    回傳與錯誤：None 回傳 None；numeric 回傳 float；其他型別拋出 ValueError。
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"value must be numeric or null: {value!r}")
    return float(value)


def _optional_str(value: Any) -> str | None:
    """
    用途與流程：把 JSON 中可為 null 的文字欄位標準化為 str 或 None。
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
    參數：value 是比例值，例如 0.1234。
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


if __name__ == "__main__":
    raise SystemExit(main())
