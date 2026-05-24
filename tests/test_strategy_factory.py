from __future__ import annotations

import unittest

from signal_forge.strategies import (
    STRATEGY_PARAMETER_DEFAULTS,
    SUPPORTED_STRATEGY_NAMES,
    AbsoluteMomentumStrategy,
    ConfluenceScoreStrategy,
    OrbVolumeVwapStrategy,
    SignalCooldownStrategy,
    SmaCrossoverStrategy,
    VolumeFilteredStrategy,
    VwapReversionStrategy,
    build_phase1_strategy,
    build_strategy,
)


class StrategyFactoryTests(unittest.TestCase):
    def test_supported_strategy_names_are_registry_backed(self) -> None:
        """
        用途與流程：驗證 supported strategy names are registry backed 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        self.assertEqual(
            SUPPORTED_STRATEGY_NAMES,
            (
                "sma-crossover",
                "vwap-reversion",
                "confluence-score",
                "absolute-momentum",
                "orb-volume-vwap",
            ),
        )
        self.assertIsInstance(build_phase1_strategy("sma-crossover"), SmaCrossoverStrategy)
        self.assertIsInstance(build_phase1_strategy("vwap-reversion"), VwapReversionStrategy)
        self.assertIsInstance(
            build_phase1_strategy("confluence-score"), ConfluenceScoreStrategy
        )
        self.assertIsInstance(
            build_phase1_strategy("absolute-momentum"), AbsoluteMomentumStrategy
        )
        self.assertIsInstance(build_phase1_strategy("orb-volume-vwap"), OrbVolumeVwapStrategy)

    def test_phase1_factory_builds_long_only_strategies(self) -> None:
        """
        用途與流程：驗證 phase1 factory builds long only strategies 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        self.assertEqual(build_phase1_strategy("sma-crossover").name, "sma_20_200_long_only")
        self.assertEqual(
            build_phase1_strategy("vwap-reversion").name,
            "vwap_reversion_20_long_only",
        )
        self.assertEqual(
            build_phase1_strategy("confluence-score").name,
            "confluence_score_long_only",
        )
        self.assertEqual(
            build_phase1_strategy("absolute-momentum").name,
            "absolute_momentum_m126_sma200_long_only",
        )
        self.assertEqual(
            build_phase1_strategy("orb-volume-vwap").name,
            "orb_volume_vwap_ss0930_or30_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
        )
        confluence = build_phase1_strategy("confluence-score")
        self.assertIsInstance(confluence, ConfluenceScoreStrategy)
        self.assertEqual(confluence.slow_window, 50)

    def test_phase1_factory_can_enable_vwap_regime_filter(self) -> None:
        """
        用途與流程：驗證 Phase 1 factory 可選擇性啟用 VWAP regime filter，且預設行為仍維持舊策略名稱。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        self.assertEqual(
            build_phase1_strategy("vwap-reversion").name,
            "vwap_reversion_20_long_only",
        )
        self.assertEqual(
            build_phase1_strategy(
                "vwap-reversion",
                vwap_regime_filter=True,
                vwap_regime_window=50,
            ).name,
            "vwap_reversion_20_regime_sma50_long_only",
        )

    def test_phase1_factory_can_enable_orb_retest_confirmation(self) -> None:
        """
        用途與流程：驗證 Phase 1 factory 可選擇性啟用 ORB retest confirmation，且預設名稱仍維持第一時間突破版本。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        self.assertEqual(
            build_phase1_strategy("orb-volume-vwap").name,
            "orb_volume_vwap_ss0930_or30_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
        )
        self.assertEqual(
            build_phase1_strategy(
                "orb-volume-vwap",
                orb_retest_confirmation=True,
            ).name,
            "orb_volume_vwap_ss0930_or30_closeonly_vw20_vm1.50_with_vwap_with_retest_long_only",
        )
        self.assertEqual(
            build_phase1_strategy(
                "orb-volume-vwap",
                orb_opening_range_minutes=15,
                orb_session_start_hour=8,
                orb_session_start_minute=45,
            ).name,
            "orb_volume_vwap_ss0845_or15_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
        )
        self.assertEqual(
            build_phase1_strategy(
                "orb-volume-vwap",
                orb_min_range_pct=0.01,
                orb_max_range_pct=0.05,
            ).name,
            "orb_volume_vwap_ss0930_or30_orpct0.010-0.050_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
        )
        self.assertEqual(
            build_phase1_strategy(
                "orb-volume-vwap",
                orb_min_breakout_pct=0.005,
            ).name,
            "orb_volume_vwap_ss0930_or30_obp0.005_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
        )
        self.assertEqual(
            build_phase1_strategy(
                "orb-volume-vwap",
                orb_full_bar_above_range=True,
            ).name,
            "orb_volume_vwap_ss0930_or30_fullbar_vw20_vm1.50_with_vwap_no_retest_long_only",
        )
        self.assertEqual(
            build_phase1_strategy(
                "orb-volume-vwap",
                orb_min_breakout_body_pct=0.60,
            ).name,
            "orb_volume_vwap_ss0930_or30_body0.60_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
        )
        self.assertEqual(
            build_phase1_strategy(
                "orb-volume-vwap",
                orb_fresh_breakout_from_or=True,
            ).name,
            "orb_volume_vwap_ss0930_or30_fresh_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
        )
        self.assertEqual(
            build_phase1_strategy(
                "orb-volume-vwap",
                orb_use_opening_range_volume_baseline=True,
            ).name,
            "orb_volume_vwap_ss0930_or30_orvol_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
        )
        self.assertEqual(
            build_phase1_strategy(
                "orb-volume-vwap",
                orb_signal_window_minutes=120,
            ).name,
            "orb_volume_vwap_ss0930_or30_sigw120_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
        )
        self.assertEqual(
            build_phase1_strategy(
                "orb-volume-vwap",
                orb_vwap_slope_confirmation=True,
            ).name,
            "orb_volume_vwap_ss0930_or30_vslope_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
        )
        self.assertEqual(
            build_phase1_strategy(
                "orb-volume-vwap",
                orb_ema_trend_confirmation=True,
                orb_ema_window=10,
            ).name,
            "orb_volume_vwap_ss0930_or30_ema10_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
        )
        self.assertEqual(
            build_phase1_strategy(
                "orb-volume-vwap",
                orb_reject_ema_inside_opening_range=True,
            ).name,
            "orb_volume_vwap_ss0930_or30_emabox_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
        )
        strategy = build_phase1_strategy(
            "orb-volume-vwap",
            orb_session_end_hour=15,
            orb_session_end_minute=30,
            orb_session_timezone="Asia/Taipei",
        )
        self.assertEqual(strategy.session_end_hour, 15)
        self.assertEqual(strategy.session_end_minute, 30)
        self.assertEqual(strategy.session_timezone, "Asia/Taipei")

    def test_direct_factory_preserves_strategy_constructor_defaults(self) -> None:
        """
        用途與流程：驗證 direct factory preserves strategy constructor defaults 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        self.assertEqual(build_strategy("sma-crossover").name, "sma_20_200_long_only")
        self.assertEqual(
            build_strategy("vwap-reversion").name,
            "vwap_reversion_20_long_short",
        )
        self.assertEqual(
            build_strategy("confluence-score").name,
            "confluence_score_long_short",
        )
        self.assertEqual(
            build_strategy("absolute-momentum").name,
            "absolute_momentum_m126_sma200_long_only",
        )
        self.assertEqual(
            build_strategy("orb-volume-vwap").name,
            "orb_volume_vwap_ss0930_or30_closeonly_vw20_vm1.50_with_vwap_no_retest_long_only",
        )
        confluence = build_strategy("confluence-score")
        self.assertIsInstance(confluence, ConfluenceScoreStrategy)
        self.assertEqual(confluence.slow_window, 50)

    def test_strategy_defaults_are_registered_for_cli_display(self) -> None:
        """
        用途與流程：驗證 strategy default registry 與各策略 constructor 預設值一致，避免 CLI 未輸入參數時套用錯誤的全域預設。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        self.assertEqual(
            STRATEGY_PARAMETER_DEFAULTS["sma-crossover"].slow_window,
            SmaCrossoverStrategy.slow_window,
        )
        self.assertEqual(
            STRATEGY_PARAMETER_DEFAULTS["vwap-reversion"].vwap_window,
            VwapReversionStrategy.window,
        )
        self.assertEqual(
            STRATEGY_PARAMETER_DEFAULTS["confluence-score"].slow_window,
            ConfluenceScoreStrategy.slow_window,
        )
        self.assertEqual(
            STRATEGY_PARAMETER_DEFAULTS["absolute-momentum"].fast_window,
            AbsoluteMomentumStrategy.momentum_window,
        )
        self.assertEqual(
            STRATEGY_PARAMETER_DEFAULTS["absolute-momentum"].slow_window,
            AbsoluteMomentumStrategy.trend_window,
        )
        self.assertEqual(
            STRATEGY_PARAMETER_DEFAULTS["orb-volume-vwap"].threshold,
            0.0,
        )
        self.assertEqual(
            STRATEGY_PARAMETER_DEFAULTS["orb-volume-vwap"].orb_session_start_hour,
            OrbVolumeVwapStrategy.session_start_hour,
        )
        self.assertEqual(
            STRATEGY_PARAMETER_DEFAULTS["orb-volume-vwap"].orb_session_end_hour,
            OrbVolumeVwapStrategy.session_end_hour,
        )
        self.assertEqual(
            STRATEGY_PARAMETER_DEFAULTS["orb-volume-vwap"].orb_session_end_minute,
            OrbVolumeVwapStrategy.session_end_minute,
        )
        self.assertEqual(
            STRATEGY_PARAMETER_DEFAULTS["orb-volume-vwap"].orb_session_timezone,
            OrbVolumeVwapStrategy.session_timezone,
        )
        self.assertFalse(
            STRATEGY_PARAMETER_DEFAULTS["orb-volume-vwap"].orb_require_vwap_slope_confirmation
        )
        self.assertEqual(
            STRATEGY_PARAMETER_DEFAULTS["orb-volume-vwap"].orb_ema_window,
            OrbVolumeVwapStrategy.ema_window,
        )
        self.assertFalse(
            STRATEGY_PARAMETER_DEFAULTS["orb-volume-vwap"].orb_require_ema_trend_confirmation
        )
        self.assertFalse(
            STRATEGY_PARAMETER_DEFAULTS["orb-volume-vwap"].orb_reject_ema_inside_opening_range
        )
        self.assertEqual(
            STRATEGY_PARAMETER_DEFAULTS["orb-volume-vwap"].orb_min_range_pct,
            0.0,
        )
        self.assertEqual(
            STRATEGY_PARAMETER_DEFAULTS["orb-volume-vwap"].orb_min_breakout_pct,
            0.0,
        )
        self.assertFalse(
            STRATEGY_PARAMETER_DEFAULTS["orb-volume-vwap"].orb_require_full_bar_above_range
        )
        self.assertEqual(
            STRATEGY_PARAMETER_DEFAULTS["orb-volume-vwap"].orb_min_breakout_body_pct,
            0.0,
        )
        self.assertFalse(
            STRATEGY_PARAMETER_DEFAULTS["orb-volume-vwap"].orb_require_fresh_breakout_from_or
        )
        self.assertFalse(
            STRATEGY_PARAMETER_DEFAULTS["orb-volume-vwap"].orb_use_opening_range_volume_baseline
        )
        self.assertIsNone(
            STRATEGY_PARAMETER_DEFAULTS["orb-volume-vwap"].orb_signal_window_minutes
        )

    def test_phase1_factory_can_wrap_volume_filter(self) -> None:
        """
        用途與流程：驗證 phase1 factory can wrap volume filter 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        strategy = build_phase1_strategy(
            "sma-crossover",
            fast_window=1,
            slow_window=2,
            volume_filter=True,
            volume_window=1,
            volume_multiplier=1.0,
        )

        self.assertIsInstance(strategy, VolumeFilteredStrategy)
        self.assertEqual(strategy.name, "volume_filter_w1_m1.00__sma_1_2_long_only")

    def test_phase1_factory_can_wrap_signal_cooldown(self) -> None:
        """
        用途與流程：驗證 Phase 1 factory 可選擇性套用 signal cooldown wrapper，且 wrapper 會包在其他 entry filter 之後。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；assertion 失敗時由 unittest 回報。
        """
        strategy = build_phase1_strategy(
            "sma-crossover",
            fast_window=1,
            slow_window=2,
            volume_filter=True,
            volume_window=1,
            volume_multiplier=1.0,
            signal_cooldown_bars=10,
        )

        self.assertIsInstance(strategy, SignalCooldownStrategy)
        self.assertEqual(
            strategy.name,
            "signal_cooldown_b10__volume_filter_w1_m1.00__sma_1_2_long_only",
        )

    def test_rejects_unsupported_strategy_name(self) -> None:
        """
        用途與流程：驗證 rejects unsupported strategy name 這個行為或 regression contract，透過 unittest assertion 鎖住預期結果。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
        """
        with self.assertRaisesRegex(ValueError, "unsupported strategy unknown"):
            build_strategy("unknown")

    def test_absolute_momentum_rejects_short_mode(self) -> None:
        """
        用途與流程：驗證 Absolute Momentum 第一版策略只允許 long-only，避免 Phase 1 factory 誤接成多空策略。
        參數：self 表示目前 unittest 測試案例。
        回傳與錯誤：回傳 None；若 factory 沒有拒絕 allow_short=True，assertion 會失敗。
        """
        with self.assertRaisesRegex(ValueError, "only supports long-only"):
            build_strategy("absolute-momentum", allow_short=True)


if __name__ == "__main__":
    unittest.main()
