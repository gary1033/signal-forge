from __future__ import annotations

import csv
import json
from collections import Counter
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

    if result.mode == "backtest" and result.signal_digests is not None:
        validate_signal_digests(result.signal_digests)

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
        signal_digest_text = _signal_digest_csv(result.signal_digests)
        signal_digest_path.write_text(
            signal_digest_text,
            encoding="utf-8",
            newline="",
        )
        signal_digest_csv = signal_digest_path
        trace_summary = _signal_trace_summary_dict(result.signal_digests)
        validate_trace_summary(trace_summary)
        validate_signal_digest_csv(trace_summary, signal_digest_text)
        trace_summary_path.write_text(
            json.dumps(
                trace_summary,
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


def validate_signal_digest_csv(trace_summary: dict[str, object], csv_text: str) -> None:
    import io

    trace = trace_summary.get("trace_summary")
    if not isinstance(trace, dict):
        raise ValueError("trace summary missing required dict key: trace_summary")

    reader = csv.DictReader(io.StringIO(csv_text))
    expected = {
        "index",
        "timestamp",
        "previous_target_position",
        "target_position",
        "position_change",
        "reason",
        "score",
        "is_long_entry",
        "is_flatten",
        "is_hold",
    }
    fieldnames = set(reader.fieldnames or [])
    if fieldnames != expected:
        raise ValueError(
            "signal digest csv must have deterministic columns: "
            f"expected={sorted(expected)} got={sorted(fieldnames)}"
        )

    rows = list(reader)
    bar_count = int(trace["bar_count"])
    if len(rows) != bar_count:
        raise ValueError(
            "signal digest csv row count must match trace summary bar_count: "
            f"rows={len(rows)} bar_count={bar_count}"
        )

    if not rows:
        return

    def parse_bool(value: str, *, field: str) -> bool:
        if value == "True":
            return True
        if value == "False":
            return False
        raise ValueError(f"signal digest csv {field} must be 'True' or 'False'")

    def parse_int(value: str, *, field: str) -> int:
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"signal digest csv {field} must be an int") from exc

    def parse_float(value: str, *, field: str) -> float:
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(f"signal digest csv {field} must be a float") from exc

    tolerance = 1e-9
    long_entry_count = 0
    flatten_count = 0
    hold_count = 0
    nonzero_target_position_count = 0
    nonzero_position_change_count = 0
    open_count = 0
    close_count = 0

    previous_index: int | None = None
    previous_timestamp: str | None = None
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    first_target_position = 0.0
    last_previous_target_position = 0.0
    last_target_position = 0.0

    for row in rows:
        index = parse_int(row["index"], field="index")
        timestamp = row["timestamp"]
        previous_target_position = parse_float(
            row["previous_target_position"], field="previous_target_position"
        )
        target_position = parse_float(row["target_position"], field="target_position")
        position_change = parse_float(row["position_change"], field="position_change")
        is_long_entry = parse_bool(row["is_long_entry"], field="is_long_entry")
        is_flatten = parse_bool(row["is_flatten"], field="is_flatten")
        is_hold = parse_bool(row["is_hold"], field="is_hold")

        if previous_index is not None and index <= previous_index:
            raise ValueError("signal digest csv rows must be sorted by increasing index")
        if previous_timestamp is not None and timestamp < previous_timestamp:
            raise ValueError("signal digest csv rows must be sorted by non-decreasing timestamp")

        if abs((target_position - previous_target_position) - position_change) > tolerance:
            raise ValueError(
                "signal digest csv position_change must match target_position delta: "
                f"index={index}"
            )

        epsilon = 1e-12
        computed_is_long_entry = target_position > epsilon and previous_target_position <= epsilon
        computed_is_flatten = target_position <= epsilon and previous_target_position > epsilon
        computed_is_hold = abs(target_position) > epsilon and abs(position_change) <= epsilon
        if is_long_entry != computed_is_long_entry:
            raise ValueError(f"signal digest csv is_long_entry mismatch: index={index}")
        if is_flatten != computed_is_flatten:
            raise ValueError(f"signal digest csv is_flatten mismatch: index={index}")
        if is_hold != computed_is_hold:
            raise ValueError(f"signal digest csv is_hold mismatch: index={index}")

        if first_timestamp is None:
            first_timestamp = timestamp
            first_target_position = target_position
        last_timestamp = timestamp
        last_previous_target_position = previous_target_position
        last_target_position = target_position

        if is_long_entry:
            long_entry_count += 1
        if is_flatten:
            flatten_count += 1
        if is_hold:
            hold_count += 1
        if abs(target_position) > 1e-12:
            nonzero_target_position_count += 1
        if abs(position_change) > 1e-12:
            nonzero_position_change_count += 1
        if abs(previous_target_position) < 1e-12 and abs(target_position) > 1e-12:
            open_count += 1
        if abs(previous_target_position) > 1e-12 and abs(target_position) < 1e-12:
            close_count += 1

        previous_index = index
        previous_timestamp = timestamp

    expected_counts = {
        "close_count": close_count,
        "flatten_count": flatten_count,
        "hold_count": hold_count,
        "long_entry_count": long_entry_count,
        "nonzero_target_position_count": nonzero_target_position_count,
        "nonzero_position_change_count": nonzero_position_change_count,
        "open_count": open_count,
    }
    for name, expected_value in expected_counts.items():
        actual_value = int(trace[name])
        if actual_value != expected_value:
            raise ValueError(
                f"signal digest csv {name} must match trace summary: "
                f"csv={expected_value} trace_summary={actual_value}"
            )

    def assert_close(name: str, expected_value: float, actual_value: float) -> None:
        if abs(expected_value - actual_value) > tolerance:
            raise ValueError(
                f"signal digest csv {name} must match trace summary: "
                f"csv={expected_value} trace_summary={actual_value}"
            )

    assert_close(
        "first_target_position",
        first_target_position,
        float(trace["first_target_position"]),
    )
    assert_close(
        "last_previous_target_position",
        last_previous_target_position,
        float(trace["last_previous_target_position"]),
    )
    assert_close(
        "last_target_position",
        last_target_position,
        float(trace["last_target_position"]),
    )
    if first_timestamp != trace["first_timestamp"]:
        raise ValueError(
            "signal digest csv first_timestamp must match trace summary: "
            f"csv={first_timestamp} trace_summary={trace['first_timestamp']}"
        )
    if last_timestamp != trace["last_timestamp"]:
        raise ValueError(
            "signal digest csv last_timestamp must match trace summary: "
            f"csv={last_timestamp} trace_summary={trace['last_timestamp']}"
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
    previous_target_position: float | None = None
    for position, digest in enumerate(digests):
        if not digest.timestamp:
            raise ValueError(
                f"signal digest timestamp must be non-empty (position={position})"
            )

        reason = digest.reason
        reason_stripped = reason.strip()
        if not reason_stripped:
            raise ValueError(
                f"signal digest reason must be non-empty (position={position})"
            )
        if reason_stripped != reason:
            raise ValueError(
                "signal digest reason must not have leading/trailing whitespace "
                f"(position={position})"
            )
        if not reason.isascii() or any(char in {"\r", "\n", "\t"} for char in reason):
            raise ValueError(
                "signal digest reason must be ASCII-only and single-line "
                f"(position={position})"
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

        if previous_target_position is not None:
            expected_previous_position = digest.target_position - digest.position_change
            if abs(expected_previous_position - previous_target_position) > 1e-9:
                raise ValueError(
                    "signal digest position_change must match target_position delta "
                    f"(position={position})"
                )

        previous_index = digest.index
        previous_timestamp = digest.timestamp
        previous_target_position = digest.target_position


def validate_trace_summary(summary: dict[str, object]) -> None:
    allowed_keys = {"trace_summary"}
    extra_keys = sorted(set(summary.keys()) - allowed_keys)
    if extra_keys:
        raise ValueError(f"trace summary has unexpected keys: {extra_keys}")

    trace_summary = summary.get("trace_summary")
    if not isinstance(trace_summary, dict):
        raise ValueError("trace summary missing required dict key: trace_summary")

    required_fields: dict[str, object] = {
        "bar_count": int,
        "close_count": int,
        "entry_count": int,
        "first_target_position": (int, float),
        "first_timestamp": (type(None), str),
        "flatten_count": int,
        "hold_count": int,
        "last_previous_target_position": (int, float),
        "last_target_position": (int, float),
        "last_timestamp": (type(None), str),
        "long_entry_count": int,
        "nonzero_target_position_count": int,
        "nonzero_position_change_count": int,
        "open_count": int,
        "reason_counts": list,
        "reasons": list,
        "unique_reason_count": int,
    }

    missing = sorted(field for field in required_fields if field not in trace_summary)
    if missing:
        raise ValueError(f"trace summary trace_summary missing keys: {missing}")

    for field, expected in required_fields.items():
        value = trace_summary.get(field)
        if not isinstance(value, expected):
            raise ValueError(f"trace summary trace_summary.{field} has invalid type")

    bar_count = int(trace_summary["bar_count"])
    if bar_count < 0:
        raise ValueError("trace summary trace_summary.bar_count must be non-negative")

    counts = {
        "close_count": int(trace_summary["close_count"]),
        "entry_count": int(trace_summary["entry_count"]),
        "flatten_count": int(trace_summary["flatten_count"]),
        "hold_count": int(trace_summary["hold_count"]),
        "long_entry_count": int(trace_summary["long_entry_count"]),
        "nonzero_target_position_count": int(trace_summary["nonzero_target_position_count"]),
        "nonzero_position_change_count": int(trace_summary["nonzero_position_change_count"]),
        "open_count": int(trace_summary["open_count"]),
    }
    for name, value in counts.items():
        if value < 0:
            raise ValueError(f"trace summary trace_summary.{name} must be non-negative")
        if value > bar_count:
            raise ValueError(f"trace summary trace_summary.{name} must be <= bar_count")

    if counts["entry_count"] != counts["open_count"]:
        raise ValueError("trace summary trace_summary.entry_count must equal open_count")

    if counts["hold_count"] > counts["nonzero_target_position_count"]:
        raise ValueError(
            "trace summary trace_summary.hold_count must be <= nonzero_target_position_count"
        )

    if counts["open_count"] + counts["close_count"] > counts["nonzero_position_change_count"]:
        raise ValueError(
            "trace summary trace_summary.open_count + close_count must be <= nonzero_position_change_count"
        )

    first_timestamp = trace_summary.get("first_timestamp")
    last_timestamp = trace_summary.get("last_timestamp")
    if bar_count == 0:
        if first_timestamp is not None or last_timestamp is not None:
            raise ValueError(
                "trace summary trace_summary timestamps must be None when bar_count=0"
            )
        if (
            float(trace_summary["first_target_position"]) != 0.0
            or float(trace_summary["last_previous_target_position"]) != 0.0
            or float(trace_summary["last_target_position"]) != 0.0
        ):
            raise ValueError(
                "trace summary trace_summary target positions must be 0.0 when bar_count=0"
            )
    else:
        if not isinstance(first_timestamp, str) or not first_timestamp:
            raise ValueError(
                "trace summary trace_summary.first_timestamp must be a non-empty str when bar_count>0"
            )
        if not isinstance(last_timestamp, str) or not last_timestamp:
            raise ValueError(
                "trace summary trace_summary.last_timestamp must be a non-empty str when bar_count>0"
            )
        if last_timestamp < first_timestamp:
            raise ValueError("trace summary trace_summary timestamps must be non-decreasing")

    reasons = trace_summary.get("reasons") or []
    if not isinstance(reasons, list):
        raise ValueError("trace summary trace_summary.reasons must be a list")
    if any((not isinstance(reason, str)) or (not reason) for reason in reasons):
        raise ValueError("trace summary trace_summary.reasons must contain non-empty strings")
    if reasons != sorted(reasons):
        raise ValueError("trace summary trace_summary.reasons must be sorted")
    if len(set(reasons)) != len(reasons):
        raise ValueError("trace summary trace_summary.reasons must be unique")

    unique_reason_count = int(trace_summary["unique_reason_count"])
    if unique_reason_count != len(reasons):
        raise ValueError("trace summary trace_summary.unique_reason_count must match reasons length")

    reason_counts = trace_summary.get("reason_counts") or []
    if not isinstance(reason_counts, list):
        raise ValueError("trace summary trace_summary.reason_counts must be a list")

    parsed_reason_counts: list[tuple[str, int]] = []
    for index, item in enumerate(reason_counts):
        if not isinstance(item, dict):
            raise ValueError(f"trace summary trace_summary.reason_counts[{index}] must be a dict")
        if set(item.keys()) != {"reason", "count"}:
            raise ValueError(f"trace summary trace_summary.reason_counts[{index}] must have keys ['reason', 'count']")
        reason = item.get("reason")
        count = item.get("count")
        if not isinstance(reason, str) or not reason:
            raise ValueError(f"trace summary trace_summary.reason_counts[{index}].reason must be a non-empty str")
        if not isinstance(count, int) or count <= 0:
            raise ValueError(f"trace summary trace_summary.reason_counts[{index}].count must be a positive int")
        parsed_reason_counts.append((reason, count))

    reason_count_reasons = [reason for reason, _count in parsed_reason_counts]
    if set(reason_count_reasons) != set(reasons):
        raise ValueError("trace summary trace_summary.reason_counts reasons must match reasons list")
    if len(set(reason_count_reasons)) != len(reason_count_reasons):
        raise ValueError("trace summary trace_summary.reason_counts reasons must be unique")

    expected_reason_counts = sorted(parsed_reason_counts, key=lambda item: (-item[1], item[0]))
    if parsed_reason_counts != expected_reason_counts:
        raise ValueError("trace summary trace_summary.reason_counts must be sorted by (-count, reason)")

    if sum(count for _reason, count in parsed_reason_counts) != bar_count:
        raise ValueError("trace summary trace_summary.reason_counts total must equal bar_count")


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
            "previous_target_position",
            "target_position",
            "position_change",
            "reason",
            "score",
            "is_long_entry",
            "is_flatten",
            "is_hold",
        ],
    )
    writer.writeheader()
    for digest in digests:
        previous_target_position = digest.target_position - digest.position_change
        is_hold = abs(digest.target_position) > 0 and abs(digest.position_change) < 1e-12
        row = {
            "index": digest.index,
            "timestamp": digest.timestamp,
            "previous_target_position": f"{previous_target_position:.6f}",
            "target_position": f"{digest.target_position:.6f}",
            "position_change": f"{digest.position_change:.6f}",
            "reason": digest.reason,
            "score": f"{digest.score:.6f}",
            "is_long_entry": digest.is_long_entry,
            "is_flatten": digest.is_flatten,
            "is_hold": is_hold,
        }
        writer.writerow(row)
    return buffer.getvalue()


def _signal_trace_summary_dict(digests: list[SignalDigest]) -> dict[str, object]:
    long_entry_count = sum(1 for digest in digests if digest.is_long_entry)
    flatten_count = sum(1 for digest in digests if digest.is_flatten)
    nonzero_target_position_count = sum(
        1 for digest in digests if abs(digest.target_position) > 1e-12
    )
    hold_count = sum(
        1
        for digest in digests
        if abs(digest.target_position) > 0 and abs(digest.position_change) < 1e-12
    )
    open_count = 0
    close_count = 0
    for digest in digests:
        previous_target_position = digest.target_position - digest.position_change
        if abs(previous_target_position) < 1e-12 and abs(digest.target_position) > 1e-12:
            open_count += 1
        if abs(previous_target_position) > 1e-12 and abs(digest.target_position) < 1e-12:
            close_count += 1
    nonzero_position_change_count = sum(
        1 for digest in digests if abs(digest.position_change) > 0
    )
    first_timestamp = digests[0].timestamp if digests else None
    last_timestamp = digests[-1].timestamp if digests else None
    first_target_position = digests[0].target_position if digests else 0.0
    last_previous_target_position = (
        digests[-1].target_position - digests[-1].position_change if digests else 0.0
    )
    last_target_position = digests[-1].target_position if digests else 0.0
    reasons = [digest.reason for digest in digests if digest.reason]
    reason_counts = Counter(reasons)
    reason_count_items = [
        {"reason": reason, "count": count}
        for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    unique_reasons = sorted(reason_counts.keys())
    return {
        "trace_summary": {
            "bar_count": len(digests),
            "close_count": close_count,
            "entry_count": open_count,
            "first_target_position": _round_float(first_target_position, 6),
            "long_entry_count": long_entry_count,
            "flatten_count": flatten_count,
            "hold_count": hold_count,
            "last_previous_target_position": _round_float(last_previous_target_position, 6),
            "nonzero_target_position_count": nonzero_target_position_count,
            "nonzero_position_change_count": nonzero_position_change_count,
            "open_count": open_count,
            "first_timestamp": first_timestamp,
            "last_timestamp": last_timestamp,
            "last_target_position": _round_float(last_target_position, 6),
            "unique_reason_count": len(unique_reasons),
            "reasons": unique_reasons,
            "reason_counts": reason_count_items,
        }
    }


def _signal_digest_invariants_summary(digests: list[SignalDigest]) -> dict[str, object]:
    index_increasing = True
    timestamp_non_decreasing = True
    timestamps_non_empty = True
    reasons_non_empty = True
    reasons_ascii_single_line = True
    reasons_trimmed = True
    previous_index: int | None = None
    previous_timestamp: str | None = None
    for digest in digests:
        if not digest.timestamp:
            timestamps_non_empty = False
        if not digest.reason.strip():
            reasons_non_empty = False
        if digest.reason.strip() != digest.reason:
            reasons_trimmed = False
        if (not digest.reason.isascii()) or any(
            char in {"\r", "\n", "\t"} for char in digest.reason
        ):
            reasons_ascii_single_line = False
        if previous_index is not None and digest.index <= previous_index:
            index_increasing = False
        if previous_timestamp is not None and digest.timestamp < previous_timestamp:
            timestamp_non_decreasing = False
        previous_index = digest.index
        previous_timestamp = digest.timestamp

    first_timestamp = digests[0].timestamp if digests else None
    last_timestamp = digests[-1].timestamp if digests else None
    last_target_position = digests[-1].target_position if digests else 0.0
    reasons = [digest.reason for digest in digests if digest.reason]
    reason_counts = Counter(reasons)
    top_reasons = [
        f"{reason}({count})"
        for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))[
            :5
        ]
    ]

    return {
        "bar_count": len(digests),
        "timestamps_non_empty": timestamps_non_empty,
        "index_increasing": index_increasing,
        "timestamp_non_decreasing": timestamp_non_decreasing,
        "reasons_non_empty": reasons_non_empty,
        "reasons_trimmed": reasons_trimmed,
        "reasons_ascii_single_line": reasons_ascii_single_line,
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
        "last_target_position": _round_float(last_target_position, 6),
        "reason_count": len(set(reasons)),
        "top_reasons": top_reasons,
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

    if result.mode == "backtest" and result.signal_digests is not None:
        invariants = _signal_digest_invariants_summary(result.signal_digests)
        top_reasons = ", ".join(invariants.get("top_reasons") or []) or "n/a"
        lines.extend(
            [
                "",
                "## Backtest Digest Invariants",
                "",
                f"- Signal digests: {invariants['bar_count']}",
                f"- Timestamps non-empty: {invariants['timestamps_non_empty']}",
                f"- Index strictly increasing: {invariants['index_increasing']}",
                f"- Timestamp non-decreasing: {invariants['timestamp_non_decreasing']}",
                f"- Reasons non-empty: {invariants['reasons_non_empty']}",
                f"- Reasons trimmed: {invariants['reasons_trimmed']}",
                f"- Reasons ASCII single-line: {invariants['reasons_ascii_single_line']}",
                f"- First timestamp: {invariants['first_timestamp']}",
                f"- Last timestamp: {invariants['last_timestamp']}",
                f"- Last target position: {invariants['last_target_position']}",
                f"- Unique reasons: {invariants['reason_count']}",
                f"- Top reasons: {top_reasons}",
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
