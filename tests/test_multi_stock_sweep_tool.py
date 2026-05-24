from __future__ import annotations

import unittest

from tools.multi_stock_entry_edge_sweep import (
    SweepRow,
    build_aggregates,
    parse_hold_bars_list,
)


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


if __name__ == "__main__":
    unittest.main()
