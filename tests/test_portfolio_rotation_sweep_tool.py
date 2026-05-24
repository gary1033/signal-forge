from __future__ import annotations

from pathlib import Path
import unittest

from signal_forge import BacktestConfig, Bar
from tools.portfolio_rotation_sweep import (
    build_parser,
    build_portfolio_retention,
    build_rolling_windows,
    align_close_table,
    PortfolioRotationResult,
    PortfolioGroupAttribution,
    PortfolioSymbolAttribution,
    parse_symbol_group_assignments,
    run_portfolio_rotation,
    run_equal_weight_benchmark,
    PortfolioWalkForwardResult,
)
from tools.multi_stock_target_state_sweep import WalkForwardWindow


class PortfolioRotationSweepToolTests(unittest.TestCase):
    def test_parser_accepts_rotation_options(self) -> None:
        """
        用途與流程：驗證 portfolio rotation CLI 可接收 rebalance、lookback、top-N 與成本壓力參數。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 parser 欄位或型別漂移，assertion 會失敗。
        """
        args = build_parser().parse_args(
            [
                "--csv",
                "data.csv",
                "--rebalance-frequency",
                "monthly",
                "--lookback-bars",
                "3",
                "--ranking-skip-bars",
                "1",
                "--ranking-mode",
                "group-residual",
                "--top-n",
                "2",
                "--min-return",
                "0.02",
                "--cost-multipliers-list",
                "1,3",
                "--market-regime-filter",
                "--market-regime-sma-bars",
                "2",
                "--breadth-filter",
                "--breadth-lookback-bars",
                "4",
                "--breadth-min-positive-count",
                "2",
                "--breadth-positive-threshold",
                "0.01",
                "--liquidity-lookback-bars",
                "5",
                "--min-average-traded-value",
                "1000000",
                "--symbol-group",
                "2330:semiconductor",
                "--symbol-group",
                "2317:electronics",
                "--max-selections-per-group",
                "1",
                "--min-symbols-per-selected-group",
                "2",
                "--max-consecutive-selections-per-symbol",
                "2",
                "--reentry-cooldown-rebalances",
                "1",
                "--group-contribution-lookback-bars",
                "3",
                "--max-group-contribution-share",
                "0.65",
                "--volatility-target",
                "--volatility-lookback-bars",
                "3",
                "--target-annual-volatility",
                "0.15",
                "--volatility-min-observations",
                "2",
                "--volatility-max-scale",
                "0.8",
            ]
        )

        self.assertEqual(args.rebalance_frequency, "monthly")
        self.assertEqual(args.lookback_bars, 3)
        self.assertEqual(args.ranking_skip_bars, 1)
        self.assertEqual(args.ranking_mode, "group-residual")
        self.assertEqual(args.top_n, 2)
        self.assertEqual(args.min_return, 0.02)
        self.assertEqual(args.cost_multipliers_list, "1,3")
        self.assertTrue(args.market_regime_filter)
        self.assertEqual(args.market_regime_sma_bars, 2)
        self.assertTrue(args.breadth_filter)
        self.assertEqual(args.breadth_lookback_bars, 4)
        self.assertEqual(args.breadth_min_positive_count, 2)
        self.assertEqual(args.breadth_positive_threshold, 0.01)
        self.assertEqual(args.liquidity_lookback_bars, 5)
        self.assertEqual(args.min_average_traded_value, 1_000_000.0)
        self.assertEqual(args.symbol_group, ["2330:semiconductor", "2317:electronics"])
        self.assertEqual(args.max_selections_per_group, 1)
        self.assertEqual(args.min_symbols_per_selected_group, 2)
        self.assertEqual(args.max_consecutive_selections_per_symbol, 2)
        self.assertEqual(args.reentry_cooldown_rebalances, 1)
        self.assertEqual(args.group_contribution_lookback_bars, 3)
        self.assertEqual(args.max_group_contribution_share, 0.65)
        self.assertTrue(args.volatility_target)
        self.assertEqual(args.volatility_lookback_bars, 3)
        self.assertEqual(args.target_annual_volatility, 0.15)
        self.assertEqual(args.volatility_min_observations, 2)
        self.assertEqual(args.volatility_max_scale, 0.8)

    def test_parser_accepts_rolling_window_options(self) -> None:
        """
        用途與流程：驗證 portfolio rotation CLI 可接收自動 rolling window 參數，避免只能手寫少數分段。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；parser 欄位漂移時 assertion 會失敗。
        """
        args = build_parser().parse_args(
            [
                "--csv",
                "data.csv",
                "--rolling-window-months",
                "24",
                "--rolling-step-months",
                "12",
                "--rolling-min-months",
                "12",
            ]
        )

        self.assertEqual(args.rolling_window_months, 24)
        self.assertEqual(args.rolling_step_months, 12)
        self.assertEqual(args.rolling_min_months, 12)

    def test_parse_symbol_group_assignments_rejects_conflicting_groups(self) -> None:
        """
        用途與流程：驗證 portfolio rotation 的 symbol group parser 能拒絕同一股票被指定到不同群組，避免 sector cap 因輸入衝突而失真。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 parser 未拒絕衝突群組，assertion 會失敗。
        """
        with self.assertRaisesRegex(ValueError, "multiple groups"):
            parse_symbol_group_assignments(["2330:semiconductor", "2330:electronics"])

    def test_build_rolling_windows_keeps_final_partial_window(self) -> None:
        """
        用途與流程：驗證 rolling window 產生器會依月份長度與最低月數建立多個穩定性檢查日期窗。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；日期推進、標籤或 final partial window 規則漂移時 assertion 會失敗。
        """
        windows = build_rolling_windows(
            start="2020-01-01",
            end="2023-05-20",
            window_months=24,
            step_months=12,
            min_window_months=12,
        )

        self.assertEqual(
            [(window.label, window.start, window.end) for window in windows],
            [
                ("roll01", "2020-01-01", "2021-12-31"),
                ("roll02", "2021-01-01", "2022-12-31"),
                ("roll03", "2022-01-01", "2023-05-20"),
            ],
        )

    def test_align_close_table_uses_only_common_timestamps(self) -> None:
        """
        用途與流程：驗證多檔 close matrix 只保留共同 timestamp，避免不同交易日資料造成錯誤輪動。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；共同日期或 close 對齊錯誤時 assertion 會失敗。
        """
        timestamps, closes = align_close_table(
            [
                (
                    "2330",
                    Path("2330.csv"),
                    [
                        _bar("2026-01-01", 10.0),
                        _bar("2026-01-02", 11.0),
                        _bar("2026-01-03", 12.0),
                    ],
                ),
                (
                    "2317",
                    Path("2317.csv"),
                    [
                        _bar("2026-01-02", 21.0),
                        _bar("2026-01-03", 22.0),
                        _bar("2026-01-04", 23.0),
                    ],
                ),
            ]
        )

        self.assertEqual(timestamps, ["2026-01-02", "2026-01-03"])
        self.assertEqual(closes["2330"], [11.0, 12.0])
        self.assertEqual(closes["2317"], [21.0, 22.0])

    def test_rotation_selects_top_positive_momentum_symbol(self) -> None:
        """
        用途與流程：驗證 daily portfolio rotation 會選擇 lookback return 最高且為正的股票，並相對 equal-weight benchmark 產生正 excess。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；選股、交易成本或 benchmark-relative 計算漂移時 assertion 失敗。
        """
        loaded = [
            (
                "2330",
                Path("2330.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 110.0),
                    _bar("2026-01-03", 121.0),
                    _bar("2026-01-04", 133.1),
                ],
            ),
            (
                "2317",
                Path("2317.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 90.0),
                    _bar("2026-01-03", 81.0),
                    _bar("2026-01-04", 72.9),
                ],
            ),
        ]

        result = run_portfolio_rotation(
            loaded,
            config=BacktestConfig(initial_equity=10_000.0, commission_bps=0.0, slippage_bps=0.0),
            cost_multiplier=1.0,
            rebalance_frequency="daily",
            lookback_bars=1,
            top_n=1,
            min_return=0.0,
            periods_per_year=252,
        )

        self.assertGreater(result.total_return, 0.20)
        self.assertGreater(result.benchmark_excess_return, 0.20)
        self.assertIsNotNone(result.tracking_error)
        self.assertIsNotNone(result.information_ratio)
        self.assertGreater(result.information_ratio or 0.0, 0.0)
        self.assertLessEqual(result.active_max_drawdown, 0.0)
        self.assertEqual(result.trade_count, 1)
        self.assertGreater(result.average_exposure, 0.0)
        self.assertEqual(result.symbol_attribution[0].symbol, "2330")
        self.assertEqual(result.symbol_attribution[0].selected_bar_count, 2)
        self.assertAlmostEqual(result.symbol_attribution[0].return_contribution, 0.20)
        self.assertGreater(
            result.symbol_attribution[0].absolute_contribution_share,
            0.99,
        )
        self.assertEqual(result.max_symbol_abs_contribution_symbol, "2330")
        self.assertGreater(result.max_symbol_abs_contribution_share, 0.99)
        self.assertGreater(result.top3_symbol_abs_contribution_share, 0.99)
        self.assertEqual(result.max_group_abs_contribution_group, "2330")
        self.assertGreater(result.max_group_abs_contribution_share, 0.99)
        self.assertGreater(result.top3_group_abs_contribution_share, 0.99)

    def test_ranking_skip_bars_excludes_recent_return_from_momentum_rank(self) -> None:
        """
        用途與流程：驗證 ranking skip bars 會把最近 N 根 bar 排除在相對動能排名之外，用較早形成期報酬決定入選股票。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 ranking skip 沒有改變排名視窗或 result 欄位漂移，assertion 會失敗。
        """
        loaded = [
            (
                "old_winner",
                Path("old_winner.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 150.0),
                    _bar("2026-01-03", 200.0),
                    _bar("2026-01-04", 100.0),
                ],
            ),
            (
                "recent_winner",
                Path("recent_winner.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 100.0),
                    _bar("2026-01-03", 100.0),
                    _bar("2026-01-04", 200.0),
                ],
            ),
        ]

        result = run_portfolio_rotation(
            loaded,
            config=BacktestConfig(
                initial_equity=10_000.0,
                commission_bps=0.0,
                slippage_bps=0.0,
            ),
            cost_multiplier=1.0,
            rebalance_frequency="daily",
            lookback_bars=2,
            ranking_skip_bars=1,
            top_n=1,
            min_return=0.0,
            periods_per_year=252,
        )

        old_winner = next(row for row in result.symbol_attribution if row.symbol == "old_winner")
        recent_winner = next(
            row for row in result.symbol_attribution if row.symbol == "recent_winner"
        )
        self.assertEqual(result.ranking_skip_bars, 1)
        self.assertEqual(old_winner.rebalance_selected_count, 1)
        self.assertEqual(recent_winner.rebalance_selected_count, 0)

    def test_group_residual_ranking_subtracts_group_momentum_before_selection(self) -> None:
        """
        用途與流程：驗證 group-residual ranking 會用個股報酬扣除同組平均報酬排序，讓較低總報酬但同組相對更強的股票能入選。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 residual ranking 沒有改變排序或 result 欄位漂移，assertion 會失敗。
        """
        loaded = [
            (
                "hot_group_leader",
                Path("hot_group_leader.csv"),
                [_bar("2026-01-01", 100.0), _bar("2026-01-02", 150.0)],
            ),
            (
                "hot_group_peer",
                Path("hot_group_peer.csv"),
                [_bar("2026-01-01", 100.0), _bar("2026-01-02", 140.0)],
            ),
            (
                "cold_group_leader",
                Path("cold_group_leader.csv"),
                [_bar("2026-01-01", 100.0), _bar("2026-01-02", 120.0)],
            ),
            (
                "cold_group_peer",
                Path("cold_group_peer.csv"),
                [_bar("2026-01-01", 100.0), _bar("2026-01-02", 100.0)],
            ),
        ]

        result = run_portfolio_rotation(
            loaded,
            config=BacktestConfig(
                initial_equity=10_000.0,
                commission_bps=0.0,
                slippage_bps=0.0,
            ),
            cost_multiplier=1.0,
            rebalance_frequency="daily",
            lookback_bars=1,
            ranking_mode="group-residual",
            top_n=1,
            min_return=0.0,
            periods_per_year=252,
            symbol_groups={
                "hot_group_leader": "hot",
                "hot_group_peer": "hot",
                "cold_group_leader": "cold",
                "cold_group_peer": "cold",
            },
        )

        hot_group_leader = next(
            row for row in result.symbol_attribution if row.symbol == "hot_group_leader"
        )
        cold_group_leader = next(
            row for row in result.symbol_attribution if row.symbol == "cold_group_leader"
        )
        self.assertEqual(result.ranking_mode, "group-residual")
        self.assertEqual(hot_group_leader.rebalance_selected_count, 0)
        self.assertEqual(cold_group_leader.rebalance_selected_count, 1)

    def test_liquidity_filter_excludes_low_traded_value_momentum_leader(self) -> None:
        """
        用途與流程：驗證 liquidity filter 會排除平均成交金額不足的強勢股，讓較低動能但可交易性較好的股票補上。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若成交金額門檻、block count 或替代股票入選語意漂移，assertion 會失敗。
        """
        loaded = [
            (
                "2330",
                Path("2330.csv"),
                [
                    _bar("2026-01-01", 100.0, volume=1.0),
                    _bar("2026-01-02", 110.0, volume=1.0),
                    _bar("2026-01-03", 121.0, volume=1.0),
                    _bar("2026-01-04", 133.1, volume=1.0),
                ],
            ),
            (
                "2317",
                Path("2317.csv"),
                [
                    _bar("2026-01-01", 100.0, volume=2_000.0),
                    _bar("2026-01-02", 102.0, volume=2_000.0),
                    _bar("2026-01-03", 104.04, volume=2_000.0),
                    _bar("2026-01-04", 106.1208, volume=2_000.0),
                ],
            ),
        ]

        result = run_portfolio_rotation(
            loaded,
            config=BacktestConfig(
                initial_equity=10_000.0,
                commission_bps=0.0,
                slippage_bps=0.0,
            ),
            cost_multiplier=1.0,
            rebalance_frequency="daily",
            lookback_bars=1,
            top_n=1,
            min_return=0.0,
            periods_per_year=252,
            liquidity_lookback_bars=1,
            min_average_traded_value=100_000.0,
        )

        liquid = next(row for row in result.symbol_attribution if row.symbol == "2317")
        illiquid = next(row for row in result.symbol_attribution if row.symbol == "2330")
        self.assertEqual(result.liquidity_lookback_bars, 1)
        self.assertEqual(result.min_average_traded_value, 100_000.0)
        self.assertEqual(result.liquidity_block_count, 3)
        self.assertEqual(result.liquidity_warmup_count, 0)
        self.assertAlmostEqual(result.average_liquidity_eligible_count or 0.0, 1.0)
        self.assertGreater(liquid.rebalance_selected_count, 0)
        self.assertEqual(illiquid.rebalance_selected_count, 0)

    def test_max_consecutive_selection_limit_forces_symbol_to_sit_out(self) -> None:
        """
        用途與流程：驗證單檔連續入選上限會讓過度連續入選的股票暫停一次 rebalance，降低單檔主導風險。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若連續入選限制、block count 或替代股票入選語意漂移，assertion 會失敗。
        """
        loaded = [
            (
                "2330",
                Path("2330.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 110.0),
                    _bar("2026-01-03", 121.0),
                    _bar("2026-01-04", 133.1),
                    _bar("2026-01-05", 146.41),
                    _bar("2026-01-06", 161.051),
                ],
            ),
            (
                "2317",
                Path("2317.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 102.0),
                    _bar("2026-01-03", 104.04),
                    _bar("2026-01-04", 106.1208),
                    _bar("2026-01-05", 108.243216),
                    _bar("2026-01-06", 110.40808032),
                ],
            ),
        ]

        result = run_portfolio_rotation(
            loaded,
            config=BacktestConfig(
                initial_equity=10_000.0,
                commission_bps=0.0,
                slippage_bps=0.0,
            ),
            cost_multiplier=1.0,
            rebalance_frequency="daily",
            lookback_bars=1,
            top_n=1,
            min_return=0.0,
            periods_per_year=252,
            max_consecutive_selections_per_symbol=2,
        )

        alternative = next(row for row in result.symbol_attribution if row.symbol == "2317")
        self.assertEqual(result.max_consecutive_selections_per_symbol, 2)
        self.assertEqual(result.consecutive_selection_block_count, 1)
        self.assertEqual(alternative.rebalance_selected_count, 1)

    def test_reentry_cooldown_blocks_fast_reentry_after_exit(self) -> None:
        """
        用途與流程：驗證股票離開輪動投組後，re-entry cooldown 會在下一次 rebalance 阻擋它立刻重新入選，且不偷看未來報酬。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 cooldown 狀態更新、block count 或替代股票入選語意漂移，assertion 會失敗。
        """
        loaded = [
            (
                "2330",
                Path("2330.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 120.0),
                    _bar("2026-01-03", 108.0),
                    _bar("2026-01-04", 129.6),
                ],
            ),
            (
                "2317",
                Path("2317.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 100.0),
                    _bar("2026-01-03", 110.0),
                    _bar("2026-01-04", 104.5),
                ],
            ),
            (
                "2881",
                Path("2881.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 100.0),
                    _bar("2026-01-03", 100.0),
                    _bar("2026-01-04", 105.0),
                ],
            ),
        ]

        result = run_portfolio_rotation(
            loaded,
            config=BacktestConfig(
                initial_equity=10_000.0,
                commission_bps=0.0,
                slippage_bps=0.0,
            ),
            cost_multiplier=1.0,
            rebalance_frequency="daily",
            lookback_bars=1,
            top_n=1,
            min_return=0.0,
            periods_per_year=252,
            reentry_cooldown_rebalances=1,
        )

        selected_by_symbol = {
            row.symbol: row.rebalance_selected_count
            for row in result.symbol_attribution
        }
        self.assertEqual(result.reentry_cooldown_rebalances, 1)
        self.assertEqual(result.reentry_cooldown_block_count, 1)
        self.assertEqual(selected_by_symbol["2330"], 1)
        self.assertEqual(selected_by_symbol["2317"], 1)
        self.assertEqual(selected_by_symbol["2881"], 1)

    def test_group_cap_limits_same_group_selection(self) -> None:
        """
        用途與流程：驗證同組入選上限會阻擋同一產業或自訂群組過度集中，讓較低排名但不同組的股票能補上配置。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 group cap 沒有阻擋同組股票或 block count 漂移，assertion 會失敗。
        """
        loaded = [
            (
                "2330",
                Path("2330.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 110.0),
                    _bar("2026-01-03", 121.0),
                ],
            ),
            (
                "2454",
                Path("2454.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 108.0),
                    _bar("2026-01-03", 116.64),
                ],
            ),
            (
                "2881",
                Path("2881.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 102.0),
                    _bar("2026-01-03", 104.04),
                ],
            ),
        ]

        result = run_portfolio_rotation(
            loaded,
            config=BacktestConfig(
                initial_equity=10_000.0,
                commission_bps=0.0,
                slippage_bps=0.0,
            ),
            cost_multiplier=1.0,
            rebalance_frequency="daily",
            lookback_bars=1,
            top_n=2,
            min_return=0.0,
            periods_per_year=252,
            symbol_groups={
                "2330": "semiconductor",
                "2454": "semiconductor",
                "2881": "financial",
            },
            max_selections_per_group=1,
        )

        selected_financial = next(row for row in result.symbol_attribution if row.symbol == "2881")
        blocked_semiconductor = next(row for row in result.symbol_attribution if row.symbol == "2454")
        self.assertEqual(result.max_selections_per_group, 1)
        self.assertEqual(result.group_selection_block_count, 2)
        self.assertEqual(result.symbol_groups["2330"], "semiconductor")
        self.assertEqual(selected_financial.rebalance_selected_count, 2)
        self.assertEqual(blocked_semiconductor.rebalance_selected_count, 0)

    def test_min_symbols_per_selected_group_blocks_single_member_group(self) -> None:
        """
        用途與流程：驗證群組成員數下限會阻擋單成員群組的強勢股，讓多成員群組中的次佳股票補上。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若單成員群組仍可入選或 block count 漂移，assertion 會失敗。
        """
        loaded = [
            (
                "2603",
                Path("2603.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 120.0),
                    _bar("2026-01-03", 144.0),
                ],
            ),
            (
                "2330",
                Path("2330.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 110.0),
                    _bar("2026-01-03", 121.0),
                ],
            ),
            (
                "2454",
                Path("2454.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 105.0),
                    _bar("2026-01-03", 110.25),
                ],
            ),
        ]

        result = run_portfolio_rotation(
            loaded,
            config=BacktestConfig(
                initial_equity=10_000.0,
                commission_bps=0.0,
                slippage_bps=0.0,
            ),
            cost_multiplier=1.0,
            rebalance_frequency="daily",
            lookback_bars=1,
            top_n=1,
            min_return=0.0,
            periods_per_year=252,
            symbol_groups={
                "2603": "shipping",
                "2330": "semiconductor",
                "2454": "semiconductor",
            },
            min_symbols_per_selected_group=2,
        )

        shipping = next(row for row in result.symbol_attribution if row.symbol == "2603")
        semiconductor = next(row for row in result.symbol_attribution if row.symbol == "2330")
        self.assertEqual(result.min_symbols_per_selected_group, 2)
        self.assertEqual(result.group_member_block_count, 2)
        self.assertEqual(shipping.rebalance_selected_count, 0)
        self.assertEqual(semiconductor.rebalance_selected_count, 2)

    def test_group_attribution_aggregates_member_contributions(self) -> None:
        """
        用途與流程：驗證 portfolio rotation 會把同一群組內多檔股票的報酬貢獻、曝險、持倉期間與入選次數彙總成 group attribution。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若群組彙總、最大群組集中度或 member 列表漂移，assertion 會失敗。
        """
        loaded = [
            (
                "2330",
                Path("2330.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 110.0),
                    _bar("2026-01-03", 121.0),
                ],
            ),
            (
                "2454",
                Path("2454.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 108.0),
                    _bar("2026-01-03", 116.64),
                ],
            ),
            (
                "2881",
                Path("2881.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 102.0),
                    _bar("2026-01-03", 104.04),
                ],
            ),
        ]

        result = run_portfolio_rotation(
            loaded,
            config=BacktestConfig(
                initial_equity=10_000.0,
                commission_bps=0.0,
                slippage_bps=0.0,
            ),
            cost_multiplier=1.0,
            rebalance_frequency="daily",
            lookback_bars=1,
            top_n=2,
            min_return=0.0,
            periods_per_year=252,
            symbol_groups={
                "2330": "semiconductor",
                "2454": "semiconductor",
                "2881": "financial",
            },
        )

        semiconductor = result.group_attribution[0]
        self.assertEqual(semiconductor.group, "semiconductor")
        self.assertEqual(semiconductor.member_symbols, ("2330", "2454"))
        self.assertEqual(semiconductor.selected_bar_count, 2)
        self.assertEqual(semiconductor.rebalance_selected_count, 4)
        self.assertAlmostEqual(semiconductor.average_weight, 0.50)
        self.assertAlmostEqual(semiconductor.return_contribution, 0.09)
        self.assertGreater(semiconductor.absolute_contribution_share, 0.99)
        self.assertEqual(result.max_group_abs_contribution_group, "semiconductor")
        self.assertGreater(result.max_group_abs_contribution_share, 0.99)
        self.assertGreater(result.top3_group_abs_contribution_share, 0.99)
        self.assertEqual(result.max_group_average_weight_group, "semiconductor")
        self.assertAlmostEqual(result.max_group_average_weight, 0.50)
        self.assertAlmostEqual(result.top3_group_average_weight, 0.50)

    def test_group_contribution_guard_blocks_recent_dominant_group(self) -> None:
        """
        用途與流程：驗證 realized group contribution gate 只用已完成持倉貢獻，會在下一次 rebalance 暫時排除過度主導的群組。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 gate 提前偷看未來貢獻或沒有排除 dominant group，assertion 會失敗。
        """
        loaded = [
            (
                "2330",
                Path("2330.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 110.0),
                    _bar("2026-01-03", 121.0),
                    _bar("2026-01-04", 133.1),
                ],
            ),
            (
                "2881",
                Path("2881.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 105.0),
                    _bar("2026-01-03", 110.25),
                    _bar("2026-01-04", 115.7625),
                ],
            ),
        ]

        result = run_portfolio_rotation(
            loaded,
            config=BacktestConfig(
                initial_equity=10_000.0,
                commission_bps=0.0,
                slippage_bps=0.0,
                transaction_tax_bps=0.0,
            ),
            cost_multiplier=1.0,
            rebalance_frequency="daily",
            lookback_bars=1,
            top_n=1,
            min_return=0.0,
            periods_per_year=252,
            symbol_groups={"2330": "semiconductor", "2881": "financial"},
            group_contribution_lookback_bars=1,
            max_group_contribution_share=0.60,
        )

        selected_by_symbol = {
            row.symbol: row.rebalance_selected_count
            for row in result.symbol_attribution
        }
        self.assertEqual(result.group_contribution_lookback_bars, 1)
        self.assertEqual(result.max_group_contribution_share, 0.60)
        self.assertEqual(result.group_contribution_block_count, 2)
        self.assertEqual(selected_by_symbol["2330"], 2)
        self.assertEqual(selected_by_symbol["2881"], 1)

    def test_format_markdown_includes_symbol_attribution(self) -> None:
        """
        用途與流程：驗證 portfolio rotation Markdown 會輸出逐股 attribution 區段，讓策略候選能檢查報酬是否集中於少數股票。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 attribution 表格標題或核心欄位遺失，assertion 會失敗。
        """
        from tools.portfolio_rotation_sweep import format_markdown

        markdown = format_markdown(
            [_rotation_result(total_return=0.20, excess=0.10, sharpe=1.0, mdd=-0.20)],
            start="2026-01-01",
            end="2026-01-02",
            periods_per_year=252,
        )

        self.assertIn("## Top Symbol Attribution", markdown)
        self.assertIn("## Top Group Attribution", markdown)
        self.assertIn("Max contrib symbol", markdown)
        self.assertIn("Max group", markdown)
        self.assertIn("Max exposure group", markdown)
        self.assertIn("Top3 group avg weight", markdown)
        self.assertIn("Ranking skip", markdown)
        self.assertIn("Ranking mode", markdown)
        self.assertIn("Liquidity min", markdown)
        self.assertIn("Liquidity blocks", markdown)
        self.assertIn("Group cap", markdown)
        self.assertIn("Min group members", markdown)
        self.assertIn("Group member blocks", markdown)
        self.assertIn("Group contrib lookback", markdown)
        self.assertIn("Group contrib blocks", markdown)
        self.assertIn("Consec cap", markdown)
        self.assertIn("Reentry cooldown", markdown)
        self.assertIn("Reentry blocks", markdown)
        self.assertIn("2330 | 75.00% | 75.00%", markdown)
        self.assertIn("| 1x | 1 | 2330 | 12.00% | 75.00%", markdown)
        self.assertIn("| 1x | 1 | semiconductor | 2330, 2454 | 15.00% | 80.00%", markdown)

    def test_market_regime_filter_blocks_rotation_when_market_index_below_sma(self) -> None:
        """
        用途與流程：驗證 market regime filter 會在等權市場指數低於 SMA 時阻擋原本可進場的相對動能輪動。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 regime gate、block count 或現金持有語意漂移，assertion 會失敗。
        """
        loaded = [
            (
                "2330",
                Path("2330.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 100.0),
                    _bar("2026-01-03", 110.0),
                    _bar("2026-01-04", 120.0),
                ],
            ),
            (
                "2317",
                Path("2317.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 70.0),
                    _bar("2026-01-03", 50.0),
                    _bar("2026-01-04", 35.0),
                ],
            ),
        ]

        result = run_portfolio_rotation(
            loaded,
            config=BacktestConfig(
                initial_equity=10_000.0,
                commission_bps=0.0,
                slippage_bps=0.0,
            ),
            cost_multiplier=1.0,
            rebalance_frequency="daily",
            lookback_bars=1,
            top_n=1,
            min_return=0.0,
            periods_per_year=252,
            market_regime_filter=True,
            market_regime_sma_bars=2,
        )

        self.assertTrue(result.market_regime_filter)
        self.assertEqual(result.market_regime_sma_bars, 2)
        self.assertEqual(result.regime_block_count, 3)
        self.assertEqual(result.trade_count, 0)
        self.assertAlmostEqual(result.total_return, 0.0)
        self.assertAlmostEqual(result.average_exposure, 0.0)

    def test_breadth_filter_blocks_rotation_when_positive_count_is_too_low(self) -> None:
        """
        用途與流程：驗證 breadth filter 會在正動能股票數不足時阻擋原本可進場的相對動能輪動，避免只靠單檔強勢股承擔 crash-prone 曝險。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 breadth count、block count 或全現金語意漂移，assertion 會失敗。
        """
        loaded = [
            (
                "2330",
                Path("2330.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 110.0),
                    _bar("2026-01-03", 120.0),
                    _bar("2026-01-04", 130.0),
                ],
            ),
            (
                "2317",
                Path("2317.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 90.0),
                    _bar("2026-01-03", 80.0),
                    _bar("2026-01-04", 70.0),
                ],
            ),
            (
                "2454",
                Path("2454.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 95.0),
                    _bar("2026-01-03", 90.0),
                    _bar("2026-01-04", 85.0),
                ],
            ),
        ]

        result = run_portfolio_rotation(
            loaded,
            config=BacktestConfig(
                initial_equity=10_000.0,
                commission_bps=0.0,
                slippage_bps=0.0,
            ),
            cost_multiplier=1.0,
            rebalance_frequency="daily",
            lookback_bars=1,
            top_n=1,
            min_return=0.0,
            periods_per_year=252,
            breadth_filter=True,
            breadth_lookback_bars=1,
            breadth_min_positive_count=2,
        )

        self.assertTrue(result.breadth_filter)
        self.assertEqual(result.breadth_lookback_bars, 1)
        self.assertEqual(result.breadth_min_positive_count, 2)
        self.assertEqual(result.breadth_block_count, 3)
        self.assertEqual(result.breadth_warmup_count, 0)
        self.assertAlmostEqual(result.average_breadth_positive_count or 0.0, 1.0)
        self.assertEqual(result.trade_count, 0)
        self.assertAlmostEqual(result.total_return, 0.0)
        self.assertAlmostEqual(result.average_exposure, 0.0)

    def test_volatility_target_scales_high_volatility_rotation_weights(self) -> None:
        """
        用途與流程：驗證 portfolio-level volatility target 會用目標投組近期波動下修權重，而不是改變相對動能選股。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 warmup、縮放或平均曝險語意漂移，assertion 會失敗。
        """
        loaded = [
            (
                "2330",
                Path("2330.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 200.0),
                    _bar("2026-01-03", 100.0),
                    _bar("2026-01-04", 200.0),
                ],
            ),
            (
                "2317",
                Path("2317.csv"),
                [
                    _bar("2026-01-01", 100.0),
                    _bar("2026-01-02", 90.0),
                    _bar("2026-01-03", 90.0),
                    _bar("2026-01-04", 90.0),
                ],
            ),
        ]

        result = run_portfolio_rotation(
            loaded,
            config=BacktestConfig(
                initial_equity=10_000.0,
                commission_bps=0.0,
                slippage_bps=0.0,
            ),
            cost_multiplier=1.0,
            rebalance_frequency="daily",
            lookback_bars=1,
            top_n=1,
            min_return=0.0,
            periods_per_year=252,
            volatility_target=True,
            volatility_lookback_bars=2,
            target_annual_volatility=0.10,
            volatility_min_observations=2,
        )

        self.assertTrue(result.volatility_target)
        self.assertEqual(result.volatility_lookback_bars, 2)
        self.assertEqual(result.target_annual_volatility, 0.10)
        self.assertEqual(result.volatility_min_observations, 2)
        self.assertEqual(result.volatility_warmup_count, 1)
        self.assertEqual(result.volatility_scaled_rebalance_count, 1)
        self.assertIsNotNone(result.average_volatility_scale)
        self.assertLess(result.average_volatility_scale or 1.0, 0.01)
        self.assertLess(result.average_exposure, 0.10)

    def test_equal_weight_benchmark_applies_initial_entry_cost(self) -> None:
        """
        用途與流程：驗證 equal-weight benchmark 會套用初始入場成本，避免和有交易成本的輪動策略比較不一致。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；成本處理漂移時 assertion 會失敗。
        """
        benchmark = run_equal_weight_benchmark(
            ["2026-01-01", "2026-01-02"],
            {"2330": [100.0, 100.0], "2317": [100.0, 100.0]},
            config=BacktestConfig(
                initial_equity=10_000.0,
                commission_bps=10.0,
                slippage_bps=0.0,
            ),
            periods_per_year=252,
        )

        self.assertAlmostEqual(benchmark["total_return"] or 0.0, -0.001)

    def test_portfolio_retention_compares_matching_cost_windows(self) -> None:
        """
        用途與流程：驗證 portfolio walk-forward retention 會以成本倍率對齊相鄰 window 的結果。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；retention 對齊或公式漂移時 assertion 會失敗。
        """
        train = _rotation_result(total_return=0.20, excess=0.10, sharpe=1.0, mdd=-0.20)
        test = _rotation_result(total_return=0.10, excess=0.04, sharpe=0.5, mdd=-0.25)

        retention = build_portfolio_retention(
            [
                PortfolioWalkForwardResult(
                    window=WalkForwardWindow("is", "2020-01-01", "2023-12-31"),
                    results=[train],
                ),
                PortfolioWalkForwardResult(
                    window=WalkForwardWindow("oos", "2024-01-01", "2026-05-20"),
                    results=[test],
                ),
            ]
        )

        self.assertEqual(len(retention), 1)
        self.assertAlmostEqual(retention[0].total_return_retention or 0.0, 0.5)
        self.assertAlmostEqual(retention[0].benchmark_excess_retention or 0.0, 0.4)
        self.assertAlmostEqual(retention[0].information_ratio_retention or 0.0, 0.5)
        self.assertAlmostEqual(retention[0].sharpe_retention or 0.0, 0.5)
        self.assertAlmostEqual(retention[0].drawdown_change, -0.05)
        self.assertAlmostEqual(retention[0].active_drawdown_change, -0.05)


def _bar(timestamp: str, close: float, volume: float = 1_000.0) -> Bar:
    """
    用途與流程：建立 portfolio rotation 測試用 Bar，讓測試聚焦 timestamp 與 close。
    參數：timestamp 是日期字串；close 是收盤價，並同步填入 open/high/low；volume 是成交量，供 liquidity filter 測試覆寫。
    回傳與錯誤：回傳 Bar；此 helper 不做 I/O，也不主動拋錯。
    """
    return Bar(
        timestamp=timestamp,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=volume,
    )


def _rotation_result(
    *,
    total_return: float,
    excess: float,
    sharpe: float,
    mdd: float,
) -> PortfolioRotationResult:
    """
    用途與流程：建立測試用 PortfolioRotationResult，讓 retention 測試聚焦公式而非回測流程。
    參數：total_return/excess/sharpe/mdd 是 retention 會讀取的核心欄位。
    回傳與錯誤：回傳 PortfolioRotationResult；此 helper 不做 I/O，也不主動拋錯。
    """
    return PortfolioRotationResult(
        strategy="portfolio-relative-momentum-rotation",
        cost_multiplier=1.0,
        cost_label="1x",
        rebalance_frequency="weekly",
        lookback_bars=1,
        ranking_skip_bars=0,
        ranking_mode="total-return",
        top_n=1,
        min_return=0.0,
        market_regime_filter=False,
        market_regime_sma_bars=126,
        breadth_filter=False,
        breadth_lookback_bars=21,
        breadth_min_positive_count=1,
        breadth_positive_threshold=0.0,
        liquidity_lookback_bars=20,
        min_average_traded_value=None,
        symbol_groups={},
        max_selections_per_group=None,
        max_consecutive_selections_per_symbol=None,
        reentry_cooldown_rebalances=0,
        volatility_target=False,
        volatility_lookback_bars=21,
        target_annual_volatility=0.20,
        volatility_min_observations=21,
        volatility_max_scale=1.0,
        symbol_count=2,
        start_timestamp="2026-01-01",
        end_timestamp="2026-01-02",
        total_return=total_return,
        cagr=total_return,
        sharpe_ratio=sharpe,
        sortino_ratio=sharpe,
        calmar_ratio=1.0,
        max_drawdown=mdd,
        benchmark_total_return=total_return - excess,
        benchmark_cagr=total_return - excess,
        benchmark_max_drawdown=-0.30,
        benchmark_excess_return=excess,
        benchmark_excess_cagr=excess,
        annualized_active_return=0.2 * sharpe,
        tracking_error=0.2,
        information_ratio=sharpe,
        active_max_drawdown=mdd + 0.10,
        trade_count=1,
        rebalance_count=1,
        regime_block_count=0,
        breadth_block_count=0,
        breadth_warmup_count=0,
        liquidity_block_count=0,
        liquidity_warmup_count=0,
        group_selection_block_count=0,
        consecutive_selection_block_count=0,
        reentry_cooldown_block_count=0,
        volatility_scaled_rebalance_count=0,
        volatility_warmup_count=0,
        total_cost=0.0,
        average_turnover=1.0,
        average_breadth_positive_count=None,
        average_liquidity_eligible_count=None,
        average_volatility_scale=None,
        average_exposure=1.0,
        average_selected_count=1.0,
        end_equity=10_000.0 * (1.0 + total_return),
        max_symbol_abs_contribution_symbol="2330",
        max_symbol_abs_contribution_share=0.75,
        top3_symbol_abs_contribution_share=0.75,
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
                absolute_contribution_share=0.75,
            )
        ],
        max_group_abs_contribution_group="semiconductor",
        max_group_abs_contribution_share=0.80,
        top3_group_abs_contribution_share=0.80,
        max_group_average_weight_group="semiconductor",
        max_group_average_weight=0.30,
        top3_group_average_weight=0.30,
        group_attribution=[
            PortfolioGroupAttribution(
                group="semiconductor",
                member_symbols=("2330", "2454"),
                selected_bar_count=12,
                rebalance_selected_count=3,
                average_weight=0.30,
                return_contribution=0.15,
                absolute_contribution_share=0.80,
            )
        ],
    )


if __name__ == "__main__":
    unittest.main()
