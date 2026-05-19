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
from signal_forge.reporting import write_entry_edge_outputs, write_phase_outputs


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
                strategy_spec={"進場方向": "純多"},
            )
            self.assertTrue(paths.markdown.exists())
            self.assertTrue(paths.summary_json.exists())
            self.assertTrue(paths.trade_log_csv.exists())
            summary = json.loads(paths.summary_json.read_text(encoding="utf-8"))
            self.assertEqual(summary["decision"], result.decision)
            self.assertIn("signal_timestamp", paths.trade_log_csv.read_text(encoding="utf-8"))
            self.assertIn("蒸餾後進場規格", paths.markdown.read_text(encoding="utf-8"))

    def test_writes_phase_output_with_adapter_metadata(self) -> None:
        bars = [
            Bar("2026-01-01", 10, 10.5, 9.5, 10, 100),
            Bar("2026-01-02", 10, 11.5, 9.5, 11, 100),
        ]
        result = PhaseRunner().run(PhaseConfig(mode="live"), OneTradeStrategy(), bars)

        with tempfile.TemporaryDirectory() as temp_dir:
            paths = write_phase_outputs(result, temp_dir, run_name="phase-live")
            summary = json.loads(paths.summary_json.read_text(encoding="utf-8"))
            markdown = paths.markdown.read_text(encoding="utf-8")

        self.assertEqual(summary["phase"]["mode"], "live")
        self.assertEqual(summary["phase"]["adapter_name"], "live")
        self.assertEqual(summary["order_intents"][0]["submitted"], False)
        self.assertIn("Adapter Metadata", markdown)
        self.assertIn("submitted=False", markdown)


if __name__ == "__main__":
    unittest.main()
