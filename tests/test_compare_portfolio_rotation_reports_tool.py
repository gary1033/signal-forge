from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.compare_portfolio_rotation_reports import (
    build_parser,
    compare_portfolio_rotation_reports,
    format_comparison_markdown,
    write_comparison_json,
    write_comparison_markdown,
)


class ComparePortfolioRotationReportsToolTests(unittest.TestCase):
    def test_parser_accepts_raw_adjusted_and_manifest_paths(self) -> None:
        """
        用途與流程：驗證 raw / adjusted 比較工具 CLI 能接收兩份 summary、adjusted batch manifest 與輸出路徑。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 parser 欄位名稱或預設 rolling cost label 漂移，assertion 會失敗。
        """
        args = build_parser().parse_args(
            [
                "--raw-summary-json",
                "reports/generated/raw.json",
                "--adjusted-summary-json",
                "reports/generated/adjusted.json",
                "--adjusted-batch-manifest-json",
                "reports/generated/adjusted-data/TWSE14_batch.json",
                "--output-json",
                "reports/generated/compare.json",
                "--output-md",
                "reports/generated/compare.md",
            ]
        )

        self.assertEqual(args.raw_summary_json, Path("reports/generated/raw.json"))
        self.assertEqual(args.adjusted_summary_json, Path("reports/generated/adjusted.json"))
        self.assertEqual(
            args.adjusted_batch_manifest_json,
            Path("reports/generated/adjusted-data/TWSE14_batch.json"),
        )
        self.assertEqual(args.rolling_cost_label, "1x")
        self.assertEqual(args.output_json, Path("reports/generated/compare.json"))
        self.assertEqual(args.output_md, Path("reports/generated/compare.md"))

    def test_compare_reports_aligns_full_and_rolling_metrics(self) -> None:
        """
        用途與流程：用小型 raw / adjusted summary fixture 驗證 full-window、rolling-window 與 batch manifest 會被正確對齊。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 delta 計算、weakest rolling 或 manifest 摘要漂移，assertion 會失敗。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_json = root / "raw.json"
            adjusted_json = root / "adjusted.json"
            manifest_json = root / "manifest.json"
            _write_json(raw_json, _summary(raw_ir=1.50, adjusted=False))
            _write_json(adjusted_json, _summary(raw_ir=1.10, adjusted=True))
            _write_json(manifest_json, _manifest())

            comparison = compare_portfolio_rotation_reports(
                raw_summary_json=raw_json,
                adjusted_summary_json=adjusted_json,
                adjusted_batch_manifest_json=manifest_json,
            )

        self.assertEqual(comparison.schema_version, "portfolio_rotation_raw_adjusted_compare.v1")
        self.assertEqual(comparison.adjusted_manifest_summary["row_count_total"], 21479)
        self.assertEqual(len(comparison.full_window), 2)
        first = comparison.full_window[0]
        self.assertEqual(first.cost_label, "1x")
        self.assertAlmostEqual(first.raw_information_ratio or 0.0, 1.50)
        self.assertAlmostEqual(first.adjusted_information_ratio or 0.0, 1.10)
        self.assertAlmostEqual(first.delta_information_ratio or 0.0, -0.40)
        self.assertAlmostEqual(first.delta_max_drawdown or 0.0, -0.10)
        self.assertEqual(len(comparison.rolling_windows), 2)
        self.assertEqual(
            comparison.adjusted_weakest_rolling_window,
            {
                "window_label": "roll02",
                "start": "2021-01-01",
                "end": "2022-12-31",
                "information_ratio": 0.1,
                "benchmark_excess_return": 0.01,
                "max_drawdown": -0.27,
                "top3_group_abs_contribution_share": 0.91,
            },
        )

    def test_writes_json_and_markdown_artifacts(self) -> None:
        """
        用途與流程：驗證比較工具能把 manifest path、full-window delta 與 weakest rolling IR 寫入 deterministic JSON/Markdown。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若輸出 schema 或 Markdown 欄位漂移，assertion 會失敗。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_json = root / "raw.json"
            adjusted_json = root / "adjusted.json"
            manifest_json = root / "manifest.json"
            output_json = root / "compare.json"
            output_md = root / "compare.md"
            _write_json(raw_json, _summary(raw_ir=1.50, adjusted=False))
            _write_json(adjusted_json, _summary(raw_ir=1.10, adjusted=True))
            _write_json(manifest_json, _manifest())
            comparison = compare_portfolio_rotation_reports(
                raw_summary_json=raw_json,
                adjusted_summary_json=adjusted_json,
                adjusted_batch_manifest_json=manifest_json,
            )

            write_comparison_json(comparison, output_json)
            write_comparison_markdown(comparison, output_md)
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")
            direct_markdown = format_comparison_markdown(comparison)

        self.assertEqual(payload["schema_version"], "portfolio_rotation_raw_adjusted_compare.v1")
        self.assertEqual(payload["adjusted_manifest_summary"]["result_count"], 14)
        self.assertEqual(payload["full_window"][0]["delta_information_ratio"], -0.3999999999999999)
        self.assertIn("Adjusted batch manifest", markdown)
        self.assertIn("Weakest adjusted rolling IR: `roll02` = `0.100`", markdown)
        self.assertEqual(markdown, direct_markdown)


def _summary(*, raw_ir: float, adjusted: bool) -> dict[str, object]:
    """
    用途與流程：建立最小 portfolio rotation summary fixture，包含 full-window 與兩個 rolling windows。
    參數：raw_ir 是 full-window IR；adjusted 表示是否使用 adjusted 版本數值。
    回傳與錯誤：回傳 dict；此 helper 不做 I/O。
    """
    if adjusted:
        full_1x = _result("1x", total=16.44, excess=11.60, ir=raw_ir, mdd=-0.28)
        full_3x = _result("3x", total=15.89, excess=11.05, ir=1.12, mdd=-0.29)
        roll01 = _result("1x", total=2.62, excess=1.57, ir=1.56, mdd=-0.18)
        roll02 = _result("1x", total=0.38, excess=0.01, ir=0.10, mdd=-0.27)
    else:
        full_1x = _result("1x", total=17.45, excess=14.09, ir=raw_ir, mdd=-0.18)
        full_3x = _result("3x", total=17.00, excess=13.64, ir=1.49, mdd=-0.19)
        roll01 = _result("1x", total=2.70, excess=1.60, ir=1.60, mdd=-0.17)
        roll02 = _result("1x", total=0.80, excess=0.37, ir=0.81, mdd=-0.19)
    return {
        "results": [full_1x, full_3x],
        "walk_forward_results": [
            {
                "window": {
                    "label": "roll01",
                    "start": "2020-01-01",
                    "end": "2021-12-31",
                },
                "results": [roll01],
            },
            {
                "window": {
                    "label": "roll02",
                    "start": "2021-01-01",
                    "end": "2022-12-31",
                },
                "results": [roll02],
            },
        ],
    }


def _result(
    cost_label: str,
    *,
    total: float,
    excess: float,
    ir: float,
    mdd: float,
) -> dict[str, object]:
    """
    用途與流程：建立比較工具測試所需的最小 result dict。
    參數：cost_label 是成本倍率；total/excess/ir/mdd 是核心績效與風險指標。
    回傳與錯誤：回傳 dict；此 helper 不做驗證。
    """
    return {
        "cost_label": cost_label,
        "total_return": total,
        "benchmark_excess_return": excess,
        "information_ratio": ir,
        "max_drawdown": mdd,
        "active_max_drawdown": -0.20,
        "top3_symbol_abs_contribution_share": 0.47,
        "top3_group_abs_contribution_share": 0.91,
    }


def _manifest() -> dict[str, object]:
    """
    用途與流程：建立 adjusted batch manifest fixture，鎖住比較工具引用資料來源的必要欄位。
    參數：無。
    回傳與錯誤：回傳 dict；此 helper 不做 I/O。
    """
    return {
        "result_count": 14,
        "row_count_total": 21479,
        "missing_adjustment_count_total": 26,
        "skipped_row_count_total": 2482,
        "symbols": ["1301", "2330"],
        "adjustment_method": "source_ohlcv_scaled_by_yahoo_adjclose_ratio",
        "volume_source": "source CSV volume preserved",
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    """
    用途與流程：將測試 fixture 以 UTF-8 JSON 寫入暫存檔。
    參數：path 是輸出路徑；payload 是 JSON 物件。
    回傳與錯誤：回傳 None；寫檔失敗時由 Path.write_text 拋出例外。
    """
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
