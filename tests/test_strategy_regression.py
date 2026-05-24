from __future__ import annotations

import unittest

from helpers import bars_from_closes, bars_from_intraday_closes
from signal_forge import Bar, BarByBarStrategy
from signal_forge.strategies import (
    AbsoluteMomentumStrategy,
    ConfluenceScoreStrategy,
    OrbVolumeVwapStrategy,
    SmaCrossoverStrategy,
    VwapReversionStrategy,
)


class StrategyRegressionTests(unittest.TestCase):
    def test_sma_crossover_contract_after_template_refactor(self) -> None:
        """
        用途與流程：驗證 sma crossover contract after template refactor 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = SmaCrossoverStrategy(fast_window=2, slow_window=3, allow_short=False)

        self.assertIsInstance(strategy, BarByBarStrategy)
        signals = strategy.generate_signals(bars_from_closes([10, 11, 12, 13, 14, 15]))

        self.assertEqual([signal.target_position for signal in signals], [0.0, 0.0, 1.0, 1.0, 1.0, 1.0])
        self.assertEqual(
            [signal.reason for signal in signals],
            [
                "warmup",
                "warmup",
                "fast_sma_above_slow_sma",
                "fast_sma_above_slow_sma",
                "fast_sma_above_slow_sma",
                "fast_sma_above_slow_sma",
            ],
        )
        self.assertEqual([signal.score for signal in signals], [0.0] * 6)

    def test_vwap_reversion_hold_state_survives_template_refactor(self) -> None:
        """
        用途與流程：驗證 vwap reversion hold state survives template refactor 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = VwapReversionStrategy(
            window=3,
            entry_z=0.5,
            exit_z=0.25,
            allow_short=False,
        )

        self.assertIsInstance(strategy, BarByBarStrategy)
        signals = strategy.generate_signals(bars_from_closes([10, 11, 12, 8, 9]))

        self.assertEqual(
            [signal.reason for signal in signals],
            [
                "warmup",
                "warmup",
                "hold",
                "price_below_vwap_band",
                "hold",
            ],
        )
        self.assertEqual(
            [signal.target_position for signal in signals],
            [0.0, 0.0, 0.0, 1.0, 1.0],
        )
        self.assertGreater(signals[3].score, 0.0)
        self.assertGreater(signals[4].score, 0.0)

    def test_vwap_regime_filter_blocks_new_long_entry_below_regime_sma(self) -> None:
        """
        用途與流程：驗證 VWAP regime filter 在 close 低於 regime SMA 時只阻擋新的 long entry。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = VwapReversionStrategy(
            window=3,
            entry_z=0.5,
            exit_z=0.25,
            allow_short=False,
            regime_filter=True,
            regime_window=3,
        )

        signals = strategy.generate_signals(bars_from_closes([10, 20, 8]))

        self.assertEqual(signals[2].target_position, 0.0)
        self.assertEqual(signals[2].reason, "regime_downtrend_blocked")
        self.assertGreater(signals[2].score, 0.0)

    def test_vwap_regime_filter_allows_long_entry_above_regime_sma(self) -> None:
        """
        用途與流程：驗證 VWAP regime filter 在 close 不低於 regime SMA 時保留原本跌深進場 reason。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = VwapReversionStrategy(
            window=3,
            entry_z=0.5,
            exit_z=0.25,
            allow_short=False,
            regime_filter=True,
            regime_window=3,
        )

        signals = strategy.generate_signals(
            bars_from_closes([20, 10, 15], volumes=[100, 1, 1])
        )

        self.assertEqual(signals[2].target_position, 1.0)
        self.assertEqual(signals[2].reason, "price_below_vwap_band")
        self.assertGreater(signals[2].score, 0.0)

    def test_vwap_regime_filter_does_not_force_exit_existing_long(self) -> None:
        """
        用途與流程：驗證 VWAP regime filter 只處理 entry，不會在已持有時因 close 低於 regime SMA 強制歸零。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = VwapReversionStrategy(
            window=3,
            entry_z=0.5,
            exit_z=0.25,
            allow_short=False,
            regime_filter=True,
            regime_window=3,
        )

        signals = strategy.generate_signals(
            bars_from_closes([20, 10, 15, 8], volumes=[100, 1, 1, 1])
        )

        self.assertEqual(signals[2].target_position, 1.0)
        self.assertEqual(signals[3].target_position, 1.0)
        self.assertEqual(signals[3].reason, "price_below_vwap_band")

    def test_confluence_score_contract_after_template_refactor(self) -> None:
        """
        用途與流程：驗證 confluence score contract after template refactor 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = ConfluenceScoreStrategy(
            fast_window=2,
            slow_window=3,
            rsi_window=2,
            vwap_window=2,
            threshold=3.0,
            allow_short=False,
        )

        signals = strategy.generate_signals(
            bars_from_closes([10, 11, 12], volumes=[100, 120, 150])
        )

        self.assertEqual([signal.target_position for signal in signals], [0.0, 0.0, 1.0])
        self.assertEqual(
            signals[2].reason,
            "trend_up+above_slow_sma+above_vwap+momentum_positive+volume_confirms_up",
        )
        self.assertEqual(signals[2].score, 5.0)

    def test_absolute_momentum_requires_positive_momentum_and_trend(self) -> None:
        """
        用途與流程：驗證 Absolute Momentum 只有在回看報酬為正且 close 高於長期 SMA 時才輸出 long。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；若 warmup、負動能或趨勢濾網 reason/target 改變，assertion 會失敗。
        """
        strategy = AbsoluteMomentumStrategy(momentum_window=2, trend_window=3)

        self.assertIsInstance(strategy, BarByBarStrategy)
        signals = strategy.generate_signals(bars_from_closes([10, 11, 12, 11, 13]))

        self.assertEqual(
            [signal.target_position for signal in signals],
            [0.0, 0.0, 1.0, 0.0, 1.0],
        )
        self.assertEqual(
            [signal.reason for signal in signals],
            [
                "warmup",
                "warmup",
                "absolute_momentum_long",
                "absolute_momentum_negative",
                "absolute_momentum_long",
            ],
        )
        self.assertGreater(signals[2].score, 0.0)
        self.assertEqual(signals[3].score, 0.0)
        self.assertGreater(signals[4].score, 0.0)

    def test_absolute_momentum_blocks_positive_momentum_below_trend_sma(self) -> None:
        """
        用途與流程：驗證 Absolute Momentum 在回看報酬為正但價格仍低於趨勢 SMA 時維持空手。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；若趨勢濾網不再阻擋這種訊號，assertion 會失敗。
        """
        strategy = AbsoluteMomentumStrategy(momentum_window=2, trend_window=3)

        signals = strategy.generate_signals(bars_from_closes([10, 20, 12]))

        self.assertEqual(signals[2].target_position, 0.0)
        self.assertEqual(signals[2].reason, "trend_filter_blocked")
        self.assertGreater(signals[2].score, 0.0)

    def test_orb_volume_vwap_breakout_requires_or_volume_and_vwap_alignment(self) -> None:
        """
        用途與流程：驗證 ORB + Volume + VWAP 策略會在開盤區間完成後，只有 close 突破 OR high、量能放大且站上 session VWAP 時才翻成 long。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = OrbVolumeVwapStrategy(opening_range_minutes=2, volume_window=2, volume_multiplier=1.2)

        signals = strategy.generate_signals(
            bars_from_intraday_closes(
                [100, 101, 100.5, 102.5, 103.0],
                start_timestamp="2026-01-01T09:30",
                step_minutes=1,
                volumes=[100, 100, 100, 150, 110],
            )
        )

        self.assertIsInstance(strategy, BarByBarStrategy)
        self.assertEqual(
            [signal.reason for signal in signals],
            [
                "opening_range_building",
                "opening_range_building",
                "below_or_high",
                "orb_volume_vwap_breakout",
                "hold_intraday_breakout",
            ],
        )
        self.assertEqual(
            [signal.target_position for signal in signals],
            [0.0, 0.0, 0.0, 1.0, 1.0],
        )
        self.assertGreaterEqual(signals[3].score, 1.2)

    def test_orb_volume_vwap_resets_on_new_session_and_rejects_date_only_bars(self) -> None:
        """
        用途與流程：驗證 ORB + Volume + VWAP 策略在新 session 會先把前一日持倉歸零，且對只有日期沒有時間的資料不會誤判成 intraday ORB。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = OrbVolumeVwapStrategy(opening_range_minutes=2, volume_window=2, volume_multiplier=1.2)

        session_signals = strategy.generate_signals(
            bars_from_intraday_closes(
                [100, 101, 102.5, 99, 100, 103],
                start_timestamp="2026-01-01T09:30",
                step_minutes=1,
                volumes=[100, 100, 150, 100, 100, 150],
            )[:3]
            + bars_from_intraday_closes(
                [99, 100, 103],
                start_timestamp="2026-01-02T09:30",
                step_minutes=1,
                volumes=[100, 100, 150],
            )
        )
        self.assertEqual(session_signals[3].reason, "session_reset")
        self.assertEqual(session_signals[3].target_position, 0.0)
        self.assertEqual(session_signals[5].reason, "orb_volume_vwap_breakout")
        self.assertEqual(session_signals[5].target_position, 1.0)

        date_only_signals = strategy.generate_signals(bars_from_closes([100, 101, 102]))
        self.assertTrue(
            all(signal.reason == "session_timestamp_required" for signal in date_only_signals)
        )
        self.assertTrue(all(signal.target_position == 0.0 for signal in date_only_signals))

    def test_orb_volume_vwap_retest_confirmation_waits_for_touch_then_reenter(self) -> None:
        """
        用途與流程：驗證 ORB 策略啟用 retest confirmation 後，不會在第一次突破時立刻進場，而是等待回踩 OR high 並重新站穩才翻成 long。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = OrbVolumeVwapStrategy(
            opening_range_minutes=2,
            volume_window=2,
            volume_multiplier=1.2,
            require_retest_confirmation=True,
        )

        signals = strategy.generate_signals(
            bars_from_intraday_closes(
                [100, 101, 102.6, 102.7, 103.0],
                start_timestamp="2026-01-01T09:30",
                step_minutes=1,
                volumes=[100, 100, 150, 230, 230],
            )
        )

        self.assertEqual(
            [signal.reason for signal in signals],
            [
                "opening_range_building",
                "opening_range_building",
                "waiting_for_retest_confirmation",
                "orb_retest_vwap_breakout",
                "hold_intraday_breakout",
            ],
        )
        self.assertEqual(
            [signal.target_position for signal in signals],
            [0.0, 0.0, 0.0, 1.0, 1.0],
        )

    def test_orb_volume_vwap_can_shift_session_start_without_changing_orb_logic(self) -> None:
        """
        用途與流程：驗證 ORB 策略可透過 session start 參數把同一段 intraday 資料重新對齊到不同開盤時間，並在新起點完成 OR 後維持相同 breakout 語意。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = OrbVolumeVwapStrategy(
            opening_range_minutes=2,
            session_start_hour=8,
            session_start_minute=0,
            volume_window=2,
            volume_multiplier=1.2,
        )

        signals = strategy.generate_signals(
            bars_from_intraday_closes(
                [100, 101, 100.5, 102.5],
                start_timestamp="2026-01-01T08:00",
                step_minutes=1,
                volumes=[100, 100, 100, 150],
            )
        )

        self.assertEqual(
            [signal.reason for signal in signals],
            [
                "opening_range_building",
                "opening_range_building",
                "below_or_high",
                "orb_volume_vwap_breakout",
            ],
        )
        self.assertEqual(
            [signal.target_position for signal in signals],
            [0.0, 0.0, 0.0, 1.0],
        )

    def test_orb_volume_vwap_range_size_filter_blocks_too_narrow_opening_range(self) -> None:
        """
        用途與流程：驗證 ORB 策略可用開盤區間寬度百分比過濾極窄區間，避免把低品質假突破當成正常訊號。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = OrbVolumeVwapStrategy(
            opening_range_minutes=2,
            volume_window=2,
            volume_multiplier=1.2,
            min_opening_range_pct=0.02,
        )

        signals = strategy.generate_signals(
            [
                Bar("2026-01-01T09:30", 100.0, 100.6, 99.9, 100.2, 100),
                Bar("2026-01-01T09:31", 100.2, 100.8, 100.1, 100.5, 100),
                Bar("2026-01-01T09:32", 100.5, 101.2, 100.4, 100.9, 180),
                Bar("2026-01-01T09:33", 100.9, 101.3, 100.8, 101.0, 180),
            ]
        )

        self.assertEqual(signals[2].reason, "opening_range_too_narrow")
        self.assertEqual(signals[2].target_position, 0.0)
        self.assertLess(signals[2].score, 0.02)

    def test_orb_volume_vwap_breakout_distance_threshold_blocks_shallow_close(self) -> None:
        """
        用途與流程：驗證 ORB 策略可用最小突破距離百分比阻擋只比 OR high 高一點點的 close，避免把貼線雜訊當成有效突破。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = OrbVolumeVwapStrategy(
            opening_range_minutes=2,
            volume_window=2,
            volume_multiplier=1.2,
            min_breakout_pct=0.01,
        )

        signals = strategy.generate_signals(
            [
                Bar("2026-01-01T09:30", 100.0, 100.8, 99.8, 100.2, 100),
                Bar("2026-01-01T09:31", 100.2, 101.0, 100.0, 100.8, 100),
                Bar("2026-01-01T09:32", 100.8, 101.5, 100.7, 101.005, 150),
                Bar("2026-01-01T09:33", 101.005, 102.5, 100.9, 102.2, 260),
            ]
        )

        self.assertEqual(signals[2].reason, "breakout_distance_too_small")
        self.assertEqual(signals[2].target_position, 0.0)
        self.assertLess(signals[2].score, 0.01)
        self.assertEqual(signals[3].reason, "orb_volume_vwap_breakout")
        self.assertEqual(signals[3].target_position, 1.0)

    def test_orb_volume_vwap_full_bar_above_range_blocks_reentry_into_or(self) -> None:
        """
        用途與流程：驗證 ORB 策略可要求 breakout candle 的整根 bar 都站在 OR high 上方，避免只有 close 越線但下影仍回到區間內的假突破。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = OrbVolumeVwapStrategy(
            opening_range_minutes=2,
            volume_window=2,
            volume_multiplier=1.2,
            require_full_bar_above_range=True,
        )

        signals = strategy.generate_signals(
            [
                Bar("2026-01-01T09:30", 100.0, 100.8, 99.8, 100.2, 100),
                Bar("2026-01-01T09:31", 100.2, 101.0, 100.0, 100.8, 100),
                Bar("2026-01-01T09:32", 100.8, 101.6, 100.9, 101.2, 150),
                Bar("2026-01-01T09:33", 101.2, 102.5, 101.1, 102.2, 260),
            ]
        )

        self.assertEqual(signals[2].reason, "breakout_bar_reentered_range")
        self.assertEqual(signals[2].target_position, 0.0)
        self.assertGreater(signals[2].score, 0.0)
        self.assertEqual(signals[3].reason, "orb_volume_vwap_breakout")
        self.assertEqual(signals[3].target_position, 1.0)

    def test_orb_volume_vwap_breakout_body_strength_blocks_weak_breakout_candle(self) -> None:
        """
        用途與流程：驗證 ORB 策略可要求 breakout candle 的 body ratio 達到下限，避免只靠長上下影或小實體 K 棒就把突破視為有效。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = OrbVolumeVwapStrategy(
            opening_range_minutes=2,
            volume_window=2,
            volume_multiplier=1.2,
            min_breakout_body_pct=0.6,
        )

        signals = strategy.generate_signals(
            [
                Bar("2026-01-01T09:30", 100.0, 100.8, 99.8, 100.2, 100),
                Bar("2026-01-01T09:31", 100.2, 101.0, 100.0, 100.8, 100),
                Bar("2026-01-01T09:32", 100.95, 101.7, 100.8, 101.2, 150),
                Bar("2026-01-01T09:33", 101.15, 102.4, 101.1, 102.2, 260),
            ]
        )

        self.assertEqual(signals[2].reason, "breakout_body_too_small")
        self.assertEqual(signals[2].target_position, 0.0)
        self.assertLess(signals[2].score, 0.6)
        self.assertEqual(signals[3].reason, "orb_volume_vwap_breakout")
        self.assertEqual(signals[3].target_position, 1.0)
        self.assertGreaterEqual(signals[3].score, 1.2)

    def test_orb_volume_vwap_fresh_breakout_gate_blocks_late_rebreak_above_or(self) -> None:
        """
        用途與流程：驗證 ORB 策略可要求 breakout 必須從 OR 盒子內部發動，避免前一根 close 已在 OR 外時，後續 bar 又被當成新的 fresh breakout。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = OrbVolumeVwapStrategy(
            opening_range_minutes=2,
            volume_window=2,
            volume_multiplier=1.2,
            require_fresh_breakout_from_or=True,
        )

        signals = strategy.generate_signals(
            [
                Bar("2026-01-01T09:30", 100.0, 100.8, 99.8, 100.2, 100),
                Bar("2026-01-01T09:31", 100.2, 101.0, 100.0, 100.8, 100),
                Bar("2026-01-01T09:32", 100.8, 101.6, 100.7, 101.2, 100),
                Bar("2026-01-01T09:33", 101.2, 102.4, 101.1, 102.2, 260),
            ]
        )

        self.assertEqual(signals[2].reason, "breakout_volume_blocked")
        self.assertEqual(signals[2].target_position, 0.0)
        self.assertEqual(signals[3].reason, "breakout_not_fresh_from_or")
        self.assertEqual(signals[3].target_position, 0.0)
        self.assertGreater(signals[3].score, 0.0)

    def test_orb_volume_vwap_can_use_opening_range_volume_as_breakout_baseline(self) -> None:
        """
        用途與流程：驗證 ORB 策略可選擇以 opening range 平均量能當成 breakout baseline，避免 rolling volume SMA 被開盤後的高量非突破 bar 拉高，導致原本合理的突破被誤擋。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        bars = [
            Bar("2026-01-01T09:30", 100.0, 100.8, 99.8, 100.2, 40),
            Bar("2026-01-01T09:31", 100.2, 101.0, 100.0, 100.8, 60),
            Bar("2026-01-01T09:32", 100.8, 100.95, 100.4, 100.9, 300),
            Bar("2026-01-01T09:33", 100.9, 102.4, 100.8, 102.2, 100),
        ]
        default_strategy = OrbVolumeVwapStrategy(
            opening_range_minutes=2,
            volume_window=3,
            volume_multiplier=1.5,
        )
        opening_range_volume_strategy = OrbVolumeVwapStrategy(
            opening_range_minutes=2,
            volume_window=3,
            volume_multiplier=1.5,
            use_opening_range_volume_baseline=True,
        )

        default_signals = default_strategy.generate_signals(bars)
        opening_range_volume_signals = opening_range_volume_strategy.generate_signals(bars)

        self.assertEqual(default_signals[3].reason, "breakout_volume_blocked")
        self.assertEqual(default_signals[3].target_position, 0.0)
        self.assertLess(default_signals[3].score, 1.5)
        self.assertEqual(opening_range_volume_signals[3].reason, "orb_volume_vwap_breakout")
        self.assertEqual(opening_range_volume_signals[3].target_position, 1.0)
        self.assertEqual(opening_range_volume_signals[3].score, 2.0)

    def test_orb_volume_vwap_signal_window_cutoff_blocks_late_breakout_without_forcing_exit(self) -> None:
        """
        用途與流程：驗證 ORB 策略可限制只在 session 開始後某段時間內接受新的 breakout；超出時間窗的 late breakout 會被擋下，但既有 long 不會因此被強制平倉。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        late_breakout_strategy = OrbVolumeVwapStrategy(
            opening_range_minutes=2,
            signal_window_minutes=4,
            volume_window=2,
            volume_multiplier=1.2,
        )
        late_breakout_signals = late_breakout_strategy.generate_signals(
            [
                Bar("2026-01-01T09:30", 100.0, 100.8, 99.8, 100.2, 100),
                Bar("2026-01-01T09:31", 100.2, 101.0, 100.0, 100.8, 100),
                Bar("2026-01-01T09:32", 100.8, 100.95, 100.4, 100.9, 120),
                Bar("2026-01-01T09:33", 100.9, 100.98, 100.6, 100.95, 120),
                Bar("2026-01-01T09:34", 100.95, 102.6, 100.9, 102.2, 180),
            ]
        )

        self.assertEqual(late_breakout_signals[4].reason, "outside_signal_window")
        self.assertEqual(late_breakout_signals[4].target_position, 0.0)
        self.assertEqual(late_breakout_signals[4].score, 4.0)

        hold_strategy = OrbVolumeVwapStrategy(
            opening_range_minutes=2,
            signal_window_minutes=4,
            volume_window=2,
            volume_multiplier=1.2,
        )
        hold_signals = hold_strategy.generate_signals(
            [
                Bar("2026-01-01T09:30", 100.0, 100.8, 99.8, 100.2, 100),
                Bar("2026-01-01T09:31", 100.2, 101.0, 100.0, 100.8, 100),
                Bar("2026-01-01T09:32", 100.8, 102.0, 100.7, 101.4, 150),
                Bar("2026-01-01T09:33", 101.4, 102.6, 101.2, 102.2, 180),
                Bar("2026-01-01T09:34", 102.2, 102.8, 101.9, 102.3, 120),
            ]
        )

        self.assertEqual(hold_signals[2].reason, "orb_volume_vwap_breakout")
        self.assertEqual(hold_signals[2].target_position, 1.0)
        self.assertEqual(hold_signals[4].reason, "hold_intraday_breakout")
        self.assertEqual(hold_signals[4].target_position, 1.0)

    def test_orb_volume_vwap_vwap_slope_confirmation_blocks_flat_or_falling_vwap(self) -> None:
        """
        用途與流程：驗證 ORB 策略可要求 breakout 當下的 session VWAP 相對前一根同 session bar 保持上升，避免只因價格站上 VWAP 就在平或下彎的 VWAP 上方追突破。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        blocked_strategy = OrbVolumeVwapStrategy(
            opening_range_minutes=2,
            volume_window=2,
            volume_multiplier=1.2,
            require_vwap_slope_confirmation=True,
        )
        blocked_signals = blocked_strategy.generate_signals(
            [
                Bar("2026-01-01T09:30", 100.0, 101.0, 99.0, 101.0, 100),
                Bar("2026-01-01T09:31", 101.0, 102.0, 100.0, 102.0, 100),
                Bar("2026-01-01T09:32", 102.0, 104.0, 90.0, 103.0, 150),
            ]
        )

        self.assertEqual(blocked_signals[2].reason, "breakout_vwap_slope_blocked")
        self.assertEqual(blocked_signals[2].target_position, 0.0)
        self.assertLessEqual(blocked_signals[2].score, 0.0)

        allowed_strategy = OrbVolumeVwapStrategy(
            opening_range_minutes=2,
            volume_window=2,
            volume_multiplier=1.2,
            require_vwap_slope_confirmation=True,
        )
        allowed_signals = allowed_strategy.generate_signals(
            bars_from_intraday_closes(
                [100, 101, 100.5, 102.5],
                start_timestamp="2026-01-01T09:30",
                step_minutes=1,
                volumes=[100, 100, 100, 150],
            )
        )

        self.assertEqual(allowed_signals[3].reason, "orb_volume_vwap_breakout")
        self.assertEqual(allowed_signals[3].target_position, 1.0)

    def test_orb_volume_vwap_ema_trend_confirmation_requires_close_above_ema(self) -> None:
        """
        用途與流程：驗證 ORB 策略可要求 breakout 當下 close 站在 rolling EMA 上方；若價格雖然突破 OR high，但仍未站回 EMA 上方，就不應被視為有效突破。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        below_ema_strategy = OrbVolumeVwapStrategy(
            opening_range_minutes=2,
            ema_window=3,
            volume_window=2,
            volume_multiplier=1.2,
            require_ema_trend_confirmation=True,
        )
        below_ema_signals = below_ema_strategy.generate_signals(
            [
                Bar("2026-01-01T09:30", 102.0, 102.4, 101.8, 102.0, 100),
                Bar("2026-01-01T09:31", 102.0, 103.0, 101.9, 103.0, 100),
                Bar("2026-01-01T09:32", 103.0, 105.2, 102.9, 105.0, 100),
                Bar("2026-01-01T09:33", 103.0, 103.6, 102.8, 103.1, 150),
            ]
        )

        self.assertEqual(below_ema_signals[3].reason, "breakout_below_ema")
        self.assertEqual(below_ema_signals[3].target_position, 0.0)
        self.assertGreater(below_ema_signals[3].score, 0.0)

        allowed_strategy = OrbVolumeVwapStrategy(
            opening_range_minutes=2,
            ema_window=2,
            volume_window=2,
            volume_multiplier=1.2,
            require_ema_trend_confirmation=True,
        )
        allowed_signals = allowed_strategy.generate_signals(
            bars_from_intraday_closes(
                [100, 101, 100.5, 102.5],
                start_timestamp="2026-01-01T09:30",
                step_minutes=1,
                volumes=[100, 100, 100, 150],
            )
        )

        self.assertEqual(allowed_signals[3].reason, "orb_volume_vwap_breakout")
        self.assertEqual(allowed_signals[3].target_position, 1.0)

    def test_orb_volume_vwap_can_reject_breakout_when_ema_sits_inside_or_box(self) -> None:
        """
        用途與流程：驗證 ORB 策略可用 EMA 與 opening range 的相對位置作為結構 gate；若 breakout 發生時 rolling EMA 仍落在 OR 盒子內，則不應把這次突破視為有效訊號。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        blocked_strategy = OrbVolumeVwapStrategy(
            opening_range_minutes=2,
            ema_window=4,
            volume_window=2,
            volume_multiplier=1.2,
            reject_ema_inside_opening_range=True,
        )
        blocked_signals = blocked_strategy.generate_signals(
            [
                Bar("2026-01-01T09:30", 100.0, 100.8, 99.8, 100.0, 100),
                Bar("2026-01-01T09:31", 100.0, 102.0, 100.0, 101.0, 100),
                Bar("2026-01-01T09:32", 101.0, 102.1, 100.7, 101.8, 110),
                Bar("2026-01-01T09:33", 101.8, 103.4, 101.7, 103.2, 170),
            ]
        )

        self.assertEqual(blocked_signals[3].reason, "ema_inside_opening_range")
        self.assertEqual(blocked_signals[3].target_position, 0.0)
        self.assertGreater(blocked_signals[3].score, 99.8)
        self.assertLess(blocked_signals[3].score, 102.0)

        allowed_strategy = OrbVolumeVwapStrategy(
            opening_range_minutes=2,
            ema_window=4,
            volume_window=2,
            volume_multiplier=1.2,
            reject_ema_inside_opening_range=True,
        )
        allowed_signals = allowed_strategy.generate_signals(
            [
                Bar("2026-01-01T09:30", 100.0, 100.8, 99.8, 100.0, 100),
                Bar("2026-01-01T09:31", 100.0, 102.0, 100.0, 101.0, 100),
                Bar("2026-01-01T09:32", 101.0, 104.2, 100.9, 104.0, 110),
                Bar("2026-01-01T09:33", 104.0, 105.4, 103.8, 105.0, 170),
            ]
        )

        self.assertEqual(allowed_signals[3].reason, "orb_volume_vwap_breakout")
        self.assertEqual(allowed_signals[3].target_position, 1.0)


if __name__ == "__main__":
    unittest.main()
