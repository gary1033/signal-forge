from __future__ import annotations

import unittest

from signal_forge import (
    PhaseConfig,
    PhaseRunner,
    normalize_signal_reason,
    parse_phase_mode,
)
from helpers import MessyReasonStrategy, OneEntryStrategy, StatefulOneEntryStrategy, sample_bars


class PhaseConfigTests(unittest.TestCase):
    def test_normalize_signal_reason_is_ascii_trimmed_single_line(self) -> None:
        """
        用途與流程：驗證 normalize signal reason is ascii trimmed single line 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        self.assertEqual(normalize_signal_reason(""), "unknown")
        self.assertEqual(normalize_signal_reason("\r\n\t"), "unknown")
        self.assertEqual(
            normalize_signal_reason("  \u9032\u5834\t\n  alpha  "), "u9032u5834 alpha"
        )

    def test_normalize_signal_reason_truncates_long_input(self) -> None:
        """
        用途與流程：驗證 normalize signal reason truncates long input 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        self.assertEqual(normalize_signal_reason("a" * 200), "a" * 120)

    def test_backtest_mode_is_default(self) -> None:
        """
        用途與流程：驗證 backtest mode is default 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        config = PhaseConfig()
        self.assertTrue(config.is_backtest)
        self.assertFalse(config.is_live)
        self.assertFalse(config.dry_run)

    def test_live_mode_is_dry_run_only(self) -> None:
        """
        用途與流程：驗證 live mode is dry run only 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with self.assertRaises(ValueError):
            PhaseConfig(mode="live", dry_run=False)

    def test_backtest_mode_rejects_dry_run_true(self) -> None:
        """
        用途與流程：驗證 backtest mode rejects dry run true 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with self.assertRaises(ValueError):
            PhaseConfig(mode="backtest", dry_run=True)

    def test_rejects_unknown_mode(self) -> None:
        """
        用途與流程：驗證 rejects unknown mode 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with self.assertRaises(ValueError):
            PhaseConfig(mode="paper")  # type: ignore[arg-type]

    def test_rejects_invalid_hold_period(self) -> None:
        """
        用途與流程：驗證 rejects invalid hold period 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with self.assertRaises(ValueError):
            PhaseConfig(hold_bars_per_day=0)

    def test_parse_phase_mode_normalizes_valid_values(self) -> None:
        """
        用途與流程：驗證 parse phase mode normalizes valid values 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        self.assertEqual(parse_phase_mode(" BACKTEST "), "backtest")
        self.assertEqual(parse_phase_mode("live"), "live")

    def test_parse_phase_mode_rejects_unknown_value(self) -> None:
        """
        用途與流程：驗證 parse phase mode rejects unknown value 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with self.assertRaises(ValueError):
            parse_phase_mode("paper")

    def test_phase_runner_routes_backtest_to_entry_edge_adapter(self) -> None:
        """
        用途與流程：驗證 phase runner routes backtest to entry edge adapter 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        result = PhaseRunner().run(
            PhaseConfig(mode="backtest"),
            OneEntryStrategy(),
            sample_bars(),
        )

        self.assertEqual(result.mode, "backtest")
        self.assertEqual(result.adapter_name, "backtest")
        self.assertFalse(result.dry_run)
        self.assertIsNotNone(result.entry_edge_result)
        self.assertEqual(result.entry_edge_result.trade_count, 1)

    def test_phase_backtest_uses_single_signal_sequence_for_digest_and_entry_edge(self) -> None:
        """
        用途與流程：驗證 Phase backtest 只呼叫 strategy 一次，並讓 EntryEdgeResult 與 SignalDigest 共用同一份 signals。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        strategy = StatefulOneEntryStrategy()

        result = PhaseRunner().run(
            PhaseConfig(mode="backtest"),
            strategy,
            sample_bars(),
        )

        self.assertEqual(strategy.call_count, 1)
        self.assertIsNotNone(result.entry_edge_result)
        self.assertIsNotNone(result.signal_digests)
        assert result.entry_edge_result is not None
        assert result.signal_digests is not None
        self.assertEqual(result.entry_edge_result.trades[0].signal_reason, "entry_call_1")
        self.assertEqual(result.signal_digests[0].reason, "entry_call_1")

    def test_phase_runner_normalizes_reasons_for_digest_and_intent(self) -> None:
        """
        用途與流程：驗證 phase runner normalizes reasons for digest and intent 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        backtest = PhaseRunner().run(
            PhaseConfig(mode="backtest"),
            MessyReasonStrategy(),
            sample_bars(),
        )
        self.assertEqual(backtest.mode, "backtest")
        self.assertEqual(
            backtest.signal_digests[0].reason, "u9032u5834 alpha"  # type: ignore[index]
        )

        live = PhaseRunner().run(
            PhaseConfig(mode="live"),
            MessyReasonStrategy(),
            sample_bars(),
        )
        self.assertEqual(live.mode, "live")
        self.assertEqual(
            live.order_intents[0].reason, "u9032u5834 alpha"  # type: ignore[index]
        )

    def test_phase_runner_routes_live_to_dry_run_order_intent_only(self) -> None:
        """
        用途與流程：驗證 phase runner routes live to dry run order intent only 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        result = PhaseRunner().run(
            PhaseConfig(mode="live"),
            OneEntryStrategy(),
            sample_bars(),
        )

        self.assertEqual(result.mode, "live")
        self.assertEqual(result.adapter_name, "live")
        self.assertTrue(result.dry_run)
        self.assertIsNone(result.entry_edge_result)
        self.assertEqual(len(result.order_intents or []), 1)
        intent = (result.order_intents or [])[0]
        self.assertTrue(intent.dry_run)
        self.assertFalse(intent.submitted)
        self.assertIn("LIVE_DRY_RUN_ONLY", intent.safety_note)
        self.assertIn("no broker", intent.safety_note)
        self.assertIn("no api keys", intent.safety_note)
        self.assertIn("submitted=False", intent.safety_note)

    def test_phase_runner_rejects_missing_data_before_live_adapter(self) -> None:
        """
        用途與流程：驗證 phase runner rejects missing data before live adapter 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with self.assertRaisesRegex(ValueError, "no bars were loaded"):
            PhaseRunner().run(
                PhaseConfig(mode="live"),
                OneEntryStrategy(),
                [],
            )

    def test_phase_runner_rejects_insufficient_data_for_hold_period(self) -> None:
        """
        用途與流程：驗證 phase runner rejects insufficient data for hold period 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with self.assertRaisesRegex(ValueError, "at least 3 bars are required"):
            PhaseRunner().run(
                PhaseConfig(mode="backtest", hold_bars_per_day=2),
                OneEntryStrategy(),
                sample_bars(),
            )


if __name__ == "__main__":
    unittest.main()
