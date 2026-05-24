from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from signal_forge.market_data import load_bars_from_csv
from tools.build_twse_adjusted_ohlcv import TAIPEI_TZ
from tools.build_twse_adjusted_ohlcv_batch import (
    build_adjusted_ohlcv_batch,
    build_parser,
    parse_symbols_list,
)


class BuildTwseAdjustedOhlcvBatchToolTests(unittest.TestCase):
    def test_parser_accepts_batch_options_and_defaults(self) -> None:
        """
        用途與流程：驗證 batch adjusted 工具 CLI 能接收股票清單、日期窗與 batch manifest，並保留預設 source/output 目錄。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 parser 欄位、預設目錄或必填參數漂移，assertion 會失敗。
        """
        args = build_parser().parse_args(
            [
                "--symbols-list",
                "2330,2317",
                "--start",
                "2024-01-02",
                "--end",
                "2024-01-03",
                "--batch-manifest-json",
                "reports/generated/adjusted-data/TWSE14_adjusted_batch_manifest.json",
            ]
        )

        self.assertEqual(args.symbols_list, "2330,2317")
        self.assertEqual(args.source_dir, Path("data/processed"))
        self.assertEqual(args.output_dir, Path("reports/generated/adjusted-data"))
        self.assertEqual(args.start, "2024-01-02")
        self.assertEqual(args.end, "2024-01-03")
        self.assertEqual(
            args.batch_manifest_json,
            Path("reports/generated/adjusted-data/TWSE14_adjusted_batch_manifest.json"),
        )

    def test_parse_symbols_list_normalizes_and_rejects_duplicates(self) -> None:
        """
        用途與流程：驗證逗號分隔股票清單會標準化空白與大小寫，並拒絕重複代號以避免 manifest 重複覆寫。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；空清單或重複代號應拋出 ValueError。
        """
        self.assertEqual(parse_symbols_list(" 2330, abc ,2317 "), ("2330", "ABC", "2317"))

        with self.assertRaisesRegex(ValueError, "duplicate"):
            parse_symbols_list("2330,2317,2330")
        with self.assertRaisesRegex(ValueError, "at least one"):
            parse_symbols_list(" , ")

    def test_build_adjusted_ohlcv_batch_outputs_manifest_without_network(self) -> None:
        """
        用途與流程：用固定 Yahoo chart fixture 驗證批次流程會寫出每檔 adjusted CSV、per-symbol manifest 與 deterministic batch manifest。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若批次欄位、彙總計數、volume 來源或 timestamp-free contract 漂移，assertion 會失敗。
        """
        payload = _yahoo_payload(
            timestamps=[
                _epoch_for_taipei_date("2024-01-02"),
                _epoch_for_taipei_date("2024-01-03"),
            ],
            closes=[100.0, 120.0],
            adjcloses=[50.0, 60.0],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "source"
            output_dir = root / "adjusted"
            batch_manifest_json = output_dir / "TWSE2_adjusted_batch_manifest.json"
            source_dir.mkdir()
            _write_source_csv(source_dir / "TWSE_2330_1D.csv", close_1=100.0, close_2=120.0)
            _write_source_csv(source_dir / "TWSE_2317_1D.csv", close_1=200.0, close_2=240.0)

            batch = build_adjusted_ohlcv_batch(
                symbols=("2330", "2317"),
                source_dir=source_dir,
                start="2024-01-02",
                end="2024-01-03",
                output_dir=output_dir,
                batch_manifest_json=batch_manifest_json,
                fetch_chart_json=lambda _symbol, _start, _end: payload,
            )

            bars_2330 = load_bars_from_csv(output_dir / "TWSEADJ_2330_1D.csv")
            bars_2317 = load_bars_from_csv(output_dir / "TWSEADJ_2317_1D.csv")
            manifest_2330 = json.loads(
                (output_dir / "TWSEADJ_2330_1D_manifest.json").read_text(encoding="utf-8")
            )
            batch_manifest = json.loads(batch_manifest_json.read_text(encoding="utf-8"))

        self.assertEqual(batch.row_count_total, 4)
        self.assertEqual(batch.missing_adjustment_count_total, 0)
        self.assertEqual(batch.skipped_row_count_total, 0)
        self.assertEqual([bar.timestamp for bar in bars_2330], ["2024-01-02", "2024-01-03"])
        self.assertAlmostEqual(bars_2330[0].close, 50.0)
        self.assertAlmostEqual(bars_2317[0].close, 100.0)
        self.assertEqual(manifest_2330["volume_source"], "source CSV volume preserved")
        self.assertTrue(batch_manifest["adjusted"])
        self.assertEqual(
            batch_manifest["adjustment_method"],
            "source_ohlcv_scaled_by_yahoo_adjclose_ratio",
        )
        self.assertEqual(batch_manifest["adjustment_source"], "Yahoo chart adjclose/close ratio")
        self.assertEqual(batch_manifest["result_count"], 2)
        self.assertEqual(batch_manifest["row_count_total"], 4)
        self.assertEqual(batch_manifest["symbols"], ["2330", "2317"])
        self.assertEqual(batch_manifest["volume_source"], "source CSV volume preserved")
        self.assertEqual(
            [result["manifest_json"] for result in batch_manifest["results"]],
            [
                (output_dir / "TWSEADJ_2330_1D_manifest.json").as_posix(),
                (output_dir / "TWSEADJ_2317_1D_manifest.json").as_posix(),
            ],
        )
        self.assertNotIn("created_at", batch_manifest)
        self.assertNotIn("timestamp", batch_manifest)


def _write_source_csv(path: Path, *, close_1: float, close_2: float) -> None:
    """
    用途與流程：寫入最小 SignalForge OHLCV fixture，供 batch adjusted 工具測試多檔股票輸入。
    參數：path 是輸出 CSV 路徑；close_1/close_2 是兩個交易日的收盤價並用來推導 OHLC。
    回傳與錯誤：回傳 None；檔案寫入失敗時由 Path.write_text 拋出例外。
    """
    rows = [
        "timestamp,open,high,low,close,volume",
        f"2024-01-02,{close_1},{close_1 * 1.1},{close_1 * 0.9},{close_1},1000",
        f"2024-01-03,{close_2},{close_2 * 1.1},{close_2 * 0.9},{close_2},1200",
    ]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _yahoo_payload(
    *,
    timestamps: list[int],
    closes: list[float | None],
    adjcloses: list[float | None],
) -> dict[str, object]:
    """
    用途與流程：建立最小 Yahoo chart JSON fixture，讓 batch 測試可重用單檔 adjusted 工具的 ratio parser。
    參數：timestamps 是 epoch seconds；closes 與 adjcloses 是對應的收盤價與調整後收盤價。
    回傳與錯誤：回傳 dict；此 helper 不主動檢查序列長度。
    """
    return {
        "chart": {
            "result": [
                {
                    "timestamp": timestamps,
                    "indicators": {
                        "quote": [{"close": closes}],
                        "adjclose": [{"adjclose": adjcloses}],
                    },
                }
            ]
        }
    }


def _epoch_for_taipei_date(value: str) -> int:
    """
    用途與流程：把台北當地日期零點轉成 UTC epoch，測試 Yahoo timestamp 到 TWSE 日期的對齊。
    參數：value 是 `YYYY-MM-DD` 日期字串。
    回傳與錯誤：回傳 epoch seconds；日期格式錯誤時由 datetime.strptime 拋出 ValueError。
    """
    local_dt = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=TAIPEI_TZ)
    return int(local_dt.astimezone(timezone.utc).timestamp())


if __name__ == "__main__":
    unittest.main()
