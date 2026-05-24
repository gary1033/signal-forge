from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.portfolio_rotation_universe_select import (
    build_parser,
    format_universe_selection_markdown,
    load_audit_json,
    run_universe_selection,
    write_universe_selection_json,
    write_universe_selection_markdown,
)


class PortfolioRotationUniverseSelectToolTests(unittest.TestCase):
    def test_parser_accepts_selection_options(self) -> None:
        """
        用途與流程：驗證 high-quality universe selector CLI 能接收 audit JSON、流動性門檻、群組成員門檻、每組上限與輸出路徑。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 parser 欄位或預設值漂移，assertion 會失敗。
        """
        args = build_parser().parse_args(
            [
                "--audit-json",
                "reports/generated/twse35-universe-audit-require-adjusted-20260524.json",
                "--min-average-traded-value",
                "1000000000",
                "--min-eligible-members-per-group",
                "2",
                "--max-symbols-per-group",
                "3",
                "--summary-json",
                "reports/generated/selection.json",
                "--summary-md",
                "reports/generated/selection.md",
            ]
        )

        self.assertEqual(
            args.audit_json,
            Path("reports/generated/twse35-universe-audit-require-adjusted-20260524.json"),
        )
        self.assertEqual(args.min_average_traded_value, 1_000_000_000.0)
        self.assertEqual(args.min_eligible_members_per_group, 2)
        self.assertEqual(args.max_symbols_per_group, 3)
        self.assertEqual(args.summary_json, Path("reports/generated/selection.json"))
        self.assertEqual(args.summary_md, Path("reports/generated/selection.md"))

    def test_selection_caps_groups_and_excludes_weak_sources(self) -> None:
        """
        用途與流程：用合成 audit payload 驗證 selector 只從 eligible rows 挑選，依成交金額排序，套用每組上限，並排除候選數不足的群組。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 selected symbols、rank 或排除原因漂移，assertion 會失敗。
        """
        selection = run_universe_selection(
            _audit_payload(),
            source_audit_json="audit.json",
            min_average_traded_value=500_000_000.0,
            min_eligible_members_per_group=2,
            max_symbols_per_group=2,
        )

        rows = {row.symbol: row for row in selection.rows}
        self.assertEqual(
            selection.selected_symbols,
            ["2308", "2317", "2330", "2454", "2881", "2882"],
        )
        self.assertEqual(selection.selected_symbol_count, 6)
        self.assertTrue(rows["2317"].selected)
        self.assertEqual(rows["2317"].rank_in_group, 1)
        self.assertFalse(rows["2327"].selected)
        self.assertIn("group_cap_excluded", rows["2327"].selection_reasons)
        self.assertFalse(rows["2603"].selected)
        self.assertIn("source_not_eligible", rows["2603"].selection_reasons)
        self.assertFalse(rows["1101"].selected)
        self.assertIn("eligible_group_members_below_threshold", rows["1101"].selection_reasons)
        self.assertEqual(selection.selected_symbols_by_group["electronics"], ["2317", "2308"])

    def test_selection_respects_extra_liquidity_threshold(self) -> None:
        """
        用途與流程：驗證 selector 額外流動性門檻會在 audit eligible 之上再排除成交金額不足的股票。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 selector_liquidity_below_threshold 原因消失，assertion 會失敗。
        """
        selection = run_universe_selection(
            _audit_payload(),
            source_audit_json=None,
            min_average_traded_value=1_000_000_000.0,
            min_eligible_members_per_group=2,
            max_symbols_per_group=3,
        )

        rows = {row.symbol: row for row in selection.rows}
        self.assertFalse(rows["2881"].selected)
        self.assertIn("selector_liquidity_below_threshold", rows["2881"].selection_reasons)
        self.assertFalse(rows["2882"].selected)
        self.assertIn("selector_liquidity_below_threshold", rows["2882"].selection_reasons)
        self.assertNotIn("financial", selection.selected_symbols_by_group)

    def test_writes_json_and_markdown_artifacts(self) -> None:
        """
        用途與流程：驗證 high-quality universe selection 可寫出 deterministic JSON/Markdown，供後續回測和筆記引用。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 schema、selected list 或 Markdown 表格漂移，assertion 會失敗。
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            audit_json = root / "audit.json"
            output_json = root / "selection.json"
            output_md = root / "selection.md"
            audit_json.write_text(
                json.dumps(_audit_payload(), ensure_ascii=False),
                encoding="utf-8",
            )

            audit = load_audit_json(audit_json)
            selection = run_universe_selection(
                audit,
                source_audit_json=audit_json.as_posix(),
                min_average_traded_value=None,
                min_eligible_members_per_group=2,
                max_symbols_per_group=2,
            )
            write_universe_selection_json(selection, output_json)
            write_universe_selection_markdown(selection, output_md)
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(payload["schema_version"], "portfolio_rotation_universe_selection.v1")
        self.assertEqual(payload["selected_symbol_count"], 6)
        self.assertIn("Selected list", markdown)
        self.assertIn("| 2317 | yes | electronics | 1 |", markdown)
        self.assertEqual(markdown, format_universe_selection_markdown(selection))


def _audit_payload() -> dict[str, object]:
    """
    用途與流程：建立 selector 測試用的最小 universe audit payload，涵蓋多成員群組、單成員群組、source diagnostic-only 與 group cap。
    參數：無。
    回傳與錯誤：回傳 dict；此函式不做 I/O。
    """
    return {
        "schema_version": "portfolio_rotation_universe_audit.v1",
        "rows": [
            _row("2317", "electronics", 2_000_000_000.0),
            _row("2308", "electronics", 1_500_000_000.0),
            _row("2327", "electronics", 1_000_000_000.0),
            _row("2330", "semiconductor", 3_000_000_000.0),
            _row("2454", "semiconductor", 2_500_000_000.0),
            _row("2881", "financial", 900_000_000.0),
            _row("2882", "financial", 800_000_000.0),
            _row("1101", "cement", 700_000_000.0),
            _row(
                "2603",
                "shipping",
                5_000_000_000.0,
                decision="diagnostic-only",
                failure_reasons=["group_members_below_threshold"],
            ),
        ],
    }


def _row(
    symbol: str,
    group: str,
    average_traded_value: float,
    *,
    decision: str = "eligible",
    failure_reasons: list[str] | None = None,
) -> dict[str, object]:
    """
    用途與流程：建立單筆 audit row fixture，讓測試可控制 group、流動性與來源 eligibility。
    參數：symbol 是股票代號；group 是群組名稱；average_traded_value 是平均成交金額；decision/failure_reasons 模擬 universe audit 結果。
    回傳與錯誤：回傳 dict；此函式不做 I/O。
    """
    return {
        "symbol": symbol,
        "group": group,
        "decision": decision,
        "average_traded_value": average_traded_value,
        "row_count": 1500,
        "failure_reasons": failure_reasons or [],
    }


if __name__ == "__main__":
    unittest.main()
