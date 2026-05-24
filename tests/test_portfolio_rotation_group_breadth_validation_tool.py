from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.portfolio_rotation_group_breadth_validation import (
    build_parser,
    format_validation_markdown,
    validate_group_breadth,
    write_validation_json,
    write_validation_markdown,
)


class PortfolioRotationGroupBreadthValidationToolTests(unittest.TestCase):
    def test_parser_accepts_csvs_thresholds_and_outputs(self) -> None:
        """
        用途與流程：驗證 group breadth validation CLI parser 可接收 summary、CSV、覆寫頻率、門檻與輸出路徑。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若參數名稱、型別或預設解析漂移，assertion 會失敗。
        """
        args = build_parser().parse_args(
            [
                "--summary-json",
                "summary.json",
                "--csv",
                "a.csv",
                "--csv",
                "b.csv",
                "--cost-label",
                "3x",
                "--rebalance-frequency",
                "daily",
                "--breadth-lookback-bars",
                "2",
                "--positive-threshold",
                "0.01",
                "--symbol-group",
                "AAA:growth",
                "--min-group-member-count",
                "3",
                "--min-average-positive-member-share",
                "0.70",
                "--min-majority-positive-rebalance-share",
                "0.60",
                "--min-average-member-return",
                "0.02",
                "--min-rebalance-count",
                "4",
                "--max-top3-group-share",
                "0.85",
                "--output-json",
                "out.json",
                "--output-md",
                "out.md",
            ]
        )

        self.assertEqual(args.summary_json, Path("summary.json"))
        self.assertEqual(args.csv, ["a.csv", "b.csv"])
        self.assertEqual(args.cost_label, "3x")
        self.assertEqual(args.rebalance_frequency, "daily")
        self.assertEqual(args.breadth_lookback_bars, 2)
        self.assertEqual(args.positive_threshold, 0.01)
        self.assertEqual(args.symbol_group, ["AAA:growth"])
        self.assertEqual(args.min_group_member_count, 3)
        self.assertEqual(args.min_average_positive_member_share, 0.70)
        self.assertEqual(args.min_majority_positive_rebalance_share, 0.60)
        self.assertEqual(args.min_average_member_return, 0.02)
        self.assertEqual(args.min_rebalance_count, 4)
        self.assertEqual(args.max_top3_group_share, 0.85)
        self.assertEqual(args.output_json, Path("out.json"))
        self.assertEqual(args.output_md, Path("out.md"))

    def test_validation_classifies_broad_and_single_member_windows(self) -> None:
        """
        用途與流程：用三檔股票 fixture 驗證工具能把雙成員廣泛同漲群組與單成員 dominant group 分開。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 breadth 分類、gate reason 或 weakest window 邏輯漂移，assertion 會失敗。
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            csv_paths = _write_csv_fixtures(root)
            summary_json = root / "summary.json"
            _write_json(summary_json, _summary_fixture())

            validation = validate_group_breadth(
                summary_json,
                csv_paths,
                start="2024-01-01",
                end="2024-01-06",
                cost_label="1x",
                rebalance_frequency="daily",
                breadth_lookback_bars=2,
                min_average_positive_member_share=0.60,
                min_majority_positive_rebalance_share=0.50,
                min_rebalance_count=2,
                max_top3_group_share=0.90,
            )

        self.assertFalse(validation.gate_pass)
        self.assertEqual(validation.row_count, 2)
        self.assertEqual(validation.broad_group_momentum_count, 1)
        self.assertEqual(validation.single_member_dominant_count, 1)
        self.assertEqual(validation.high_concentration_count, 1)
        self.assertEqual(validation.rows[0].breadth_type, "broad_group_momentum")
        self.assertTrue(validation.rows[0].gate_pass)
        self.assertEqual(validation.rows[0].dominant_group_member_count, 2)
        self.assertEqual(
            validation.rows[0].dominant_group_average_positive_member_share,
            1.0,
        )
        self.assertEqual(validation.rows[1].breadth_type, "single_member_group")
        self.assertIn("single_member_dominant_group", validation.rows[1].failure_reasons)
        self.assertIn(
            "top3_group_contribution_concentration",
            validation.rows[1].failure_reasons,
        )
        self.assertEqual(validation.weakest_ir_window["window_label"], "roll01")

    def test_writes_json_and_markdown_artifacts(self) -> None:
        """
        用途與流程：驗證 group breadth validation 可輸出 deterministic JSON 與 Markdown，並保留 single-member failure reason。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 artifact schema 或 Markdown 摘要漂移，assertion 會失敗。
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            csv_paths = _write_csv_fixtures(root)
            summary_json = root / "summary.json"
            output_json = root / "validation.json"
            output_md = root / "validation.md"
            _write_json(summary_json, _summary_fixture())
            validation = validate_group_breadth(
                summary_json,
                csv_paths,
                rebalance_frequency="daily",
                breadth_lookback_bars=2,
                min_rebalance_count=2,
            )

            write_validation_json(validation, output_json)
            write_validation_markdown(validation, output_md)

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(
            payload["schema_version"],
            "portfolio_rotation_group_breadth_validation.v1",
        )
        self.assertEqual(payload["single_member_dominant_count"], 1)
        self.assertIn("Gate pass: `false`", markdown)
        self.assertIn("single_member_dominant_group", markdown)
        self.assertEqual(markdown, format_validation_markdown(validation))


def _summary_fixture() -> dict[str, object]:
    """
    用途與流程：建立最小 portfolio rotation summary fixture，包含 full-window 與一個 rolling window 的 dominant group。
    參數：無。
    回傳與錯誤：回傳 dict；不主動拋錯。
    """
    return {
        "results": [
            _result(
                group="growth",
                top3_share=0.80,
                ir=1.20,
                excess=0.40,
                symbol_groups={"AAA": "growth", "BBB": "growth", "CCC": "single"},
            )
        ],
        "walk_forward_results": [
            {
                "window": {
                    "label": "roll01",
                    "start": "2024-01-01",
                    "end": "2024-01-06",
                },
                "results": [
                    _result(
                        group="single",
                        top3_share=0.92,
                        ir=0.10,
                        excess=0.05,
                        symbol_groups={
                            "AAA": "growth",
                            "BBB": "growth",
                            "CCC": "single",
                        },
                    )
                ],
            }
        ],
    }


def _result(
    *,
    group: str,
    top3_share: float,
    ir: float,
    excess: float,
    symbol_groups: dict[str, str],
) -> dict[str, object]:
    """
    用途與流程：建立單一 portfolio result fixture，保留 group breadth validation 需要的 summary 欄位。
    參數：group 是 dominant contribution group；top3_share/ir/excess 是績效與集中度；symbol_groups 是分組表。
    回傳與錯誤：回傳 dict；不主動拋錯。
    """
    return {
        "cost_label": "1x",
        "rebalance_frequency": "daily",
        "breadth_lookback_bars": 2,
        "breadth_positive_threshold": 0.0,
        "start_timestamp": "2024-01-01",
        "end_timestamp": "2024-01-06",
        "information_ratio": ir,
        "benchmark_excess_return": excess,
        "max_drawdown": -0.10,
        "active_max_drawdown": -0.08,
        "max_group_abs_contribution_group": group,
        "max_group_abs_contribution_share": 0.60,
        "top3_group_abs_contribution_share": top3_share,
        "symbol_groups": symbol_groups,
    }


def _write_csv_fixtures(root: Path) -> list[Path]:
    """
    用途與流程：寫入三檔小型 OHLCV CSV fixture，兩檔 growth 成員持續正動能，一檔 single 成員供單成員 dominant 測試。
    參數：root 是暫存資料夾。
    回傳與錯誤：回傳 CSV 路徑清單；寫檔失敗時由 pathlib 拋出例外。
    """
    dates = [
        "2024-01-01",
        "2024-01-02",
        "2024-01-03",
        "2024-01-04",
        "2024-01-05",
        "2024-01-06",
    ]
    fixtures = {
        "AAA": [10, 11, 12, 13, 14, 15],
        "BBB": [20, 21, 22, 23, 24, 25],
        "CCC": [30, 31, 32, 33, 34, 35],
    }
    paths: list[Path] = []
    for symbol, closes in fixtures.items():
        path = root / f"TWSE_{symbol}_1D.csv"
        lines = ["timestamp,open,high,low,close,volume"]
        for timestamp, close in zip(dates, closes):
            lines.append(f"{timestamp},{close},{close},{close},{close},1000")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        paths.append(path)
    return paths


def _write_json(path: Path, payload: dict[str, object]) -> None:
    """
    用途與流程：以 deterministic JSON 寫入 summary fixture，避免測試受到欄位排序干擾。
    參數：path 是輸出路徑；payload 是 JSON object。
    回傳與錯誤：回傳 None；寫檔失敗時由 pathlib 拋出例外。
    """
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
