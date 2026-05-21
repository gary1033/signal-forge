from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

from signal_forge.entry_edge import EntryEdgeComparisonResult, EntryEdgeResult
from signal_forge.market_data import BarValidationResult
from signal_forge.phase import PhaseExecutionResult, SignalDigest
from signal_forge.reporting._orb_attribution import (
    ORB_BLOCKED_GROUP_KEYS,
    ORB_GROUP_KEYS,
    build_orb_filter_attribution,
    validate_orb_filter_attribution_dict,
)


def _round_float(value: float, decimals: int) -> float:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：value（float）由呼叫端傳入，需符合函式 contract；decimals（int）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 float；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    return float(f"{value:.{decimals}f}")


_ISO_DATE_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
def _is_iso8601_timestamp(timestamp: str) -> bool:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：timestamp（str）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 bool；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    if not timestamp:
        return False
    if _ISO_DATE_PATTERN.match(timestamp):
        try:
            date.fromisoformat(timestamp)
        except ValueError:
            return False
        return True
    candidate = timestamp.replace("Z", "+00:00")
    try:
        datetime.fromisoformat(candidate)
    except ValueError:
        return False
    return True


def _extract_iso8601_date(timestamp: str | None) -> str | None:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：timestamp（str | None）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 str | None；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    if not timestamp:
        return None
    if _ISO_DATE_PATTERN.match(timestamp):
        try:
            date.fromisoformat(timestamp)
        except ValueError:
            return None
        return timestamp
    candidate = timestamp.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    return parsed.date().isoformat()


def _build_reason_count_items(reason_counts: Counter[str]) -> list[dict[str, int | str]]:
    """
    用途與流程：把 reason Counter 轉成 deterministic list[dict] 結構，統一供 trace summary 與 attribution 區塊重用。
    參數：reason_counts（Counter[str]）由呼叫端傳入，key 為 reason 字串、value 為出現次數。
    回傳與錯誤：回傳 list[dict[str, int | str]]；若 Counter 為空，回傳空清單，不主動丟錯。
    """
    return [
        {"reason": reason, "count": count}
        for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))
    ]


@dataclass(frozen=True)
class EntryEdgeReportPaths:
    markdown: Path
    summary_json: Path
    trade_log_csv: Path


@dataclass(frozen=True)
class EntryEdgeComparisonReportPaths:
    markdown: Path
    summary_json: Path


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
    """
    用途與流程：寫出 Entry Edge markdown、summary JSON 與 trade log CSV，並回傳輸出路徑。
    參數：result（EntryEdgeResult）由呼叫端傳入，需符合函式 contract；output_dir（str | Path）由呼叫端傳入，需符合函式 contract；run_name（str | None）由呼叫端傳入，需符合函式 contract；data_validation（BarValidationResult | None）由呼叫端傳入，需符合函式 contract；strategy_spec（dict[str, str] | None）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 EntryEdgeReportPaths；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
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


def write_entry_edge_comparison_outputs(
    comparison: EntryEdgeComparisonResult,
    output_dir: str | Path,
    *,
    run_name: str | None = None,
    data_validation: BarValidationResult | None = None,
    strategy_spec: dict[str, str] | None = None,
) -> EntryEdgeComparisonReportPaths:
    """
    用途與流程：寫出多持有期比較 markdown 與 summary JSON，維持 deterministic artifact contract。
    參數：comparison（EntryEdgeComparisonResult）由呼叫端傳入，需符合函式 contract；output_dir（str | Path）由呼叫端傳入，需符合函式 contract；run_name（str | None）由呼叫端傳入，需符合函式 contract；data_validation（BarValidationResult | None）由呼叫端傳入，需符合函式 contract；strategy_spec（dict[str, str] | None）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 EntryEdgeComparisonReportPaths；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    stem = _safe_stem(run_name or comparison.strategy_name)
    markdown_path = output_path / f"{stem}_hold_comparison.md"
    summary_path = output_path / f"{stem}_hold_comparison.json"

    summary = _entry_edge_comparison_summary_dict(
        comparison,
        data_validation,
        strategy_spec,
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        _entry_edge_comparison_markdown(comparison, data_validation, strategy_spec),
        encoding="utf-8",
    )

    return EntryEdgeComparisonReportPaths(
        markdown=markdown_path,
        summary_json=summary_path,
    )


def write_phase_outputs(
    result: PhaseExecutionResult,
    output_dir: str | Path,
    *,
    run_name: str | None = None,
) -> PhaseReportPaths:
    """
    用途與流程：依 Phase 執行結果寫出 summary JSON、markdown 與 backtest signal artifacts。
    參數：result（PhaseExecutionResult）由呼叫端傳入，需符合函式 contract；output_dir（str | Path）由呼叫端傳入，需符合函式 contract；run_name（str | None）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 PhaseReportPaths；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
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

    signal_digest_csv: Path | None = None
    trace_summary_json: Path | None = None
    trace_summary: dict[str, object] | None = None
    signal_digest_text: str | None = None
    if result.mode == "backtest" and result.signal_digests is not None:
        signal_digest_text = _signal_digest_csv(result.signal_digests)
        trace_summary = _signal_trace_summary_dict(result.signal_digests)
        validate_trace_summary(trace_summary)
        validate_signal_digest_csv(trace_summary, signal_digest_text)

    markdown_path.write_text(
        _phase_markdown_report(result, trace_summary=trace_summary),
        encoding="utf-8",
    )

    if result.mode == "backtest" and result.signal_digests is not None:
        assert signal_digest_text is not None
        signal_digest_path.write_text(
            signal_digest_text,
            encoding="utf-8",
            newline="",
        )
        signal_digest_csv = signal_digest_path
        assert trace_summary is not None
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
    """
    用途與流程：讀回 signals CSV 與 trace summary，交叉驗證 deterministic artifact invariants。
    參數：trace_summary（dict[str, object]）由呼叫端傳入，需符合函式 contract；csv_text（str）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
    """
    import io
    import math
    import re

    trace = trace_summary.get("trace_summary")
    if not isinstance(trace, dict):
        raise ValueError("trace summary missing required dict key: trace_summary")

    expected_hash = trace.get("signal_digest_sha256")
    if expected_hash is not None:
        if not isinstance(expected_hash, str):
            raise ValueError("trace summary signal_digest_sha256 must be a string")
        computed_hash = hashlib.sha256(csv_text.encode("utf-8")).hexdigest()
        if computed_hash != expected_hash:
            raise ValueError("signal digest csv sha256 must match trace summary")

    reader = csv.DictReader(io.StringIO(csv_text))
    expected = {
        "index",
        "timestamp",
        "previous_target_position",
        "target_position",
        "position_bucket",
        "position_change",
        "reason",
        "score",
        "is_long_entry",
        "is_flatten",
        "is_hold",
        "hold_side",
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

    fixed_decimal_re = re.compile(r"^-?\d+\.\d{6}$")

    def parse_bool(value: str, *, field: str) -> bool:
        """
        用途與流程：解析外部輸入文字或 CSV 欄位，轉成程式內部可驗證的型別與格式。
        參數：value（str）由呼叫端傳入，需符合函式 contract；field（str）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 bool；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        if value == "True":
            return True
        if value == "False":
            return False
        raise ValueError(f"signal digest csv {field} must be 'True' or 'False'")

    def assert_fixed_decimal(value: str, *, field: str, index: int) -> None:
        """
        用途與流程：執行此模組定義的業務流程，依輸入資料產生後續 reporting、策略或測試所需結果。
        參數：value（str）由呼叫端傳入，需符合函式 contract；field（str）由呼叫端傳入，需符合函式 contract；index（int）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        if not fixed_decimal_re.match(value):
            raise ValueError(
                "signal digest csv numeric fields must use fixed 6-decimal formatting: "
                f"index={index} field={field} value={value!r}"
            )

    def parse_int(value: str, *, field: str) -> int:
        """
        用途與流程：解析外部輸入文字或 CSV 欄位，轉成程式內部可驗證的型別與格式。
        參數：value（str）由呼叫端傳入，需符合函式 contract；field（str）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 int；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"signal digest csv {field} must be an int") from exc

    def parse_float(value: str, *, field: str) -> float:
        """
        用途與流程：解析外部輸入文字或 CSV 欄位，轉成程式內部可驗證的型別與格式。
        參數：value（str）由呼叫端傳入，需符合函式 contract；field（str）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 float；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(f"signal digest csv {field} must be a float") from exc

    tolerance = 1e-9
    reason_counts: Counter[str] = Counter()
    long_entry_count = 0
    flatten_count = 0
    flatten_to_short_count = 0
    flatten_to_zero_count = 0
    flip_count = 0
    hold_count = 0
    hold_long_count = 0
    hold_short_count = 0
    nonzero_target_position_count = 0
    nonzero_position_change_count = 0
    open_count = 0
    close_count = 0
    position_bucket_long_count = 0
    position_bucket_short_count = 0
    position_bucket_flat_count = 0

    previous_index: int | None = None
    previous_timestamp: str | None = None
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    first_reason: str | None = None
    last_reason: str | None = None
    first_previous_target_position = 0.0
    first_target_position = 0.0
    last_previous_target_position = 0.0
    last_target_position = 0.0
    min_target_position = 0.0
    max_target_position = 0.0
    has_target_position = False

    for row in rows:
        index = parse_int(row["index"], field="index")
        timestamp = row["timestamp"]
        if not timestamp:
            raise ValueError(f"signal digest csv timestamp must be non-empty: index={index}")
        if not _is_iso8601_timestamp(timestamp):
            raise ValueError(
                "signal digest csv timestamp must be ISO-8601 (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS[.ffffff][Z|+HH:MM]): "
                f"index={index} timestamp={timestamp!r}"
            )

        for numeric_field in (
            "previous_target_position",
            "target_position",
            "position_change",
            "score",
        ):
            assert_fixed_decimal(row[numeric_field], field=numeric_field, index=index)

        previous_target_position = parse_float(
            row["previous_target_position"], field="previous_target_position"
        )
        target_position = parse_float(row["target_position"], field="target_position")
        position_bucket = row["position_bucket"]
        position_change = parse_float(row["position_change"], field="position_change")
        reason = row["reason"]
        score = parse_float(row["score"], field="score")
        if not math.isfinite(score):
            raise ValueError(f"signal digest csv score must be finite: index={index}")
        is_long_entry = parse_bool(row["is_long_entry"], field="is_long_entry")
        is_flatten = parse_bool(row["is_flatten"], field="is_flatten")
        is_hold = parse_bool(row["is_hold"], field="is_hold")
        hold_side = row["hold_side"]
        if hold_side not in ("none", "long", "short"):
            raise ValueError(
                "signal digest csv hold_side must be one of 'none', 'long', 'short': "
                f"index={index} hold_side={hold_side!r}"
            )

        if previous_index is not None and index <= previous_index:
            raise ValueError("signal digest csv rows must be sorted by increasing index")
        if previous_timestamp is not None and timestamp < previous_timestamp:
            raise ValueError("signal digest csv rows must be sorted by non-decreasing timestamp")

        if abs((target_position - previous_target_position) - position_change) > tolerance:
            raise ValueError(
                "signal digest csv position_change must match target_position delta: "
                f"index={index}"
            )

        if not reason:
            raise ValueError(f"signal digest csv reason must be non-empty: index={index}")
        if reason.strip() != reason:
            raise ValueError(
                "signal digest csv reason must not have leading/trailing whitespace: "
                f"index={index}"
            )
        if (not reason.isascii()) or any(char in {"\r", "\n", "\t"} for char in reason):
            raise ValueError(
                "signal digest csv reason must be ASCII-only and single-line: "
                f"index={index}"
            )
        reason_counts[reason] += 1

        epsilon = 1e-12
        if abs(target_position) <= epsilon:
            expected_position_bucket = "flat"
        elif target_position > 0:
            expected_position_bucket = "long"
        else:
            expected_position_bucket = "short"
        if position_bucket != expected_position_bucket:
            raise ValueError(
                "signal digest csv position_bucket mismatch: "
                f"index={index} expected={expected_position_bucket} got={position_bucket}"
            )
        if position_bucket == "flat":
            position_bucket_flat_count += 1
        elif position_bucket == "long":
            position_bucket_long_count += 1
        else:
            position_bucket_short_count += 1

        computed_is_long_entry = target_position > epsilon and previous_target_position <= epsilon
        computed_is_flatten = target_position <= epsilon and previous_target_position > epsilon
        computed_is_hold = abs(target_position) > epsilon and abs(position_change) <= epsilon
        if computed_is_hold:
            computed_hold_side = "long" if target_position > 0 else "short"
        else:
            computed_hold_side = "none"
        if is_long_entry != computed_is_long_entry:
            raise ValueError(f"signal digest csv is_long_entry mismatch: index={index}")
        if is_flatten != computed_is_flatten:
            raise ValueError(f"signal digest csv is_flatten mismatch: index={index}")
        if is_hold != computed_is_hold:
            raise ValueError(f"signal digest csv is_hold mismatch: index={index}")
        if hold_side != computed_hold_side:
            raise ValueError(f"signal digest csv hold_side mismatch: index={index}")

        if first_timestamp is None:
            first_timestamp = timestamp
            first_reason = reason
            first_previous_target_position = previous_target_position
            first_target_position = target_position
            min_target_position = target_position
            max_target_position = target_position
            has_target_position = True
        last_timestamp = timestamp
        last_reason = reason
        last_previous_target_position = previous_target_position
        last_target_position = target_position
        if has_target_position:
            if target_position < min_target_position:
                min_target_position = target_position
            if target_position > max_target_position:
                max_target_position = target_position

        if is_long_entry:
            long_entry_count += 1
        if is_flatten:
            flatten_count += 1
            if target_position < -1e-12:
                flatten_to_short_count += 1
            elif abs(target_position) <= 1e-12:
                flatten_to_zero_count += 1
        if is_hold:
            hold_count += 1
            if hold_side == "long":
                hold_long_count += 1
            elif hold_side == "short":
                hold_short_count += 1
        if abs(target_position) > 1e-12:
            nonzero_target_position_count += 1
        if abs(position_change) > 1e-12:
            nonzero_position_change_count += 1
        if abs(previous_target_position) < 1e-12 and abs(target_position) > 1e-12:
            open_count += 1
        if abs(previous_target_position) > 1e-12 and abs(target_position) < 1e-12:
            close_count += 1
        if (
            abs(previous_target_position) > 1e-12
            and abs(target_position) > 1e-12
            and ((previous_target_position > 0) != (target_position > 0))
        ):
            flip_count += 1

        previous_index = index
        previous_timestamp = timestamp

    if position_bucket_long_count + position_bucket_short_count != nonzero_target_position_count:
        raise ValueError(
            "signal digest csv position_bucket non-flat count must equal nonzero_target_position_count: "
            f"bucket_non_flat={position_bucket_long_count + position_bucket_short_count} nonzero_target_position_count={nonzero_target_position_count}"
        )
    if position_bucket_flat_count != bar_count - nonzero_target_position_count:
        raise ValueError(
            "signal digest csv position_bucket flat count must match bar_count - nonzero_target_position_count: "
            f"bucket_flat={position_bucket_flat_count} expected={bar_count - nonzero_target_position_count}"
        )

    short_entry_count = open_count - long_entry_count
    expected_counts = {
        "close_count": close_count,
        "entry_count": open_count,
        "flatten_count": flatten_count,
        "flatten_to_short_count": flatten_to_short_count,
        "flatten_to_zero_count": flatten_to_zero_count,
        "flip_count": flip_count,
        "hold_count": hold_count,
        "hold_long_count": hold_long_count,
        "hold_short_count": hold_short_count,
        "long_entry_count": long_entry_count,
        "nonzero_target_position_count": nonzero_target_position_count,
        "nonzero_position_change_count": nonzero_position_change_count,
        "open_count": open_count,
        "short_entry_count": short_entry_count,
    }
    for name, expected_value in expected_counts.items():
        actual_value = int(trace[name])
        if actual_value != expected_value:
            raise ValueError(
                f"signal digest csv {name} must match trace summary: "
                f"csv={expected_value} trace_summary={actual_value}"
            )

    bucket_counts = trace.get("position_bucket_counts")
    if not isinstance(bucket_counts, dict):
        raise ValueError("trace summary position_bucket_counts missing required dict")

    expected_bucket_counts = {
        "flat": position_bucket_flat_count,
        "long": position_bucket_long_count,
        "short": position_bucket_short_count,
    }
    for key, expected_value in expected_bucket_counts.items():
        actual_value = bucket_counts.get(key)
        if not isinstance(actual_value, int):
            raise ValueError(f"trace summary position_bucket_counts.{key} must be an int")
        if actual_value != expected_value:
            raise ValueError(
                "signal digest csv position bucket count must match trace summary: "
                f"bucket={key} csv={expected_value} trace_summary={actual_value}"
            )

    expected_reasons = sorted(reason_counts.keys())
    actual_reasons = trace.get("reasons") or []
    if actual_reasons != expected_reasons:
        raise ValueError(
            "signal digest csv reasons must match trace summary: "
            f"csv={expected_reasons} trace_summary={actual_reasons}"
        )

    if int(trace.get("unique_reason_count", -1)) != len(expected_reasons):
        raise ValueError(
            "signal digest csv unique reason count must match trace summary unique_reason_count: "
            f"csv={len(expected_reasons)} trace_summary={trace.get('unique_reason_count')}"
        )

    expected_reason_count_items = [
        {"reason": reason, "count": count}
        for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    actual_reason_count_items = trace.get("reason_counts") or []
    if actual_reason_count_items != expected_reason_count_items:
        raise ValueError("signal digest csv reason_counts must match trace summary reason_counts")

    def assert_close(name: str, expected_value: float, actual_value: float) -> None:
        """
        用途與流程：執行此模組定義的業務流程，依輸入資料產生後續 reporting、策略或測試所需結果。
        參數：name（str）由呼叫端傳入，需符合函式 contract；expected_value（float）由呼叫端傳入，需符合函式 contract；actual_value（float）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        if abs(expected_value - actual_value) > tolerance:
            raise ValueError(
                f"signal digest csv {name} must match trace summary: "
                f"csv={expected_value} trace_summary={actual_value}"
            )

    assert_close(
        "first_previous_target_position",
        first_previous_target_position,
        float(trace["first_previous_target_position"]),
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
    assert_close(
        "min_target_position",
        min_target_position if has_target_position else 0.0,
        float(trace["min_target_position"]),
    )
    assert_close(
        "max_target_position",
        max_target_position if has_target_position else 0.0,
        float(trace["max_target_position"]),
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
    if "first_reason" in trace and first_reason != trace.get("first_reason"):
        raise ValueError(
            "signal digest csv first_reason must match trace summary: "
            f"csv={first_reason} trace_summary={trace.get('first_reason')}"
        )
    if "last_reason" in trace and last_reason != trace.get("last_reason"):
        raise ValueError(
            "signal digest csv last_reason must match trace summary: "
            f"csv={last_reason} trace_summary={trace.get('last_reason')}"
        )

    if trace.get("timestamps_iso8601") is not True:
        raise ValueError(
            "signal digest csv timestamps are ISO-8601 but trace summary timestamps_iso8601 is not true"
        )


def _summary_dict(
    result: EntryEdgeResult,
    data_validation: BarValidationResult | None,
    strategy_spec: dict[str, str] | None,
) -> dict[str, object]:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：result（EntryEdgeResult）由呼叫端傳入，需符合函式 contract；data_validation（BarValidationResult | None）由呼叫端傳入，需符合函式 contract；strategy_spec（dict[str, str] | None）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 dict[str, object]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
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


def _entry_edge_comparison_summary_dict(
    comparison: EntryEdgeComparisonResult,
    data_validation: BarValidationResult | None,
    strategy_spec: dict[str, str] | None,
) -> dict[str, object]:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：comparison（EntryEdgeComparisonResult）由呼叫端傳入，需符合函式 contract；data_validation（BarValidationResult | None）由呼叫端傳入，需符合函式 contract；strategy_spec（dict[str, str] | None）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 dict[str, object]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    if not comparison.results:
        raise ValueError("entry-edge comparison must include at least one result")
    config = comparison.results[0].config
    return {
        "strategy_name": comparison.strategy_name,
        "hold_bars_per_day": list(comparison.hold_bars_per_day),
        "config": {
            "initial_equity": config.initial_equity,
            "commission_bps": config.commission_bps,
            "slippage_bps": config.slippage_bps,
            "pass_profit_factor": config.pass_profit_factor,
        },
        "rows": [
            _entry_edge_comparison_row(result)
            for result in comparison.results
        ],
        "data_validation": asdict(data_validation) if data_validation else None,
        "strategy_spec": strategy_spec or {},
    }


def _entry_edge_comparison_row(result: EntryEdgeResult) -> dict[str, object]:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：result（EntryEdgeResult）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 dict[str, object]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    profit_factor = (
        None
        if result.profit_factor is None
        else _round_float(result.profit_factor, 6)
    )
    return {
        "hold_bars_per_day": result.config.hold_bars_per_day,
        "decision": result.decision,
        "profit_factor_status": result.profit_factor_status,
        "profit_factor": profit_factor,
        "trade_count": result.trade_count,
        "win_rate": _round_float(result.win_rate, 6),
        "average_net_pnl": _round_float(result.average_net_pnl, 2),
        "max_drawdown": _round_float(result.max_drawdown, 6),
        "ignored_short_count": result.ignored_short_count,
        "unclosed_signal_count": result.unclosed_signal_count,
        "overlapping_signal_count": result.overlapping_signal_count,
        "failure_reason": result.failure_reason,
        "end_equity": _round_float(result.end_equity, 2),
    }


def _phase_summary_dict(result: PhaseExecutionResult) -> dict[str, object]:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：result（PhaseExecutionResult）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 dict[str, object]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
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
    """
    用途與流程：執行內部 contract 驗證，將格式錯誤、語意不一致或安全邊界破壞轉成明確例外。
    參數：summary（dict[str, object]）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
    """
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

    """
    用途與流程：驗證記憶體中的 SignalDigest 清單符合 index、timestamp、reason 與 position contract。
    參數：digests（list[SignalDigest]）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
    """
    previous_index: int | None = None
    previous_timestamp: str | None = None
    previous_target_position: float | None = None
    for position, digest in enumerate(digests):
        if not digest.timestamp:
            raise ValueError(
                f"signal digest timestamp must be non-empty (position={position})"
            )
        if not _is_iso8601_timestamp(digest.timestamp):
            raise ValueError(
                "signal digest timestamp must be ISO-8601 (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS[.ffffff][Z|+HH:MM]) "
                f"(position={position})"
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
    """
    用途與流程：驗證 trace summary JSON 與 signal digest 統計值一致，避免 reporting drift。
    參數：summary（dict[str, object]）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
    """
    allowed_keys = {"trace_summary"}
    extra_keys = sorted(set(summary.keys()) - allowed_keys)
    if extra_keys:
        raise ValueError(f"trace summary has unexpected keys: {extra_keys}")

    trace_summary = summary.get("trace_summary")
    if not isinstance(trace_summary, dict):
        raise ValueError("trace summary missing required dict key: trace_summary")

    required_fields: dict[str, object] = {
        "schema_version": int,
        "bar_count": int,
        "close_count": int,
        "end_date": (type(None), str),
        "entry_count": int,
        "first_index": (type(None), int),
        "first_previous_target_position": (int, float),
        "first_reason": (type(None), str),
        "first_target_position": (int, float),
        "first_timestamp": (type(None), str),
        "flatten_count": int,
        "flatten_to_long_count": int,
        "flatten_to_short_count": int,
        "flatten_to_zero_count": int,
        "flip_count": int,
        "hold_count": int,
        "hold_long_count": int,
        "hold_short_count": int,
        "last_index": (type(None), int),
        "last_previous_target_position": (int, float),
        "last_reason": (type(None), str),
        "last_target_position": (int, float),
        "last_timestamp": (type(None), str),
        "long_entry_count": int,
        "max_target_position": (int, float),
        "min_target_position": (int, float),
        "nonzero_target_position_count": int,
        "nonzero_position_change_count": int,
        "open_count": int,
        "position_bucket_counts": dict,
        "reason_counts": list,
        "reasons": list,
        "signal_digest_sha256": str,
        "short_entry_count": int,
        "start_date": (type(None), str),
        "timestamps_iso8601": bool,
        "unique_reason_count": int,
    }
    optional_fields: dict[str, object] = {
        "orb_filter_attribution": dict,
    }

    missing = sorted(field for field in required_fields if field not in trace_summary)
    if missing:
        raise ValueError(f"trace summary trace_summary missing keys: {missing}")

    for field, expected in {**required_fields, **optional_fields}.items():
        value = trace_summary.get(field)
        if field in optional_fields and value is None:
            continue
        if not isinstance(value, expected):
            raise ValueError(f"trace summary trace_summary.{field} has invalid type")

    schema_version = int(trace_summary["schema_version"])
    if schema_version < 1:
        raise ValueError("trace summary trace_summary.schema_version must be >= 1")

    bar_count = int(trace_summary["bar_count"])
    if bar_count < 0:
        raise ValueError("trace summary trace_summary.bar_count must be non-negative")

    first_index = trace_summary.get("first_index")
    last_index = trace_summary.get("last_index")
    if bar_count == 0:
        if first_index is not None or last_index is not None:
            raise ValueError(
                "trace summary trace_summary first_index/last_index must be None when bar_count=0"
            )
    else:
        if not isinstance(first_index, int) or not isinstance(last_index, int):
            raise ValueError(
                "trace summary trace_summary first_index/last_index must be int when bar_count>0"
            )
        if first_index < 0:
            raise ValueError("trace summary trace_summary.first_index must be non-negative")
        if last_index < first_index:
            raise ValueError(
                "trace summary trace_summary.last_index must be >= first_index"
            )

    digest_hash = trace_summary.get("signal_digest_sha256")
    if not isinstance(digest_hash, str) or len(digest_hash) != 64 or not all(
        char in "0123456789abcdef" for char in digest_hash
    ):
        raise ValueError("trace summary trace_summary.signal_digest_sha256 must be lowercase hex sha256")

    start_date = trace_summary.get("start_date")
    end_date = trace_summary.get("end_date")
    for label, value in (("start_date", start_date), ("end_date", end_date)):
        if value is None:
            continue
        if not isinstance(value, str) or not _ISO_DATE_PATTERN.match(value):
            raise ValueError(f"trace summary trace_summary.{label} must be ISO date")
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"trace summary trace_summary.{label} must be ISO date") from exc

    min_target_position = float(trace_summary["min_target_position"])
    max_target_position = float(trace_summary["max_target_position"])
    if min_target_position > max_target_position:
        raise ValueError(
            "trace summary trace_summary min_target_position must be <= max_target_position"
        )

    counts = {
        "close_count": int(trace_summary["close_count"]),
        "entry_count": int(trace_summary["entry_count"]),
        "flatten_count": int(trace_summary["flatten_count"]),
        "flatten_to_long_count": int(trace_summary["flatten_to_long_count"]),
        "flatten_to_short_count": int(trace_summary["flatten_to_short_count"]),
        "flatten_to_zero_count": int(trace_summary["flatten_to_zero_count"]),
        "flip_count": int(trace_summary["flip_count"]),
        "hold_count": int(trace_summary["hold_count"]),
        "hold_long_count": int(trace_summary["hold_long_count"]),
        "hold_short_count": int(trace_summary["hold_short_count"]),
        "long_entry_count": int(trace_summary["long_entry_count"]),
        "nonzero_target_position_count": int(trace_summary["nonzero_target_position_count"]),
        "nonzero_position_change_count": int(trace_summary["nonzero_position_change_count"]),
        "open_count": int(trace_summary["open_count"]),
        "short_entry_count": int(trace_summary["short_entry_count"]),
    }
    for name, value in counts.items():
        if value < 0:
            raise ValueError(f"trace summary trace_summary.{name} must be non-negative")
        if value > bar_count:
            raise ValueError(f"trace summary trace_summary.{name} must be <= bar_count")

    bucket_counts = trace_summary.get("position_bucket_counts")
    if not isinstance(bucket_counts, dict):
        raise ValueError("trace summary trace_summary.position_bucket_counts must be a dict")

    expected_bucket_keys = {"flat", "long", "short"}
    actual_bucket_keys = set(bucket_counts.keys())
    if actual_bucket_keys != expected_bucket_keys:
        raise ValueError(
            "trace summary trace_summary.position_bucket_counts must have deterministic keys: "
            f"expected={sorted(expected_bucket_keys)} got={sorted(actual_bucket_keys)}"
        )

    total_bucket_count = 0
    for key in sorted(expected_bucket_keys):
        value = bucket_counts.get(key)
        if not isinstance(value, int):
            raise ValueError(
                f"trace summary trace_summary.position_bucket_counts.{key} must be an int"
            )
        if value < 0:
            raise ValueError(
                f"trace summary trace_summary.position_bucket_counts.{key} must be non-negative"
            )
        if value > bar_count:
            raise ValueError(
                f"trace summary trace_summary.position_bucket_counts.{key} must be <= bar_count"
            )
        total_bucket_count += value

    if total_bucket_count != bar_count:
        raise ValueError(
            "trace summary trace_summary.position_bucket_counts must sum to bar_count"
        )

    if counts["entry_count"] != counts["open_count"]:
        raise ValueError("trace summary trace_summary.entry_count must equal open_count")

    if counts["long_entry_count"] + counts["short_entry_count"] != counts["entry_count"]:
        raise ValueError(
            "trace summary trace_summary.long_entry_count + short_entry_count must equal entry_count"
        )

    if (
        counts["flatten_to_long_count"]
        + counts["flatten_to_short_count"]
        + counts["flatten_to_zero_count"]
        != counts["flatten_count"]
    ):
        raise ValueError(
            "trace summary trace_summary.flatten_to_long_count + flatten_to_short_count + flatten_to_zero_count must equal flatten_count"
        )

    if counts["flip_count"] > counts["nonzero_position_change_count"]:
        raise ValueError(
            "trace summary trace_summary.flip_count must be <= nonzero_position_change_count"
        )

    if counts["hold_count"] > counts["nonzero_target_position_count"]:
        raise ValueError(
            "trace summary trace_summary.hold_count must be <= nonzero_target_position_count"
        )

    if counts["hold_long_count"] + counts["hold_short_count"] != counts["hold_count"]:
        raise ValueError(
            "trace summary trace_summary.hold_long_count + hold_short_count must equal hold_count"
        )

    if counts["open_count"] + counts["close_count"] > counts["nonzero_position_change_count"]:
        raise ValueError(
            "trace summary trace_summary.open_count + close_count must be <= nonzero_position_change_count"
        )

    first_reason = trace_summary.get("first_reason")
    last_reason = trace_summary.get("last_reason")
    first_timestamp = trace_summary.get("first_timestamp")
    last_timestamp = trace_summary.get("last_timestamp")
    if bar_count == 0:
        if first_timestamp is not None or last_timestamp is not None:
            raise ValueError(
                "trace summary trace_summary timestamps must be None when bar_count=0"
            )
        if first_reason is not None or last_reason is not None:
            raise ValueError(
                "trace summary trace_summary first_reason/last_reason must be None when bar_count=0"
            )
        if (
            float(trace_summary["first_previous_target_position"]) != 0.0
            or float(trace_summary["first_target_position"]) != 0.0
            or float(trace_summary["last_previous_target_position"]) != 0.0
            or float(trace_summary["last_target_position"]) != 0.0
            or min_target_position != 0.0
            or max_target_position != 0.0
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
        if not isinstance(first_reason, str) or not first_reason:
            raise ValueError(
                "trace summary trace_summary.first_reason must be a non-empty str when bar_count>0"
            )
        if not isinstance(last_reason, str) or not last_reason:
            raise ValueError(
                "trace summary trace_summary.last_reason must be a non-empty str when bar_count>0"
            )
        if not _is_iso8601_timestamp(first_timestamp):
            raise ValueError(
                "trace summary trace_summary.first_timestamp must be ISO-8601 when bar_count>0"
            )
        if not _is_iso8601_timestamp(last_timestamp):
            raise ValueError(
                "trace summary trace_summary.last_timestamp must be ISO-8601 when bar_count>0"
            )
        if last_timestamp < first_timestamp:
            raise ValueError("trace summary trace_summary timestamps must be non-decreasing")

        first_target_position = float(trace_summary["first_target_position"])
        last_target_position = float(trace_summary["last_target_position"])
        if not (min_target_position <= first_target_position <= max_target_position):
            raise ValueError(
                "trace summary trace_summary first_target_position must be within min/max target_position range"
            )
        if not (min_target_position <= last_target_position <= max_target_position):
            raise ValueError(
                "trace summary trace_summary last_target_position must be within min/max target_position range"
            )

    reasons = trace_summary.get("reasons") or []
    if not isinstance(reasons, list):
        raise ValueError("trace summary trace_summary.reasons must be a list")
    if any((not isinstance(reason, str)) or (not reason) for reason in reasons):
        raise ValueError("trace summary trace_summary.reasons must contain non-empty strings")
    if reasons != sorted(reasons):
        raise ValueError("trace summary trace_summary.reasons must be sorted")
    if len(set(reasons)) != len(reasons):
        raise ValueError("trace summary trace_summary.reasons must be unique")
    if bar_count > 0:
        if first_reason not in reasons:
            raise ValueError("trace summary trace_summary.first_reason must be present in reasons")
        if last_reason not in reasons:
            raise ValueError("trace summary trace_summary.last_reason must be present in reasons")

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

    orb_filter_attribution = trace_summary.get("orb_filter_attribution")
    if orb_filter_attribution is not None:
        validate_orb_filter_attribution_dict(
            orb_filter_attribution=orb_filter_attribution,
            bar_count=bar_count,
            flatten_count=counts["flatten_count"],
            hold_count=counts["hold_count"],
            long_entry_count=counts["long_entry_count"],
        )


def _validate_order_intent_dict(intent: dict[str, object], index: int) -> None:
    """
    用途與流程：執行內部 contract 驗證，將格式錯誤、語意不一致或安全邊界破壞轉成明確例外。
    參數：intent（dict[str, object]）由呼叫端傳入，需符合函式 contract；index（int）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
    """
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
    """
    用途與流程：執行內部 contract 驗證，將格式錯誤、語意不一致或安全邊界破壞轉成明確例外。
    參數：entry_edge（dict[str, object]）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
    """
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
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：result（EntryEdgeResult）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
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
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：digests（list[SignalDigest]）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        lineterminator="\n",
        fieldnames=[
            "index",
            "timestamp",
            "previous_target_position",
            "target_position",
            "position_bucket",
            "position_change",
            "reason",
            "score",
            "is_long_entry",
            "is_flatten",
            "is_hold",
            "hold_side",
        ],
    )
    writer.writeheader()
    for digest in digests:
        previous_target_position = digest.target_position - digest.position_change
        epsilon = 1e-12
        if abs(digest.target_position) <= epsilon:
            position_bucket = "flat"
        elif digest.target_position > 0:
            position_bucket = "long"
        else:
            position_bucket = "short"
        is_hold = abs(digest.target_position) > epsilon and abs(digest.position_change) <= epsilon
        if is_hold:
            hold_side = "long" if digest.target_position > 0 else "short"
        else:
            hold_side = "none"
        row = {
            "index": digest.index,
            "timestamp": digest.timestamp,
            "previous_target_position": f"{previous_target_position:.6f}",
            "target_position": f"{digest.target_position:.6f}",
            "position_bucket": position_bucket,
            "position_change": f"{digest.position_change:.6f}",
            "reason": digest.reason,
            "score": f"{digest.score:.6f}",
            "is_long_entry": digest.is_long_entry,
            "is_flatten": digest.is_flatten,
            "is_hold": is_hold,
            "hold_side": hold_side,
        }
        writer.writerow(row)
    return buffer.getvalue()


def _signal_trace_summary_dict(digests: list[SignalDigest]) -> dict[str, object]:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：digests（list[SignalDigest]）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 dict[str, object]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    long_entry_count = sum(1 for digest in digests if digest.is_long_entry)
    flatten_count = sum(1 for digest in digests if digest.is_flatten)
    flatten_to_long_count = sum(
        1 for digest in digests if digest.is_flatten and digest.target_position > 1e-12
    )
    flatten_to_short_count = sum(
        1 for digest in digests if digest.is_flatten and digest.target_position < -1e-12
    )
    flatten_to_zero_count = sum(
        1 for digest in digests if digest.is_flatten and abs(digest.target_position) <= 1e-12
    )
    nonzero_target_position_count = sum(
        1 for digest in digests if abs(digest.target_position) > 1e-12
    )
    epsilon = 1e-12
    hold_count = sum(
        1
        for digest in digests
        if abs(digest.target_position) > epsilon and abs(digest.position_change) <= epsilon
    )
    hold_long_count = sum(
        1
        for digest in digests
        if digest.target_position > epsilon and abs(digest.position_change) <= epsilon
    )
    hold_short_count = sum(
        1
        for digest in digests
        if digest.target_position < -epsilon and abs(digest.position_change) <= epsilon
    )
    open_count = 0
    close_count = 0
    short_entry_count = 0
    flip_count = 0
    for digest in digests:
        previous_target_position = digest.target_position - digest.position_change
        is_open = abs(previous_target_position) < 1e-12 and abs(digest.target_position) > 1e-12
        if is_open:
            open_count += 1
            if not digest.is_long_entry:
                short_entry_count += 1
        if abs(previous_target_position) > 1e-12 and abs(digest.target_position) < 1e-12:
            close_count += 1
        if (
            abs(previous_target_position) > 1e-12
            and abs(digest.target_position) > 1e-12
            and ((previous_target_position > 0) != (digest.target_position > 0))
        ):
            flip_count += 1
    nonzero_position_change_count = sum(
        1 for digest in digests if abs(digest.position_change) > epsilon
    )
    first_index = digests[0].index if digests else None
    last_index = digests[-1].index if digests else None
    first_timestamp = digests[0].timestamp if digests else None
    last_timestamp = digests[-1].timestamp if digests else None
    first_reason = digests[0].reason if digests else None
    last_reason = digests[-1].reason if digests else None
    first_previous_target_position = (
        digests[0].target_position - digests[0].position_change if digests else 0.0
    )
    first_target_position = digests[0].target_position if digests else 0.0
    target_positions = [digest.target_position for digest in digests]
    min_target_position = min(target_positions) if target_positions else 0.0
    max_target_position = max(target_positions) if target_positions else 0.0
    last_previous_target_position = (
        digests[-1].target_position - digests[-1].position_change if digests else 0.0
    )
    last_target_position = digests[-1].target_position if digests else 0.0
    reasons = [digest.reason for digest in digests if digest.reason]
    reason_counts = Counter(reasons)
    reason_count_items = _build_reason_count_items(reason_counts)
    unique_reasons = sorted(reason_counts.keys())
    timestamps_iso8601 = all(_is_iso8601_timestamp(digest.timestamp) for digest in digests)
    start_date = _extract_iso8601_date(first_timestamp)
    end_date = _extract_iso8601_date(last_timestamp)
    flat_bucket_count = sum(1 for digest in digests if abs(digest.target_position) <= epsilon)
    long_bucket_count = sum(1 for digest in digests if digest.target_position > epsilon)
    short_bucket_count = sum(1 for digest in digests if digest.target_position < -epsilon)
    orb_filter_attribution = build_orb_filter_attribution(digests)
    trace_summary = {
        "schema_version": 10,
        "bar_count": len(digests),
        "close_count": close_count,
        "end_date": end_date,
        "entry_count": open_count,
        "first_index": first_index,
        "first_previous_target_position": _round_float(first_previous_target_position, 6),
        "first_reason": first_reason,
        "first_target_position": _round_float(first_target_position, 6),
        "long_entry_count": long_entry_count,
        "flatten_count": flatten_count,
        "flatten_to_long_count": flatten_to_long_count,
        "flip_count": flip_count,
        "flatten_to_short_count": flatten_to_short_count,
        "flatten_to_zero_count": flatten_to_zero_count,
        "hold_count": hold_count,
        "hold_long_count": hold_long_count,
        "hold_short_count": hold_short_count,
        "last_index": last_index,
        "last_previous_target_position": _round_float(last_previous_target_position, 6),
        "last_reason": last_reason,
        "nonzero_target_position_count": nonzero_target_position_count,
        "nonzero_position_change_count": nonzero_position_change_count,
        "open_count": open_count,
        "position_bucket_counts": {
            "flat": flat_bucket_count,
            "long": long_bucket_count,
            "short": short_bucket_count,
        },
        "first_timestamp": first_timestamp,
        "last_timestamp": last_timestamp,
        "last_target_position": _round_float(last_target_position, 6),
        "max_target_position": _round_float(max_target_position, 6),
        "min_target_position": _round_float(min_target_position, 6),
        "short_entry_count": short_entry_count,
        "start_date": start_date,
        "timestamps_iso8601": timestamps_iso8601,
        "unique_reason_count": len(unique_reasons),
        "reasons": unique_reasons,
        "reason_counts": reason_count_items,
        "signal_digest_sha256": hashlib.sha256(_signal_digest_csv(digests).encode("utf-8")).hexdigest(),
    }
    if orb_filter_attribution is not None:
        trace_summary["orb_filter_attribution"] = orb_filter_attribution
    return {"trace_summary": trace_summary}


def _signal_digest_invariants_summary(digests: list[SignalDigest]) -> dict[str, object]:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：digests（list[SignalDigest]）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 dict[str, object]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    index_increasing = True
    timestamp_non_decreasing = True
    timestamps_non_empty = True
    timestamps_iso8601 = True
    reasons_non_empty = True
    reasons_ascii_single_line = True
    reasons_trimmed = True
    previous_index: int | None = None
    previous_timestamp: str | None = None
    for digest in digests:
        if not digest.timestamp:
            timestamps_non_empty = False
            timestamps_iso8601 = False
        elif not _is_iso8601_timestamp(digest.timestamp):
            timestamps_iso8601 = False
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
        "timestamps_iso8601": timestamps_iso8601,
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


def _build_phase_orb_filter_attribution_lines(
    orb_filter_attribution: dict[str, object],
) -> list[str]:
    """
    用途與流程：根據既有 ORB attribution dict 建立 Phase markdown 片段，讓 phase 報表只補強人類可讀摘要，不擴新 schema。
    參數：orb_filter_attribution（dict[str, object]）需符合 `_orb_attribution` 模組已驗證過的 contract，至少包含 accepted、blocked、hold 與 group/reason 摘要。
    回傳與錯誤：回傳 list[str] 供 `_phase_markdown_report(...)` 直接串接；若欄位缺漏，會以 `None` / `n/a` 形式保守輸出，不主動丟錯。
    """
    group_counts = orb_filter_attribution.get("group_counts")
    blocked_reason_counts = orb_filter_attribution.get("blocked_reason_counts")
    blocked_reason_text = "n/a"
    if isinstance(blocked_reason_counts, list) and blocked_reason_counts:
        blocked_reason_text = ", ".join(
            f"{item.get('reason')}({item.get('count')})"
            for item in blocked_reason_counts
            if isinstance(item, dict)
        )
    accepted_group = hold_group = other_group = range_group = retest_group = None
    session_group = structure_group = trend_group = volume_group = None
    if isinstance(group_counts, dict):
        accepted_group = group_counts.get("accepted")
        hold_group = group_counts.get("hold")
        other_group = group_counts.get("other")
        range_group = group_counts.get("range")
        retest_group = group_counts.get("retest")
        session_group = group_counts.get("session")
        structure_group = group_counts.get("structure")
        trend_group = group_counts.get("trend")
        volume_group = group_counts.get("volume")
    return [
        "",
        "## ORB Filter Attribution",
        "",
        f"- Accepted breakouts: {orb_filter_attribution.get('accepted_entry_count')}",
        f"- Blocked non-entry bars: {orb_filter_attribution.get('blocked_signal_count')}",
        f"- Hold bars: {orb_filter_attribution.get('hold_count')}",
        "- Groups (accepted/hold/session/range/structure/trend/volume/retest/other): "
        f"{accepted_group}/{hold_group}/{session_group}/{range_group}/{structure_group}/{trend_group}/{volume_group}/{retest_group}/{other_group}",
        f"- Blocked reasons: {blocked_reason_text}",
        "- Interpretation: this phase report keeps ORB attribution as a compact blocked/accepted summary; state, tier, and rule metadata remain in entry-edge strategy_spec artifacts.",
    ]


def _phase_markdown_report(
    result: PhaseExecutionResult,
    *,
    trace_summary: dict[str, object] | None = None,
) -> str:
    """
    用途與流程：組裝 Phase markdown 報表，依 mode 決定是否加入 backtest digest、trace summary 與 live dry-run intents 區塊。
    參數：result（PhaseExecutionResult）提供 Phase 執行結果；trace_summary（dict[str, object] | None）在 backtest 時提供已驗證的 signals trace 摘要。
    回傳與錯誤：回傳 str 供 writer 直接落盤；若上游傳入不符合 contract 的資料，會沿用既有欄位讀取結果並在必要時由上游 validator 擋下。
    """
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
                f"- Timestamps ISO-8601: {invariants['timestamps_iso8601']}",
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

        if trace_summary is not None:
            trace = trace_summary.get("trace_summary")
            if isinstance(trace, dict):
                lines.extend(
                    [
                        f"- Trace summary bar_count: {trace.get('bar_count')}",
                        f"- Trace summary unique reasons: {trace.get('unique_reason_count')}",
                        f"- Trace summary last target position: {trace.get('last_target_position')}",
                    ]
                )

        if trace_summary is not None:
            trace = trace_summary.get("trace_summary")
            if isinstance(trace, dict):
                bucket_counts = trace.get("position_bucket_counts")
                flat_bucket = None
                long_bucket = None
                short_bucket = None
                if isinstance(bucket_counts, dict):
                    flat_bucket = bucket_counts.get("flat")
                    long_bucket = bucket_counts.get("long")
                    short_bucket = bucket_counts.get("short")
                lines.extend(
                    [
                        "",
                        "## Backtest Trace Summary",
                        "",
                        f"- Bar count: {trace.get('bar_count')}",
                        f"- Trace schema version: {trace.get('schema_version')}",
                        f"- Entry/Flatten/Hold: {trace.get('entry_count')}/{trace.get('flatten_count')}/{trace.get('hold_count')}",
                        f"- Hold long/short: {trace.get('hold_long_count')}/{trace.get('hold_short_count')}",
                        f"- Open/Close: {trace.get('open_count')}/{trace.get('close_count')}",
                        f"- Position buckets (flat/long/short): {flat_bucket}/{long_bucket}/{short_bucket}",
                        f"- First previous target position: {trace.get('first_previous_target_position')}",
                        f"- First target position: {trace.get('first_target_position')}",
                        f"- Last previous target position: {trace.get('last_previous_target_position')}",
                        f"- Nonzero target positions: {trace.get('nonzero_target_position_count')}",
                        f"- Nonzero position changes: {trace.get('nonzero_position_change_count')}",
                        f"- Unique reasons: {trace.get('unique_reason_count')}",
                    ]
                )
                orb_filter_attribution = trace.get("orb_filter_attribution")
                if isinstance(orb_filter_attribution, dict):
                    lines.extend(_build_phase_orb_filter_attribution_lines(orb_filter_attribution))

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
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：result（EntryEdgeResult）由呼叫端傳入，需符合函式 contract；data_validation（BarValidationResult | None）由呼叫端傳入，需符合函式 contract；strategy_spec（dict[str, str] | None）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
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
            "- Phase 1 constraints: long-only; ignore short signals; optimization is allowed, but live execution, broker connections, credential reads, and real order submission remain disabled.",
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


def _entry_edge_comparison_markdown(
    comparison: EntryEdgeComparisonResult,
    data_validation: BarValidationResult | None,
    strategy_spec: dict[str, str] | None,
) -> str:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：comparison（EntryEdgeComparisonResult）由呼叫端傳入，需符合函式 contract；data_validation（BarValidationResult | None）由呼叫端傳入，需符合函式 contract；strategy_spec（dict[str, str] | None）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    if not comparison.results:
        raise ValueError("entry-edge comparison must include at least one result")
    config = comparison.results[0].config
    compared_holds = ", ".join(
        str(result.config.hold_bars_per_day) for result in comparison.results
    )
    lines = [
        f"# Entry Edge Hold Comparison - {comparison.strategy_name}",
        "",
        "## Comparison",
        "",
        "| Hold bars | Decision | PF status | PF value | Trades | Win rate | Avg net PnL | Max drawdown | Ignored shorts | Unclosed | Overlap | Failure reason |",
        "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for result in comparison.results:
        failure_reason = result.failure_reason or "-"
        lines.append(
            "| "
            f"{result.config.hold_bars_per_day} | "
            f"{result.decision.upper()} | "
            f"{result.profit_factor_status} | "
            f"{_format_profit_factor(result)} | "
            f"{result.trade_count} | "
            f"{result.win_rate:.2%} | "
            f"{result.average_net_pnl:.2f} | "
            f"{result.max_drawdown:.2%} | "
            f"{result.ignored_short_count} | "
            f"{result.unclosed_signal_count} | "
            f"{result.overlapping_signal_count} | "
            f"{failure_reason} |"
        )

    lines.extend(
        [
            "",
            "## Backtest Settings",
            "",
            f"- Initial equity: {config.initial_equity:.2f}",
            f"- Commission (bps): {config.commission_bps:.2f}",
            f"- Slippage (bps): {config.slippage_bps:.2f}",
            f"- Compared hold bars: {compared_holds}",
            f"- Pass threshold PF: >{config.pass_profit_factor:.2f}",
            "- Execution: signal confirmed at bar close; enter at next bar open; exit at exit bar close after fixed hold.",
            "- Phase 1 constraints: long-only; ignore short signals; optimization is allowed, but live execution, broker connections, credential reads, and real order submission remain disabled.",
            "- Interpretation: comparison is for audit and research first; optimization decisions may build on this report, but must be recorded and re-verified separately.",
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

    lines.append("")
    return "\n".join(lines)


def _format_profit_factor(result: EntryEdgeResult) -> str:
    """
    用途與流程：將內部資料格式化為 artifact 或 CLI 需要的 deterministic 文字表示。
    參數：result（EntryEdgeResult）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    if result.profit_factor_status == "infinite":
        return "Infinity"
    if result.profit_factor is None:
        return "undefined"
    return f"{result.profit_factor:.3f}"


def _safe_stem(value: str) -> str:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：value（str）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    allowed = []
    for char in value.lower():
        if char.isalnum() or char in {"-", "_"}:
            allowed.append(char)
        elif char.isspace():
            allowed.append("-")
    stem = "".join(allowed).strip("-_")
    return stem or "entry-edge-report"
