from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.portfolio_rotation_group_regime_validation import (
    build_parser,
    format_validation_markdown,
    validate_group_regime,
    write_validation_json,
    write_validation_markdown,
)


class PortfolioRotationGroupRegimeValidationToolTests(unittest.TestCase):
    def test_parser_accepts_summary_thresholds_and_outputs(self) -> None:
        """
        用途與流程：驗證 group regime validation CLI parser 能接收 summary、成本倍率、門檻與輸出路徑。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 parser 欄位、預設值或型別漂移，assertion 會失敗。
        """
        args = build_parser().parse_args(
            [
                "--summary-json",
                "summary.json",
                "--cost-label",
                "3x",
                "--max-top3-group-share",
                "0.85",
                "--max-contribution-exposure-gap",
                "0.25",
                "--output-json",
                "out.json",
                "--output-md",
                "out.md",
            ]
        )

        self.assertEqual(args.summary_json, Path("summary.json"))
        self.assertEqual(args.cost_label, "3x")
        self.assertEqual(args.max_top3_group_share, 0.85)
        self.assertEqual(args.max_contribution_exposure_gap, 0.25)
        self.assertEqual(args.output_json, Path("out.json"))
        self.assertEqual(args.output_md, Path("out.md"))

    def test_validation_classifies_return_regime_and_exposure_windows(self) -> None:
        """
        用途與流程：用小型 portfolio summary fixture 驗證工具能分類 return-regime dominated 與 exposure dominated window。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 gate、分類、worst top3 或 weakest IR 邏輯漂移，assertion 會失敗。
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            summary_json = Path(tmpdir) / "summary.json"
            _write_json(summary_json, _summary_fixture())

            validation = validate_group_regime(
                summary_json,
                max_top3_group_share=0.90,
                max_contribution_exposure_gap=0.30,
            )

        self.assertFalse(validation.gate_pass)
        self.assertEqual(validation.row_count, 3)
        self.assertEqual(validation.high_concentration_count, 2)
        self.assertEqual(validation.return_regime_dominated_count, 2)
        self.assertEqual(validation.exposure_dominated_count, 1)
        self.assertEqual(validation.mixed_count, 0)
        self.assertEqual(validation.worst_top3_group_window["window_label"], "full")
        self.assertEqual(validation.weakest_ir_window["window_label"], "roll01")
        self.assertEqual(validation.rows[0].dominance_type, "return_regime_dominated")
        self.assertIn("contribution_exposure_gap", validation.rows[0].failure_reasons)
        self.assertTrue(validation.rows[2].gate_pass)

    def test_writes_json_and_markdown_artifacts(self) -> None:
        """
        用途與流程：驗證 group regime validation 能輸出 deterministic JSON 與 Markdown，並保留 gate failure reason。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 artifact schema 或 Markdown 摘要漂移，assertion 會失敗。
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            summary_json = root / "summary.json"
            output_json = root / "validation.json"
            output_md = root / "validation.md"
            _write_json(summary_json, _summary_fixture())
            validation = validate_group_regime(summary_json)

            write_validation_json(validation, output_json)
            write_validation_markdown(validation, output_md)

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(
            payload["schema_version"],
            "portfolio_rotation_group_regime_validation.v1",
        )
        self.assertEqual(payload["return_regime_dominated_count"], 2)
        self.assertIn("Gate pass: `false`", markdown)
        self.assertIn("top3_group_contribution_concentration", markdown)
        self.assertEqual(markdown, format_validation_markdown(validation))


def _summary_fixture() -> dict[str, object]:
    """
    用途與流程：建立最小 portfolio rotation summary fixture，包含 full-window 與兩個 rolling windows。
    參數：無。
    回傳與錯誤：回傳 dict；不主動拋錯。
    """
    return {
        "results": [
            _result(
                cost_label="1x",
                ir=1.20,
                excess=1.50,
                mdd=-0.20,
                active_mdd=-0.18,
                max_group="electronics",
                max_group_share=0.75,
                max_exposure_group="semiconductor",
                max_exposure=0.35,
                top3_share=0.93,
                top3_weight=0.66,
                contribution_group_weight=0.20,
            )
        ],
        "walk_forward_results": [
            {
                "window": {
                    "label": "roll01",
                    "start": "2021-01-01",
                    "end": "2022-12-31",
                },
                "results": [
                    _result(
                        cost_label="1x",
                        ir=0.10,
                        excess=0.12,
                        mdd=-0.25,
                        active_mdd=-0.21,
                        max_group="shipping",
                        max_group_share=0.55,
                        max_exposure_group="financial",
                        max_exposure=0.30,
                        top3_share=0.92,
                        top3_weight=0.50,
                        contribution_group_weight=0.10,
                    )
                ],
            },
            {
                "window": {
                    "label": "roll02",
                    "start": "2022-01-01",
                    "end": "2023-12-31",
                },
                "results": [
                    _result(
                        cost_label="1x",
                        ir=0.80,
                        excess=0.33,
                        mdd=-0.12,
                        active_mdd=-0.10,
                        max_group="semiconductor",
                        max_group_share=0.40,
                        max_exposure_group="semiconductor",
                        max_exposure=0.36,
                        top3_share=0.70,
                        top3_weight=0.60,
                        contribution_group_weight=0.32,
                    )
                ],
            },
        ],
    }


def _result(
    *,
    cost_label: str,
    ir: float,
    excess: float,
    mdd: float,
    active_mdd: float,
    max_group: str,
    max_group_share: float,
    max_exposure_group: str,
    max_exposure: float,
    top3_share: float,
    top3_weight: float,
    contribution_group_weight: float,
) -> dict[str, object]:
    """
    用途與流程：建立單一 portfolio result fixture，保留 group contribution 與 exposure validation 需要的欄位。
    參數：cost_label/ir/excess/mdd 定義績效；group 參數定義最大貢獻、最大曝險與 top3 concentration。
    回傳與錯誤：回傳 dict；不主動拋錯。
    """
    return {
        "cost_label": cost_label,
        "start_timestamp": "2020-01-02",
        "end_timestamp": "2026-05-20",
        "information_ratio": ir,
        "benchmark_excess_return": excess,
        "max_drawdown": mdd,
        "active_max_drawdown": active_mdd,
        "max_group_abs_contribution_group": max_group,
        "max_group_abs_contribution_share": max_group_share,
        "max_group_average_weight_group": max_exposure_group,
        "max_group_average_weight": max_exposure,
        "top3_group_abs_contribution_share": top3_share,
        "top3_group_average_weight": top3_weight,
        "group_attribution": [
            _group(max_group, max_group_share, contribution_group_weight),
            _group(max_exposure_group, 0.15, max_exposure),
        ],
    }


def _group(group: str, share: float, weight: float) -> dict[str, object]:
    """
    用途與流程：建立 group attribution fixture row，供 validation 計算貢獻群組的平均曝險。
    參數：group 是群組名稱；share 是絕對貢獻占比；weight 是平均權重。
    回傳與錯誤：回傳 dict；不主動拋錯。
    """
    return {
        "group": group,
        "member_symbols": ["2330"],
        "selected_bar_count": 10,
        "rebalance_selected_count": 2,
        "average_weight": weight,
        "return_contribution": 0.1,
        "absolute_contribution_share": share,
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    """
    用途與流程：以 deterministic JSON 格式寫入 fixture，讓測試讀回時欄位排序穩定。
    參數：path 是輸出路徑；payload 是要寫入的 JSON object。
    回傳與錯誤：回傳 None；寫檔失敗時由 Path.write_text 拋出例外。
    """
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
