from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.portfolio_rotation_promotion_gate import (
    build_parser,
    build_promotion_gate,
    format_promotion_gate_markdown,
    write_promotion_gate_json,
    write_promotion_gate_markdown,
)


class PortfolioRotationPromotionGateToolTests(unittest.TestCase):
    def test_parser_accepts_artifact_paths_and_thresholds(self) -> None:
        """
        用途與流程：驗證 promotion gate CLI 能接收 summary、raw/adjusted、group regime、group breadth 與門檻參數。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 parser 欄位名稱、預設成本標籤或門檻漂移，assertion 會失敗。
        """
        args = build_parser().parse_args(
            [
                "--summary-json",
                "reports/generated/summary.json",
                "--raw-adjusted-comparison-json",
                "reports/generated/compare.json",
                "--group-regime-validation-json",
                "reports/generated/regime.json",
                "--group-breadth-validation-json",
                "reports/generated/breadth.json",
                "--min-rolling-ir",
                "0.60",
                "--output-json",
                "reports/generated/gate.json",
                "--output-md",
                "reports/generated/gate.md",
            ]
        )

        self.assertEqual(args.summary_json, Path("reports/generated/summary.json"))
        self.assertEqual(
            args.raw_adjusted_comparison_json,
            Path("reports/generated/compare.json"),
        )
        self.assertEqual(args.primary_cost_label, "1x")
        self.assertEqual(args.stress_cost_label, "3x")
        self.assertEqual(args.min_rolling_ir, 0.60)
        self.assertEqual(args.output_json, Path("reports/generated/gate.json"))
        self.assertEqual(args.output_md, Path("reports/generated/gate.md"))

    def test_gate_passes_when_all_required_evidence_passes(self) -> None:
        """
        用途與流程：用最小 fixture 驗證 full、stress、rolling、raw/adjusted 與 group diagnostics 全通過時 decision 為 keep。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 promotion gate 合併邏輯或 decision 名稱漂移，assertion 會失敗。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            summary = root / "summary.json"
            comparison = root / "compare.json"
            regime = root / "regime.json"
            breadth = root / "breadth.json"
            _write_json(summary, _summary(pass_gate=True))
            _write_json(comparison, _comparison(pass_gate=True))
            _write_json(regime, _regime(pass_gate=True))
            _write_json(breadth, _breadth(pass_gate=True))

            gate = build_promotion_gate(
                summary_json=summary,
                raw_adjusted_comparison_json=comparison,
                group_regime_validation_json=regime,
                group_breadth_validation_json=breadth,
            )

        self.assertEqual(gate.schema_version, "portfolio_rotation_promotion_gate.v1")
        self.assertEqual(gate.decision, "keep")
        self.assertTrue(gate.gate_pass)
        self.assertEqual(gate.failure_reasons, [])
        self.assertEqual(gate.metrics["rolling_windows"]["min_information_ratio"], 0.62)
        self.assertTrue(gate.diagnostics["raw_adjusted_comparison"]["gate_pass"])

    def test_gate_fails_on_rolling_concentration_and_group_diagnostics(self) -> None:
        """
        用途與流程：用失敗 fixture 驗證 rolling IR、集中度、raw/adjusted 降級與群組診斷會合併成 compare-only。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 failure reason 對應關係漂移，assertion 會失敗。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            summary = root / "summary.json"
            comparison = root / "compare.json"
            regime = root / "regime.json"
            breadth = root / "breadth.json"
            _write_json(summary, _summary(pass_gate=False))
            _write_json(comparison, _comparison(pass_gate=False))
            _write_json(regime, _regime(pass_gate=False))
            _write_json(breadth, _breadth(pass_gate=False))

            gate = build_promotion_gate(
                summary_json=summary,
                raw_adjusted_comparison_json=comparison,
                group_regime_validation_json=regime,
                group_breadth_validation_json=breadth,
            )

        self.assertEqual(gate.decision, "compare-only")
        self.assertFalse(gate.gate_pass)
        self.assertIn("rolling_ir_below_threshold", gate.failure_reasons)
        self.assertIn("group_concentration_above_threshold", gate.failure_reasons)
        self.assertIn("raw_adjusted_ir_drop_above_threshold", gate.failure_reasons)
        self.assertIn("group_regime_gate_failed", gate.failure_reasons)
        self.assertIn("group_breadth_gate_failed", gate.failure_reasons)
        self.assertIn("single_member_dominant_group", gate.failure_reasons)
        self.assertIn("narrow_group_momentum", gate.failure_reasons)

    def test_writes_json_and_markdown_artifacts(self) -> None:
        """
        用途與流程：驗證 promotion gate 可寫出 deterministic JSON/Markdown，供實驗紀錄引用。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 schema、Markdown 標題或輸出內容漂移，assertion 會失敗。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            summary = root / "summary.json"
            comparison = root / "compare.json"
            regime = root / "regime.json"
            breadth = root / "breadth.json"
            output_json = root / "gate.json"
            output_md = root / "gate.md"
            _write_json(summary, _summary(pass_gate=False))
            _write_json(comparison, _comparison(pass_gate=False))
            _write_json(regime, _regime(pass_gate=False))
            _write_json(breadth, _breadth(pass_gate=False))
            gate = build_promotion_gate(
                summary_json=summary,
                raw_adjusted_comparison_json=comparison,
                group_regime_validation_json=regime,
                group_breadth_validation_json=breadth,
            )

            write_promotion_gate_json(gate, output_json)
            write_promotion_gate_markdown(gate, output_md)
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(payload["schema_version"], "portfolio_rotation_promotion_gate.v1")
        self.assertEqual(payload["decision"], "compare-only")
        self.assertIn("Portfolio Rotation Promotion Gate", markdown)
        self.assertIn("group_breadth_gate_failed", markdown)
        self.assertEqual(markdown, format_promotion_gate_markdown(gate))


def _summary(*, pass_gate: bool) -> dict[str, object]:
    """
    用途與流程：建立 promotion gate 測試用 portfolio summary fixture，包含 full-window 與兩個 rolling windows。
    參數：pass_gate 表示是否建立可通過門檻的數值。
    回傳與錯誤：回傳 dict；此 helper 不做 I/O。
    """
    if pass_gate:
        full = _result("1x", ir=1.20, excess=0.50, mdd=-0.20, symbol=0.50, group=0.70)
        stress = _result("3x", ir=0.90, excess=0.45, mdd=-0.21, symbol=0.50, group=0.70)
        rolling = [
            _result("1x", ir=0.62, excess=0.10, mdd=-0.18, symbol=0.55, group=0.72),
            _result("1x", ir=0.70, excess=0.12, mdd=-0.16, symbol=0.57, group=0.74),
        ]
    else:
        full = _result("1x", ir=1.10, excess=0.50, mdd=-0.35, symbol=0.82, group=0.94)
        stress = _result("3x", ir=0.60, excess=0.30, mdd=-0.36, symbol=0.82, group=0.94)
        rolling = [
            _result("1x", ir=0.20, excess=0.02, mdd=-0.34, symbol=0.84, group=0.96),
            _result("1x", ir=0.30, excess=0.04, mdd=-0.32, symbol=0.83, group=0.95),
        ]
    return {
        "results": [full, stress],
        "walk_forward_results": [
            {
                "window": {
                    "label": "roll01",
                    "start": "2020-01-01",
                    "end": "2021-12-31",
                },
                "results": [rolling[0]],
            },
            {
                "window": {
                    "label": "roll02",
                    "start": "2021-01-01",
                    "end": "2022-12-31",
                },
                "results": [rolling[1]],
            },
        ],
    }


def _result(
    cost_label: str,
    *,
    ir: float,
    excess: float,
    mdd: float,
    symbol: float,
    group: float,
) -> dict[str, object]:
    """
    用途與流程：建立 promotion gate 測試所需的最小 portfolio result dict。
    參數：cost_label 是成本倍率；ir/excess/mdd/symbol/group 是 gate 使用的核心指標。
    回傳與錯誤：回傳 dict；此 helper 不做驗證。
    """
    return {
        "cost_label": cost_label,
        "strategy": "portfolio-relative-momentum-rotation",
        "rebalance_frequency": "monthly",
        "lookback_bars": 21,
        "ranking_skip_bars": 0,
        "top_n": 3,
        "min_return": 0.0,
        "breadth_filter": True,
        "breadth_lookback_bars": 42,
        "breadth_min_positive_count": 4,
        "max_consecutive_selections_per_symbol": 5,
        "liquidity_lookback_bars": 20,
        "min_average_traded_value": 500_000_000.0,
        "symbol_count": 14,
        "start_timestamp": "2020-01-01",
        "end_timestamp": "2022-12-31",
        "total_return": excess + 0.10,
        "benchmark_excess_return": excess,
        "information_ratio": ir,
        "max_drawdown": mdd,
        "active_max_drawdown": mdd + 0.05,
        "top3_symbol_abs_contribution_share": symbol,
        "top3_group_abs_contribution_share": group,
    }


def _comparison(*, pass_gate: bool) -> dict[str, object]:
    """
    用途與流程：建立 raw/adjusted comparison fixture，控制 adjusted IR 降幅與 drawdown 惡化是否通過。
    參數：pass_gate 表示是否建立可通過門檻的 comparison。
    回傳與錯誤：回傳 dict；此 helper 不做 I/O。
    """
    delta_ir = -0.10 if pass_gate else -0.40
    delta_mdd = -0.02 if pass_gate else -0.08
    return {
        "schema_version": "portfolio_rotation_raw_adjusted_compare.v1",
        "full_window": [
            {
                "cost_label": "1x",
                "delta_information_ratio": delta_ir,
                "delta_max_drawdown": delta_mdd,
            }
        ],
        "adjusted_weakest_rolling_window": {
            "window_label": "roll01",
            "information_ratio": 0.62 if pass_gate else 0.20,
        },
    }


def _regime(*, pass_gate: bool) -> dict[str, object]:
    """
    用途與流程：建立 group regime validation fixture，控制 gate_pass 與 regime count。
    參數：pass_gate 表示是否建立通過的 validation。
    回傳與錯誤：回傳 dict；此 helper 不做 I/O。
    """
    return {
        "schema_version": "portfolio_rotation_group_regime_validation.v1",
        "gate_pass": pass_gate,
        "high_concentration_count": 0 if pass_gate else 3,
        "return_regime_dominated_count": 0 if pass_gate else 3,
        "exposure_dominated_count": 0,
        "mixed_count": 0,
        "row_count": 3,
    }


def _breadth(*, pass_gate: bool) -> dict[str, object]:
    """
    用途與流程：建立 group breadth validation fixture，控制單成員與窄廣度失敗是否出現。
    參數：pass_gate 表示是否建立通過的 validation。
    回傳與錯誤：回傳 dict；此 helper 不做 I/O。
    """
    return {
        "schema_version": "portfolio_rotation_group_breadth_validation.v1",
        "gate_pass": pass_gate,
        "high_concentration_count": 0 if pass_gate else 3,
        "broad_group_momentum_count": 3 if pass_gate else 0,
        "narrow_group_momentum_count": 0 if pass_gate else 1,
        "single_member_dominant_count": 0 if pass_gate else 2,
        "missing_breadth_count": 0,
        "row_count": 3,
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    """
    用途與流程：將測試 fixture 寫成 UTF-8 JSON 檔，供 promotion gate 讀取。
    參數：path 是輸出路徑；payload 是 JSON object。
    回傳與錯誤：回傳 None；寫檔失敗時由 pathlib 拋出例外。
    """
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
