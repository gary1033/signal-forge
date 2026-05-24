from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.portfolio_rotation_universe_audit import (
    build_parser,
    format_universe_audit_markdown,
    run_universe_audit,
    write_universe_audit_json,
    write_universe_audit_markdown,
)


class PortfolioRotationUniverseAuditToolTests(unittest.TestCase):
    def test_parser_accepts_universe_audit_options(self) -> None:
        """
        用途與流程：驗證 universe audit CLI 能接收 CSV 清單、分組、門檻、adjusted 目錄與輸出路徑。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 parser 欄位或預設門檻漂移，assertion 會失敗。
        """
        args = build_parser().parse_args(
            [
                "--csv",
                "data/processed/TWSE_2330_1D.csv",
                "--start",
                "2020-01-01",
                "--end",
                "2026-05-20",
                "--min-row-count",
                "1200",
                "--min-average-traded-value",
                "500000000",
                "--min-group-members",
                "2",
                "--adjusted-csv-dir",
                "reports/generated/adjusted-data",
                "--require-adjusted-csv",
                "--symbol-group",
                "2330:semiconductor",
                "--summary-json",
                "reports/generated/universe.json",
                "--summary-md",
                "reports/generated/universe.md",
            ]
        )

        self.assertEqual(args.csv, ["data/processed/TWSE_2330_1D.csv"])
        self.assertEqual(args.start, "2020-01-01")
        self.assertEqual(args.end, "2026-05-20")
        self.assertEqual(args.min_row_count, 1200)
        self.assertEqual(args.min_average_traded_value, 500_000_000.0)
        self.assertEqual(args.min_group_members, 2)
        self.assertEqual(args.adjusted_csv_dir, Path("reports/generated/adjusted-data"))
        self.assertTrue(args.require_adjusted_csv)
        self.assertEqual(args.symbol_group, ["2330:semiconductor"])
        self.assertEqual(args.summary_json, Path("reports/generated/universe.json"))
        self.assertEqual(args.summary_md, Path("reports/generated/universe.md"))

    def test_run_universe_audit_marks_history_liquidity_group_and_adjusted_failures(self) -> None:
        """
        用途與流程：用暫存 OHLCV 檔驗證逐股 audit 會標記歷史長度、成交金額、群組成員數與 adjusted CSV 缺失。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 decision、failure reason 或 group summary 漂移，assertion 會失敗。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            data_dir = root / "data"
            adjusted_dir = root / "adjusted"
            data_dir.mkdir()
            adjusted_dir.mkdir()
            csv_2330 = data_dir / "TWSE_2330_1D.csv"
            csv_2454 = data_dir / "TWSE_2454_1D.csv"
            csv_2603 = data_dir / "TWSE_2603_1D.csv"
            _write_csv(csv_2330, volumes=(10_000_000, 10_000_000, 10_000_000))
            _write_csv(csv_2454, volumes=(8_000_000, 8_000_000, 8_000_000))
            _write_csv(csv_2603, volumes=(1, 1, 1))
            (adjusted_dir / "TWSEADJ_2330_1D.csv").write_text(
                "timestamp,open,high,low,close,volume\n",
                encoding="utf-8",
            )
            (adjusted_dir / "TWSEADJ_2454_1D.csv").write_text(
                "timestamp,open,high,low,close,volume\n",
                encoding="utf-8",
            )

            audit = run_universe_audit(
                csv_paths=[csv_2330, csv_2454, csv_2603],
                start="2024-01-01",
                end="2024-01-03",
                min_row_count=3,
                min_average_traded_value=500_000_000.0,
                min_group_members=2,
                adjusted_csv_dir=adjusted_dir,
                require_adjusted_csv=True,
                symbol_groups={
                    "2330": "semiconductor",
                    "2454": "semiconductor",
                    "2603": "shipping",
                },
            )

        rows = {row.symbol: row for row in audit.rows}
        self.assertEqual(audit.symbol_count, 3)
        self.assertEqual(audit.eligible_symbol_count, 2)
        self.assertEqual(audit.adjusted_available_count, 2)
        self.assertEqual(audit.singleton_group_count, 1)
        self.assertEqual(rows["2330"].decision, "eligible")
        self.assertEqual(rows["2454"].decision, "eligible")
        self.assertEqual(rows["2603"].decision, "diagnostic-only")
        self.assertIn("liquidity_below_threshold", rows["2603"].failure_reasons)
        self.assertIn("group_members_below_threshold", rows["2603"].failure_reasons)
        self.assertIn("adjusted_csv_missing", rows["2603"].failure_reasons)
        self.assertEqual(audit.groups[0].group, "semiconductor")
        self.assertEqual(audit.groups[0].eligible_member_count, 2)

    def test_writes_json_and_markdown_artifacts(self) -> None:
        """
        用途與流程：驗證 universe audit 可寫成 deterministic JSON/Markdown，供實驗紀錄引用。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 schema、Markdown 表格或寫檔格式漂移，assertion 會失敗。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            csv_path = root / "TWSE_2330_1D.csv"
            _write_csv(csv_path, volumes=(10_000_000, 10_000_000, 10_000_000))
            audit = run_universe_audit(
                csv_paths=[csv_path],
                start=None,
                end=None,
                min_row_count=3,
                min_average_traded_value=500_000_000.0,
                min_group_members=1,
                adjusted_csv_dir=None,
                require_adjusted_csv=False,
                symbol_groups={"2330": "semiconductor"},
            )
            output_json = root / "universe.json"
            output_md = root / "universe.md"

            write_universe_audit_json(audit, output_json)
            write_universe_audit_markdown(audit, output_md)
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(payload["schema_version"], "portfolio_rotation_universe_audit.v1")
        self.assertEqual(payload["eligible_symbol_count"], 1)
        self.assertIn("Portfolio Rotation Universe Audit", markdown)
        self.assertIn("| 2330 | eligible | semiconductor | 3 |", markdown)
        self.assertEqual(markdown, format_universe_audit_markdown(audit))


def _write_csv(path: Path, *, volumes: tuple[int, ...]) -> None:
    """
    用途與流程：寫入最小 OHLCV CSV fixture，讓 universe audit 測試可控制資料筆數與成交金額。
    參數：path 是輸出 CSV 路徑；volumes 是每個交易日的成交量序列，價格固定為 100。
    回傳與錯誤：回傳 None；檔案寫入失敗時由 Path.write_text 拋出例外。
    """
    rows = ["timestamp,open,high,low,close,volume"]
    for index, volume in enumerate(volumes, start=1):
        rows.append(f"2024-01-0{index},100,110,90,100,{volume}")
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
