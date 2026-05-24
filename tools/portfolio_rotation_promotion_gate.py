from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PortfolioRotationPromotionGate:
    """portfolio rotation 候選是否可升級的綜合 gate 結果。"""

    schema_version: str
    decision: str
    gate_pass: bool
    failure_reasons: list[str]
    summary_json: str
    raw_adjusted_comparison_json: str | None
    group_regime_validation_json: str | None
    group_breadth_validation_json: str | None
    primary_cost_label: str
    stress_cost_label: str | None
    thresholds: dict[str, float]
    allow_missing_diagnostics: bool
    candidate_parameters: dict[str, Any]
    metrics: dict[str, Any]
    diagnostics: dict[str, Any]


def build_parser() -> argparse.ArgumentParser:
    """
    用途與流程：建立 promotion gate CLI parser，集中定義 portfolio summary、診斷 artifact 與升級門檻。
    參數：無。
    回傳與錯誤：回傳 argparse.ArgumentParser；命令列格式錯誤由 argparse 處理，檔案內容驗證由 build_promotion_gate 處理。
    """
    parser = argparse.ArgumentParser(
        description=(
            "Combine portfolio rotation summary, raw/adjusted comparison, "
            "group regime, and group breadth artifacts into one promotion gate."
        )
    )
    parser.add_argument("--summary-json", type=Path, required=True)
    parser.add_argument("--raw-adjusted-comparison-json", type=Path)
    parser.add_argument("--group-regime-validation-json", type=Path)
    parser.add_argument("--group-breadth-validation-json", type=Path)
    parser.add_argument("--primary-cost-label", default="1x")
    parser.add_argument("--stress-cost-label", default="3x")
    parser.add_argument("--min-full-ir", type=float, default=1.0)
    parser.add_argument("--min-stress-ir", type=float, default=0.75)
    parser.add_argument("--min-rolling-ir", type=float, default=0.50)
    parser.add_argument("--min-rolling-excess-return", type=float, default=0.0)
    parser.add_argument("--max-drawdown-abs", type=float, default=0.30)
    parser.add_argument("--max-active-drawdown-abs", type=float, default=0.30)
    parser.add_argument("--max-top3-symbol-share", type=float, default=0.80)
    parser.add_argument("--max-top3-group-share", type=float, default=0.90)
    parser.add_argument("--max-raw-adjusted-ir-drop", type=float, default=0.25)
    parser.add_argument(
        "--max-adjusted-drawdown-worsening",
        type=float,
        default=0.05,
    )
    parser.add_argument(
        "--allow-missing-diagnostics",
        action="store_true",
        help="Do not fail the gate when optional diagnostic artifacts are absent.",
    )
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    return parser


def build_promotion_gate(
    *,
    summary_json: Path,
    raw_adjusted_comparison_json: Path | None = None,
    group_regime_validation_json: Path | None = None,
    group_breadth_validation_json: Path | None = None,
    primary_cost_label: str = "1x",
    stress_cost_label: str | None = "3x",
    thresholds: dict[str, float] | None = None,
    allow_missing_diagnostics: bool = False,
) -> PortfolioRotationPromotionGate:
    """
    用途與流程：讀取 portfolio rotation 主要 summary 與可選診斷 artifact，合併 full-window、stress cost、rolling、raw/adjusted 與 group validation 指標後產生升級判斷。
    參數：summary_json 是 portfolio_rotation_sweep summary；raw_adjusted_comparison_json、group_regime_validation_json、group_breadth_validation_json 是既有診斷報告；primary_cost_label/stress_cost_label 指定成本倍率；thresholds 是 gate 門檻覆寫；allow_missing_diagnostics 控制缺診斷是否直接失敗。
    回傳與錯誤：回傳 PortfolioRotationPromotionGate；summary schema 不符、成本倍率不存在或診斷 JSON 不是物件時拋出 ValueError。
    """
    effective_thresholds = _default_thresholds()
    if thresholds:
        effective_thresholds.update(thresholds)

    summary = _load_json_object(summary_json)
    primary = _find_result_by_cost(
        _require_list(summary, "results"), primary_cost_label
    )
    stress = (
        _find_result_by_cost(_require_list(summary, "results"), stress_cost_label)
        if stress_cost_label
        else None
    )
    rolling_rows = _rolling_rows(summary, primary_cost_label)
    metrics = _build_metrics(primary, stress, rolling_rows)
    candidate_parameters = _candidate_parameters(primary)

    failure_reasons: list[str] = []
    failure_reasons.extend(_metric_failure_reasons(metrics, effective_thresholds))

    diagnostics: dict[str, Any] = {}
    diagnostics["raw_adjusted_comparison"] = _comparison_diagnostic(
        raw_adjusted_comparison_json,
        primary_cost_label=primary_cost_label,
        thresholds=effective_thresholds,
        allow_missing=allow_missing_diagnostics,
    )
    diagnostics["group_regime_validation"] = _validation_diagnostic(
        group_regime_validation_json,
        missing_reason="missing_group_regime_validation",
        failed_reason="group_regime_gate_failed",
        count_keys=(
            "high_concentration_count",
            "return_regime_dominated_count",
            "exposure_dominated_count",
            "mixed_count",
            "row_count",
        ),
        allow_missing=allow_missing_diagnostics,
    )
    diagnostics["group_breadth_validation"] = _validation_diagnostic(
        group_breadth_validation_json,
        missing_reason="missing_group_breadth_validation",
        failed_reason="group_breadth_gate_failed",
        count_keys=(
            "high_concentration_count",
            "broad_group_momentum_count",
            "narrow_group_momentum_count",
            "single_member_dominant_count",
            "missing_breadth_count",
            "row_count",
        ),
        allow_missing=allow_missing_diagnostics,
    )

    for diagnostic in diagnostics.values():
        failure_reasons.extend(diagnostic.get("failure_reasons", []))
    breadth_diag = diagnostics["group_breadth_validation"]
    if (breadth_diag.get("single_member_dominant_count") or 0) > 0:
        failure_reasons.append("single_member_dominant_group")
    if (breadth_diag.get("narrow_group_momentum_count") or 0) > 0:
        failure_reasons.append("narrow_group_momentum")

    unique_reasons = _unique_preserving_order(failure_reasons)
    gate_pass = not unique_reasons
    return PortfolioRotationPromotionGate(
        schema_version="portfolio_rotation_promotion_gate.v1",
        decision="keep" if gate_pass else "compare-only",
        gate_pass=gate_pass,
        failure_reasons=unique_reasons,
        summary_json=summary_json.as_posix(),
        raw_adjusted_comparison_json=(
            raw_adjusted_comparison_json.as_posix()
            if raw_adjusted_comparison_json
            else None
        ),
        group_regime_validation_json=(
            group_regime_validation_json.as_posix()
            if group_regime_validation_json
            else None
        ),
        group_breadth_validation_json=(
            group_breadth_validation_json.as_posix()
            if group_breadth_validation_json
            else None
        ),
        primary_cost_label=primary_cost_label,
        stress_cost_label=stress_cost_label,
        thresholds=effective_thresholds,
        allow_missing_diagnostics=allow_missing_diagnostics,
        candidate_parameters=candidate_parameters,
        metrics=metrics,
        diagnostics=diagnostics,
    )


def write_promotion_gate_json(
    gate: PortfolioRotationPromotionGate,
    output_json: Path,
) -> None:
    """
    用途與流程：將 promotion gate 結果寫成 deterministic JSON，供後續策略實驗紀錄、文件與自動化流程引用。
    參數：gate 是 build_promotion_gate 的回傳結果；output_json 是輸出路徑。
    回傳與錯誤：回傳 None；建立目錄或寫檔失敗時由 pathlib 拋出例外。
    """
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(asdict(gate), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="",
    )


def format_promotion_gate_markdown(gate: PortfolioRotationPromotionGate) -> str:
    """
    用途與流程：將 promotion gate 結果轉成 Markdown，先列決策與 failure reasons，再列主要指標與診斷摘要。
    參數：gate 是 build_promotion_gate 的回傳結果。
    回傳與錯誤：回傳 Markdown 字串；此函式不做 I/O。
    """
    metrics = gate.metrics
    full = metrics["full_window"]
    stress = metrics.get("stress_cost")
    rolling = metrics["rolling_windows"]
    lines = [
        "# Portfolio Rotation Promotion Gate",
        "",
        f"- Schema: `{gate.schema_version}`",
        f"- Decision: `{gate.decision}`",
        f"- Gate pass: `{str(gate.gate_pass).lower()}`",
        f"- Summary: `{gate.summary_json}`",
        "- Failure reasons: "
        + ("`none`" if not gate.failure_reasons else ", ".join(gate.failure_reasons)),
        "",
        "## Metrics",
        "",
        "| Scope | IR | Excess | MDD | Active MDD | Top3 symbol | Top3 group |",
        "|---|---:|---:|---:|---:|---:|---:|",
        (
            f"| Full `{gate.primary_cost_label}` | "
            f"{_format_decimal(full.get('information_ratio'))} | "
            f"{_format_percent(full.get('benchmark_excess_return'))} | "
            f"{_format_percent(full.get('max_drawdown'))} | "
            f"{_format_percent(full.get('active_max_drawdown'))} | "
            f"{_format_percent(full.get('top3_symbol_abs_contribution_share'))} | "
            f"{_format_percent(full.get('top3_group_abs_contribution_share'))} |"
        ),
    ]
    if stress is not None:
        lines.append(
            f"| Stress `{gate.stress_cost_label}` | "
            f"{_format_decimal(stress.get('information_ratio'))} | "
            f"{_format_percent(stress.get('benchmark_excess_return'))} | "
            f"{_format_percent(stress.get('max_drawdown'))} | "
            f"{_format_percent(stress.get('active_max_drawdown'))} | "
            f"{_format_percent(stress.get('top3_symbol_abs_contribution_share'))} | "
            f"{_format_percent(stress.get('top3_group_abs_contribution_share'))} |"
        )
    lines.append(
        "| Rolling worst / max | "
        f"{_format_decimal(rolling.get('min_information_ratio'))} | "
        f"{_format_percent(rolling.get('min_benchmark_excess_return'))} | "
        f"{_format_percent(rolling.get('worst_max_drawdown'))} | "
        f"{_format_percent(rolling.get('worst_active_max_drawdown'))} | "
        f"{_format_percent(rolling.get('max_top3_symbol_abs_contribution_share'))} | "
        f"{_format_percent(rolling.get('max_top3_group_abs_contribution_share'))} |"
    )
    lines.extend(
        [
            "",
            "## Diagnostics",
            "",
            "| Diagnostic | Gate | Failure reasons | Key counts |",
            "|---|---|---|---|",
        ]
    )
    for name, diagnostic in gate.diagnostics.items():
        counts = {
            key: value
            for key, value in diagnostic.items()
            if key.endswith("_count") or key.endswith("_counts")
        }
        lines.append(
            f"| {name} | `{str(diagnostic.get('gate_pass')).lower()}` | "
            f"{', '.join(diagnostic.get('failure_reasons') or []) or 'none'} | "
            f"`{json.dumps(counts, sort_keys=True)}` |"
        )
    lines.append("")
    return "\n".join(lines)


def write_promotion_gate_markdown(
    gate: PortfolioRotationPromotionGate,
    output_md: Path,
) -> None:
    """
    用途與流程：將 promotion gate 結果寫成 Markdown artifact，方便人工審查策略是否能從 compare-only 升級。
    參數：gate 是 promotion gate 結果；output_md 是輸出路徑。
    回傳與錯誤：回傳 None；建立目錄或寫檔失敗時由 pathlib 拋出例外。
    """
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(
        format_promotion_gate_markdown(gate),
        encoding="utf-8",
        newline="",
    )


def main(argv: list[str] | None = None) -> int:
    """
    用途與流程：CLI 入口，解析 promotion gate 參數後輸出 JSON / Markdown 或將 Markdown 印到 stdout。
    參數：argv 是可選命令列參數清單；None 時使用系統命令列。
    回傳與錯誤：成功回傳 0；輸入 artifact 缺失或 schema 不符時由底層例外回報。
    """
    args = build_parser().parse_args(argv)
    thresholds = {
        "min_full_ir": args.min_full_ir,
        "min_stress_ir": args.min_stress_ir,
        "min_rolling_ir": args.min_rolling_ir,
        "min_rolling_excess_return": args.min_rolling_excess_return,
        "max_drawdown_abs": args.max_drawdown_abs,
        "max_active_drawdown_abs": args.max_active_drawdown_abs,
        "max_top3_symbol_share": args.max_top3_symbol_share,
        "max_top3_group_share": args.max_top3_group_share,
        "max_raw_adjusted_ir_drop": args.max_raw_adjusted_ir_drop,
        "max_adjusted_drawdown_worsening": args.max_adjusted_drawdown_worsening,
    }
    gate = build_promotion_gate(
        summary_json=args.summary_json,
        raw_adjusted_comparison_json=args.raw_adjusted_comparison_json,
        group_regime_validation_json=args.group_regime_validation_json,
        group_breadth_validation_json=args.group_breadth_validation_json,
        primary_cost_label=args.primary_cost_label,
        stress_cost_label=args.stress_cost_label or None,
        thresholds=thresholds,
        allow_missing_diagnostics=args.allow_missing_diagnostics,
    )
    if args.output_json:
        write_promotion_gate_json(gate, args.output_json)
    markdown = format_promotion_gate_markdown(gate)
    if args.output_md:
        write_promotion_gate_markdown(gate, args.output_md)
    print(markdown, end="")
    return 0


def _default_thresholds() -> dict[str, float]:
    """
    用途與流程：提供 promotion gate 的預設門檻，對齊策略評估準則中 full-window、rolling、成本壓力、回撤與集中度的最低要求。
    參數：無。
    回傳與錯誤：回傳可覆寫的 threshold dict；此函式不拋錯。
    """
    return {
        "min_full_ir": 1.0,
        "min_stress_ir": 0.75,
        "min_rolling_ir": 0.50,
        "min_rolling_excess_return": 0.0,
        "max_drawdown_abs": 0.30,
        "max_active_drawdown_abs": 0.30,
        "max_top3_symbol_share": 0.80,
        "max_top3_group_share": 0.90,
        "max_raw_adjusted_ir_drop": 0.25,
        "max_adjusted_drawdown_worsening": 0.05,
    }


def _load_json_object(path: Path) -> dict[str, Any]:
    """
    用途與流程：讀取 UTF-8 JSON 檔並確認頂層是 object，避免把 list 或 scalar 誤當成 artifact。
    參數：path 是 JSON 檔案路徑。
    回傳與錯誤：回傳 dict；檔案不是 JSON object 時拋出 ValueError。
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must be an object: {path}")
    return payload


def _build_metrics(
    primary: dict[str, Any],
    stress: dict[str, Any] | None,
    rolling_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    用途與流程：從主要成本、壓力成本與 rolling results 聚合出 promotion gate 需要的核心績效與集中度指標。
    參數：primary 是 full-window 主要成本 result；stress 是壓力成本 result 或 None；rolling_rows 是指定成本倍率的 rolling result 清單。
    回傳與錯誤：回傳 metrics dict；必要 numeric 欄位缺失或型別不符時拋出 ValueError。
    """
    full = _metric_snapshot(primary)
    stress_snapshot = _metric_snapshot(stress) if stress is not None else None
    rolling_snapshots = [_metric_snapshot(row["result"]) for row in rolling_rows]
    weakest = _weakest_rolling_window(rolling_rows)
    rolling = {
        "window_count": len(rolling_snapshots),
        "min_information_ratio": _min_optional(
            row.get("information_ratio") for row in rolling_snapshots
        ),
        "min_benchmark_excess_return": _min_optional(
            row.get("benchmark_excess_return") for row in rolling_snapshots
        ),
        "worst_max_drawdown": _min_optional(
            row.get("max_drawdown") for row in rolling_snapshots
        ),
        "worst_active_max_drawdown": _min_optional(
            row.get("active_max_drawdown") for row in rolling_snapshots
        ),
        "max_top3_symbol_abs_contribution_share": _max_optional(
            row.get("top3_symbol_abs_contribution_share") for row in rolling_snapshots
        ),
        "max_top3_group_abs_contribution_share": _max_optional(
            row.get("top3_group_abs_contribution_share") for row in rolling_snapshots
        ),
        "weakest_ir_window": weakest,
    }
    return {
        "full_window": full,
        "stress_cost": stress_snapshot,
        "rolling_windows": rolling,
    }


def _metric_snapshot(result: dict[str, Any] | None) -> dict[str, Any] | None:
    """
    用途與流程：從 portfolio result 抽出 gate 會使用的固定欄位，將 numeric/null 欄位標準化。
    參數：result 是 summary JSON 的單一 result，或 None。
    回傳與錯誤：result 為 None 時回傳 None；欄位型別不符時拋出 ValueError。
    """
    if result is None:
        return None
    keys = (
        "cost_label",
        "total_return",
        "benchmark_excess_return",
        "information_ratio",
        "max_drawdown",
        "active_max_drawdown",
        "top3_symbol_abs_contribution_share",
        "top3_group_abs_contribution_share",
    )
    snapshot: dict[str, Any] = {}
    for key in keys:
        value = result.get(key)
        snapshot[key] = value if key == "cost_label" else _optional_float(value, key=key)
    return snapshot


def _metric_failure_reasons(
    metrics: dict[str, Any],
    thresholds: dict[str, float],
) -> list[str]:
    """
    用途與流程：依 full-window、stress cost 與 rolling metrics 產生 promotion gate 的績效與集中度 failure reasons。
    參數：metrics 是 _build_metrics 的輸出；thresholds 是 gate 門檻。
    回傳與錯誤：回傳 failure reason list；缺值視為失敗，不主動拋錯。
    """
    reasons: list[str] = []
    full = metrics["full_window"]
    stress = metrics.get("stress_cost")
    rolling = metrics["rolling_windows"]
    if _below(full.get("information_ratio"), thresholds["min_full_ir"]):
        reasons.append("full_ir_below_threshold")
    if stress is None or _below(
        stress.get("information_ratio"), thresholds["min_stress_ir"]
    ):
        reasons.append("stress_ir_below_threshold")
    if _below(rolling.get("min_information_ratio"), thresholds["min_rolling_ir"]):
        reasons.append("rolling_ir_below_threshold")
    if _below(
        rolling.get("min_benchmark_excess_return"),
        thresholds["min_rolling_excess_return"],
    ):
        reasons.append("rolling_excess_below_threshold")
    if _above_abs(full.get("max_drawdown"), thresholds["max_drawdown_abs"]):
        reasons.append("drawdown_above_threshold")
    if _above_abs(
        full.get("active_max_drawdown"), thresholds["max_active_drawdown_abs"]
    ):
        reasons.append("active_drawdown_above_threshold")
    if _above(
        rolling.get("max_top3_symbol_abs_contribution_share"),
        thresholds["max_top3_symbol_share"],
    ):
        reasons.append("symbol_concentration_above_threshold")
    if _above(
        rolling.get("max_top3_group_abs_contribution_share"),
        thresholds["max_top3_group_share"],
    ):
        reasons.append("group_concentration_above_threshold")
    return reasons


def _comparison_diagnostic(
    path: Path | None,
    *,
    primary_cost_label: str,
    thresholds: dict[str, float],
    allow_missing: bool,
) -> dict[str, Any]:
    """
    用途與流程：讀取 raw/adjusted comparison artifact，檢查 adjusted 後 IR 降幅與 MDD 惡化是否仍在可接受範圍。
    參數：path 是 comparison JSON 或 None；primary_cost_label 是對齊成本倍率；thresholds 提供降幅門檻；allow_missing 控制缺檔是否失敗。
    回傳與錯誤：回傳 diagnostic dict；comparison schema 不符或成本倍率不存在時拋出 ValueError。
    """
    if path is None:
        return _missing_diagnostic("missing_raw_adjusted_comparison", allow_missing)
    payload = _load_json_object(path)
    row = _find_compare_row(_require_list(payload, "full_window"), primary_cost_label)
    delta_ir = _optional_float(row.get("delta_information_ratio"), key="delta_ir")
    delta_mdd = _optional_float(row.get("delta_max_drawdown"), key="delta_mdd")
    reasons: list[str] = []
    if delta_ir is None or -delta_ir > thresholds["max_raw_adjusted_ir_drop"]:
        reasons.append("raw_adjusted_ir_drop_above_threshold")
    if (
        delta_mdd is None
        or delta_mdd < -thresholds["max_adjusted_drawdown_worsening"]
    ):
        reasons.append("adjusted_drawdown_worsening_above_threshold")
    weakest = payload.get("adjusted_weakest_rolling_window")
    if weakest is not None and not isinstance(weakest, dict):
        raise ValueError("adjusted_weakest_rolling_window must be an object or null")
    return {
        "gate_pass": not reasons,
        "failure_reasons": reasons,
        "cost_label": primary_cost_label,
        "delta_information_ratio": delta_ir,
        "delta_max_drawdown": delta_mdd,
        "adjusted_weakest_rolling_window": weakest,
    }


def _validation_diagnostic(
    path: Path | None,
    *,
    missing_reason: str,
    failed_reason: str,
    count_keys: tuple[str, ...],
    allow_missing: bool,
) -> dict[str, Any]:
    """
    用途與流程：讀取 group regime 或 group breadth validation JSON，抽出 gate_pass、failure reason 與摘要 count。
    參數：path 是 validation JSON 或 None；missing_reason/failed_reason 是 promotion gate 的失敗代碼；count_keys 是需要轉存的統計欄位；allow_missing 控制缺檔是否失敗。
    回傳與錯誤：回傳 diagnostic dict；validation schema 不符時拋出 ValueError。
    """
    if path is None:
        return _missing_diagnostic(missing_reason, allow_missing)
    payload = _load_json_object(path)
    gate_pass = payload.get("gate_pass")
    if not isinstance(gate_pass, bool):
        raise ValueError(f"validation gate_pass must be boolean: {path}")
    diagnostic: dict[str, Any] = {
        "gate_pass": gate_pass,
        "failure_reasons": [] if gate_pass else [failed_reason],
    }
    for key in count_keys:
        diagnostic[key] = payload.get(key)
    return diagnostic


def _missing_diagnostic(reason: str, allow_missing: bool) -> dict[str, Any]:
    """
    用途與流程：建立缺少診斷 artifact 時的標準 diagnostic payload。
    參數：reason 是缺檔 failure code；allow_missing 表示是否允許缺檔。
    回傳與錯誤：回傳 diagnostic dict；此函式不拋錯。
    """
    return {
        "gate_pass": allow_missing,
        "failure_reasons": [] if allow_missing else [reason],
        "missing": True,
    }


def _candidate_parameters(result: dict[str, Any]) -> dict[str, Any]:
    """
    用途與流程：從 primary result 抽出策略參數，讓 promotion gate artifact 可直接回看候選設定。
    參數：result 是 primary cost 的 full-window result。
    回傳與錯誤：回傳參數 dict；此函式只讀欄位，不做嚴格型別驗證。
    """
    keys = (
        "strategy",
        "rebalance_frequency",
        "lookback_bars",
        "ranking_skip_bars",
        "ranking_mode",
        "top_n",
        "min_return",
        "breadth_filter",
        "breadth_lookback_bars",
        "breadth_min_positive_count",
        "max_consecutive_selections_per_symbol",
        "reentry_cooldown_rebalances",
        "reentry_cooldown_block_count",
        "min_symbols_per_selected_group",
        "group_contribution_lookback_bars",
        "max_group_contribution_share",
        "group_contribution_block_count",
        "liquidity_lookback_bars",
        "min_average_traded_value",
        "symbol_count",
        "start_timestamp",
        "end_timestamp",
    )
    return {key: result.get(key) for key in keys}


def _rolling_rows(
    summary: dict[str, Any],
    cost_label: str,
) -> list[dict[str, Any]]:
    """
    用途與流程：從 summary walk_forward_results 取出指定成本倍率的 rolling result，並保留 window metadata。
    參數：summary 是 portfolio summary JSON；cost_label 是目標成本倍率。
    回傳與錯誤：回傳含 window/result 的清單；window 或 result 結構不合法時拋出 ValueError。
    """
    rows: list[dict[str, Any]] = []
    for window_payload in summary.get("walk_forward_results") or []:
        if not isinstance(window_payload, dict):
            raise ValueError("walk_forward_results rows must be objects")
        window = _require_dict(window_payload, "window")
        result = _find_result_by_cost(
            _require_list(window_payload, "results"),
            cost_label,
        )
        rows.append({"window": window, "result": result})
    return rows


def _weakest_rolling_window(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    用途與流程：找出 rolling results 中 Information Ratio 最弱的一段，方便 gate 報告定位策略破口。
    參數：rows 是 _rolling_rows 的輸出。
    回傳與錯誤：有可比較 IR 時回傳 window 摘要；否則回傳 None。
    """
    candidates: list[dict[str, Any]] = []
    for row in rows:
        ir = _optional_float(
            row["result"].get("information_ratio"),
            key="information_ratio",
        )
        if ir is None:
            continue
        candidates.append({"window": row["window"], "result": row["result"], "ir": ir})
    if not candidates:
        return None
    weakest = min(candidates, key=lambda item: item["ir"])
    window = weakest["window"]
    result = weakest["result"]
    return {
        "window_label": window.get("label"),
        "start": window.get("start"),
        "end": window.get("end"),
        "information_ratio": weakest["ir"],
        "benchmark_excess_return": result.get("benchmark_excess_return"),
        "max_drawdown": result.get("max_drawdown"),
        "top3_group_abs_contribution_share": result.get(
            "top3_group_abs_contribution_share"
        ),
    }


def _find_result_by_cost(results: list[Any], cost_label: str) -> dict[str, Any]:
    """
    用途與流程：從 portfolio result list 找出指定 cost_label 的 result。
    參數：results 是 JSON result list；cost_label 是成本倍率標籤。
    回傳與錯誤：找到時回傳 dict；row 不是 object 或缺少成本倍率時拋出 ValueError。
    """
    for result in results:
        if not isinstance(result, dict):
            raise ValueError("result rows must be objects")
        if result.get("cost_label") == cost_label:
            return result
    raise ValueError(f"missing cost label: {cost_label}")


def _find_compare_row(rows: list[Any], cost_label: str) -> dict[str, Any]:
    """
    用途與流程：從 raw/adjusted full_window comparison list 找出指定 cost_label 的對照列。
    參數：rows 是 comparison JSON 的 full_window list；cost_label 是成本倍率。
    回傳與錯誤：找到時回傳 dict；row 不是 object 或缺成本倍率時拋出 ValueError。
    """
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("comparison rows must be objects")
        if row.get("cost_label") == cost_label:
            return row
    raise ValueError(f"comparison is missing cost label: {cost_label}")


def _require_list(payload: dict[str, Any], key: str) -> list[Any]:
    """
    用途與流程：從 JSON object 取出必要 list 欄位。
    參數：payload 是 JSON dict；key 是必要欄位名稱。
    回傳與錯誤：欄位存在且為 list 時回傳；否則拋出 ValueError。
    """
    value = payload.get(key)
    if not isinstance(value, list):
        raise ValueError(f"JSON field must be a list: {key}")
    return value


def _require_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    """
    用途與流程：從 JSON object 取出必要 dict 欄位。
    參數：payload 是 JSON dict；key 是必要欄位名稱。
    回傳與錯誤：欄位存在且為 dict 時回傳；否則拋出 ValueError。
    """
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"JSON field must be an object: {key}")
    return value


def _optional_float(value: Any, *, key: str) -> float | None:
    """
    用途與流程：將 JSON numeric/null 欄位轉成 float 或 None，並拒絕 bool 與文字。
    參數：value 是 JSON 欄位值；key 是錯誤訊息中的欄位名稱。
    回傳與錯誤：None 回傳 None；數字回傳 float；其他型別拋出 ValueError。
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"field must be numeric or null: {key}")
    return float(value)


def _min_optional(values: Any) -> float | None:
    """
    用途與流程：計算可選數值序列的最小值，忽略 None。
    參數：values 是可能包含 None 的可迭代物件。
    回傳與錯誤：有數值時回傳最小值；否則回傳 None。
    """
    filtered = [value for value in values if value is not None]
    return min(filtered) if filtered else None


def _max_optional(values: Any) -> float | None:
    """
    用途與流程：計算可選數值序列的最大值，忽略 None。
    參數：values 是可能包含 None 的可迭代物件。
    回傳與錯誤：有數值時回傳最大值；否則回傳 None。
    """
    filtered = [value for value in values if value is not None]
    return max(filtered) if filtered else None


def _below(value: float | None, threshold: float) -> bool:
    """
    用途與流程：判斷數值是否缺失或低於門檻，供 gate failure reason 使用。
    參數：value 是可選數值；threshold 是最低門檻。
    回傳與錯誤：缺值或低於門檻回傳 True；不拋錯。
    """
    return value is None or value < threshold


def _above(value: float | None, threshold: float) -> bool:
    """
    用途與流程：判斷數值是否缺失或高於門檻，適用 concentration share gate。
    參數：value 是可選數值；threshold 是最高門檻。
    回傳與錯誤：缺值或高於門檻回傳 True；不拋錯。
    """
    return value is None or value > threshold


def _above_abs(value: float | None, threshold: float) -> bool:
    """
    用途與流程：判斷回撤絕對值是否缺失或高於可承受門檻。
    參數：value 是可選回撤值，通常為負數；threshold 是最大絕對值。
    回傳與錯誤：缺值或 abs(value) 高於門檻回傳 True；不拋錯。
    """
    return value is None or abs(value) > threshold


def _unique_preserving_order(values: list[str]) -> list[str]:
    """
    用途與流程：移除 failure reason 重複值，同時保留首次出現順序。
    參數：values 是 failure reason list。
    回傳與錯誤：回傳去重後 list；不拋錯。
    """
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _format_percent(value: Any) -> str:
    """
    用途與流程：將小數比例格式化為百分比，供 Markdown table 使用。
    參數：value 是數字或 None。
    回傳與錯誤：None 回傳 n/a；數字回傳百分比字串。
    """
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.2f}%"


def _format_decimal(value: Any) -> str:
    """
    用途與流程：將 Information Ratio 等一般小數格式化為三位小數。
    參數：value 是數字或 None。
    回傳與錯誤：None 回傳 n/a；數字回傳三位小數字串。
    """
    if value is None:
        return "n/a"
    return f"{float(value):.3f}"


if __name__ == "__main__":
    raise SystemExit(main())
