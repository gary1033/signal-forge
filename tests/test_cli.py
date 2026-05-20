from __future__ import annotations

from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from signal_forge import MarketDataValidationError
from signal_forge.cli import main
from signal_forge.data_fetch import FetchDataResult


class CliTests(unittest.TestCase):
    def test_phase_backtest_command_reports_entry_edge_result(self) -> None:
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

    def test_phase_live_command_reports_dry_run_intent_without_submission(self) -> None:
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

    def test_fetch_data_command_reports_written_paths(self) -> None:
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
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        exit_code = main(argv)
    if exit_code != 0:
        raise AssertionError(f"CLI exited with {exit_code}")
    return buffer.getvalue()


def _write_sample_csv(directory: Path) -> Path:
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


if __name__ == "__main__":
    unittest.main()
