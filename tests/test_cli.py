from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from signal_forge import MarketDataValidationError
from signal_forge.cli import (
    build_parser,
    build_strategy_from_args,
    main,
    strategy_spec_from_args,
)
from signal_forge.cli.strategy_options import (
    _validate_orb_prior_day_close_contract,
    _validate_orb_same_session_contract,
)
from signal_forge.data_fetch import FetchDataResult
from signal_forge.strategies import ConfluenceScoreStrategy


class CliTests(unittest.TestCase):
    def test_cli_uses_strategy_defaults_when_parameters_are_omitted(self) -> None:
        """
        用途與流程：驗證 CLI 未輸入策略參數時不套用全域預設，而是交由各策略自己的 default parameter 生效。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        args = build_parser().parse_args(
            [
                "phase",
                "--csv",
                "sample.csv",
                "--strategy",
                "confluence-score",
            ]
        )

        strategy = build_strategy_from_args(args)

        self.assertIsInstance(strategy, ConfluenceScoreStrategy)
        self.assertEqual(strategy.slow_window, 50)

    def test_strategy_spec_from_args_locks_orb_vwap_slope_tier_contract(self) -> None:
        """
        用途與流程：直接驗證 strategy_spec_from_args 在 ORB 的 disabled 與 enabled 兩條 VWAP slope 路徑都會穩定輸出 state、tier 與 rule，避免每次都只能靠 CLI 端到端 artifact 才發現 metadata drift。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        disabled_args = build_parser().parse_args(
            [
                "entry-edge",
                "--csv",
                "sample.csv",
                "--strategy",
                "orb-volume-vwap",
            ]
        )
        disabled_strategy = build_strategy_from_args(disabled_args)
        disabled_spec = strategy_spec_from_args(disabled_args, disabled_strategy)

        enabled_args = build_parser().parse_args(
            [
                "entry-edge",
                "--csv",
                "sample.csv",
                "--strategy",
                "orb-volume-vwap",
                "--orb-vwap-slope-confirmation",
            ]
        )
        enabled_strategy = build_strategy_from_args(enabled_args)
        enabled_spec = strategy_spec_from_args(enabled_args, enabled_strategy)

        self.assertEqual(disabled_spec["orb_vwap_slope_confirmation"], "disabled")
        self.assertEqual(disabled_spec["orb_vwap_slope_tier"], "secondary_refinement")
        self.assertEqual(
            disabled_spec["orb_vwap_slope_rule"],
            "this secondary refinement only accepts breakouts if session VWAP is rising versus the previous bar in the same session",
        )
        self.assertEqual(enabled_spec["orb_vwap_slope_confirmation"], "enabled")
        self.assertEqual(enabled_spec["orb_vwap_slope_tier"], "secondary_refinement")
        self.assertEqual(
            enabled_spec["orb_vwap_slope_rule"],
            "this secondary refinement only accepts breakouts if session VWAP is rising versus the previous bar in the same session",
        )

    def test_strategy_spec_from_args_keeps_previous_day_family_outside_orb_contract(
        self,
    ) -> None:
        """
        用途與流程：直接驗證目前 ORB 的 strategy spec 仍只描述同 session 的研究 contract，不會提前洩漏 previous-day、gap 或 overnight family 欄位，避免研究題尚未定義完成就悄悄膨脹成正式 surface。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        args = build_parser().parse_args(
            [
                "entry-edge",
                "--csv",
                "sample.csv",
                "--strategy",
                "orb-volume-vwap",
            ]
        )
        strategy = build_strategy_from_args(args)
        spec = strategy_spec_from_args(args, strategy)

        self.assertEqual(
            spec["orb_session_scope"],
            "regular-session research contract only",
        )
        self.assertEqual(
            spec["orb_extended_hours_policy"],
            "extended-hours bars are outside the current ORB research contract until session/data boundaries are defined explicitly",
        )
        for forbidden_prefix in ("orb_previous_day_", "orb_gap_", "orb_overnight_"):
            self.assertFalse(
                any(key.startswith(forbidden_prefix) for key in spec),
                f"unexpected previous-day family surface leaked into ORB contract: {forbidden_prefix}",
            )

    def test_strategy_spec_from_args_marks_known_twse_sample_market_clock_alignment(
        self,
    ) -> None:
        """
        用途與流程：直接驗證已知的 `TWSE_2330_5M.csv` 樣本會在 ORB strategy spec 中寫出 canonical market-clock 預期，以及目前 CLI 設定是 aligned 還是 mismatch，避免後續跨樣本比較必須靠外部研究筆記才能判讀是否沿用了錯誤市場時鐘。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        mismatched_args = build_parser().parse_args(
            [
                "entry-edge",
                "--csv",
                "data/processed/TWSE_2330_5M.csv",
                "--strategy",
                "orb-volume-vwap",
            ]
        )
        mismatched_strategy = build_strategy_from_args(mismatched_args)
        mismatched_spec = strategy_spec_from_args(
            mismatched_args, mismatched_strategy
        )

        aligned_args = build_parser().parse_args(
            [
                "entry-edge",
                "--csv",
                "data/processed/TWSE_2330_5M.csv",
                "--strategy",
                "orb-volume-vwap",
                "--orb-session-start-hour",
                "9",
                "--orb-session-start-minute",
                "0",
                "--orb-session-end-hour",
                "13",
                "--orb-session-end-minute",
                "30",
                "--orb-session-timezone",
                "Asia/Taipei",
            ]
        )
        aligned_strategy = build_strategy_from_args(aligned_args)
        aligned_spec = strategy_spec_from_args(aligned_args, aligned_strategy)

        self.assertEqual(
            mismatched_spec["orb_known_sample_market_clock_name"], "TWSE_2330_5M.csv"
        )
        self.assertEqual(
            mismatched_spec["orb_known_sample_market_clock_expected_timezone"],
            "Asia/Taipei",
        )
        self.assertEqual(
            mismatched_spec["orb_known_sample_market_clock_expected_session_start"],
            "09:00",
        )
        self.assertEqual(
            mismatched_spec["orb_known_sample_market_clock_expected_session_end"],
            "13:30",
        )
        self.assertEqual(
            mismatched_spec["orb_known_sample_market_clock_alignment"], "mismatch"
        )
        self.assertEqual(
            aligned_spec["orb_known_sample_market_clock_alignment"], "aligned"
        )

    def test_validate_orb_same_session_contract_rejects_previous_day_surface(self) -> None:
        """
        用途與流程：直接驗證 ORB same-session contract validator 會拒絕 previous-day family key，避免只有外層 CLI regression 發現 metadata drift，讓失敗可以更靠近 strategy spec 建構點。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        args = build_parser().parse_args(
            [
                "entry-edge",
                "--csv",
                "sample.csv",
                "--strategy",
                "orb-volume-vwap",
            ]
        )
        strategy = build_strategy_from_args(args)
        spec = strategy_spec_from_args(args, strategy)
        spec["orb_previous_day_close"] = "100.0"

        with self.assertRaisesRegex(ValueError, "previous-day family surface"):
            _validate_orb_same_session_contract(spec)

    def test_validate_orb_prior_day_close_contract_accepts_first_session_unavailable(
        self,
    ) -> None:
        """
        用途與流程：直接驗證 prior-day close 的最小正面 contract 允許第一個 session 明確標示 unavailable，讓 previous-day family 未來若要落地時，先有可重複使用的 validator 邊界而不是只停在研究文字。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        unavailable_contract = {
            "prior_day_close_regular_session": "unavailable",
            "prior_day_close_source_session": "regular_session",
            "prior_day_close_timezone": "orb_session_timezone",
            "prior_day_close_availability": "unavailable_first_session",
            "prior_day_close_fill_policy": "no_forward_fill",
        }
        available_contract = {
            "prior_day_close_regular_session": "431.25",
            "prior_day_close_source_session": "regular_session",
            "prior_day_close_timezone": "orb_session_timezone",
            "prior_day_close_availability": "available",
            "prior_day_close_fill_policy": "no_forward_fill",
        }

        _validate_orb_prior_day_close_contract(unavailable_contract)
        _validate_orb_prior_day_close_contract(available_contract)

    def test_validate_orb_prior_day_close_contract_rejects_fill_policy_drift(
        self,
    ) -> None:
        """
        用途與流程：直接驗證 prior-day close 的正面 contract 會拒絕 fill policy 或 first-session unavailable 表示法漂移，避免日後 previous-day family 還沒正式進 ORB surface 前，就把補值或模糊 unavailable 語意悄悄帶進 validator。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        bad_fill_policy = {
            "prior_day_close_regular_session": "431.25",
            "prior_day_close_source_session": "regular_session",
            "prior_day_close_timezone": "orb_session_timezone",
            "prior_day_close_availability": "available",
            "prior_day_close_fill_policy": "forward_fill",
        }
        bad_unavailable_marker = {
            "prior_day_close_regular_session": "431.25",
            "prior_day_close_source_session": "regular_session",
            "prior_day_close_timezone": "orb_session_timezone",
            "prior_day_close_availability": "unavailable_first_session",
            "prior_day_close_fill_policy": "no_forward_fill",
        }

        with self.assertRaisesRegex(ValueError, "no_forward_fill"):
            _validate_orb_prior_day_close_contract(bad_fill_policy)
        with self.assertRaisesRegex(ValueError, "unavailable"):
            _validate_orb_prior_day_close_contract(bad_unavailable_marker)

    def test_phase_command_accepts_minimal_strategy_invocation(self) -> None:
        """
        用途與流程：驗證 phase CLI 可只指定 CSV、mode 與 strategy，策略參數全部使用 default，不需要在一般呼叫時輸入長串參數。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_sample_csv(Path(temp_dir))
            output = _run_cli(
                [
                    "phase",
                    "--csv",
                    str(csv_path),
                    "--mode",
                    "backtest",
                    "--strategy",
                    "sma-crossover",
                    "--output-dir",
                    temp_dir,
                ]
            )

        self.assertIn("phase=backtest", output)
        self.assertIn("adapter=backtest", output)
        self.assertIn("phase_summary_json=", output)

    def test_phase_backtest_command_reports_entry_edge_result(self) -> None:
        """
        用途與流程：驗證 phase backtest command reports entry edge result 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_sample_csv(Path(temp_dir))
            output = _run_cli(
                [
                    "phase",
                    "--csv",
                    str(csv_path),
                    "--mode",
                    "backtest",
                    "--strategy",
                    "sma-crossover",
                    "--fast-window",
                    "1",
                    "--slow-window",
                    "2",
                    "--output-dir",
                    temp_dir,
                ]
            )

        self.assertIn("phase=backtest", output)
        self.assertIn("adapter=backtest", output)
        self.assertIn("entry_edge_trades=1", output)
        self.assertIn("phase_summary_json=", output)

    def test_phase_backtest_command_accepts_volume_filter(self) -> None:
        """
        用途與流程：驗證 phase backtest command accepts volume filter 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_sample_csv(Path(temp_dir))
            output = _run_cli(
                [
                    "phase",
                    "--csv",
                    str(csv_path),
                    "--mode",
                    "backtest",
                    "--strategy",
                    "sma-crossover",
                    "--fast-window",
                    "1",
                    "--slow-window",
                    "2",
                    "--volume-filter",
                    "--volume-window",
                    "1",
                    "--volume-multiplier",
                    "1.0",
                    "--output-dir",
                    temp_dir,
                ]
            )

        self.assertIn("phase=backtest", output)
        self.assertIn("entry_edge_trades=1", output)

    def test_phase_live_command_reports_dry_run_intent_without_submission(self) -> None:
        """
        用途與流程：驗證 phase live command reports dry run intent without submission 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_sample_csv(Path(temp_dir))
            output = _run_cli(
                [
                    "phase",
                    "--csv",
                    str(csv_path),
                    "--mode",
                    "live",
                    "--strategy",
                    "sma-crossover",
                    "--fast-window",
                    "1",
                    "--slow-window",
                    "2",
                    "--output-dir",
                    temp_dir,
                ]
            )

        self.assertIn("phase=live", output)
        self.assertIn("adapter=live", output)
        self.assertIn("dry_run=True", output)
        self.assertIn("order_intents=1", output)
        self.assertIn("submitted=False", output)
        self.assertIn("phase_markdown=", output)

    def test_entry_edge_command_writes_volume_filter_strategy_spec(self) -> None:
        """
        用途與流程：驗證 entry edge command writes volume filter strategy spec 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_sample_csv(Path(temp_dir))
            output = _run_cli(
                [
                    "entry-edge",
                    "--csv",
                    str(csv_path),
                    "--strategy",
                    "sma-crossover",
                    "--fast-window",
                    "1",
                    "--slow-window",
                    "2",
                    "--volume-filter",
                    "--volume-window",
                    "1",
                    "--volume-multiplier",
                    "1.0",
                    "--output-dir",
                    temp_dir,
                    "--run-name",
                    "volume-filter-cli",
                ]
            )
            summary = json.loads(
                (Path(temp_dir) / "volume-filter-cli.json").read_text(encoding="utf-8")
            )

        self.assertIn("strategy=volume_filter_w1_m1.00__sma_1_2_long_only", output)
        self.assertEqual(summary["strategy_spec"]["volume_filter"], "enabled")
        self.assertEqual(summary["strategy_spec"]["volume_window"], "1")
        self.assertEqual(summary["strategy_spec"]["volume_multiplier"], "1.00")
        self.assertEqual(
            summary["strategy_spec"]["volume_rule"],
            "volume >= sma(volume, volume_window) * volume_multiplier",
        )
        self.assertNotIn("hold_comparison_json=", output)

    def test_entry_edge_command_writes_hold_comparison_outputs(self) -> None:
        """
        用途與流程：驗證 entry edge command writes hold comparison outputs 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_trending_csv(Path(temp_dir), row_count=8)
            output = _run_cli(
                [
                    "entry-edge",
                    "--csv",
                    str(csv_path),
                    "--strategy",
                    "sma-crossover",
                    "--fast-window",
                    "1",
                    "--slow-window",
                    "2",
                    "--hold-bars-list",
                    "1,3,5",
                    "--output-dir",
                    temp_dir,
                    "--run-name",
                    "sma-multi-hold",
                ]
            )
            comparison = json.loads(
                (Path(temp_dir) / "sma-multi-hold_hold_comparison.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertIn("markdown=", output)
        self.assertIn("summary_json=", output)
        self.assertIn("trade_log_csv=", output)
        self.assertIn("hold_comparison_markdown=", output)
        self.assertIn("hold_comparison_json=", output)
        self.assertEqual(comparison["hold_bars_per_day"], [1, 3, 5])
        self.assertEqual(
            [row["hold_bars_per_day"] for row in comparison["rows"]],
            [1, 3, 5],
        )

    def test_entry_edge_command_rejects_invalid_hold_comparison_list(self) -> None:
        """
        用途與流程：驗證 entry edge command rejects invalid hold comparison list 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_sample_csv(Path(temp_dir))
            with self.assertRaisesRegex(ValueError, "--hold-bars-list"):
                _run_cli(
                    [
                        "entry-edge",
                        "--csv",
                        str(csv_path),
                        "--strategy",
                        "sma-crossover",
                        "--fast-window",
                        "1",
                        "--slow-window",
                        "2",
                        "--hold-bars-list",
                        "1,0",
                        "--output-dir",
                        temp_dir,
                    ]
                )

    def test_entry_edge_command_accepts_vwap_regime_filter(self) -> None:
        """
        用途與流程：驗證 entry-edge CLI 可啟用 VWAP regime filter，並把 regime 設定寫入 strategy spec。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_vwap_reversion_csv(Path(temp_dir))
            output = _run_cli(
                [
                    "entry-edge",
                    "--csv",
                    str(csv_path),
                    "--strategy",
                    "vwap-reversion",
                    "--vwap-window",
                    "3",
                    "--vwap-regime-filter",
                    "--vwap-regime-window",
                    "3",
                    "--entry-z",
                    "0.5",
                    "--exit-z",
                    "0.25",
                    "--output-dir",
                    temp_dir,
                    "--run-name",
                    "vwap-regime-cli",
                ]
            )
            summary = json.loads(
                (Path(temp_dir) / "vwap-regime-cli.json").read_text(encoding="utf-8")
            )

        self.assertIn("strategy=vwap_reversion_3_regime_sma3_long_only", output)
        self.assertEqual(summary["strategy_spec"]["vwap_regime_filter"], "enabled")
        self.assertEqual(summary["strategy_spec"]["vwap_regime_window"], "3")
        self.assertEqual(
            summary["strategy_spec"]["vwap_regime_rule"],
            "long entries require close >= sma(close, vwap_regime_window) when enabled",
        )

    def test_entry_edge_command_accepts_orb_retest_confirmation(self) -> None:
        """
        用途與流程：驗證 entry-edge CLI 可啟用 ORB retest confirmation，並把設定寫入 strategy spec。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_intraday_orb_csv(Path(temp_dir))
            output = _run_cli(
                [
                    "entry-edge",
                    "--csv",
                    str(csv_path),
                    "--strategy",
                    "orb-volume-vwap",
                    "--orb-retest-confirmation",
                    "--output-dir",
                    temp_dir,
                    "--run-name",
                    "orb-retest-cli",
                ]
            )
            summary = json.loads(
                (Path(temp_dir) / "orb-retest-cli.json").read_text(encoding="utf-8")
            )

        self.assertIn(
            "strategy=orb_volume_vwap_ss0930_or30_closeonly_vw20_vm1.50_with_vwap_with_retest_long_only",
            output,
        )
        self.assertEqual(summary["strategy_spec"]["orb_retest_confirmation"], "enabled")
        self.assertEqual(
            summary["strategy_spec"]["orb_retest_rule"],
            "long entries wait for breakout, OR-high retest, and close-confirmed reclaim when enabled",
        )
        self.assertEqual(summary["strategy_spec"]["volume_window"], "20")
        self.assertEqual(summary["strategy_spec"]["volume_multiplier"], "1.50")
        self.assertEqual(
            summary["strategy_spec"]["orb_session_scope"],
            "regular-session research contract only",
        )
        self.assertEqual(
            summary["strategy_spec"]["orb_extended_hours_policy"],
            "extended-hours bars are outside the current ORB research contract until session/data boundaries are defined explicitly",
        )

    def test_entry_edge_command_accepts_orb_session_parameters(self) -> None:
        """
        用途與流程：驗證 entry-edge CLI 可覆寫 ORB 的 session start、session end、timezone 與 opening range 長度，並把實際生效值寫入 strategy spec。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_intraday_shifted_orb_csv(Path(temp_dir))
            output = _run_cli(
                [
                    "entry-edge",
                    "--csv",
                    str(csv_path),
                    "--strategy",
                    "orb-volume-vwap",
                    "--orb-opening-range-minutes",
                    "2",
                    "--orb-session-start-hour",
                    "8",
                    "--orb-session-start-minute",
                    "0",
                    "--orb-session-end-hour",
                    "13",
                    "--orb-session-end-minute",
                    "30",
                    "--orb-session-timezone",
                    "Asia/Taipei",
                    "--output-dir",
                    temp_dir,
                    "--run-name",
                    "orb-session-cli",
                ]
            )
            summary = json.loads(
                (Path(temp_dir) / "orb-session-cli.json").read_text(encoding="utf-8")
            )

        self.assertIn(
            "strategy=orb_volume_vwap_ss0800_or2_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
            output,
        )
        self.assertEqual(summary["strategy_spec"]["orb_opening_range_minutes"], "2")
        self.assertEqual(summary["strategy_spec"]["orb_session_start_hour"], "8")
        self.assertEqual(summary["strategy_spec"]["orb_session_start_minute"], "0")
        self.assertEqual(summary["strategy_spec"]["orb_session_end_hour"], "13")
        self.assertEqual(summary["strategy_spec"]["orb_session_end_minute"], "30")
        self.assertEqual(summary["strategy_spec"]["orb_session_timezone"], "Asia/Taipei")
        self.assertEqual(
            summary["strategy_spec"]["orb_session_rule"],
            "intraday ORB only evaluates bars at or after the configured session start time",
        )
        self.assertEqual(
            summary["strategy_spec"]["orb_session_end_rule"],
            "configured session end currently documents the intended regular-session boundary for ORB research artifacts; it does not force-flat open positions by itself",
        )
        self.assertEqual(
            summary["strategy_spec"]["orb_session_timezone_rule"],
            "configured timezone documents the intended market-clock reference for ORB session metadata and research artifacts",
        )
        self.assertEqual(
            summary["strategy_spec"]["orb_session_scope"],
            "regular-session research contract only",
        )
        self.assertEqual(summary["strategy_spec"]["orb_observed_range_pct_sessions"], "1")
        self.assertEqual(summary["strategy_spec"]["orb_observed_range_pct_first"], "0.0300")
        self.assertEqual(summary["strategy_spec"]["orb_observed_range_pct_last"], "0.0300")

    def test_entry_edge_command_accepts_orb_signal_window_cutoff(self) -> None:
        """
        用途與流程：驗證 entry-edge CLI 可設定 ORB signal window cutoff，並把 cutoff 規則寫入 strategy spec，而不把它誤解成強制平倉規則。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_intraday_signal_window_orb_csv(Path(temp_dir))
            output = _run_cli(
                [
                    "entry-edge",
                    "--csv",
                    str(csv_path),
                    "--strategy",
                    "orb-volume-vwap",
                    "--orb-opening-range-minutes",
                    "2",
                    "--orb-signal-window-minutes",
                    "4",
                    "--output-dir",
                    temp_dir,
                    "--run-name",
                    "orb-signal-window-cli",
                ]
            )
            summary = json.loads(
                (Path(temp_dir) / "orb-signal-window-cli.json").read_text(encoding="utf-8")
            )

        self.assertIn(
            "strategy=orb_volume_vwap_ss0930_or2_sigw4_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
            output,
        )
        self.assertEqual(summary["strategy_spec"]["orb_signal_window_minutes"], "4")
        self.assertEqual(
            summary["strategy_spec"]["orb_signal_window_rule"],
            "when configured, new ORB breakouts are only accepted before orb_signal_window_minutes from session start; existing long positions are not force-flattened by this cutoff",
        )

    def test_entry_edge_command_accepts_orb_vwap_slope_confirmation(self) -> None:
        """
        用途與流程：驗證 entry-edge CLI 可啟用 ORB 的 VWAP slope confirmation，並把它在 strategy spec 中明確標示為 secondary refinement，而不是主線核心結構條件。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_intraday_orb_csv(Path(temp_dir))
            output = _run_cli(
                [
                    "entry-edge",
                    "--csv",
                    str(csv_path),
                    "--strategy",
                    "orb-volume-vwap",
                    "--orb-vwap-slope-confirmation",
                    "--output-dir",
                    temp_dir,
                    "--run-name",
                    "orb-vwap-slope-cli",
                ]
            )
            summary = json.loads(
                (Path(temp_dir) / "orb-vwap-slope-cli.json").read_text(encoding="utf-8")
            )

        self.assertIn(
            "strategy=orb_volume_vwap_ss0930_or30_vslope_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
            output,
        )
        self.assertEqual(summary["strategy_spec"]["orb_vwap_slope_confirmation"], "enabled")
        self.assertEqual(
            summary["strategy_spec"]["orb_vwap_slope_tier"],
            "secondary_refinement",
        )
        self.assertEqual(
            summary["strategy_spec"]["orb_vwap_slope_rule"],
            "this secondary refinement only accepts breakouts if session VWAP is rising versus the previous bar in the same session",
        )

    def test_entry_edge_command_keeps_orb_vwap_slope_tier_when_disabled(self) -> None:
        """
        用途與流程：驗證 entry-edge CLI 在未啟用 ORB 的 VWAP slope confirmation 時，仍會固定輸出 disabled 狀態與 secondary refinement tier，避免 strategy spec 只在 enabled 路徑才帶出 tier 欄位。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_intraday_orb_csv(Path(temp_dir))
            output = _run_cli(
                [
                    "entry-edge",
                    "--csv",
                    str(csv_path),
                    "--strategy",
                    "orb-volume-vwap",
                    "--output-dir",
                    temp_dir,
                    "--run-name",
                    "orb-vwap-slope-disabled-cli",
                ]
            )
            summary = json.loads(
                (Path(temp_dir) / "orb-vwap-slope-disabled-cli.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertIn(
            "strategy=orb_volume_vwap_ss0930_or30_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
            output,
        )
        self.assertEqual(
            summary["strategy_spec"]["orb_vwap_slope_confirmation"], "disabled"
        )
        self.assertEqual(
            summary["strategy_spec"]["orb_vwap_slope_tier"],
            "secondary_refinement",
        )
        self.assertEqual(
            summary["strategy_spec"]["orb_vwap_slope_rule"],
            "this secondary refinement only accepts breakouts if session VWAP is rising versus the previous bar in the same session",
        )

    def test_entry_edge_command_accepts_orb_ema_trend_confirmation(self) -> None:
        """
        用途與流程：驗證 entry-edge CLI 可啟用 ORB 的 EMA trend confirmation，並把 rolling EMA 視窗與 entry-quality 規則寫入 strategy spec。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_intraday_orb_csv(Path(temp_dir))
            output = _run_cli(
                [
                    "entry-edge",
                    "--csv",
                    str(csv_path),
                    "--strategy",
                    "orb-volume-vwap",
                    "--orb-ema-trend-confirmation",
                    "--orb-ema-window",
                    "10",
                    "--output-dir",
                    temp_dir,
                    "--run-name",
                    "orb-ema-trend-cli",
                ]
            )
            summary = json.loads(
                (Path(temp_dir) / "orb-ema-trend-cli.json").read_text(encoding="utf-8")
            )

        self.assertIn(
            "strategy=orb_volume_vwap_ss0930_or30_ema10_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
            output,
        )
        self.assertEqual(summary["strategy_spec"]["orb_ema_trend_confirmation"], "enabled")
        self.assertEqual(summary["strategy_spec"]["orb_ema_window"], "10")
        self.assertEqual(
            summary["strategy_spec"]["orb_ema_trend_rule"],
            "when enabled, breakout is only accepted if close stays above the rolling EMA and that EMA is rising versus the previous bar in the same session",
        )

    def test_entry_edge_command_accepts_orb_reject_ema_inside_range(self) -> None:
        """
        用途與流程：驗證 entry-edge CLI 可啟用 ORB 的 EMA inside-range 結構 gate，並把 EMA 與 OR 盒子相對位置的規則寫入 strategy spec。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_intraday_orb_csv(Path(temp_dir))
            output = _run_cli(
                [
                    "entry-edge",
                    "--csv",
                    str(csv_path),
                    "--strategy",
                    "orb-volume-vwap",
                    "--orb-reject-ema-inside-range",
                    "--output-dir",
                    temp_dir,
                    "--run-name",
                    "orb-ema-box-cli",
                ]
            )
            summary = json.loads(
                (Path(temp_dir) / "orb-ema-box-cli.json").read_text(encoding="utf-8")
            )

        self.assertIn(
            "strategy=orb_volume_vwap_ss0930_or30_emabox_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
            output,
        )
        self.assertEqual(
            summary["strategy_spec"]["orb_reject_ema_inside_opening_range"], "enabled"
        )
        self.assertEqual(
            summary["strategy_spec"]["orb_ema_inside_range_rule"],
            "when enabled, new ORB breakouts are rejected if the rolling EMA still falls inside the opening-range box",
        )

    def test_entry_edge_command_accepts_orb_range_size_filter(self) -> None:
        """
        用途與流程：驗證 entry-edge CLI 可啟用 ORB 開盤區間寬度百分比濾網，並把 range size 設定寫入 strategy spec。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_intraday_orb_csv(Path(temp_dir))
            output = _run_cli(
                [
                    "entry-edge",
                    "--csv",
                    str(csv_path),
                    "--strategy",
                    "orb-volume-vwap",
                    "--orb-min-range-pct",
                    "0.0100",
                    "--orb-max-range-pct",
                    "0.0500",
                    "--orb-opening-range-minutes",
                    "2",
                    "--output-dir",
                    temp_dir,
                    "--run-name",
                    "orb-range-cli",
                ]
            )
            summary = json.loads(
                (Path(temp_dir) / "orb-range-cli.json").read_text(encoding="utf-8")
            )

        self.assertIn(
            "strategy=orb_volume_vwap_ss0930_or2_orpct0.010-0.050_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
            output,
        )
        self.assertEqual(summary["strategy_spec"]["orb_opening_range_minutes"], "2")
        self.assertEqual(summary["strategy_spec"]["orb_min_range_pct"], "0.0100")
        self.assertEqual(summary["strategy_spec"]["orb_max_range_pct"], "0.0500")
        self.assertEqual(
            summary["strategy_spec"]["orb_range_size_rule"],
            "when configured, OR width divided by the first session open must stay within the min/max range pct gate",
        )
        self.assertEqual(summary["strategy_spec"]["orb_observed_range_pct_sessions"], "1")
        self.assertEqual(summary["strategy_spec"]["orb_observed_range_pct_min"], "0.0300")
        self.assertEqual(summary["strategy_spec"]["orb_observed_range_pct_max"], "0.0300")
        self.assertEqual(
            summary["strategy_spec"]["orb_observed_range_pct_below_min_sessions"], "0"
        )
        self.assertEqual(
            summary["strategy_spec"]["orb_observed_range_pct_within_gate_sessions"], "1"
        )
        self.assertEqual(
            summary["strategy_spec"]["orb_observed_range_pct_above_max_sessions"], "0"
        )

    def test_entry_edge_command_accepts_orb_breakout_distance_threshold(self) -> None:
        """
        用途與流程：驗證 entry-edge CLI 可啟用 ORB 最小突破距離百分比，並把 breakout distance 規則寫入 strategy spec。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_intraday_orb_csv(Path(temp_dir))
            output = _run_cli(
                [
                    "entry-edge",
                    "--csv",
                    str(csv_path),
                    "--strategy",
                    "orb-volume-vwap",
                    "--orb-min-breakout-pct",
                    "0.0050",
                    "--output-dir",
                    temp_dir,
                    "--run-name",
                    "orb-breakout-distance-cli",
                ]
            )
            summary = json.loads(
                (Path(temp_dir) / "orb-breakout-distance-cli.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertIn(
            "strategy=orb_volume_vwap_ss0930_or30_obp0.005_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
            output,
        )
        self.assertEqual(summary["strategy_spec"]["orb_min_breakout_pct"], "0.0050")
        self.assertEqual(
            summary["strategy_spec"]["orb_breakout_distance_rule"],
            "when configured, close must finish at least orb_min_breakout_pct above OR high before the breakout is accepted",
        )

    def test_entry_edge_command_accepts_orb_full_bar_above_range(self) -> None:
        """
        用途與流程：驗證 entry-edge CLI 可啟用 ORB full-bar-above-range 條件，並把 breakout candle 結構規則寫入 strategy spec。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_intraday_orb_csv(Path(temp_dir))
            output = _run_cli(
                [
                    "entry-edge",
                    "--csv",
                    str(csv_path),
                    "--strategy",
                    "orb-volume-vwap",
                    "--orb-full-bar-above-range",
                    "--output-dir",
                    temp_dir,
                    "--run-name",
                    "orb-fullbar-cli",
                ]
            )
            summary = json.loads(
                (Path(temp_dir) / "orb-fullbar-cli.json").read_text(encoding="utf-8")
            )

        self.assertIn(
            "strategy=orb_volume_vwap_ss0930_or30_fullbar_vw20_vm1.50_with_vwap_no_retest_long_only",
            output,
        )
        self.assertEqual(summary["strategy_spec"]["orb_full_bar_above_range"], "enabled")
        self.assertEqual(
            summary["strategy_spec"]["orb_full_bar_rule"],
            "when enabled, the breakout candle low must stay above OR high so the full bar remains outside the opening range",
        )

    def test_entry_edge_command_accepts_orb_min_breakout_body_pct(self) -> None:
        """
        用途與流程：驗證 entry-edge CLI 可啟用 ORB breakout candle body ratio 門檻，並把 body strength 規則寫入 strategy spec。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_intraday_body_orb_csv(Path(temp_dir))
            output = _run_cli(
                [
                    "entry-edge",
                    "--csv",
                    str(csv_path),
                    "--strategy",
                    "orb-volume-vwap",
                    "--orb-min-breakout-body-pct",
                    "0.6000",
                    "--output-dir",
                    temp_dir,
                    "--run-name",
                    "orb-breakout-body-cli",
                ]
            )
            summary = json.loads(
                (Path(temp_dir) / "orb-breakout-body-cli.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertIn(
            "strategy=orb_volume_vwap_ss0930_or30_body0.60_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
            output,
        )
        self.assertEqual(summary["strategy_spec"]["orb_min_breakout_body_pct"], "0.6000")
        self.assertEqual(
            summary["strategy_spec"]["orb_breakout_body_rule"],
            "when configured, breakout candle body divided by full candle range must be at least orb_min_breakout_body_pct before the breakout is accepted",
        )

    def test_entry_edge_command_accepts_orb_fresh_breakout_from_or(self) -> None:
        """
        用途與流程：驗證 entry-edge CLI 可啟用 ORB fresh breakout gate，並把前一根 close 需仍在 OR 內的規則寫入 strategy spec。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_intraday_fresh_orb_csv(Path(temp_dir))
            output = _run_cli(
                [
                    "entry-edge",
                    "--csv",
                    str(csv_path),
                    "--strategy",
                    "orb-volume-vwap",
                    "--orb-fresh-breakout-from-or",
                    "--output-dir",
                    temp_dir,
                    "--run-name",
                    "orb-fresh-breakout-cli",
                ]
            )
            summary = json.loads(
                (Path(temp_dir) / "orb-fresh-breakout-cli.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertIn(
            "strategy=orb_volume_vwap_ss0930_or30_fresh_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
            output,
        )
        self.assertEqual(summary["strategy_spec"]["orb_fresh_breakout_from_or"], "enabled")
        self.assertEqual(
            summary["strategy_spec"]["orb_fresh_breakout_rule"],
            "when enabled, the previous close must still be inside the OR box before the current bar can count as a fresh breakout",
        )

    def test_entry_edge_command_accepts_orb_opening_range_volume_baseline(self) -> None:
        """
        用途與流程：驗證 entry-edge CLI 可啟用 ORB 的 opening-range volume baseline，並把 breakout 量能比較基準改成 opening range 平均量能，同時將規則寫入 strategy spec。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_intraday_or_volume_baseline_orb_csv(Path(temp_dir))
            output = _run_cli(
                [
                    "entry-edge",
                    "--csv",
                    str(csv_path),
                    "--strategy",
                    "orb-volume-vwap",
                    "--orb-opening-range-minutes",
                    "2",
                    "--volume-window",
                    "3",
                    "--volume-multiplier",
                    "1.5",
                    "--orb-use-opening-range-volume-baseline",
                    "--output-dir",
                    temp_dir,
                    "--run-name",
                    "orb-or-volume-cli",
                ]
            )
            summary = json.loads(
                (Path(temp_dir) / "orb-or-volume-cli.json").read_text(encoding="utf-8")
            )

        self.assertIn(
            "strategy=orb_volume_vwap_ss0930_or2_orvol_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
            output,
        )
        self.assertEqual(
            summary["strategy_spec"]["orb_use_opening_range_volume_baseline"], "enabled"
        )
        self.assertEqual(
            summary["strategy_spec"]["orb_volume_baseline_rule"],
            "when enabled, breakout volume is compared against the average volume observed during the opening range instead of the rolling volume SMA baseline",
        )

    def test_entry_edge_command_writes_orb_range_gate_observation_counts(self) -> None:
        """
        用途與流程：驗證 entry-edge CLI 在 ORB range gate 啟用時，會把每個 session 的 opening range 百分比分類摘要寫進 strategy spec，讓 artifact 可直接看出有多少樣本低於下限、落在 gate 內或高於上限。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = _write_intraday_two_session_orb_csv(Path(temp_dir))
            _run_cli(
                [
                    "entry-edge",
                    "--csv",
                    str(csv_path),
                    "--strategy",
                    "orb-volume-vwap",
                    "--orb-min-range-pct",
                    "0.0100",
                    "--orb-max-range-pct",
                    "0.0500",
                    "--orb-opening-range-minutes",
                    "2",
                    "--output-dir",
                    temp_dir,
                    "--run-name",
                    "orb-range-counts-cli",
                ]
            )
            summary = json.loads(
                (Path(temp_dir) / "orb-range-counts-cli.json").read_text(encoding="utf-8")
            )

        self.assertEqual(summary["strategy_spec"]["orb_observed_range_pct_sessions"], "2")
        self.assertEqual(
            summary["strategy_spec"]["orb_observed_range_pct_below_min_sessions"], "1"
        )
        self.assertEqual(
            summary["strategy_spec"]["orb_observed_range_pct_within_gate_sessions"], "1"
        )
        self.assertEqual(
            summary["strategy_spec"]["orb_observed_range_pct_above_max_sessions"], "0"
        )

    def test_fetch_data_command_reports_written_paths(self) -> None:
        """
        用途與流程：驗證 fetch data command reports written paths 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_result = FetchDataResult(
                market="twse",
                symbol="2330",
                start="2024-01-01",
                end="2024-01-31",
                row_count=2,
                raw_csv=Path(temp_dir) / "data" / "raw" / "TWSE_2330_1D_raw.csv",
                processed_csv=Path(temp_dir) / "data" / "processed" / "TWSE_2330_1D.csv",
                manifest_json=Path(temp_dir)
                / "data"
                / "processed"
                / "TWSE_2330_1D_manifest.json",
            )
            with patch("signal_forge.cli.fetch_market_data", return_value=fake_result):
                output = _run_cli(
                    [
                        "fetch-data",
                        "--market",
                        "twse",
                        "--symbol",
                        "2330",
                        "--start",
                        "2024-01-01",
                        "--end",
                        "2024-01-31",
                        "--output-root",
                        temp_dir,
                    ]
                )

        self.assertIn("market=twse", output)
        self.assertIn("symbol=2330", output)
        self.assertIn("rows=2", output)
        self.assertIn("processed_csv=", output)

    def test_fetch_data_command_reports_data_source_errors_without_traceback(self) -> None:
        """
        用途與流程：驗證 fetch data command reports data source errors without traceback 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with patch(
            "signal_forge.cli.fetch_market_data",
            side_effect=MarketDataValidationError(
                "Stooq CSV download currently requires a free apikey"
            ),
        ):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = main(
                    [
                        "fetch-data",
                        "--market",
                        "us",
                        "--symbol",
                        "AAPL",
                        "--start",
                        "2024-01-01",
                        "--end",
                        "2024-01-31",
                    ]
                )

        self.assertEqual(exit_code, 2)
        self.assertIn("error=Stooq CSV download currently requires", buffer.getvalue())


def _run_cli(argv: list[str]) -> str:
    """
    用途與流程：用測試參數呼叫 CLI main，捕捉 stdout 與 exit code 供 assertion 使用。
    參數：argv（list[str]）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        exit_code = main(argv)
    if exit_code != 0:
        raise AssertionError(f"CLI exited with {exit_code}")
    return buffer.getvalue()


def _write_sample_csv(directory: Path) -> Path:
    """
    用途與流程：寫出最小可用 OHLCV CSV fixture，供 CLI 與資料載入測試讀取。
    參數：directory（Path）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 Path；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    csv_path = directory / "sample.csv"
    csv_path.write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume",
                "2026-01-01,10,10.5,9.5,10,100",
                "2026-01-02,11,11.5,10.5,11,100",
                "2026-01-03,12,12.5,11.5,12,100",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return csv_path


def _write_trending_csv(directory: Path, row_count: int) -> Path:
    """
    用途與流程：寫出趨勢型 OHLCV CSV fixture，讓策略在 CLI 測試中產生可預期 entry。
    參數：directory（Path）由呼叫端傳入，需符合函式 contract；row_count（int）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 Path；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    csv_path = directory / "trending.csv"
    rows = ["timestamp,open,high,low,close,volume"]
    for index in range(row_count):
        price = 10 + index
        rows.append(
            f"2026-01-{index + 1:02d},{price},{price + 0.5},{price - 0.5},{price},100"
        )
    csv_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return csv_path


def _write_vwap_reversion_csv(directory: Path) -> Path:
    """
    用途與流程：寫出可觸發 VWAP reversion long entry 且通過 regime SMA 的 CLI fixture。
    參數：directory（Path）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 Path；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    csv_path = directory / "vwap_reversion.csv"
    csv_path.write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume",
                "2026-01-01,20,20.5,19.5,20,100",
                "2026-01-02,10,10.5,9.5,10,1",
                "2026-01-03,15,15.5,14.5,15,1",
                "2026-01-04,16,16.5,15.5,16,1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return csv_path


def _write_intraday_orb_csv(directory: Path) -> Path:
    """
    用途與流程：寫出含 intraday 時間欄位的 ORB CSV fixture，供 CLI 測試 ORB retest 參數與 strategy spec。
    參數：directory（Path）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 Path；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    csv_path = directory / "intraday_orb.csv"
    csv_path.write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume",
                "2026-01-01T09:30,100,101,99,100,100",
                "2026-01-01T09:31,100,102,100,101,100",
                "2026-01-01T09:32,101,103.6,100.8,102.6,150",
                "2026-01-01T09:33,102.6,103.7,101.7,102.7,230",
                "2026-01-01T09:34,102.7,104.0,102.0,103.0,230",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return csv_path


def _write_intraday_body_orb_csv(directory: Path) -> Path:
    """
    用途與流程：寫出可先出現弱 breakout、再出現強 breakout 的 ORB CSV fixture，供 CLI 測試 breakout candle body ratio 條件。
    參數：directory（Path）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 Path；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    csv_path = directory / "intraday_orb_body.csv"
    csv_path.write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume",
                "2026-01-01T09:30,100.0,100.8,99.8,100.2,100",
                "2026-01-01T09:31,100.2,101.0,100.0,100.8,100",
                "2026-01-01T09:32,100.95,101.7,100.8,101.2,150",
                "2026-01-01T09:33,101.15,102.4,101.1,102.2,260",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return csv_path


def _write_intraday_fresh_orb_csv(directory: Path) -> Path:
    """
    用途與流程：寫出會先出現一根低量 breakout、再出現一根高量但已非 fresh breakout 的 ORB CSV fixture，供 CLI 測試 fresh breakout gate。
    參數：directory（Path）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 Path；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    csv_path = directory / "intraday_orb_fresh.csv"
    csv_path.write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume",
                "2026-01-01T09:30,100.0,100.8,99.8,100.2,100",
                "2026-01-01T09:31,100.2,101.0,100.0,100.8,100",
                "2026-01-01T09:32,100.8,101.6,100.7,101.2,100",
                "2026-01-01T09:33,101.2,102.4,101.1,102.2,260",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return csv_path


def _write_intraday_or_volume_baseline_orb_csv(directory: Path) -> Path:
    """
    用途與流程：寫出 ORB opening-range volume baseline 專用 CSV fixture，讓 CLI 測試可穩定重現「rolling volume SMA 會擋掉 breakout，但 OR 平均量能 baseline 會放行」的情境。
    參數：directory（Path）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 Path；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    csv_path = directory / "intraday_orb_or_volume.csv"
    csv_path.write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume",
                "2026-01-01T09:30,100.0,100.8,99.8,100.2,40",
                "2026-01-01T09:31,100.2,101.0,100.0,100.8,60",
                "2026-01-01T09:32,100.8,100.95,100.4,100.9,300",
                "2026-01-01T09:33,100.9,102.4,100.8,102.2,100",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return csv_path


def _write_intraday_shifted_orb_csv(directory: Path) -> Path:
    """
    用途與流程：寫出 session 起點為 08:00 的 ORB CSV fixture，供 CLI 測試 ORB session 參數化。
    參數：directory（Path）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 Path；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    csv_path = directory / "intraday_orb_shifted.csv"
    csv_path.write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume",
                "2026-01-01T08:00,100,101,99,100,100",
                "2026-01-01T08:01,100,102,100,101,100",
                "2026-01-01T08:02,101,102.2,100.4,100.5,100",
                "2026-01-01T08:03,100.5,103.4,100.2,102.5,150",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return csv_path


def _write_intraday_signal_window_orb_csv(directory: Path) -> Path:
    """
    用途與流程：寫出會在 signal window 外才出現 breakout 的 ORB CSV fixture，供 CLI 驗證 ORB 的時間窗 cutoff 規則。
    參數：directory（Path）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 Path；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    csv_path = directory / "intraday_orb_signal_window.csv"
    csv_path.write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume",
                "2026-01-01T09:30,100.0,100.8,99.8,100.2,100",
                "2026-01-01T09:31,100.2,101.0,100.0,100.8,100",
                "2026-01-01T09:32,100.8,100.95,100.4,100.9,120",
                "2026-01-01T09:33,100.9,100.98,100.6,100.95,120",
                "2026-01-01T09:34,100.95,102.6,100.9,102.2,180",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return csv_path


def _write_intraday_two_session_orb_csv(directory: Path) -> Path:
    """
    用途與流程：寫出兩個 session 的 ORB CSV fixture，其中一個 session 的 opening range 低於 min gate，另一個落在 gate 內，供 CLI 驗證 artifact 的 gate 分類摘要。
    參數：directory（Path）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 Path；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    csv_path = directory / "intraday_orb_two_session.csv"
    csv_path.write_text(
        "\n".join(
            [
                "timestamp,open,high,low,close,volume",
                "2026-01-01T09:30,100,100.2,99.9,100.0,100",
                "2026-01-01T09:31,100,100.3,99.9,100.1,100",
                "2026-01-01T09:32,100.1,100.4,100.0,100.2,120",
                "2026-01-02T09:30,100,101.0,99.0,100.0,100",
                "2026-01-02T09:31,100,102.0,100.0,101.0,100",
                "2026-01-02T09:32,101.0,102.5,100.8,102.0,140",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return csv_path


if __name__ == "__main__":
    unittest.main()
