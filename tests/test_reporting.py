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
