from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from signal_forge.entry_edge import EntryEdgeResult
from signal_forge.market_data import BarValidationResult
from signal_forge.phase import PhaseExecutionResult, SignalDigest


def _round_float(value: float, decimals: int) -> float:
    return float(f"{value:.{decimals}f}")


@dataclass(frozen=True)
class EntryEdgeReportPaths:
    markdown: Path
    summary_json: Path
    trade_log_csv: Path


@dataclass(frozen=True)
class PhaseReportPaths:
    markdown: Path
    summary_json: Path
    signal_digest_csv: Path | None = None
    trace_summary_json: Path | None = None


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
    signal_digest_path = output_path / f"{stem}_signals.csv"
    trace_summary_path = output_path / f"{stem}_trace_summary.json"

    summary = _phase_summary_dict(result)
    validate_phase_summary(summary)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_phase_markdown_report(result), encoding="utf-8")

    signal_digest_csv: Path | None = None
    trace_summary_json: Path | None = None
    if result.mode == "backtest" and result.signal_digests is not None:
        validate_signal_digests(result.signal_digests)
        signal_digest_path.write_text(
            _signal_digest_csv(result.signal_digests),
            encoding="utf-8",
            newline="",
        )
        signal_digest_csv = signal_digest_path
        trace_summary_path.write_text(
            json.dumps(
                _signal_trace_summary_dict(result.signal_digests),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        trace_summary_json = trace_summary_path

    return PhaseReportPaths(
        markdown=markdown_path,
        summary_json=summary_path,
        signal_digest_csv=signal_digest_csv,
        trace_summary_json=trace_summary_json,
    )


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
            "gross_profit": _round_float(result.gross_profit, 2),
            "gross_loss": _round_float(result.gross_loss, 2),
            "trade_count": result.trade_count,
            "ignored_short_count": result.ignored_short_count,
            "unclosed_signal_count": result.unclosed_signal_count,
            "overlapping_signal_count": result.overlapping_signal_count,
            "win_rate": _round_float(result.win_rate, 6),
            "average_net_pnl": _round_float(result.average_net_pnl, 2),
            "max_drawdown": _round_float(result.max_drawdown, 6),
            "start_equity": _round_float(result.start_equity, 2),
            "end_equity": _round_float(result.end_equity, 2),
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

    # Cross-field invariants (safety + clarity):
    # - live must be dry-run only; never allow submitted intents in summaries.
    # - backtest must include entry_edge; must not claim dry_run.
    if mode == "live":
        if dry_run is not True:
            raise ValueError("phase summary live mode must have phase.dry_run=True")
        if entry_edge is not None:
            raise ValueError("phase summary live mode must not include entry_edge")
        if order_intents is None:
            raise ValueError("phase summary live mode must include order_intents")
        for index, intent in enumerate(order_intents, start=1):
            if intent.get("dry_run") is not True:
                raise ValueError(
                    f"phase summary order_intents[{index}].dry_run must be True in live mode"
                )
            if intent.get("submitted") is not False:
                raise ValueError(
                    f"phase summary order_intents[{index}].submitted must be False in live mode"
                )
            safety_note = intent.get("safety_note")
            if not isinstance(safety_note, str) or "LIVE_DRY_RUN_ONLY" not in safety_note:
                raise ValueError(
                    f"phase summary order_intents[{index}].safety_note must include LIVE_DRY_RUN_ONLY"
                )
    else:
        if dry_run is not False:
            raise ValueError("phase summary backtest mode must have phase.dry_run=False")
        if entry_edge is None:
            raise ValueError("phase summary backtest mode must include entry_edge")
        if order_intents is not None and order_intents:
            raise ValueError("phase summary backtest mode must not include any order_intents")


def validate_signal_digests(digests: list[SignalDigest]) -> None:
    """Enforce deterministic invariants for backtest signal digests."""

    previous_index: int | None = None
    previous_timestamp: str | None = None
    for position, digest in enumerate(digests):
        if not digest.timestamp:
            raise ValueError(
                f"signal digest timestamp must be non-empty (position={position})"
            )

        if previous_index is not None and digest.index <= previous_index:
            raise ValueError(
                "signal digests must be sorted by increasing index "
                f"(position={position})"
            )
        if previous_timestamp is not None and digest.timestamp < previous_timestamp:
            raise ValueError(
                "signal digests must be sorted by non-decreasing timestamp "
                f"(position={position})"
            )

        previous_index = digest.index
        previous_timestamp = digest.timestamp


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
        row = asdict(trade)
        for money_key in ("gross_pnl", "cost", "net_pnl"):
            if isinstance(row.get(money_key), float):
                row[money_key] = f"{row[money_key]:.2f}"
        if isinstance(row.get("return_pct"), float):
            row["return_pct"] = f"{row['return_pct']:.6f}"
        if isinstance(row.get("signal_score"), float):
            row["signal_score"] = f"{row['signal_score']:.6f}"
        writer.writerow(row)
    return buffer.getvalue()


def _signal_digest_csv(digests: list[SignalDigest]) -> str:
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "index",
            "timestamp",
            "target_position",
            "position_change",
            "reason",
            "score",
            "is_long_entry",
            "is_flatten",
        ],
    )
    writer.writeheader()
    for digest in digests:
        row = asdict(digest)
        if isinstance(row.get("target_position"), float):
            row["target_position"] = f"{row['target_position']:.6f}"
        if isinstance(row.get("position_change"), float):
            row["position_change"] = f"{row['position_change']:.6f}"
        if isinstance(row.get("score"), float):
            row["score"] = f"{row['score']:.6f}"
        writer.writerow(row)
    return buffer.getvalue()


def _signal_trace_summary_dict(digests: list[SignalDigest]) -> dict[str, object]:
    long_entry_count = sum(1 for digest in digests if digest.is_long_entry)
    flatten_count = sum(1 for digest in digests if digest.is_flatten)
    nonzero_position_change_count = sum(
        1 for digest in digests if abs(digest.position_change) > 0
    )
    first_timestamp = digests[0].timestamp if digests else None
    last_timestamp = digests[-1].timestamp if digests else None
    last_target_position = digests[-1].target_position if digests else 0.0
    reasons = sorted({digest.reason for digest in digests if digest.reason})
    return {
        "trace_summary": {
            "bar_count": len(digests),
            "long_entry_count": long_entry_count,
            "flatten_count": flatten_count,
            "nonzero_position_change_count": nonzero_position_change_count,
            "first_timestamp": first_timestamp,
            "last_timestamp": last_timestamp,
            "last_target_position": _round_float(last_target_position, 6),
            "reasons": reasons,
        }
    }


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
        "## Conclusion",
        "",
        f"- Decision: {result.decision.upper()}",
        f"- Profit Factor: {pf}",
        f"- Trades: {result.trade_count}",
        f"- Win rate: {result.win_rate:.2%}",
        f"- Average net PnL: {result.average_net_pnl:.2f}",
        f"- Max drawdown: {result.max_drawdown:.2%}",
    ]
    if result.failure_reason:
        lines.append(f"- Failure reason: {result.failure_reason}")
    if result.sample_risk:
        lines.append(f"- Sample risk: {result.sample_risk}")

    lines.extend(
        [
            "",
            "## Backtest Settings",
            "",
            f"- Initial equity: {result.config.initial_equity:.2f}",
            f"- Commission (bps): {result.config.commission_bps:.2f}",
            f"- Slippage (bps): {result.config.slippage_bps:.2f}",
            f"- Fixed hold bars: {result.config.hold_bars_per_day}",
            f"- Pass threshold PF: >{result.config.pass_profit_factor:.2f}",
            "- Execution: signal confirmed at bar close; enter at next bar open; exit at exit bar close after fixed hold.",
            "- Phase 1 constraints: long-only; ignore short signals; no stops/take-profit/filters/parameter optimization.",
            "",
            "## Data Validation",
            "",
        ]
    )

    if data_validation:
        lines.extend(
            [
                f"- Bars: {data_validation.bar_count}",
                f"- Start: {data_validation.start_timestamp}",
                f"- End: {data_validation.end_timestamp}",
                f"- Errors: {len(data_validation.errors)}",
                f"- Warnings: {len(data_validation.warnings)}",
            ]
        )
        for warning in data_validation.warnings:
            lines.append(f"- Warning: {warning}")
    else:
        lines.append("- Data validation was not provided.")

    lines.extend(["", "## Strategy Spec (Distilled)", ""])
    if strategy_spec:
        for key, value in strategy_spec.items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- No strategy spec was provided.")

    lines.extend(
        [
            "",
            "## Trade Statistics",
            "",
            f"- Gross profit: {result.gross_profit:.2f}",
            f"- Gross loss: {result.gross_loss:.2f}",
            f"- Ignored short signals: {result.ignored_short_count}",
            f"- Unclosed signals: {result.unclosed_signal_count}",
            f"- Overlapping ignored signals: {result.overlapping_signal_count}",
            f"- End equity: {result.end_equity:.2f}",
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
