from __future__ import annotations

import unittest

from tools.multi_stock_entry_edge_sweep import (
    SweepRow,
    build_aggregates,
    parse_hold_bars_list,
)
from tools.multi_stock_target_state_sweep import (
    TargetStateRow,
    _drawdown_attribution,
    build_aggregates as build_target_state_aggregates,
    build_parser as build_target_state_parser,
    parse_cost_multipliers_list,
)
from signal_forge.backtesting.backtester import BacktestResult, EquityPoint


class MultiStockSweepToolTests(unittest.TestCase):
    def test_parse_hold_bars_list_requires_positive_integers(self) -> None:
        """
        用途與流程：驗證多股票 sweep 工具能把逗號分隔持有期解析成正整數 tuple，並拒絕
        空欄位或非正整數。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 parser 行為偏離預期，unittest assertion 會回報失敗。
        """
        self.assertEqual(parse_hold_bars_list("1, 3,10"), (1, 3, 10))
        with self.assertRaises(ValueError):
            parse_hold_bars_list("1,0")
        with self.assertRaises(ValueError):
            parse_hold_bars_list("1,,3")

    def test_build_aggregates_uses_total_profit_and_loss_for_pf(self) -> None:
        """
        用途與流程：驗證 aggregate PF 使用跨股票 gross profit / gross loss 加總，而不是
        直接平均各股票自己的 PF，避免少數股票扭曲多股票比較。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 aggregate 計算公式改變，assertion 會回報失敗。
        """
        rows = [
            _row("2330", gross_profit=300.0, gross_loss=-100.0),
            _row("2317", gross_profit=100.0, gross_loss=-100.0),
        ]

        aggregates = build_aggregates(rows)

        self.assertEqual(len(aggregates), 1)
        self.assertEqual(aggregates[0].stock_count, 2)
        self.assertEqual(aggregates[0].total_trades, 20)
        self.assertAlmostEqual(aggregates[0].aggregate_profit_factor or 0.0, 2.0)

    def test_parse_cost_multipliers_list_requires_positive_numbers(self) -> None:
        """
        用途與流程：驗證 target-state sweep 可解析 1x/2x/3x 成本壓力倍率，並拒絕空欄位、非數字或非正數。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 parser 行為偏離預期，unittest assertion 會回報失敗。
        """
        self.assertEqual(parse_cost_multipliers_list("1, 2.5,3"), (1.0, 2.5, 3.0))
        with self.assertRaises(ValueError):
            parse_cost_multipliers_list("1,0")
        with self.assertRaises(ValueError):
            parse_cost_multipliers_list("1,,3")

    def test_target_state_aggregates_track_benchmark_and_drawdown_counts(self) -> None:
        """
        用途與流程：驗證 target-state aggregate 會同時計算正報酬、勝過 benchmark 與低於 benchmark 回撤的股票數，避免只看平均報酬。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 aggregate 規則改變，unittest assertion 會回報失敗。
        """
        rows = [
            _target_state_row(
                "2330",
                total_return=0.20,
                benchmark_total_return=0.10,
                max_drawdown=-0.05,
                benchmark_max_drawdown=-0.20,
            ),
            _target_state_row(
                "2317",
                total_return=-0.10,
                benchmark_total_return=0.05,
                max_drawdown=-0.25,
                benchmark_max_drawdown=-0.15,
            ),
        ]

        aggregates = build_target_state_aggregates(rows)

        self.assertEqual(len(aggregates), 1)
        self.assertEqual(aggregates[0].stock_count, 2)
        self.assertEqual(aggregates[0].positive_return_count, 1)
        self.assertEqual(aggregates[0].outperform_benchmark_count, 1)
        self.assertEqual(aggregates[0].lower_drawdown_than_benchmark_count, 1)
        self.assertAlmostEqual(aggregates[0].average_total_return, 0.05)
        self.assertAlmostEqual(aggregates[0].average_benchmark_excess_return, -0.025)
        self.assertEqual(aggregates[0].worst_drawdown_symbol, "2317")
        self.assertEqual(aggregates[0].worst_drawdown_trough_timestamp, "2026-01-03")

    def test_target_state_drawdown_attribution_tracks_peak_trough_and_recovery(self) -> None:
        """
        用途與流程：驗證 target-state drawdown attribution 會定位最大回撤的 peak、trough、recovery 與回撤期間曝險，避免只知道 MDD 數字但不知道來源。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；若 attribution 演算法或欄位語意漂移，assertion 會失敗。
        """
        result = BacktestResult(
            strategy_name="test",
            start_equity=100.0,
            end_equity=105.0,
            total_return=0.05,
            max_drawdown=-0.30,
            trade_count=0,
            equity_curve=[
                EquityPoint("2026-01-01", 100.0, 0.0),
                EquityPoint("2026-01-02", 120.0, 0.5),
                EquityPoint("2026-01-03", 90.0, 0.8),
                EquityPoint("2026-01-04", 84.0, 0.4),
                EquityPoint("2026-01-05", 121.0, 0.0),
            ],
            trades=[],
        )

        attribution = _drawdown_attribution(result)

        self.assertEqual(attribution.start_timestamp, "2026-01-02")
        self.assertEqual(attribution.trough_timestamp, "2026-01-04")
        self.assertEqual(attribution.recovery_timestamp, "2026-01-05")
        self.assertEqual(attribution.duration_bars, 2)
        self.assertEqual(attribution.recovery_bars, 1)
        self.assertEqual(attribution.trough_position, 0.4)
        self.assertAlmostEqual(attribution.average_abs_position, (0.5 + 0.8 + 0.4) / 3)

    def test_target_state_parser_accepts_volatility_target_options(self) -> None:
        """
        用途與流程：驗證 target-state CLI 可接收 volatility target 相關參數，讓研究報表能用命令列重現波動縮放設定。
        參數：self 是 unittest 測試案例。
        回傳與錯誤：回傳 None；parser 參數名稱或預設型別漂移時 assertion 失敗。
        """
        args = build_target_state_parser().parse_args(
            [
                "--csv",
                "data.csv",
                "--volatility-target",
                "--volatility-lookback-bars",
                "30",
                "--target-annual-volatility",
                "0.25",
                "--volatility-min-observations",
                "20",
                "--volatility-max-scale",
                "0.8",
            ]
        )

        self.assertTrue(args.volatility_target)
        self.assertEqual(args.volatility_lookback_bars, 30)
        self.assertEqual(args.target_annual_volatility, 0.25)
        self.assertEqual(args.volatility_min_observations, 20)
        self.assertEqual(args.volatility_max_scale, 0.8)


def _row(symbol: str, *, gross_profit: float, gross_loss: float) -> SweepRow:
    """
    用途與流程：建立測試用 SweepRow，讓 aggregate 測試聚焦在 PF 彙總公式。
    參數：symbol 是股票代號；gross_profit/gross_loss 是該股票該策略的總獲利與總虧損。
    回傳與錯誤：回傳 SweepRow；本測試 helper 不做 I/O，也不主動拋錯。
    """
    return SweepRow(
        symbol=symbol,
        csv_path=f"{symbol}.csv",
        strategy="confluence-score",
        hold_bars=10,
        decision="pass",
        profit_factor_status="finite",
        profit_factor=gross_profit / abs(gross_loss),
        trade_count=10,
        win_rate=0.5,
        average_net_pnl=10.0,
        total_return=0.01,
        cagr=0.02,
        sharpe_ratio=1.0,
        sortino_ratio=1.2,
        calmar_ratio=0.5,
        max_drawdown=-0.1,
        benchmark_total_return=0.03,
        benchmark_max_drawdown=-0.2,
        benchmark_excess_return=-0.02,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        end_equity=10_100.0,
        overlapping_signal_count=0,
    )


def _target_state_row(
    symbol: str,
    *,
    total_return: float,
    benchmark_total_return: float,
    max_drawdown: float,
    benchmark_max_drawdown: float,
) -> TargetStateRow:
    """
    用途與流程：建立 target-state sweep 測試用 row，讓 aggregate 測試聚焦在 benchmark-relative 計算。
    參數：symbol 是股票代號；total_return/benchmark_total_return 是策略與 benchmark 報酬；max_drawdown/benchmark_max_drawdown 是兩者回撤。
    回傳與錯誤：回傳 TargetStateRow；此 helper 不做 I/O，也不主動拋錯。
    """
    return TargetStateRow(
        symbol=symbol,
        csv_path=f"{symbol}.csv",
        strategy="absolute-momentum",
        strategy_impl="absolute_momentum_m126_sma200_long_only",
        cost_multiplier=1.0,
        cost_label="1x",
        commission_bps=1.0,
        slippage_bps=1.0,
        transaction_tax_bps=0.0,
        total_return=total_return,
        cagr=0.03,
        sharpe_ratio=0.5,
        sortino_ratio=0.8,
        calmar_ratio=0.4,
        max_drawdown=max_drawdown,
        benchmark_total_return=benchmark_total_return,
        benchmark_cagr=0.02,
        benchmark_max_drawdown=benchmark_max_drawdown,
        benchmark_excess_return=total_return - benchmark_total_return,
        benchmark_excess_cagr=0.01,
        trade_count=4,
        total_cost=12.0,
        turnover=2.0,
        time_in_market=0.5,
        end_equity=10_000.0 * (1.0 + total_return),
        max_drawdown_start_timestamp="2026-01-01",
        max_drawdown_trough_timestamp="2026-01-03",
        max_drawdown_recovery_timestamp=None,
        max_drawdown_duration_bars=2,
        max_drawdown_recovery_bars=None,
        max_drawdown_trough_position=0.5,
        max_drawdown_average_abs_position=0.4,
    )


if __name__ == "__main__":
    unittest.main()
