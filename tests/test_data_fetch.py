from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from signal_forge.data_fetch import (
    fetch_market_data,
    fetch_stooq_daily_stock,
    fetch_twse_daily_stock,
    parse_stooq_csv,
    parse_twse_row,
)
from signal_forge.market_data import MarketDataValidationError, load_bars_from_csv


class DataFetchTests(unittest.TestCase):
    def test_parse_twse_row_converts_roc_date_and_numeric_fields(self) -> None:
        """
        用途與流程：驗證 parse twse row converts roc date and numeric fields 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bar = parse_twse_row(
            {
                "日期": "113/01/02",
                "成交股數": "27,997,826",
                "開盤價": "590.00",
                "最高價": "593.00",
                "最低價": "589.00",
                "收盤價": "593.00",
            }
        )

        self.assertIsNotNone(bar)
        assert bar is not None
        self.assertEqual(bar.timestamp, "2024-01-02")
        self.assertEqual(bar.open, 590.0)
        self.assertEqual(bar.high, 593.0)
        self.assertEqual(bar.low, 589.0)
        self.assertEqual(bar.close, 593.0)
        self.assertEqual(bar.volume, 27997826.0)

    def test_parse_twse_row_skips_empty_market_values(self) -> None:
        """
        用途與流程：驗證 parse twse row skips empty market values 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        self.assertIsNone(
            parse_twse_row(
                {
                    "日期": "113/01/02",
                    "成交股數": "27,997,826",
                    "開盤價": "--",
                    "最高價": "593.00",
                    "最低價": "589.00",
                    "收盤價": "593.00",
                }
            )
        )

    def test_fetch_twse_daily_stock_uses_monthly_json_and_filters_range(self) -> None:
        """
        用途與流程：驗證 fetch twse daily stock uses monthly json and filters range 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        payload = {
            "fields": ["日期", "成交股數", "成交金額", "開盤價", "最高價", "最低價", "收盤價"],
            "data": [
                ["113/01/02", "1,000", "10,000", "10.00", "11.00", "9.00", "10.50"],
                ["113/01/03", "1,100", "12,000", "11.00", "12.00", "10.00", "11.50"],
                ["113/02/01", "1,200", "13,000", "12.00", "13.00", "11.00", "12.50"],
            ],
        }
        seen_urls: list[str] = []

        def fake_fetch(url: str) -> str:
            """
            用途與流程：執行此模組定義的業務流程，依輸入資料產生後續 reporting、策略或測試所需結果。
            參數：url（str）由呼叫端傳入，需符合函式 contract
            回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
            """
            seen_urls.append(url)
            return json.dumps(payload)

        raw_csv, bars, source = fetch_twse_daily_stock(
            "2330",
            date(2024, 1, 3),
            date(2024, 1, 31),
            fetch_text=fake_fetch,
        )

        self.assertEqual(source, "TWSE STOCK_DAY")
        self.assertEqual(len(seen_urls), 1)
        self.assertIn("exchangeReport/STOCK_DAY", seen_urls[0])
        self.assertIn("stockNo=2330", seen_urls[0])
        self.assertIn("date=20240101", seen_urls[0])
        self.assertIn("113/01/02", raw_csv)
        self.assertEqual([bar.timestamp for bar in bars], ["2024-01-03"])

    def test_parse_stooq_csv_converts_daily_ohlcv(self) -> None:
        """
        用途與流程：驗證 parse stooq csv converts daily ohlcv 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = parse_stooq_csv(
            "\n".join(
                [
                    "Date,Open,High,Low,Close,Volume",
                    "2024-01-02,187.15,188.44,183.89,185.64,82488700",
                    "2024-01-03,184.22,185.88,183.43,184.25,58414500",
                ]
            )
            + "\n"
        )

        self.assertEqual([bar.timestamp for bar in bars], ["2024-01-02", "2024-01-03"])
        self.assertEqual(bars[0].volume, 82488700.0)

    def test_fetch_stooq_requires_apikey_when_endpoint_requests_it(self) -> None:
        """
        用途與流程：驗證 fetch stooq requires apikey when endpoint requests it 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with self.assertRaisesRegex(MarketDataValidationError, "requires a free apikey"):
            fetch_stooq_daily_stock(
                "AAPL",
                date(2024, 1, 1),
                date(2024, 1, 10),
                fetch_text=lambda _url: "Get your apikey:\nOpen https://stooq.com",
            )

    def test_fetch_market_data_outputs_loadable_signal_forge_csv(self) -> None:
        """
        用途與流程：驗證 fetch market data outputs loadable signal forge csv 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        payload = {
            "fields": ["日期", "成交股數", "成交金額", "開盤價", "最高價", "最低價", "收盤價"],
            "data": [
                ["113/01/02", "1,000", "10,000", "10.00", "11.00", "9.00", "10.50"],
                ["113/01/03", "1,100", "12,000", "11.00", "12.00", "10.00", "11.50"],
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "signal_forge.data_fetch._fetch_url_text",
                return_value=json.dumps(payload),
            ):
                result = fetch_market_data(
                    market="twse",
                    symbol="2330",
                    start="2024-01-02",
                    end="2024-01-03",
                    output_root=temp_dir,
                )

            bars = load_bars_from_csv(result.processed_csv)
            manifest = json.loads(Path(result.manifest_json).read_text(encoding="utf-8"))

        self.assertEqual(result.row_count, 2)
        self.assertEqual([bar.timestamp for bar in bars], ["2024-01-02", "2024-01-03"])
        self.assertEqual(manifest["data_source"], "TWSE STOCK_DAY")
        self.assertFalse(manifest["adjusted"])


if __name__ == "__main__":
    unittest.main()
