from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from signal_forge.market_data import load_bars_from_csv
from tools.build_twse_adjusted_ohlcv import (
    TAIPEI_TZ,
    apply_adjustment_ratios,
    build_adjusted_ohlcv,
    build_manifest,
    build_parser,
    parse_yahoo_adjustment_ratios,
)


class BuildTwseAdjustedOhlcvToolTests(unittest.TestCase):
    def test_parser_accepts_adjusted_ohlcv_options(self) -> None:
        """
        用途與流程：驗證調整價工具 CLI 能接收台股代號、來源 CSV、日期窗與輸出路徑，避免批次回測命令漂移。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 parser 欄位或預設 Yahoo 代號語意漂移，assertion 會失敗。
        """
        args = build_parser().parse_args(
            [
                "--symbol",
                "2330",
                "--source-csv",
                "data/processed/TWSE_2330_1D.csv",
                "--start",
                "2024-01-02",
                "--end",
                "2024-01-03",
                "--output-csv",
                "reports/generated/adjusted-data/TWSEADJ_2330_1D.csv",
                "--manifest-json",
                "reports/generated/adjusted-data/TWSEADJ_2330_1D_manifest.json",
            ]
        )

        self.assertEqual(args.symbol, "2330")
        self.assertIsNone(args.yahoo_symbol)
        self.assertEqual(args.source_csv, Path("data/processed/TWSE_2330_1D.csv"))
        self.assertEqual(args.start, "2024-01-02")
        self.assertEqual(args.output_csv, Path("reports/generated/adjusted-data/TWSEADJ_2330_1D.csv"))

    def test_parse_yahoo_ratios_uses_taipei_local_date(self) -> None:
        """
        用途與流程：驗證 Yahoo chart timestamp 會先轉成 Asia/Taipei 日期再對齊 TWSE CSV，避免 UTC 日期造成調整比例錯位。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若日期轉換、缺值略過或 ratio 公式漂移，assertion 會失敗。
        """
        payload = _yahoo_payload(
            timestamps=[
                _epoch_for_taipei_date("2024-01-02"),
                _epoch_for_taipei_date("2024-01-03"),
            ],
            closes=[100.0, None],
            adjcloses=[50.0, 80.0],
        )

        ratios = parse_yahoo_adjustment_ratios(payload)

        self.assertEqual(set(ratios), {"2024-01-02"})
        self.assertAlmostEqual(ratios["2024-01-02"], 0.5)

    def test_apply_adjustment_ratios_scales_ohlc_and_preserves_volume(self) -> None:
        """
        用途與流程：驗證調整比例只縮放 OHLC，成交量保留 TWSE source CSV 口徑，缺少 ratio 的交易日會被明確計數與略過。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若價格縮放、volume 保存或 skip count 漂移，assertion 會失敗。
        """
        source_bars = [
            _bar("2024-01-01", 90.0, volume=900.0),
            _bar("2024-01-02", 100.0, volume=1000.0),
            _bar("2024-01-03", 120.0, volume=1200.0),
        ]

        build = apply_adjustment_ratios(
            source_bars,
            {"2024-01-02": 0.5},
            start=datetime.strptime("2024-01-02", "%Y-%m-%d").date(),
            end=datetime.strptime("2024-01-03", "%Y-%m-%d").date(),
        )

        self.assertEqual(build.source_row_count, 3)
        self.assertEqual(build.row_count, 1)
        self.assertEqual(build.missing_adjustment_count, 1)
        self.assertEqual(build.skipped_row_count, 2)
        adjusted = build.bars[0]
        self.assertEqual(adjusted.timestamp, "2024-01-02")
        self.assertAlmostEqual(adjusted.open, 50.0)
        self.assertAlmostEqual(adjusted.high, 55.0)
        self.assertAlmostEqual(adjusted.low, 45.0)
        self.assertAlmostEqual(adjusted.close, 50.0)
        self.assertAlmostEqual(adjusted.volume, 1000.0)

    def test_build_adjusted_ohlcv_outputs_manifest_without_network(self) -> None:
        """
        用途與流程：用固定 Yahoo chart fixture 驗證完整工具流程會寫出可載入 CSV 與 deterministic manifest，不依賴真實網路。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若寫檔 schema、manifest 欄位或調整來源說明漂移，assertion 會失敗。
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
            source_csv = root / "TWSE_2330_1D.csv"
            output_csv = root / "TWSEADJ_2330_1D.csv"
            manifest_json = root / "TWSEADJ_2330_1D_manifest.json"
            source_csv.write_text(
                "\n".join(
                    [
                        "timestamp,open,high,low,close,volume",
                        "2024-01-02,100,110,90,100,1000",
                        "2024-01-03,120,132,108,120,1200",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = build_adjusted_ohlcv(
                symbol="2330",
                source_csv=source_csv,
                start="2024-01-02",
                end="2024-01-03",
                output_csv=output_csv,
                manifest_json=manifest_json,
                fetch_chart_json=lambda _symbol, _start, _end: payload,
            )

            adjusted_bars = load_bars_from_csv(output_csv)
            manifest = json.loads(manifest_json.read_text(encoding="utf-8"))

        self.assertEqual(result.yahoo_symbol, "2330.TW")
        self.assertEqual(result.row_count, 2)
        self.assertEqual([bar.timestamp for bar in adjusted_bars], ["2024-01-02", "2024-01-03"])
        self.assertAlmostEqual(adjusted_bars[0].close, 50.0)
        self.assertAlmostEqual(adjusted_bars[1].volume, 1200.0)
        self.assertTrue(manifest["adjusted"])
        self.assertEqual(
            manifest["adjustment_method"],
            "source_ohlcv_scaled_by_yahoo_adjclose_ratio",
        )
        self.assertEqual(manifest["adjustment_source"], "Yahoo chart adjclose/close ratio")
        self.assertEqual(manifest["volume_source"], "source CSV volume preserved")
        self.assertEqual(manifest["missing_adjustment_count"], 0)
        self.assertNotIn("created_at", manifest)

    def test_manifest_documents_source_and_output_without_current_time(self) -> None:
        """
        用途與流程：直接驗證 manifest builder 的欄位穩定性，確保資料來源、volume 口徑與日期窗可被後續回測稽核。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 manifest 加入非 deterministic 時間戳或漏掉 source 欄位，assertion 會失敗。
        """
        build = apply_adjustment_ratios(
            [_bar("2024-01-02", 100.0, volume=1000.0), _bar("2024-01-03", 101.0, volume=1100.0)],
            {"2024-01-02": 0.5, "2024-01-03": 0.5},
            start=datetime.strptime("2024-01-02", "%Y-%m-%d").date(),
            end=datetime.strptime("2024-01-03", "%Y-%m-%d").date(),
        )

        manifest = build_manifest(
            symbol="2330",
            yahoo_symbol="2330.TW",
            source_csv=Path("data/processed/TWSE_2330_1D.csv"),
            output_csv=Path("reports/generated/adjusted-data/TWSEADJ_2330_1D.csv"),
            start=datetime.strptime("2024-01-02", "%Y-%m-%d").date(),
            end=datetime.strptime("2024-01-03", "%Y-%m-%d").date(),
            build=build,
        )

        self.assertEqual(manifest["price_source_csv"], "data/processed/TWSE_2330_1D.csv")
        self.assertEqual(manifest["output_csv"], "reports/generated/adjusted-data/TWSEADJ_2330_1D.csv")
        self.assertEqual(manifest["row_count"], 2)
        self.assertEqual(manifest["timezone"], "Asia/Taipei")
        self.assertNotIn("timestamp", manifest)


def _bar(timestamp: str, close: float, *, volume: float) -> object:
    """
    用途與流程：建立測試用 Bar，讓調整價測試能聚焦日期、價格與成交量保存。
    參數：timestamp 是 `YYYY-MM-DD`；close 是收盤價並用來推導 OHLC；volume 是成交量。
    回傳與錯誤：回傳 Bar；此 helper 不做資料驗證，也不主動拋錯。
    """
    from signal_forge import Bar

    return Bar(
        timestamp=timestamp,
        open=close,
        high=close * 1.1,
        low=close * 0.9,
        close=close,
        volume=volume,
    )


def _yahoo_payload(
    *,
    timestamps: list[int],
    closes: list[float | None],
    adjcloses: list[float | None],
) -> dict[str, object]:
    """
    用途與流程：建立最小 Yahoo chart JSON fixture，避免單元測試連網。
    參數：timestamps 是 epoch seconds；closes 與 adjcloses 是對應的收盤價與調整後收盤價。
    回傳與錯誤：回傳 dict；此 helper 不主動驗證三個序列長度。
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
    用途與流程：把台北當地日期零點轉成 UTC epoch，測試 Yahoo timestamp 轉本地日期的對齊邊界。
    參數：value 是 `YYYY-MM-DD` 日期字串。
    回傳與錯誤：回傳 epoch seconds；日期格式錯誤時由 datetime.strptime 拋出 ValueError。
    """
    local_dt = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=TAIPEI_TZ)
    return int(local_dt.astimezone(timezone.utc).timestamp())


if __name__ == "__main__":
    unittest.main()
