from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.multi_stock_target_state_sweep import WalkForwardWindow
from tools.portfolio_rotation_grid_search import (
    build_parser,
    format_grid_search_markdown,
    run_portfolio_rotation_grid_search,
    write_grid_search_json,
    write_grid_search_markdown,
)
from tools.portfolio_rotation_sweep import (
    PortfolioGroupAttribution,
    PortfolioRotationResult,
    PortfolioSymbolAttribution,
    PortfolioWalkForwardResult,
)


class PortfolioRotationGridSearchToolTests(unittest.TestCase):
    def test_parser_accepts_parameter_grid_and_outputs(self) -> None:
        """
        用途與流程：驗證 grid search CLI 能接收 top-N、breadth、liquidity、max-consecutive 清單與輸出路徑。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 parser 欄位名稱或預設成本標籤漂移，assertion 會失敗。
        """
        args = build_parser().parse_args(
            [
                "--csv",
                "reports/generated/adjusted-data/TWSEADJ_2330_1D.csv",
                "--start",
                "2020-01-01",
                "--end",
                "2026-05-20",
                "--top-n-list",
                "3,4",
                "--breadth-min-positive-count-list",
                "2,3",
                "--min-average-traded-value-list",
                "none,500000000",
                "--max-consecutive-selections-list",
                "none,5",
                "--summary-json",
                "reports/generated/grid.json",
                "--summary-md",
                "reports/generated/grid.md",
            ]
        )

        self.assertEqual(args.top_n_list, "3,4")
        self.assertEqual(args.breadth_min_positive_count_list, "2,3")
        self.assertEqual(args.min_average_traded_value_list, "none,500000000")
        self.assertEqual(args.max_consecutive_selections_list, "none,5")
        self.assertEqual(args.primary_cost_label, "1x")
        self.assertEqual(args.stress_cost_label, "3x")
        self.assertEqual(args.summary_json, Path("reports/generated/grid.json"))
        self.assertEqual(args.summary_md, Path("reports/generated/grid.md"))

    def test_grid_search_ranks_gate_pass_before_high_full_ir_failure(self) -> None:
        """
        用途與流程：用 mock 回測結果驗證排名先看 rolling stability gate，再看 full-window IR。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 gate、failure reason 或 rank 邏輯漂移，assertion 會失敗。
        """
        with (
            patch(
                "tools.portfolio_rotation_grid_search.run_portfolio_rotation_sweep",
                side_effect=_mock_sweep,
            ),
            patch(
                "tools.portfolio_rotation_grid_search.run_walk_forward_rotation",
                side_effect=_mock_walk_forward,
            ),
        ):
            search = run_portfolio_rotation_grid_search(
                csv_paths=[Path("a.csv"), Path("b.csv")],
                start="2020-01-01",
                end="2023-12-31",
                cost_multipliers=(1.0, 3.0),
                primary_cost_label="1x",
                stress_cost_label="3x",
                initial_equity=10_000.0,
                commission_bps=1.0,
                slippage_bps=1.0,
                transaction_tax_bps=0.0,
                rebalance_frequency="monthly",
                lookback_bars=21,
                min_return=0.0,
                periods_per_year=252,
                top_n_values=[4, 3],
                breadth_lookback_bars=42,
                breadth_min_positive_count_values=[3],
                breadth_positive_threshold=0.0,
                liquidity_lookback_bars=20,
                min_average_traded_value_values=[500_000_000.0],
                max_consecutive_selection_values=[5],
                symbol_groups={},
                rolling_window_months=24,
                rolling_step_months=12,
                rolling_min_months=12,
                thresholds={
                    "min_full_ir": 1.0,
                    "min_rolling_ir": 0.20,
                    "min_rolling_excess_return": 0.0,
                    "max_drawdown_abs": 0.30,
                    "max_top3_group_share": 0.90,
                },
            )

        self.assertEqual(search.candidate_count, 2)
        self.assertEqual(search.rows[0].rank, 1)
        self.assertEqual(search.rows[0].top_n, 3)
        self.assertEqual(search.rows[0].decision, "candidate")
        self.assertTrue(search.rows[0].gate_pass)
        self.assertEqual(search.rows[0].failure_reasons, [])
        self.assertEqual(search.rows[1].top_n, 4)
        self.assertEqual(search.rows[1].decision, "compare-only")
        self.assertIn("rolling_ir_below_threshold", search.rows[1].failure_reasons)

    def test_writes_json_and_markdown_artifacts(self) -> None:
        """
        用途與流程：驗證 grid search 結果可寫成 deterministic JSON/Markdown，供實驗紀錄引用。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 schema、ranking 表格或寫檔格式漂移，assertion 會失敗。
        """
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch(
                "tools.portfolio_rotation_grid_search.run_portfolio_rotation_sweep",
                side_effect=_mock_sweep,
            ),
            patch(
                "tools.portfolio_rotation_grid_search.run_walk_forward_rotation",
                side_effect=_mock_walk_forward,
            ),
        ):
            root = Path(temp_dir)
            search = run_portfolio_rotation_grid_search(
                csv_paths=[Path("a.csv"), Path("b.csv")],
                start="2020-01-01",
                end="2023-12-31",
                cost_multipliers=(1.0, 3.0),
                primary_cost_label="1x",
                stress_cost_label="3x",
                initial_equity=10_000.0,
                commission_bps=1.0,
                slippage_bps=1.0,
                transaction_tax_bps=0.0,
                rebalance_frequency="monthly",
                lookback_bars=21,
                min_return=0.0,
                periods_per_year=252,
                top_n_values=[3],
                breadth_lookback_bars=42,
                breadth_min_positive_count_values=[3],
                breadth_positive_threshold=0.0,
                liquidity_lookback_bars=20,
                min_average_traded_value_values=[500_000_000.0],
                max_consecutive_selection_values=[5],
                symbol_groups={},
                rolling_window_months=24,
                rolling_step_months=12,
                rolling_min_months=12,
                thresholds={
                    "min_full_ir": 1.0,
                    "min_rolling_ir": 0.20,
                    "min_rolling_excess_return": 0.0,
                    "max_drawdown_abs": 0.30,
                    "max_top3_group_share": 0.90,
                },
            )
            output_json = root / "grid.json"
            output_md = root / "grid.md"

            write_grid_search_json(search, output_json)
            write_grid_search_markdown(search, output_md)
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            markdown = output_md.read_text(encoding="utf-8")

        self.assertEqual(payload["schema_version"], "portfolio_rotation_grid_search.v1")
        self.assertEqual(payload["candidate_count"], 1)
        self.assertIn("Portfolio Rotation Grid Search", markdown)
        self.assertIn("| 1 | candidate | 3 | 3 | 5 | 500000000", markdown)
        self.assertEqual(markdown, format_grid_search_markdown(search))


def _mock_sweep(**kwargs: object) -> list[PortfolioRotationResult]:
    """
    用途與流程：依 top_n 產生 deterministic full-window mock 結果，讓測試聚焦 grid ranking。
    參數：kwargs 是 run_portfolio_rotation_sweep 收到的命名參數。
    回傳與錯誤：回傳 1x/3x PortfolioRotationResult list；缺少 top_n 時會自然 KeyError。
    """
    top_n = int(kwargs["top_n"])
    if top_n == 3:
        return [
            _result(cost_label="1x", top_n=3, ir=1.20, excess=0.50, mdd=-0.20, group=0.80),
            _result(cost_label="3x", top_n=3, ir=1.10, excess=0.45, mdd=-0.21, group=0.80),
        ]
    return [
        _result(cost_label="1x", top_n=4, ir=1.50, excess=0.70, mdd=-0.18, group=0.95),
        _result(cost_label="3x", top_n=4, ir=1.40, excess=0.66, mdd=-0.19, group=0.95),
    ]


def _mock_walk_forward(**kwargs: object) -> tuple[list[PortfolioWalkForwardResult], list[object]]:
    """
    用途與流程：依 top_n 產生 deterministic rolling mock 結果，讓測試鎖住最弱 rolling IR gate。
    參數：kwargs 是 run_walk_forward_rotation 收到的命名參數。
    回傳與錯誤：回傳 rolling results 與空 retention list；缺少 windows/top_n 時會自然 KeyError。
    """
    top_n = int(kwargs["top_n"])
    windows = kwargs["windows"]
    assert isinstance(windows, tuple)
    if top_n == 3:
        ir_values = [0.40, 0.30]
        group_share = 0.80
    else:
        ir_values = [0.10, 0.05]
        group_share = 0.95
    results = []
    for index, window in enumerate(windows[:2]):
        assert isinstance(window, WalkForwardWindow)
        results.append(
            PortfolioWalkForwardResult(
                window=window,
                results=[
                    _result(
                        cost_label="1x",
                        top_n=top_n,
                        ir=ir_values[index],
                        excess=0.05 + index * 0.01,
                        mdd=-0.20,
                        group=group_share,
                    ),
                    _result(
                        cost_label="3x",
                        top_n=top_n,
                        ir=ir_values[index] - 0.05,
                        excess=0.03 + index * 0.01,
                        mdd=-0.22,
                        group=group_share,
                    ),
                ],
            )
        )
    return results, []


def _result(
    *,
    cost_label: str,
    top_n: int,
    ir: float,
    excess: float,
    mdd: float,
    group: float,
) -> PortfolioRotationResult:
    """
    用途與流程：建立 grid search 測試所需的最小 PortfolioRotationResult fixture。
    參數：cost_label/top_n 定義候選；ir/excess/mdd/group 是 ranking 與 gate 使用的指標。
    回傳與錯誤：回傳 PortfolioRotationResult；此 helper 不做 I/O。
    """
    multiplier = 3.0 if cost_label == "3x" else 1.0
    return PortfolioRotationResult(
        strategy="portfolio-relative-momentum-rotation",
        cost_multiplier=multiplier,
        cost_label=cost_label,
        rebalance_frequency="monthly",
        lookback_bars=21,
        top_n=top_n,
        min_return=0.0,
        market_regime_filter=False,
        market_regime_sma_bars=126,
        breadth_filter=True,
        breadth_lookback_bars=42,
        breadth_min_positive_count=3,
        breadth_positive_threshold=0.0,
        liquidity_lookback_bars=20,
        min_average_traded_value=500_000_000.0,
        symbol_groups={},
        max_selections_per_group=None,
        max_consecutive_selections_per_symbol=5,
        volatility_target=False,
        volatility_lookback_bars=21,
        target_annual_volatility=0.20,
        volatility_min_observations=21,
        volatility_max_scale=1.0,
        symbol_count=2,
        start_timestamp="2020-01-01",
        end_timestamp="2023-12-31",
        total_return=excess + 0.10,
        cagr=0.20,
        sharpe_ratio=ir,
        sortino_ratio=ir,
        calmar_ratio=1.0,
        max_drawdown=mdd,
        benchmark_total_return=0.10,
        benchmark_cagr=0.05,
        benchmark_max_drawdown=-0.25,
        benchmark_excess_return=excess,
        benchmark_excess_cagr=excess,
        annualized_active_return=0.20 * ir,
        tracking_error=0.20,
        information_ratio=ir,
        active_max_drawdown=mdd + 0.05,
        trade_count=10,
        rebalance_count=10,
        regime_block_count=0,
        breadth_block_count=0,
        breadth_warmup_count=0,
        liquidity_block_count=0,
        liquidity_warmup_count=0,
        group_selection_block_count=0,
        consecutive_selection_block_count=1,
        volatility_scaled_rebalance_count=0,
        volatility_warmup_count=0,
        total_cost=0.0,
        average_turnover=0.5,
        average_breadth_positive_count=4.0,
        average_liquidity_eligible_count=2.0,
        average_volatility_scale=None,
        average_exposure=0.8,
        average_selected_count=float(top_n),
        end_equity=10_000.0 * (1.0 + excess + 0.10),
        max_symbol_abs_contribution_symbol="2330",
        max_symbol_abs_contribution_share=0.60,
        top3_symbol_abs_contribution_share=0.70,
        symbol_attribution=[
            PortfolioSymbolAttribution(
                symbol="2330",
                selected_bar_count=10,
                selected_bar_share=0.50,
                rebalance_selected_count=2,
                rebalance_selected_share=0.40,
                average_weight=0.25,
                average_selected_weight=0.50,
                return_contribution=0.12,
                absolute_contribution_share=0.60,
            )
        ],
        max_group_abs_contribution_group="semiconductor",
        max_group_abs_contribution_share=group,
        top3_group_abs_contribution_share=group,
        max_group_average_weight_group="semiconductor",
        max_group_average_weight=0.30,
        top3_group_average_weight=0.30,
        group_attribution=[
            PortfolioGroupAttribution(
                group="semiconductor",
                member_symbols=("2330",),
                selected_bar_count=10,
                rebalance_selected_count=2,
                average_weight=0.30,
                return_contribution=0.12,
                absolute_contribution_share=group,
            )
        ],
    )


if __name__ == "__main__":
    unittest.main()
