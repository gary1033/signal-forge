from __future__ import annotations

import hashlib
import json
import tempfile
import unittest

from signal_forge import (
    Bar,
    EntryEdgeConfig,
    EntryEdgeEvaluator,
    PhaseConfig,
    PhaseRunner,
    Signal,
    Strategy,
    run_entry_edge_hold_comparison,
    validate_bars,
)
from signal_forge.reporting import (
    validate_trace_summary,
    validate_phase_summary,
    validate_signal_digest_csv,
    validate_signal_digests,
    write_entry_edge_comparison_outputs,
    write_entry_edge_outputs,
    write_phase_outputs,
)
from signal_forge.reporting._orb_attribution import build_orb_filter_attribution
from signal_forge.phase import SignalDigest


class OneTradeStrategy(Strategy):
    name = "one_trade"

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        """
        用途與流程：在測試替身策略中產生固定 Signal 序列，讓測試可聚焦於被測流程而非策略細節。
        參數：self 表示目前物件實例；bars（list[Bar]）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 list[Signal]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        return [Signal(index, bar.timestamp, 1.0 if index == 0 else 0.0, "entry") for index, bar in enumerate(bars)]


class TinyPositionStrategy(Strategy):
    name = "tiny_position"

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        # Use a position that is below the reporting epsilon threshold so that
        # trace_summary + CSV flags remain deterministic and consistent.
        """
        用途與流程：在測試替身策略中產生固定 Signal 序列，讓測試可聚焦於被測流程而非策略細節。
        參數：self 表示目前物件實例；bars（list[Bar]）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 list[Signal]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        tiny_position = 1e-13
        return [Signal(index, bar.timestamp, tiny_position, "tiny") for index, bar in enumerate(bars)]


class OrbAttributionStrategy(Strategy):
    name = "orb_attribution"

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        """
        用途與流程：產生帶有 ORB blocked、accepted、hold 與 session-reset reason 的固定訊號序列，讓 reporting 測試可鎖住 attribution artifact contract。
        參數：self 表示目前物件實例；bars（list[Bar]）由呼叫端傳入，需與測試預期的 5 根 bar 對齊。
        回傳與錯誤：回傳 list[Signal]；若 bars 長度改變，仍依 enumerate 產生對應索引，不主動丟錯。
        """
        reasons = [
            "opening_range_building",
            "breakout_vwap_slope_blocked",
            "orb_volume_vwap_breakout",
            "hold_intraday_breakout",
            "session_reset",
        ]
        target_positions = [0.0, 0.0, 1.0, 1.0, 0.0]
        return [
            Signal(index, bar.timestamp, target_positions[index], reasons[index])
            for index, bar in enumerate(bars)
        ]


class ReportingTests(unittest.TestCase):
    def test_signal_digest_csv_validator_matches_trace_summary(self) -> None:
        """
        用途與流程：驗證 signal digest csv validator matches trace summary 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = [
            Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
            Bar("2026-01-02", 10, 11.5, 9.5, 11, 100),
        ]
        result = PhaseRunner().run(PhaseConfig(mode="backtest"), OneTradeStrategy(), bars)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_phase_outputs(result, temp_dir, run_name="phase-csv-validator")
            csv_text = paths.signal_digest_csv.read_text(encoding="utf-8")  # type: ignore[union-attr]
            trace_summary = json.loads(paths.trace_summary_json.read_text(encoding="utf-8"))  # type: ignore[union-attr]
            expected_hash = trace_summary["trace_summary"]["signal_digest_sha256"]

        validate_trace_summary(trace_summary)
        validate_signal_digest_csv(trace_summary, csv_text)

        trace_summary["trace_summary"]["signal_digest_sha256"] = "0" * 64  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "sha256 must match"):
            validate_signal_digest_csv(trace_summary, csv_text)
        trace_summary["trace_summary"]["signal_digest_sha256"] = expected_hash  # type: ignore[index]

        lines = csv_text.splitlines()
        header = lines[0].split(",")
        target_index = header.index("target_position")
        change_index = header.index("position_change")
        row = lines[1].split(",")
        row[target_index] = "2.000000"
        row[change_index] = "2.000000"
        lines[1] = ",".join(row)
        bad_csv = "\n".join(lines) + "\n"
        trace_summary["trace_summary"]["signal_digest_sha256"] = hashlib.sha256(  # type: ignore[index]
            bad_csv.encode("utf-8")
        ).hexdigest()
        with self.assertRaisesRegex(ValueError, "first_target_position must match"):
            validate_signal_digest_csv(trace_summary, bad_csv)

    def test_signal_digest_csv_validator_rejects_short_entry_count_mismatch(self) -> None:
        """
        用途與流程：驗證 signal digest csv validator rejects short entry count mismatch 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = [
            Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
            Bar("2026-01-02", 10, 11.5, 9.5, 11, 100),
        ]
        result = PhaseRunner().run(PhaseConfig(mode="backtest"), OneTradeStrategy(), bars)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_phase_outputs(result, temp_dir, run_name="phase-csv-short-entry-count")
            csv_text = paths.signal_digest_csv.read_text(encoding="utf-8")  # type: ignore[union-attr]
            trace_summary = json.loads(paths.trace_summary_json.read_text(encoding="utf-8"))  # type: ignore[union-attr]

        validate_trace_summary(trace_summary)
        validate_signal_digest_csv(trace_summary, csv_text)

        trace_summary["trace_summary"]["short_entry_count"] = 99  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "short_entry_count must match trace summary"):
            validate_signal_digest_csv(trace_summary, csv_text)

    def test_signal_digest_csv_validator_rejects_min_target_position_mismatch(self) -> None:
        """
        用途與流程：驗證 signal digest csv validator rejects min target position mismatch 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = [
            Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
            Bar("2026-01-02", 10, 11.5, 9.5, 11, 100),
        ]
        result = PhaseRunner().run(PhaseConfig(mode="backtest"), OneTradeStrategy(), bars)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_phase_outputs(result, temp_dir, run_name="phase-csv-min-target-position")
            csv_text = paths.signal_digest_csv.read_text(encoding="utf-8")  # type: ignore[union-attr]
            trace_summary = json.loads(paths.trace_summary_json.read_text(encoding="utf-8"))  # type: ignore[union-attr]

        validate_trace_summary(trace_summary)
        validate_signal_digest_csv(trace_summary, csv_text)

        trace_summary["trace_summary"]["min_target_position"] = -123.0  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "min_target_position must match trace summary"):
            validate_signal_digest_csv(trace_summary, csv_text)

    def test_signal_digest_csv_validator_rejects_flatten_bucket_mismatch(self) -> None:
        """
        用途與流程：驗證 signal digest csv validator rejects flatten bucket mismatch 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = [
            Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
            Bar("2026-01-02", 10, 11.5, 9.5, 11, 100),
        ]
        result = PhaseRunner().run(PhaseConfig(mode="backtest"), OneTradeStrategy(), bars)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_phase_outputs(result, temp_dir, run_name="phase-csv-flatten-bucket")
            csv_text = paths.signal_digest_csv.read_text(encoding="utf-8")  # type: ignore[union-attr]
            trace_summary = json.loads(paths.trace_summary_json.read_text(encoding="utf-8"))  # type: ignore[union-attr]

        validate_trace_summary(trace_summary)
        validate_signal_digest_csv(trace_summary, csv_text)

        trace_summary["trace_summary"]["flatten_to_zero_count"] = 99  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "flatten_to_zero_count must match trace summary"):
            validate_signal_digest_csv(trace_summary, csv_text)

    def test_signal_digest_csv_validator_rejects_reason_mismatch(self) -> None:
        """
        用途與流程：驗證 signal digest csv validator rejects reason mismatch 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = [
            Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
            Bar("2026-01-02", 10, 11.5, 9.5, 11, 100),
        ]
        result = PhaseRunner().run(PhaseConfig(mode="backtest"), OneTradeStrategy(), bars)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_phase_outputs(result, temp_dir, run_name="phase-csv-reason-mismatch")
            csv_text = paths.signal_digest_csv.read_text(encoding="utf-8")  # type: ignore[union-attr]
            trace_summary = json.loads(paths.trace_summary_json.read_text(encoding="utf-8"))  # type: ignore[union-attr]

        validate_trace_summary(trace_summary)
        validate_signal_digest_csv(trace_summary, csv_text)

        lines = csv_text.splitlines()
        header = lines[0].split(",")
        reason_index = header.index("reason")
        row = lines[1].split(",")
        row[reason_index] = "other-reason"
        lines[1] = ",".join(row)
        bad_csv = "\n".join(lines) + "\n"
        trace_summary["trace_summary"]["signal_digest_sha256"] = hashlib.sha256(  # type: ignore[index]
            bad_csv.encode("utf-8")
        ).hexdigest()
        with self.assertRaisesRegex(ValueError, "reasons must match trace summary"):
            validate_signal_digest_csv(trace_summary, bad_csv)

    def test_signal_digest_csv_validator_handles_tiny_positions_deterministically(self) -> None:
        """
        用途與流程：驗證 signal digest csv validator handles tiny positions deterministically 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = [
            Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
            Bar("2026-01-02", 10, 11.5, 9.5, 11, 100),
            Bar("2026-01-03", 11, 12.0, 10.5, 11.5, 100),
        ]
        result = PhaseRunner().run(PhaseConfig(mode="backtest"), TinyPositionStrategy(), bars)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_phase_outputs(result, temp_dir, run_name="phase-csv-tiny")
            csv_text = paths.signal_digest_csv.read_text(encoding="utf-8")  # type: ignore[union-attr]
            trace_summary = json.loads(paths.trace_summary_json.read_text(encoding="utf-8"))  # type: ignore[union-attr]

        validate_trace_summary(trace_summary)
        validate_signal_digest_csv(trace_summary, csv_text)

        trace = trace_summary["trace_summary"]
        self.assertEqual(int(trace["nonzero_target_position_count"]), 0)
        self.assertEqual(int(trace["hold_count"]), 0)
        self.assertEqual(int(trace["hold_long_count"]), 0)
        self.assertEqual(int(trace["hold_short_count"]), 0)

        lines = csv_text.splitlines()
        header = lines[0].split(",")
        hold_index = header.index("is_hold")
        for row_text in lines[1:]:
            row = row_text.split(",")
            self.assertEqual(row[hold_index], "False")

    def test_signal_digest_csv_validator_rejects_non_iso8601_timestamp(self) -> None:
        """
        用途與流程：驗證 signal digest csv validator rejects non iso8601 timestamp 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = [
            Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
            Bar("2026-01-02", 10, 11.5, 9.5, 11, 100),
        ]
        result = PhaseRunner().run(PhaseConfig(mode="backtest"), OneTradeStrategy(), bars)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_phase_outputs(result, temp_dir, run_name="phase-csv-timestamp")
            csv_text = paths.signal_digest_csv.read_text(encoding="utf-8")  # type: ignore[union-attr]
            trace_summary = json.loads(paths.trace_summary_json.read_text(encoding="utf-8"))  # type: ignore[union-attr]

        validate_trace_summary(trace_summary)
        validate_signal_digest_csv(trace_summary, csv_text)

        lines = csv_text.splitlines()
        header = lines[0].split(",")
        timestamp_index = header.index("timestamp")
        row = lines[1].split(",")
        row[timestamp_index] = "01-02-2026"
        lines[1] = ",".join(row)
        bad_csv = "\n".join(lines) + "\n"
        trace_summary["trace_summary"]["signal_digest_sha256"] = hashlib.sha256(  # type: ignore[index]
            bad_csv.encode("utf-8")
        ).hexdigest()
        with self.assertRaisesRegex(ValueError, "timestamp must be ISO-8601"):
            validate_signal_digest_csv(trace_summary, bad_csv)

    def test_signal_digest_csv_validator_rejects_non_fixed_decimal_numeric_fields(self) -> None:
        """
        用途與流程：驗證 signal digest csv validator rejects non fixed decimal numeric fields 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = [
            Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
            Bar("2026-01-02", 10, 11.5, 9.5, 11, 100),
        ]
        result = PhaseRunner().run(PhaseConfig(mode="backtest"), OneTradeStrategy(), bars)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_phase_outputs(result, temp_dir, run_name="phase-csv-decimals")
            csv_text = paths.signal_digest_csv.read_text(encoding="utf-8")  # type: ignore[union-attr]
            trace_summary = json.loads(paths.trace_summary_json.read_text(encoding="utf-8"))  # type: ignore[union-attr]

        validate_trace_summary(trace_summary)
        validate_signal_digest_csv(trace_summary, csv_text)

        lines = csv_text.splitlines()
        header = lines[0].split(",")
        score_index = header.index("score")
        row = lines[1].split(",")
        row[score_index] = "1.0"
        lines[1] = ",".join(row)
        bad_csv = "\n".join(lines) + "\n"
        trace_summary["trace_summary"]["signal_digest_sha256"] = hashlib.sha256(  # type: ignore[index]
            bad_csv.encode("utf-8")
        ).hexdigest()
        with self.assertRaisesRegex(ValueError, "fixed 6-decimal formatting"):
            validate_signal_digest_csv(trace_summary, bad_csv)

    def test_signal_digest_csv_validator_rejects_semantic_flag_mismatch(self) -> None:
        """
        用途與流程：驗證 signal digest csv validator rejects semantic flag mismatch 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = [
            Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
            Bar("2026-01-02", 10, 11.5, 9.5, 11, 100),
        ]
        result = PhaseRunner().run(PhaseConfig(mode="backtest"), OneTradeStrategy(), bars)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_phase_outputs(result, temp_dir, run_name="phase-csv-flags")
            csv_text = paths.signal_digest_csv.read_text(encoding="utf-8")  # type: ignore[union-attr]
            trace_summary = json.loads(paths.trace_summary_json.read_text(encoding="utf-8"))  # type: ignore[union-attr]

        validate_trace_summary(trace_summary)
        validate_signal_digest_csv(trace_summary, csv_text)

        lines = csv_text.splitlines()
        header = lines[0].split(",")
        long_entry_index = header.index("is_long_entry")
        row1 = lines[1].split(",")
        row2 = lines[2].split(",")

        # Swap the boolean values to keep counts identical but violate per-row semantics.
        row1_val = row1[long_entry_index]
        row1[long_entry_index] = row2[long_entry_index]
        row2[long_entry_index] = row1_val
        lines[1] = ",".join(row1)
        lines[2] = ",".join(row2)
        bad_csv = "\n".join(lines) + "\n"

        trace_summary["trace_summary"]["signal_digest_sha256"] = hashlib.sha256(  # type: ignore[index]
            bad_csv.encode("utf-8")
        ).hexdigest()
        with self.assertRaisesRegex(ValueError, "is_long_entry mismatch"):
            validate_signal_digest_csv(trace_summary, bad_csv)

    def test_signal_digest_csv_validator_rejects_hold_side_mismatch(self) -> None:
        """
        用途與流程：驗證 signal digest csv validator rejects hold side mismatch 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = [
            Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
            Bar("2026-01-02", 10, 11.5, 9.5, 11, 100),
            Bar("2026-01-03", 11, 12.0, 10.5, 11.5, 100),
        ]

        class HoldLongStrategy(Strategy):
            name = "hold_long"

            def generate_signals(self, bars: list[Bar]) -> list[Signal]:
                """
                用途與流程：在測試替身策略中產生固定 Signal 序列，讓測試可聚焦於被測流程而非策略細節。
                參數：self 表示目前物件實例；bars（list[Bar]）由呼叫端傳入，需符合函式 contract
                回傳與錯誤：回傳 list[Signal]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
                """
                return [
                    Signal(index, bar.timestamp, 1.0 if index == 0 else 1.0, "hold")
                    for index, bar in enumerate(bars)
                ]

        result = PhaseRunner().run(PhaseConfig(mode="backtest"), HoldLongStrategy(), bars)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_phase_outputs(result, temp_dir, run_name="phase-csv-hold-side")
            csv_text = paths.signal_digest_csv.read_text(encoding="utf-8")  # type: ignore[union-attr]
            trace_summary = json.loads(paths.trace_summary_json.read_text(encoding="utf-8"))  # type: ignore[union-attr]

        validate_trace_summary(trace_summary)
        validate_signal_digest_csv(trace_summary, csv_text)

        lines = csv_text.splitlines()
        header = lines[0].split(",")
        hold_side_index = header.index("hold_side")
        row = lines[2].split(",")
        row[hold_side_index] = "short"
        lines[2] = ",".join(row)
        bad_csv = "\n".join(lines) + "\n"

        trace_summary["trace_summary"]["signal_digest_sha256"] = hashlib.sha256(  # type: ignore[index]
            bad_csv.encode("utf-8")
        ).hexdigest()
        with self.assertRaisesRegex(ValueError, "hold_side mismatch"):
            validate_signal_digest_csv(trace_summary, bad_csv)

    def test_trace_summary_includes_orb_filter_attribution_when_reasons_match_orb_contract(self) -> None:
        """
        用途與流程：驗證 ORB trace summary 會輸出 deterministic attribution 區塊，讓後續比較各 filter 阻擋分布時有穩定 artifact 可用。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = [
            Bar("2026-01-01T09:30:00", 10, 10.5, 9.5, 10, 100),
            Bar("2026-01-01T09:31:00", 10, 10.7, 9.8, 10.1, 110),
            Bar("2026-01-01T09:32:00", 10.1, 10.9, 10.0, 10.8, 130),
            Bar("2026-01-01T09:33:00", 10.8, 11.0, 10.7, 10.9, 120),
            Bar("2026-01-02T09:30:00", 10.9, 11.1, 10.8, 10.85, 90),
        ]
        result = PhaseRunner().run(PhaseConfig(mode="backtest"), OrbAttributionStrategy(), bars)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_phase_outputs(result, temp_dir, run_name="phase-orb-attribution")
            trace_summary = json.loads(paths.trace_summary_json.read_text(encoding="utf-8"))  # type: ignore[union-attr]
            markdown = paths.markdown.read_text(encoding="utf-8")

        validate_trace_summary(trace_summary)

        orb_filter_attribution = trace_summary["trace_summary"]["orb_filter_attribution"]
        self.assertEqual(
            orb_filter_attribution,
            {
                "accepted_entry_count": 1,
                "accepted_reason_counts": [{"count": 1, "reason": "orb_volume_vwap_breakout"}],
                "blocked_reason_counts": [{"count": 1, "reason": "breakout_vwap_slope_blocked"}],
                "blocked_signal_count": 1,
                "group_counts": {
                    "accepted": 1,
                    "hold": 1,
                    "other": 0,
                    "range": 0,
                    "retest": 0,
                    "session": 2,
                    "structure": 0,
                    "trend": 1,
                    "volume": 0,
                },
                "hold_count": 1,
                "hold_reason_counts": [{"count": 1, "reason": "hold_intraday_breakout"}],
            },
        )
        self.assertIn("## ORB Filter Attribution", markdown)
        self.assertIn("- Accepted breakouts: 1", markdown)
        self.assertIn("- Blocked reasons: breakout_vwap_slope_blocked(1)", markdown)

    def test_trace_summary_validator_rejects_orb_filter_attribution_group_sum_mismatch(self) -> None:
        """
        用途與流程：驗證 ORB attribution 的 group_counts 若無法和 bar_count 對齊，validator 會明確拒絕，避免 reporting artifact drift。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = [
            Bar("2026-01-01T09:30:00", 10, 10.5, 9.5, 10, 100),
            Bar("2026-01-01T09:31:00", 10, 10.7, 9.8, 10.1, 110),
            Bar("2026-01-01T09:32:00", 10.1, 10.9, 10.0, 10.8, 130),
            Bar("2026-01-01T09:33:00", 10.8, 11.0, 10.7, 10.9, 120),
            Bar("2026-01-02T09:30:00", 10.9, 11.1, 10.8, 10.85, 90),
        ]
        result = PhaseRunner().run(PhaseConfig(mode="backtest"), OrbAttributionStrategy(), bars)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_phase_outputs(result, temp_dir, run_name="phase-orb-attribution-invalid")
            trace_summary = json.loads(paths.trace_summary_json.read_text(encoding="utf-8"))  # type: ignore[union-attr]

        trace_summary["trace_summary"]["orb_filter_attribution"]["group_counts"]["trend"] = 2  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "group_counts must be non-negative ints summing to bar_count"):
            validate_trace_summary(trace_summary)

    def test_build_orb_filter_attribution_helper_keeps_reporting_contract(self) -> None:
        """
        用途與流程：直接驗證 ORB attribution helper 在模組抽離後仍維持既有 deterministic contract，避免 generic reporting 與 ORB taxonomy 重新耦合時沒有最小單元測試守住。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若 helper 輸出結構、排序或統計關係漂移，會由 assertion 失敗回報。
        """
        digests = [
            SignalDigest(
                index=0,
                timestamp="2026-01-01T09:30:00",
                target_position=0.0,
                position_change=0.0,
                reason="opening_range_building",
                score=0.0,
                is_long_entry=False,
                is_flatten=False,
            ),
            SignalDigest(
                index=1,
                timestamp="2026-01-01T09:31:00",
                target_position=0.0,
                position_change=0.0,
                reason="breakout_vwap_slope_blocked",
                score=0.0,
                is_long_entry=False,
                is_flatten=False,
            ),
            SignalDigest(
                index=2,
                timestamp="2026-01-01T09:32:00",
                target_position=1.0,
                position_change=1.0,
                reason="orb_volume_vwap_breakout",
                score=1.0,
                is_long_entry=True,
                is_flatten=False,
            ),
            SignalDigest(
                index=3,
                timestamp="2026-01-01T09:33:00",
                target_position=1.0,
                position_change=0.0,
                reason="hold_intraday_breakout",
                score=0.0,
                is_long_entry=False,
                is_flatten=False,
            ),
            SignalDigest(
                index=4,
                timestamp="2026-01-02T09:30:00",
                target_position=0.0,
                position_change=-1.0,
                reason="session_reset",
                score=0.0,
                is_long_entry=False,
                is_flatten=True,
            ),
        ]

        self.assertEqual(
            build_orb_filter_attribution(digests),
            {
                "accepted_entry_count": 1,
                "accepted_reason_counts": [{"count": 1, "reason": "orb_volume_vwap_breakout"}],
                "blocked_reason_counts": [{"count": 1, "reason": "breakout_vwap_slope_blocked"}],
                "blocked_signal_count": 1,
                "group_counts": {
                    "accepted": 1,
                    "hold": 1,
                    "other": 0,
                    "range": 0,
                    "retest": 0,
                    "session": 2,
                    "structure": 0,
                    "trend": 1,
                    "volume": 0,
                },
                "hold_count": 1,
                "hold_reason_counts": [{"count": 1, "reason": "hold_intraday_breakout"}],
            },
        )

    def test_signal_digest_csv_validator_rejects_position_bucket_mismatch(self) -> None:
        """
        用途與流程：驗證 signal digest csv validator rejects position bucket mismatch 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = [
            Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
            Bar("2026-01-02", 10, 11.5, 9.5, 11, 100),
        ]
        result = PhaseRunner().run(PhaseConfig(mode="backtest"), OneTradeStrategy(), bars)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_phase_outputs(result, temp_dir, run_name="phase-csv-position-bucket")
            csv_text = paths.signal_digest_csv.read_text(encoding="utf-8")  # type: ignore[union-attr]
            trace_summary = json.loads(paths.trace_summary_json.read_text(encoding="utf-8"))  # type: ignore[union-attr]

        validate_trace_summary(trace_summary)
        validate_signal_digest_csv(trace_summary, csv_text)

        lines = csv_text.splitlines()
        header = lines[0].split(",")
        bucket_index = header.index("position_bucket")
        row = lines[1].split(",")
        row[bucket_index] = "flat"
        lines[1] = ",".join(row)
        bad_csv = "\n".join(lines) + "\n"

        trace_summary["trace_summary"]["signal_digest_sha256"] = hashlib.sha256(  # type: ignore[index]
            bad_csv.encode("utf-8")
        ).hexdigest()
        with self.assertRaisesRegex(ValueError, "position_bucket mismatch"):
            validate_signal_digest_csv(trace_summary, bad_csv)

    def test_signal_digest_validator_rejects_non_monotonic_index(self) -> None:
        """
        用途與流程：驗證 signal digest validator rejects non monotonic index 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        digests = [
            SignalDigest(
                index=1,
                timestamp="2026-01-02",
                target_position=0.0,
                position_change=0.0,
                reason="hold",
                score=0.0,
                is_long_entry=False,
                is_flatten=False,
            ),
            SignalDigest(
                index=0,
                timestamp="2026-01-01",
                target_position=1.0,
                position_change=1.0,
                reason="entry",
                score=1.0,
                is_long_entry=True,
                is_flatten=False,
            ),
        ]
        with self.assertRaisesRegex(ValueError, "sorted by increasing index"):
            validate_signal_digests(digests)

    def test_signal_digest_validator_rejects_decreasing_timestamp(self) -> None:
        """
        用途與流程：驗證 signal digest validator rejects decreasing timestamp 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        digests = [
            SignalDigest(
                index=0,
                timestamp="2026-01-02",
                target_position=1.0,
                position_change=1.0,
                reason="entry",
                score=1.0,
                is_long_entry=True,
                is_flatten=False,
            ),
            SignalDigest(
                index=1,
                timestamp="2026-01-01",
                target_position=0.0,
                position_change=-1.0,
                reason="flatten",
                score=0.0,
                is_long_entry=False,
                is_flatten=True,
            ),
        ]
        with self.assertRaisesRegex(ValueError, "sorted by non-decreasing timestamp"):
            validate_signal_digests(digests)

    def test_signal_digest_validator_rejects_non_iso8601_timestamp(self) -> None:
        """
        用途與流程：驗證 signal digest validator rejects non iso8601 timestamp 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        digests = [
            SignalDigest(
                index=0,
                timestamp="2026/01/01",
                target_position=1.0,
                position_change=1.0,
                reason="entry",
                score=1.0,
                is_long_entry=True,
                is_flatten=False,
            ),
        ]
        with self.assertRaisesRegex(ValueError, "timestamp must be ISO-8601"):
            validate_signal_digests(digests)

    def test_signal_digest_validator_rejects_empty_reason(self) -> None:
        """
        用途與流程：驗證 signal digest validator rejects empty reason 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        digests = [
            SignalDigest(
                index=0,
                timestamp="2026-01-01",
                target_position=1.0,
                position_change=1.0,
                reason="",
                score=1.0,
                is_long_entry=True,
                is_flatten=False,
            ),
        ]
        with self.assertRaisesRegex(ValueError, "reason must be non-empty"):
            validate_signal_digests(digests)

    def test_signal_digest_validator_rejects_non_ascii_reason(self) -> None:
        """
        用途與流程：驗證 signal digest validator rejects non ascii reason 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        digests = [
            SignalDigest(
                index=0,
                timestamp="2026-01-01",
                target_position=1.0,
                position_change=1.0,
                reason="進場",
                score=1.0,
                is_long_entry=True,
                is_flatten=False,
            ),
        ]
        with self.assertRaisesRegex(ValueError, "reason must be ASCII-only"):
            validate_signal_digests(digests)

    def test_signal_digest_validator_rejects_mismatched_position_delta(self) -> None:
        """
        用途與流程：驗證 signal digest validator rejects mismatched position delta 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        digests = [
            SignalDigest(
                index=0,
                timestamp="2026-01-01",
                target_position=1.0,
                position_change=1.0,
                reason="entry",
                score=1.0,
                is_long_entry=True,
                is_flatten=False,
            ),
            SignalDigest(
                index=1,
                timestamp="2026-01-02",
                target_position=0.0,
                position_change=0.0,
                reason="hold",
                score=0.0,
                is_long_entry=False,
                is_flatten=False,
            ),
        ]
        with self.assertRaisesRegex(ValueError, "position_change must match"):
            validate_signal_digests(digests)

    def test_trace_summary_validator_rejects_reason_count_total_mismatch(self) -> None:
        """
        用途與流程：驗證 trace summary validator rejects reason count total mismatch 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = [
            Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
            Bar("2026-01-02", 10, 11.5, 9.5, 11, 100),
        ]
        result = PhaseRunner().run(PhaseConfig(mode="backtest"), OneTradeStrategy(), bars)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_phase_outputs(result, temp_dir, run_name="phase-backtest-trace-summary-validate")
            self.assertIsNotNone(paths.trace_summary_json)
            trace_summary = json.loads((paths.trace_summary_json or paths.summary_json).read_text(encoding="utf-8"))

        (trace_summary["trace_summary"]["reason_counts"] or [])[0]["count"] = 1
        with self.assertRaisesRegex(ValueError, "total must equal bar_count"):
            validate_trace_summary(trace_summary)

    def test_writes_markdown_json_and_trade_log(self) -> None:
        """
        用途與流程：驗證 writes markdown json and trade log 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = [
            Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
            Bar("2026-01-02", 10, 11.5, 9.5, 11, 100),
        ]
        result = EntryEdgeEvaluator(
            EntryEdgeConfig(commission_bps=0, slippage_bps=0)
        ).run(OneTradeStrategy(), bars)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_entry_edge_outputs(
                result,
                temp_dir,
                data_validation=validate_bars(bars),
                strategy_spec={"entry_side": "long_only"},
            )
            self.assertTrue(paths.markdown.exists())
            self.assertTrue(paths.summary_json.exists())
            self.assertTrue(paths.trade_log_csv.exists())
            summary = json.loads(paths.summary_json.read_text(encoding="utf-8"))
            self.assertEqual(summary["decision"], result.decision)
            self.assertIn("signal_timestamp", paths.trade_log_csv.read_text(encoding="utf-8"))
            self.assertIn(
                "Strategy Spec (Distilled)",
                paths.markdown.read_text(encoding="utf-8"),
            )

    def test_entry_edge_outputs_have_stable_contract(self) -> None:
        """
        用途與流程：驗證 entry edge outputs have stable contract 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = [
            Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
            Bar("2026-01-02", 10, 11.5, 9.5, 11, 100),
        ]
        result = EntryEdgeEvaluator(
            EntryEdgeConfig(commission_bps=0, slippage_bps=0)
        ).run(OneTradeStrategy(), bars)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_entry_edge_outputs(
                result,
                temp_dir,
                run_name="entry-edge-contract",
                data_validation=validate_bars(bars),
                strategy_spec={"entry_side": "long_only"},
            )
            summary_text = paths.summary_json.read_text(encoding="utf-8")
            summary = json.loads(summary_text)
            markdown_text = paths.markdown.read_text(encoding="utf-8")
            trade_csv_text = paths.trade_log_csv.read_text(encoding="utf-8")

        expected_summary = {
            "config": {
                "commission_bps": 0,
                "hold_bars_per_day": 1,
                "initial_equity": 10000.0,
                "pass_profit_factor": 1.2,
                "slippage_bps": 0,
            },
            "data_validation": {
                "bar_count": 2,
                "end_timestamp": "2026-01-02",
                "errors": [],
                "start_timestamp": "2026-01-01",
                "warnings": [
                    "Sample has fewer than 30 bars; profit factor may be unstable."
                ],
            },
            "decision": "pass",
            "failure_reason": None,
            "metrics": {
                "average_net_pnl": 1000.0,
                "end_equity": 11000.0,
                "gross_loss": 0.0,
                "gross_profit": 1000.0,
                "ignored_short_count": 0,
                "max_drawdown": 0.0,
                "overlapping_signal_count": 0,
                "start_equity": 10000.0,
                "trade_count": 1,
                "unclosed_signal_count": 0,
                "win_rate": 1.0,
            },
            "profit_factor": None,
            "profit_factor_status": "infinite",
            "sample_risk": "No losing trades; PF is infinite. Manually inspect sample size and representativeness.",
            "strategy_name": "one_trade",
            "strategy_spec": {"entry_side": "long_only"},
        }
        self.assertEqual(summary, expected_summary)
        self.assertEqual(
            summary_text,
            json.dumps(expected_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        self.assertEqual(
            markdown_text,
            "\n".join(
                [
                    "# Entry Edge Report - one_trade",
                    "",
                    "## Conclusion",
                    "",
                    "- Decision: PASS",
                    "- Profit Factor: Infinity",
                    "- Trades: 1",
                    "- Win rate: 100.00%",
                    "- Average net PnL: 1000.00",
                    "- Max drawdown: 0.00%",
                    "- Sample risk: No losing trades; PF is infinite. Manually inspect sample size and representativeness.",
                    "",
                    "## Backtest Settings",
                    "",
                    "- Initial equity: 10000.00",
                    "- Commission (bps): 0.00",
                    "- Slippage (bps): 0.00",
                    "- Fixed hold bars: 1",
                    "- Pass threshold PF: >1.20",
                    "- Execution: signal confirmed at bar close; enter at next bar open; exit at exit bar close after fixed hold.",
                    "- Phase 1 constraints: long-only; ignore short signals; optimization is allowed, but live execution, broker connections, credential reads, and real order submission remain disabled.",
                    "",
                    "## Data Validation",
                    "",
                    "- Bars: 2",
                    "- Start: 2026-01-01",
                    "- End: 2026-01-02",
                    "- Errors: 0",
                    "- Warnings: 1",
                    "- Warning: Sample has fewer than 30 bars; profit factor may be unstable.",
                    "",
                    "## Strategy Spec (Distilled)",
                    "",
                    "- entry_side: long_only",
                    "",
                    "## Trade Statistics",
                    "",
                    "- Gross profit: 1000.00",
                    "- Gross loss: 0.00",
                    "- Ignored short signals: 0",
                    "- Unclosed signals: 0",
                    "- Overlapping ignored signals: 0",
                    "- End equity: 11000.00",
                    "",
                ]
            ),
        )
        self.assertEqual(
            trade_csv_text,
            "\n".join(
                [
                    "signal_index,signal_timestamp,entry_index,entry_timestamp,exit_index,exit_timestamp,entry_price,exit_price,gross_pnl,cost,net_pnl,return_pct,signal_reason,signal_score",
                    "0,2026-01-01,1,2026-01-02,1,2026-01-02,10,11,1000.00,0.00,1000.00,0.100000,entry,0.000000",
                    "",
                ]
            ),
        )

    def test_entry_edge_hold_comparison_outputs_have_stable_contract(self) -> None:
        """
        用途與流程：驗證 entry edge hold comparison outputs have stable contract 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = [
            Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
            Bar("2026-01-02", 10, 12.5, 9.5, 12, 100),
            Bar("2026-01-03", 12, 15.5, 11.5, 15, 100),
        ]
        comparison = run_entry_edge_hold_comparison(
            OneTradeStrategy(),
            bars,
            EntryEdgeConfig(commission_bps=0, slippage_bps=0),
            [2, 1],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_entry_edge_comparison_outputs(
                comparison,
                temp_dir,
                run_name="entry-edge-comparison-contract",
                data_validation=validate_bars(bars),
                strategy_spec={"entry_side": "long_only"},
            )
            summary_text = paths.summary_json.read_text(encoding="utf-8")
            summary = json.loads(summary_text)
            markdown_text = paths.markdown.read_text(encoding="utf-8")

        expected_summary = {
            "config": {
                "commission_bps": 0,
                "initial_equity": 10000.0,
                "pass_profit_factor": 1.2,
                "slippage_bps": 0,
            },
            "data_validation": {
                "bar_count": 3,
                "end_timestamp": "2026-01-03",
                "errors": [],
                "start_timestamp": "2026-01-01",
                "warnings": [
                    "Sample has fewer than 30 bars; profit factor may be unstable."
                ],
            },
            "hold_bars_per_day": [2, 1],
            "rows": [
                {
                    "average_net_pnl": 5000.0,
                    "decision": "pass",
                    "end_equity": 15000.0,
                    "failure_reason": None,
                    "hold_bars_per_day": 2,
                    "ignored_short_count": 0,
                    "max_drawdown": 0.0,
                    "overlapping_signal_count": 0,
                    "profit_factor": None,
                    "profit_factor_status": "infinite",
                    "trade_count": 1,
                    "unclosed_signal_count": 0,
                    "win_rate": 1.0,
                },
                {
                    "average_net_pnl": 2000.0,
                    "decision": "pass",
                    "end_equity": 12000.0,
                    "failure_reason": None,
                    "hold_bars_per_day": 1,
                    "ignored_short_count": 0,
                    "max_drawdown": 0.0,
                    "overlapping_signal_count": 0,
                    "profit_factor": None,
                    "profit_factor_status": "infinite",
                    "trade_count": 1,
                    "unclosed_signal_count": 0,
                    "win_rate": 1.0,
                },
            ],
            "strategy_name": "one_trade",
            "strategy_spec": {"entry_side": "long_only"},
        }
        self.assertEqual(summary, expected_summary)
        self.assertEqual(
            summary_text,
            json.dumps(expected_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        self.assertEqual(
            markdown_text,
            "\n".join(
                [
                    "# Entry Edge Hold Comparison - one_trade",
                    "",
                    "## Comparison",
                    "",
                    "| Hold bars | Decision | PF status | PF value | Trades | Win rate | Avg net PnL | Max drawdown | Ignored shorts | Unclosed | Overlap | Failure reason |",
                    "|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
                    "| 2 | PASS | infinite | Infinity | 1 | 100.00% | 5000.00 | 0.00% | 0 | 0 | 0 | - |",
                    "| 1 | PASS | infinite | Infinity | 1 | 100.00% | 2000.00 | 0.00% | 0 | 0 | 0 | - |",
                    "",
                    "## Backtest Settings",
                    "",
                    "- Initial equity: 10000.00",
                    "- Commission (bps): 0.00",
                    "- Slippage (bps): 0.00",
                    "- Compared hold bars: 2, 1",
                    "- Pass threshold PF: >1.20",
                    "- Execution: signal confirmed at bar close; enter at next bar open; exit at exit bar close after fixed hold.",
                    "- Phase 1 constraints: long-only; ignore short signals; optimization is allowed, but live execution, broker connections, credential reads, and real order submission remain disabled.",
                    "- Interpretation: comparison is for audit and research first; optimization decisions may build on this report, but must be recorded and re-verified separately.",
                    "",
                    "## Data Validation",
                    "",
                    "- Bars: 3",
                    "- Start: 2026-01-01",
                    "- End: 2026-01-03",
                    "- Errors: 0",
                    "- Warnings: 1",
                    "- Warning: Sample has fewer than 30 bars; profit factor may be unstable.",
                    "",
                    "## Strategy Spec (Distilled)",
                    "",
                    "- entry_side: long_only",
                    "",
                ]
            ),
        )

    def test_writes_phase_output_with_adapter_metadata(self) -> None:
        """
        用途與流程：驗證 writes phase output with adapter metadata 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = [
            Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
            Bar("2026-01-02", 10, 11.5, 9.5, 11, 100),
        ]
        result = PhaseRunner().run(PhaseConfig(mode="live"), OneTradeStrategy(), bars)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_phase_outputs(result, temp_dir, run_name="phase-live")
            summary_text = paths.summary_json.read_text(encoding="utf-8")
            summary = json.loads(summary_text)
            markdown = paths.markdown.read_text(encoding="utf-8")
            self.assertIsNone(paths.signal_digest_csv)

        validate_phase_summary(summary)
        self.assertEqual(summary["phase"]["mode"], "live")
        self.assertEqual(summary["phase"]["adapter_name"], "live")
        self.assertEqual(summary["phase"]["dry_run"], True)
        self.assertEqual(summary_text, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        self.assertEqual(
            summary["order_intents"],
            [
                {
                    "timestamp": "2026-01-01",
                    "side": "buy",
                    "target_position": 1.0,
                    "reason": "entry",
                    "dry_run": True,
                    "submitted": False,
                    "safety_note": "LIVE_DRY_RUN_ONLY: dry_run order intent only; no broker; no api keys; submitted=False",
                }
            ],
        )
        self.assertEqual(summary["order_intents"][0]["submitted"], False)
        self.assertEqual(
            markdown,
            "\n".join(
                [
                    "# Phase Report - live",
                    "",
                    "## Adapter Metadata",
                    "",
                    "- Phase mode: live",
                    "- Adapter: live",
                    "- Dry run: True",
                    "",
                    "## Live Dry-Run Intents",
                    "",
                    "- Intent 1: 2026-01-01, buy, target=1.0, dry_run=True, submitted=False, safety=LIVE_DRY_RUN_ONLY: dry_run order intent only; no broker; no api keys; submitted=False",
                    "",
                ]
            ),
        )

    def test_writes_phase_output_backtest_has_stable_summary_contract(self) -> None:
        """
        用途與流程：驗證 writes phase output backtest has stable summary contract 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = [
            Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
            Bar("2026-01-02", 10, 11.5, 9.5, 11, 100),
        ]
        result = PhaseRunner().run(PhaseConfig(mode="backtest"), OneTradeStrategy(), bars)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_phase_outputs(result, temp_dir, run_name="phase-backtest")
            summary_text = paths.summary_json.read_text(encoding="utf-8")
            summary = json.loads(summary_text)
            markdown = paths.markdown.read_text(encoding="utf-8")
            self.assertIsNotNone(paths.signal_digest_csv)
            self.assertIsNotNone(paths.trace_summary_json)
            self.assertTrue((paths.signal_digest_csv or paths.summary_json).exists())
            if paths.signal_digest_csv:
                self.assertEqual(
                    paths.signal_digest_csv.read_text(encoding="utf-8"),
                    "\n".join(
                        [
                            "index,timestamp,previous_target_position,target_position,position_bucket,position_change,reason,score,is_long_entry,is_flatten,is_hold,hold_side",
                            "0,2026-01-01,0.000000,1.000000,long,1.000000,entry,0.000000,True,False,False,none",
                            "1,2026-01-02,1.000000,0.000000,flat,-1.000000,entry,0.000000,False,True,False,none",
                            "",
                        ]
                    ),
                )
            if paths.trace_summary_json:
                self.assertEqual(
                    paths.trace_summary_json.read_text(encoding="utf-8"),
                    "\n".join(
                        [
                            "{",
                            '  "trace_summary": {',
                            '    "bar_count": 2,',
                            '    "close_count": 1,',
                            '    "end_date": "2026-01-02",',
                            '    "entry_count": 1,',
                            '    "first_index": 0,',
                            '    "first_previous_target_position": 0.0,',
                            '    "first_reason": "entry",',
                            '    "first_target_position": 1.0,',
                            '    "first_timestamp": "2026-01-01",',
                            '    "flatten_count": 1,',
                            '    "flatten_to_long_count": 0,',
                            '    "flatten_to_short_count": 0,',
                            '    "flatten_to_zero_count": 1,',
                            '    "flip_count": 0,',
                            '    "hold_count": 0,',
                            '    "hold_long_count": 0,',
                            '    "hold_short_count": 0,',
                            '    "last_index": 1,',
                            '    "last_previous_target_position": 1.0,',
                            '    "last_reason": "entry",',
                            '    "last_target_position": 0.0,',
                            '    "last_timestamp": "2026-01-02",',
                            '    "long_entry_count": 1,',
                            '    "max_target_position": 1.0,',
                            '    "min_target_position": 0.0,',
                            '    "nonzero_position_change_count": 2,',
                            '    "nonzero_target_position_count": 1,',
                            '    "open_count": 1,',
                            '    "position_bucket_counts": {',
                            '      "flat": 1,',
                            '      "long": 1,',
                            '      "short": 0',
                            "    },",
                            '    "reason_counts": [',
                            "      {",
                            '        "count": 2,',
                            '        "reason": "entry"',
                            "      }",
                            "    ],",
                            '    "reasons": [',
                            '      "entry"',
                            "    ],",
                            '    "schema_version": 10,',
                            '    "short_entry_count": 0,',
                            '    "signal_digest_sha256": "ec219433008c9685086950c5b27d4ea50aef0c3562be0f2d0adf0826e43ef388",',
                            '    "start_date": "2026-01-01",',
                            '    "timestamps_iso8601": true,',
                            '    "unique_reason_count": 1',
                            "  }",
                            "}",
                            "",
                        ]
                    ),
                )

        validate_phase_summary(summary)
        self.assertEqual(summary["phase"]["mode"], "backtest")
        self.assertEqual(summary["phase"]["adapter_name"], "backtest")
        self.assertEqual(summary["phase"]["dry_run"], False)
        self.assertEqual(summary["entry_edge"]["strategy_name"], "one_trade")
        self.assertEqual(summary["entry_edge"]["decision"], "pass")
        self.assertEqual(summary["entry_edge"]["profit_factor_status"], "infinite")
        self.assertIsNone(summary["entry_edge"]["profit_factor"])
        self.assertEqual(summary["entry_edge"]["trade_count"], 1)
        self.assertAlmostEqual(summary["entry_edge"]["end_equity"], 10995.8, places=6)
        self.assertEqual(
            summary_text,
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        self.assertEqual(
            markdown,
            "\n".join(
                [
                    "# Phase Report - backtest",
                    "",
                    "## Adapter Metadata",
                    "",
                    "- Phase mode: backtest",
                    "- Adapter: backtest",
                    "- Dry run: False",
                    "",
                    "## Backtest Result",
                    "",
                    "- Strategy: one_trade",
                    "- Decision: pass",
                    "- Profit Factor: Infinity",
                    "- Trades: 1",
                    "- End equity: 10995.80",
                    "",
                    "## Backtest Digest Invariants",
                    "",
                    "- Signal digests: 2",
                    "- Timestamps non-empty: True",
                    "- Timestamps ISO-8601: True",
                    "- Index strictly increasing: True",
                    "- Timestamp non-decreasing: True",
                    "- Reasons non-empty: True",
                    "- Reasons trimmed: True",
                    "- Reasons ASCII single-line: True",
                    "- First timestamp: 2026-01-01",
                    "- Last timestamp: 2026-01-02",
                    "- Last target position: 0.0",
                    "- Unique reasons: 1",
                    "- Top reasons: entry(2)",
                    "- Trace summary bar_count: 2",
                    "- Trace summary unique reasons: 1",
                    "- Trace summary last target position: 0.0",
                    "",
                    "## Backtest Trace Summary",
                    "",
                    "- Bar count: 2",
                    "- Trace schema version: 10",
                    "- Entry/Flatten/Hold: 1/1/0",
                    "- Hold long/short: 0/0",
                    "- Open/Close: 1/1",
                    "- Position buckets (flat/long/short): 1/1/0",
                    "- First previous target position: 0.0",
                    "- First target position: 1.0",
                    "- Last previous target position: 1.0",
                    "- Nonzero target positions: 1",
                    "- Nonzero position changes: 2",
                    "- Unique reasons: 1",
                    "",
                    "## Live Dry-Run Intents",
                    "",
                    "- No dry-run order intents were emitted.",
                    "",
                ]
            ),
        )

    def test_writes_phase_output_live_has_stable_contract(self) -> None:
        """
        用途與流程：驗證 writes phase output live has stable contract 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = [
            Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
            Bar("2026-01-02", 10, 11.5, 9.5, 11, 100),
        ]
        result = PhaseRunner().run(PhaseConfig(mode="live"), OneTradeStrategy(), bars)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_phase_outputs(result, temp_dir, run_name="phase-live-contract")
            summary_text = paths.summary_json.read_text(encoding="utf-8")
            summary = json.loads(summary_text)
            markdown = paths.markdown.read_text(encoding="utf-8")
            self.assertIsNone(paths.signal_digest_csv)

        validate_phase_summary(summary)
        self.assertEqual(summary["phase"]["mode"], "live")
        self.assertEqual(summary["phase"]["adapter_name"], "live")
        self.assertEqual(summary["phase"]["dry_run"], True)
        self.assertIsNone(summary.get("entry_edge"))
        self.assertEqual(len(summary.get("order_intents") or []), 1)

        intent = (summary.get("order_intents") or [])[0]
        self.assertEqual(intent["side"], "buy")
        self.assertTrue(intent["dry_run"])
        self.assertFalse(intent["submitted"])
        self.assertIn("LIVE_DRY_RUN_ONLY", intent["safety_note"])

        self.assertEqual(
            summary_text,
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        self.assertEqual(
            markdown,
            "\n".join(
                [
                    "# Phase Report - live",
                    "",
                    "## Adapter Metadata",
                    "",
                    "- Phase mode: live",
                    "- Adapter: live",
                    "- Dry run: True",
                    "",
                    "## Live Dry-Run Intents",
                    "",
                    "- Intent 1: 2026-01-01, buy, target=1.0, dry_run=True, submitted=False, safety=LIVE_DRY_RUN_ONLY: dry_run order intent only; no broker; no api keys; submitted=False",
                    "",
                ]
            ),
        )

    def test_phase_summary_schema_validator_rejects_missing_phase(self) -> None:
        """
        用途與流程：驗證 phase summary schema validator rejects missing phase 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with self.assertRaisesRegex(ValueError, "missing required dict key: phase"):
            validate_phase_summary({})

    def test_phase_summary_schema_validator_rejects_live_submitted_intent(self) -> None:
        """
        用途與流程：驗證 phase summary schema validator rejects live submitted intent 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = [
            Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
            Bar("2026-01-02", 10, 11.5, 9.5, 11, 100),
        ]
        result = PhaseRunner().run(PhaseConfig(mode="live"), OneTradeStrategy(), bars)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_phase_outputs(result, temp_dir, run_name="phase-live")
            summary = json.loads(paths.summary_json.read_text(encoding="utf-8"))

        summary["order_intents"][0]["submitted"] = True
        with self.assertRaisesRegex(ValueError, "submitted must be False"):
            validate_phase_summary(summary)

    def test_phase_summary_schema_validator_rejects_backtest_missing_entry_edge(self) -> None:
        """
        用途與流程：驗證 phase summary schema validator rejects backtest missing entry edge 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = [
            Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
            Bar("2026-01-02", 10, 11.5, 9.5, 11, 100),
        ]
        result = PhaseRunner().run(PhaseConfig(mode="backtest"), OneTradeStrategy(), bars)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_phase_outputs(result, temp_dir, run_name="phase-backtest")
            summary = json.loads(paths.summary_json.read_text(encoding="utf-8"))

        del summary["entry_edge"]
        with self.assertRaisesRegex(ValueError, "backtest mode must include entry_edge"):
            validate_phase_summary(summary)


if __name__ == "__main__":
    unittest.main()
