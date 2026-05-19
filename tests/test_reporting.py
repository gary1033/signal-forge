from __future__ import annotations

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
    validate_bars,
)
from signal_forge.reporting import (
    validate_phase_summary,
    write_entry_edge_outputs,
    write_phase_outputs,
)


class OneTradeStrategy(Strategy):
    name = "one_trade"

    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        return [Signal(index, bar.timestamp, 1.0 if index == 0 else 0.0, "entry") for index, bar in enumerate(bars)]


class ReportingTests(unittest.TestCase):
    def test_writes_markdown_json_and_trade_log(self) -> None:
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
                    "- Phase 1 constraints: long-only; ignore short signals; no stops/take-profit/filters/parameter optimization.",
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

    def test_writes_phase_output_with_adapter_metadata(self) -> None:
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
            self.assertTrue((paths.signal_digest_csv or paths.summary_json).exists())
            if paths.signal_digest_csv:
                self.assertEqual(
                    paths.signal_digest_csv.read_text(encoding="utf-8"),
                    "\n".join(
                        [
                            "index,timestamp,target_position,reason,score,is_long_entry,is_flatten",
                            "0,2026-01-01,1.000000,entry,0.000000,True,False",
                            "1,2026-01-02,0.000000,entry,0.000000,False,True",
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
                    "## Live Dry-Run Intents",
                    "",
                    "- No dry-run order intents were emitted.",
                    "",
                ]
            ),
        )
        self.assertIn("Backtest Result", markdown)
        self.assertIn("Profit Factor: Infinity", markdown)
        self.assertIn("End equity: 10995.80", markdown)

    def test_writes_phase_output_live_has_stable_contract(self) -> None:
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
        with self.assertRaisesRegex(ValueError, "missing required dict key: phase"):
            validate_phase_summary({})

    def test_phase_summary_schema_validator_rejects_live_submitted_intent(self) -> None:
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
