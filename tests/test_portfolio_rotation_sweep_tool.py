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
    PortfolioSymbolAttribution,
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
        self.assertEqual(args.top_n, 2)
        self.assertEqual(args.min_return, 0.02)
        self.assertEqual(args.cost_multipliers_list, "1,3")
        self.assertTrue(args.market_regime_filter)
        self.assertEqual(args.market_regime_sma_bars, 2)
        self.assertTrue(args.breadth_filter)
        self.assertEqual(args.breadth_lookback_bars, 4)
        self.assertEqual(args.breadth_min_positive_count, 2)
        self.assertEqual(args.breadth_positive_threshold, 0.01)
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
        self.assertIn("| 1x | 1 | 2330 | 12.00% | 75.00%", markdown)

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


def _bar(timestamp: str, close: float) -> Bar:
    """
    用途與流程：建立 portfolio rotation 測試用 Bar，讓測試聚焦 timestamp 與 close。
    參數：timestamp 是日期字串；close 是收盤價，並同步填入 open/high/low。
    回傳與錯誤：回傳 Bar；此 helper 不做 I/O，也不主動拋錯。
    """
    return Bar(
        timestamp=timestamp,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1_000.0,
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
        top_n=1,
        min_return=0.0,
        market_regime_filter=False,
        market_regime_sma_bars=126,
        breadth_filter=False,
        breadth_lookback_bars=21,
        breadth_min_positive_count=1,
        breadth_positive_threshold=0.0,
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
        volatility_scaled_rebalance_count=0,
        volatility_warmup_count=0,
        total_cost=0.0,
        average_turnover=1.0,
        average_breadth_positive_count=None,
        average_volatility_scale=None,
        average_exposure=1.0,
        average_selected_count=1.0,
        end_equity=10_000.0 * (1.0 + total_return),
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
    )


if __name__ == "__main__":
    unittest.main()
