from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from signal_forge.entry_edge import EntryEdgeResult
from signal_forge.market_data import BarValidationResult
from signal_forge.phase import PhaseExecutionResult


@dataclass(frozen=True)
class EntryEdgeReportPaths:
    markdown: Path
    summary_json: Path
    trade_log_csv: Path


@dataclass(frozen=True)
class PhaseReportPaths:
    markdown: Path
    summary_json: Path


def write_entry_edge_outputs(
    result: EntryEdgeResult,
    output_dir: str | Path,
    *,
    run_name: str | None = None,
    data_validation: BarValidationResult | None = None,
    strategy_spec: dict[str, str] | None = None,
) -> EntryEdgeReportPaths:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    stem = _safe_stem(run_name or result.strategy_name)
    markdown_path = output_path / f"{stem}.md"
    summary_path = output_path / f"{stem}.json"
    trade_log_path = output_path / f"{stem}_trades.csv"

    summary = _summary_dict(result, data_validation, strategy_spec)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    trade_log_path.write_text(_trade_log_csv(result), encoding="utf-8", newline="")
    markdown_path.write_text(
        _markdown_report(result, data_validation, strategy_spec),
        encoding="utf-8",
    )

    return EntryEdgeReportPaths(
        markdown=markdown_path,
        summary_json=summary_path,
        trade_log_csv=trade_log_path,
    )


def write_phase_outputs(
    result: PhaseExecutionResult,
    output_dir: str | Path,
    *,
    run_name: str | None = None,
) -> PhaseReportPaths:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    stem = _safe_stem(run_name or f"phase-{result.mode}-{result.adapter_name}")
    markdown_path = output_path / f"{stem}.md"
    summary_path = output_path / f"{stem}.json"

    summary = _phase_summary_dict(result)
    validate_phase_summary(summary)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_phase_markdown_report(result), encoding="utf-8")

    return PhaseReportPaths(markdown=markdown_path, summary_json=summary_path)


def _summary_dict(
    result: EntryEdgeResult,
    data_validation: BarValidationResult | None,
    strategy_spec: dict[str, str] | None,
) -> dict[str, object]:
    return {
        "strategy_name": result.strategy_name,
        "decision": result.decision,
        "failure_reason": result.failure_reason,
        "profit_factor": result.profit_factor,
        "profit_factor_status": result.profit_factor_status,
        "sample_risk": result.sample_risk,
        "metrics": {
            "gross_profit": result.gross_profit,
            "gross_loss": result.gross_loss,
            "trade_count": result.trade_count,
            "ignored_short_count": result.ignored_short_count,
            "unclosed_signal_count": result.unclosed_signal_count,
            "overlapping_signal_count": result.overlapping_signal_count,
            "win_rate": result.win_rate,
            "average_net_pnl": result.average_net_pnl,
            "max_drawdown": result.max_drawdown,
            "start_equity": result.start_equity,
            "end_equity": result.end_equity,
        },
        "config": asdict(result.config),
        "data_validation": asdict(data_validation) if data_validation else None,
        "strategy_spec": strategy_spec or {},
    }


def _phase_summary_dict(result: PhaseExecutionResult) -> dict[str, object]:
    summary: dict[str, object] = {
        "phase": {
            "mode": result.mode,
            "adapter_name": result.adapter_name,
            "dry_run": result.dry_run,
        }
    }
    if result.entry_edge_result is not None:
        entry_edge = result.entry_edge_result
        summary["entry_edge"] = {
            "strategy_name": entry_edge.strategy_name,
            "decision": entry_edge.decision,
            "profit_factor": entry_edge.profit_factor,
            "profit_factor_status": entry_edge.profit_factor_status,
            "trade_count": entry_edge.trade_count,
            "end_equity": entry_edge.end_equity,
        }
    if result.order_intents is not None:
        summary["order_intents"] = [asdict(intent) for intent in result.order_intents]
    return summary


def validate_phase_summary(summary: dict[str, object]) -> None:
    allowed_keys = {"phase", "entry_edge", "order_intents"}
    extra_keys = sorted(set(summary.keys()) - allowed_keys)
    if extra_keys:
        raise ValueError(f"phase summary has unexpected keys: {extra_keys}")

    phase = summary.get("phase")
    if not isinstance(phase, dict):
        raise ValueError("phase summary missing required dict key: phase")

    mode = phase.get("mode")
    adapter_name = phase.get("adapter_name")
    dry_run = phase.get("dry_run")
    if mode not in {"backtest", "live"}:
        raise ValueError("phase summary phase.mode must be 'backtest' or 'live'")
    if not isinstance(adapter_name, str) or not adapter_name:
        raise ValueError("phase summary phase.adapter_name must be a non-empty str")
    if not isinstance(dry_run, bool):
        raise ValueError("phase summary phase.dry_run must be a bool")

    order_intents = summary.get("order_intents")
    if order_intents is not None:
        if not isinstance(order_intents, list):
            raise ValueError("phase summary order_intents must be a list when present")
        for index, intent in enumerate(order_intents, start=1):
            if not isinstance(intent, dict):
                raise ValueError(
                    f"phase summary order_intents[{index}] must be a dict"
                )
            _validate_order_intent_dict(intent, index)

    entry_edge = summary.get("entry_edge")
    if entry_edge is not None:
        if not isinstance(entry_edge, dict):
            raise ValueError("phase summary entry_edge must be a dict when present")
        _validate_entry_edge_dict(entry_edge)


def _validate_order_intent_dict(intent: dict[str, object], index: int) -> None:
    required_fields = {
        "timestamp": str,
        "side": str,
        "target_position": (int, float),
        "reason": str,
        "dry_run": bool,
        "submitted": bool,
        "safety_note": str,
    }
    missing = sorted(field for field in required_fields if field not in intent)
    if missing:
        raise ValueError(f"phase summary order_intents[{index}] missing keys: {missing}")
    for field, expected in required_fields.items():
        value = intent.get(field)
        if not isinstance(value, expected):
            raise ValueError(
                f"phase summary order_intents[{index}].{field} has invalid type"
            )
    if intent.get("side") not in {"buy"}:
        raise ValueError(f"phase summary order_intents[{index}].side must be 'buy'")


def _validate_entry_edge_dict(entry_edge: dict[str, object]) -> None:
    required_fields = {
        "strategy_name": str,
        "decision": str,
        "profit_factor": (type(None), int, float),
        "profit_factor_status": str,
        "trade_count": int,
        "end_equity": (int, float),
    }
    missing = sorted(field for field in required_fields if field not in entry_edge)
    if missing:
        raise ValueError(f"phase summary entry_edge missing keys: {missing}")
    for field, expected in required_fields.items():
        value = entry_edge.get(field)
        if not isinstance(value, expected):
            raise ValueError(f"phase summary entry_edge.{field} has invalid type")

def _trade_log_csv(result: EntryEdgeResult) -> str:
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "signal_index",
            "signal_timestamp",
            "entry_index",
            "entry_timestamp",
            "exit_index",
            "exit_timestamp",
            "entry_price",
            "exit_price",
            "gross_pnl",
            "cost",
            "net_pnl",
            "return_pct",
            "signal_reason",
            "signal_score",
        ],
    )
    writer.writeheader()
    for trade in result.trades:
        writer.writerow(asdict(trade))
    return buffer.getvalue()


def _phase_markdown_report(result: PhaseExecutionResult) -> str:
    lines = [
        f"# Phase Report - {result.mode}",
        "",
        "## Adapter Metadata",
        "",
        f"- Phase mode: {result.mode}",
        f"- Adapter: {result.adapter_name}",
        f"- Dry run: {result.dry_run}",
    ]

    if result.entry_edge_result is not None:
        entry_edge = result.entry_edge_result
        lines.extend(
            [
                "",
                "## Backtest Result",
                "",
                f"- Strategy: {entry_edge.strategy_name}",
                f"- Decision: {entry_edge.decision}",
                f"- Profit Factor: {_format_profit_factor(entry_edge)}",
                f"- Trades: {entry_edge.trade_count}",
                f"- End equity: {entry_edge.end_equity:.2f}",
            ]
        )

    if result.order_intents is not None:
        lines.extend(["", "## Live Dry-Run Intents", ""])
        if not result.order_intents:
            lines.append("- No dry-run order intents were emitted.")
        for index, intent in enumerate(result.order_intents, start=1):
            lines.append(
                f"- Intent {index}: {intent.timestamp}, {intent.side}, "
                f"target={intent.target_position}, dry_run={intent.dry_run}, "
                f"submitted={intent.submitted}, safety={intent.safety_note}"
            )

    lines.append("")
    return "\n".join(lines)


def _markdown_report(
    result: EntryEdgeResult,
    data_validation: BarValidationResult | None,
    strategy_spec: dict[str, str] | None,
) -> str:
    pf = _format_profit_factor(result)
    lines = [
        f"# Entry Edge Report - {result.strategy_name}",
        "",
        "## 結論",
        "",
        f"- 判定：{result.decision.upper()}",
        f"- Profit Factor：{pf}",
        f"- 交易數：{result.trade_count}",
        f"- 勝率：{result.win_rate:.2%}",
        f"- 平均淨損益：{result.average_net_pnl:.2f}",
        f"- 最大回撤：{result.max_drawdown:.2%}",
    ]
    if result.failure_reason:
        lines.append(f"- 未通過原因：{result.failure_reason}")
    if result.sample_risk:
        lines.append(f"- 樣本風險：{result.sample_risk}")

    lines.extend(
        [
            "",
            "## 回測設定",
            "",
            f"- 初始權益：{result.config.initial_equity:.2f}",
            f"- 手續費 bps：{result.config.commission_bps:.2f}",
            f"- 滑價 bps：{result.config.slippage_bps:.2f}",
            f"- 固定持有 bars：{result.config.hold_bars_per_day}",
            f"- PF 門檻：>{result.config.pass_profit_factor:.2f}",
            "- 成交規則：訊號於 bar close 後成立，下一根 bar open 進場，固定持有後以 exit bar close 出場。",
            "- 第一階段規則：純多優先；short 訊號忽略；不套用停損、停利、濾網或參數最佳化。",
            "",
            "## 資料檢查",
            "",
        ]
    )

    if data_validation:
        lines.extend(
            [
                f"- bar 數：{data_validation.bar_count}",
                f"- 起始時間：{data_validation.start_timestamp}",
                f"- 結束時間：{data_validation.end_timestamp}",
                f"- 錯誤數：{len(data_validation.errors)}",
                f"- 警告數：{len(data_validation.warnings)}",
            ]
        )
        for warning in data_validation.warnings:
            lines.append(f"- 警告：{warning}")
    else:
        lines.append("- 未提供資料檢查結果。")

    lines.extend(["", "## 蒸餾後進場規格", ""])
    if strategy_spec:
        for key, value in strategy_spec.items():
            lines.append(f"- {key}：{value}")
    else:
        lines.append("- 未提供策略蒸餾規格。")

    lines.extend(
        [
            "",
            "## 交易統計",
            "",
            f"- 總獲利：{result.gross_profit:.2f}",
            f"- 總虧損：{result.gross_loss:.2f}",
            f"- 忽略 short 訊號數：{result.ignored_short_count}",
            f"- 無法關閉訊號數：{result.unclosed_signal_count}",
            f"- 重疊略過訊號數：{result.overlapping_signal_count}",
            f"- 期末權益：{result.end_equity:.2f}",
            "",
        ]
    )
    return "\n".join(lines)


def _format_profit_factor(result: EntryEdgeResult) -> str:
    if result.profit_factor_status == "infinite":
        return "Infinity"
    if result.profit_factor is None:
        return "undefined"
    return f"{result.profit_factor:.3f}"


def _safe_stem(value: str) -> str:
    allowed = []
    for char in value.lower():
        if char.isalnum() or char in {"-", "_"}:
            allowed.append(char)
        elif char.isspace():
            allowed.append("-")
    stem = "".join(allowed).strip("-_")
    return stem or "entry-edge-report"
