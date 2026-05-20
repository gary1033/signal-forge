from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from signal_forge import MarketDataValidationError
from signal_forge.cli import main
from signal_forge.data_fetch import FetchDataResult


class CliTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
