from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from signal_forge.core.market_data import Bar
from signal_forge.strategies import STRATEGY_PARAMETER_DEFAULTS, build_phase1_strategy
from signal_forge.strategies.orb_volume_vwap import OrbVolumeVwapStrategy
from signal_forge.strategies.volume_filter import VolumeFilteredStrategy
from signal_forge.strategy import Strategy

ORB_SESSION_SCOPE_CONTRACT = "regular-session research contract only"
ORB_EXTENDED_HOURS_POLICY_CONTRACT = (
    "extended-hours bars are outside the current ORB research contract until "
    "session/data boundaries are defined explicitly"
)
ORB_FORBIDDEN_PREVIOUS_DAY_PREFIXES = (
    "orb_previous_day_",
    "orb_gap_",
    "orb_overnight_",
)
ORB_KNOWN_SAMPLE_MARKET_CLOCKS = {
    "TWSE_2330_5M.csv": {
        "timezone": "Asia/Taipei",
        "session_start": "09:00",
        "session_end": "13:30",
    }
}


def add_strategy_arguments(parser: argparse.ArgumentParser) -> None:
    """
    用途與流程：把 entry-edge 與 phase 共用的策略參數註冊到 argparse parser，集中維護
    SMA、VWAP、Confluence、ORB，以及外層 volume filter / signal cooldown wrapper 的 CLI
    入口。
    參數：parser 是呼叫端建立的 argparse.ArgumentParser，函式會原地新增 strategy 相關
    options，不會回傳新 parser。
    回傳與錯誤：回傳 None；若同名參數重複註冊，會由 argparse 拋出錯誤。
    """
    from signal_forge.strategies import SUPPORTED_STRATEGY_NAMES

    parser.add_argument(
        "--strategy",
        choices=SUPPORTED_STRATEGY_NAMES,
        default="sma-crossover",
    )
    parser.add_argument("--fast-window", type=int, help="override strategy fast window")
    parser.add_argument("--slow-window", type=int, help="override strategy slow window")
    parser.add_argument("--vwap-window", type=int, help="override strategy VWAP window")
    parser.add_argument(
        "--vwap-regime-filter",
        action="store_true",
        help="enable close >= SMA regime filter for VWAP long entries",
    )
    parser.add_argument(
        "--vwap-regime-window",
        type=int,
        help="override VWAP regime SMA window",
    )
    parser.add_argument("--rsi-window", type=int, help="override strategy RSI window")
    parser.add_argument("--entry-z", type=float, help="override VWAP entry z-score")
    parser.add_argument("--exit-z", type=float, help="override VWAP exit z-score")
    parser.add_argument("--threshold", type=float, help="override score threshold")
    parser.add_argument(
        "--volume-filter",
        action="store_true",
        help="enable relative volume filter for long signals",
    )
    parser.add_argument("--volume-window", type=int, help="override volume SMA window")
    parser.add_argument(
        "--volume-multiplier",
        type=float,
        help="override required relative volume multiplier",
    )
    parser.add_argument(
        "--signal-cooldown-bars",
        type=int,
        help="block new long entries for this many bars after an accepted long entry",
    )
    parser.add_argument(
        "--orb-retest-confirmation",
        action="store_true",
        help="require breakout to retest OR high before ORB long entry",
    )
    parser.add_argument(
        "--orb-opening-range-minutes",
        type=int,
        help="override ORB opening range length in minutes",
    )
    parser.add_argument(
        "--orb-session-start-hour",
        type=int,
        help="override ORB session start hour (24h clock)",
    )
    parser.add_argument(
        "--orb-session-start-minute",
        type=int,
        help="override ORB session start minute",
    )
    parser.add_argument(
        "--orb-session-end-hour",
        type=int,
        help="document the intended ORB regular-session end hour (24h clock) for reporting and artifact metadata",
    )
    parser.add_argument(
        "--orb-session-end-minute",
        type=int,
        help="document the intended ORB regular-session end minute for reporting and artifact metadata",
    )
    parser.add_argument(
        "--orb-session-timezone",
        help="document the intended ORB market-clock timezone for reporting and artifact metadata",
    )
    parser.add_argument(
        "--orb-vwap-slope-confirmation",
        action="store_true",
        help="enable the secondary ORB refinement that requires session VWAP to keep rising into the breakout bar before long entry",
    )
    parser.add_argument(
        "--orb-ema-trend-confirmation",
        action="store_true",
        help="require breakout close to stay above a rising rolling EMA before ORB long entry",
    )
    parser.add_argument(
        "--orb-ema-window",
        type=int,
        help="override the rolling EMA window used by ORB EMA trend confirmation",
    )
    parser.add_argument(
        "--orb-reject-ema-inside-range",
        action="store_true",
        help="reject ORB breakouts when the rolling EMA still sits inside the opening-range box",
    )
    parser.add_argument(
        "--orb-signal-window-minutes",
        type=int,
        help="only accept new ORB breakouts before this many minutes from session start",
    )
    parser.add_argument(
        "--orb-min-range-pct",
        type=float,
        help="require OR width / session opening price to stay above this fraction",
    )
    parser.add_argument(
        "--orb-max-range-pct",
        type=float,
        help="require OR width / session opening price to stay below this fraction",
    )
    parser.add_argument(
        "--orb-min-breakout-pct",
        type=float,
        help="require close to finish at least this fraction above OR high before ORB long entry",
    )
    parser.add_argument(
        "--orb-full-bar-above-range",
        action="store_true",
        help="require the breakout candle low to stay above OR high before ORB long entry",
    )
    parser.add_argument(
        "--orb-min-breakout-body-pct",
        type=float,
        help="require breakout candle body divided by full candle range to stay above this fraction before ORB long entry",
    )
    parser.add_argument(
        "--orb-fresh-breakout-from-or",
        action="store_true",
        help="require the previous close to still be inside the opening range before ORB long entry",
    )
    parser.add_argument(
        "--orb-use-opening-range-volume-baseline",
        action="store_true",
        help="compare breakout volume against opening-range average volume instead of the rolling volume SMA baseline",
    )


def build_strategy_from_args(args: argparse.Namespace) -> Strategy:
    """
    用途與流程：將 CLI args 轉交給 Phase 1 strategy factory，建立 long-only 策略並套用
    已啟用的 VWAP regime、ORB refinements、volume filter 與 signal cooldown wrapper。
    參數：args 是 add_strategy_arguments 註冊後解析出的命名空間；未提供的欄位會用
    getattr fallback 交給 factory 使用策略預設值。
    回傳與錯誤：回傳 Strategy；若策略名稱或 wrapper 參數不合法，會由 build_phase1_strategy
    拋出 ValueError。
    """
    return build_phase1_strategy(
        args.strategy,
        fast_window=args.fast_window,
        slow_window=args.slow_window,
        vwap_window=args.vwap_window,
        rsi_window=args.rsi_window,
        entry_z=args.entry_z,
        exit_z=args.exit_z,
        threshold=args.threshold,
        vwap_regime_filter=getattr(args, "vwap_regime_filter", False),
        vwap_regime_window=getattr(args, "vwap_regime_window", None),
        orb_retest_confirmation=getattr(args, "orb_retest_confirmation", False),
        orb_opening_range_minutes=getattr(args, "orb_opening_range_minutes", None),
        orb_session_start_hour=getattr(args, "orb_session_start_hour", None),
        orb_session_start_minute=getattr(args, "orb_session_start_minute", None),
        orb_session_end_hour=getattr(args, "orb_session_end_hour", None),
        orb_session_end_minute=getattr(args, "orb_session_end_minute", None),
        orb_session_timezone=getattr(args, "orb_session_timezone", None),
        orb_vwap_slope_confirmation=getattr(args, "orb_vwap_slope_confirmation", False),
        orb_ema_window=getattr(args, "orb_ema_window", None),
        orb_ema_trend_confirmation=getattr(args, "orb_ema_trend_confirmation", False),
        orb_reject_ema_inside_opening_range=getattr(
            args, "orb_reject_ema_inside_range", False
        ),
        orb_signal_window_minutes=getattr(args, "orb_signal_window_minutes", None),
        orb_min_range_pct=getattr(args, "orb_min_range_pct", None),
        orb_max_range_pct=getattr(args, "orb_max_range_pct", None),
        orb_min_breakout_pct=getattr(args, "orb_min_breakout_pct", None),
        orb_full_bar_above_range=getattr(args, "orb_full_bar_above_range", False),
        orb_min_breakout_body_pct=getattr(args, "orb_min_breakout_body_pct", None),
        orb_fresh_breakout_from_or=getattr(args, "orb_fresh_breakout_from_or", False),
        orb_use_opening_range_volume_baseline=getattr(
            args, "orb_use_opening_range_volume_baseline", False
        ),
        volume_filter=getattr(args, "volume_filter", False),
        volume_window=getattr(args, "volume_window", None),
        volume_multiplier=getattr(args, "volume_multiplier", None),
        signal_cooldown_bars=getattr(args, "signal_cooldown_bars", None),
    )


def strategy_spec_from_args(args: argparse.Namespace, strategy: Strategy) -> dict[str, str]:
    """
    用途與流程：將 CLI 解析後的策略設定整理成 deterministic `strategy_spec`，
    供 entry-edge / phase summary / markdown / comparison artifact 共用。這裡只負責
    報表與 validator 需要的研究語意，不改變任何實際交易邏輯。

    參數：
    - `args`：CLI 命名空間，包含 strategy 名稱、ORB session 設定、各種 refinement
      開關與已知樣本路徑。
    - `strategy`：已由 `build_strategy_from_args()` 建立完成的策略實例，用來回填實際
      採用的 strategy implementation 名稱。

    回傳與錯誤：
    - 回傳 `dict[str, str]`，其中每個欄位都必須可穩定寫入 artifact，避免同一設定在不
      同報表中被解讀成不同語意。
    - 若當前策略是 ORB，函式最後會觸發 ORB contract validator；若 same-session、
      retest、signal window、one-and-done 或 known-sample metadata 發生 drift，
      會拋出 `ValueError`。
    """
    defaults = STRATEGY_PARAMETER_DEFAULTS[args.strategy]
    volume_window, volume_multiplier = _strategy_level_volume_reporting_defaults(args)
    spec = {
        "source_strategy": args.strategy,
        "strategy_impl": strategy.name,
        "entry_side": "long_only",
        "entry_event": "bar close signal where target_position flips from <=0 to >0",
        "excluded_in_phase1": "short/live-execution/broker-connection/credential-reading/real-order-submission",
        "repaint_handling": "phase 1 accepts signals confirmed on closed bars only",
        "volume_filter": "enabled" if getattr(args, "volume_filter", False) else "disabled",
        "volume_window": str(volume_window),
        "volume_multiplier": f"{volume_multiplier:.2f}",
        "volume_rule": "volume >= sma(volume, volume_window) * volume_multiplier",
        "signal_cooldown_bars": _stringify_optional_number(
            getattr(args, "signal_cooldown_bars", None)
        ),
        "signal_cooldown_rule": "when configured, new long entries are blocked for signal_cooldown_bars after an accepted adjusted long entry; existing long positions are not force-flattened",
        "signal_cooldown_signal_basis": "confirmed_bar_close_only",
        "signal_cooldown_position_effect": "entry_cooldown_only_no_force_flatten",
        "vwap_regime_filter": "enabled"
        if getattr(args, "vwap_regime_filter", False)
        else "disabled",
        "vwap_regime_window": str(
            _arg_or_default(args, "vwap_regime_window", defaults.vwap_regime_window)
        ),
        "vwap_regime_rule": "long entries require close >= sma(close, vwap_regime_window) when enabled",
        "orb_retest_confirmation": "enabled"
        if getattr(args, "orb_retest_confirmation", False)
        else "disabled",
        "orb_retest_rule": "long entries wait for breakout, OR-high retest, and close-confirmed reclaim when enabled",
        "orb_retest_scope": "same_session_only",
        "orb_retest_signal_basis": "confirmed_bar_close_only",
        "orb_retest_level_reference": "opening_range_high_reclaim",
        "orb_retest_data_family": "no_previous_day_or_higher_timeframe_context",
        "orb_opening_range_minutes": str(
            _arg_or_default(
                args,
                "orb_opening_range_minutes",
                defaults.orb_opening_range_minutes,
            )
        ),
        "orb_session_start_hour": str(
            _arg_or_default(
                args,
                "orb_session_start_hour",
                defaults.orb_session_start_hour,
            )
        ),
        "orb_session_start_minute": str(
            _arg_or_default(
                args,
                "orb_session_start_minute",
                defaults.orb_session_start_minute,
            )
        ),
        "orb_session_end_hour": str(
            _arg_or_default(
                args,
                "orb_session_end_hour",
                defaults.orb_session_end_hour,
            )
        ),
        "orb_session_end_minute": str(
            _arg_or_default(
                args,
                "orb_session_end_minute",
                defaults.orb_session_end_minute,
            )
        ),
        "orb_session_timezone": str(
            _arg_or_default(
                args,
                "orb_session_timezone",
                defaults.orb_session_timezone,
            )
        ),
        "orb_session_rule": "intraday ORB only evaluates bars at or after the configured session start time",
        "orb_session_end_rule": "configured session end currently documents the intended regular-session boundary for ORB research artifacts; it does not force-flat open positions by itself",
        "orb_session_timezone_rule": "configured timezone documents the intended market-clock reference for ORB session metadata and research artifacts",
        "orb_vwap_slope_confirmation": "enabled"
        if getattr(args, "orb_vwap_slope_confirmation", False)
        else "disabled",
        "orb_vwap_slope_tier": "secondary_refinement",
        "orb_vwap_slope_rule": "this secondary refinement only accepts breakouts if session VWAP is rising versus the previous bar in the same session",
        "orb_ema_trend_confirmation": "enabled"
        if getattr(args, "orb_ema_trend_confirmation", False)
        else "disabled",
        "orb_ema_window": str(
            _arg_or_default(
                args,
                "orb_ema_window",
                defaults.orb_ema_window,
            )
        ),
        "orb_ema_trend_rule": "when enabled, breakout is only accepted if close stays above the rolling EMA and that EMA is rising versus the previous bar in the same session",
        "orb_reject_ema_inside_opening_range": "enabled"
        if getattr(args, "orb_reject_ema_inside_range", False)
        else "disabled",
        "orb_ema_inside_range_rule": "when enabled, new ORB breakouts are rejected if the rolling EMA still falls inside the opening-range box",
        "orb_signal_window_minutes": _stringify_optional_number(
            _arg_or_default(
                args,
                "orb_signal_window_minutes",
                defaults.orb_signal_window_minutes,
            )
        ),
        "orb_signal_window_rule": "when configured, new ORB breakouts are only accepted before orb_signal_window_minutes from session start; existing long positions are not force-flattened by this cutoff",
        "orb_signal_window_scope": "same_session_only",
        "orb_signal_window_signal_basis": "confirmed_bar_close_only",
        "orb_signal_window_cutoff_reference": "session_start_elapsed_minutes",
        "orb_signal_window_position_effect": "entry_cutoff_only_no_force_flatten",
        "orb_one_and_done_mode": "research_candidate_only",
        "orb_one_and_done_rule": "when enabled in future research, only the first close-confirmed long breakout accepted within the current session should remain eligible; later same-session breakout attempts stay blocked until the next session reset",
        "orb_one_and_done_scope": "same_session_only",
        "orb_one_and_done_guard_scope": "long_only_per_direction_first_entry",
        "orb_one_and_done_signal_basis": "confirmed_bar_close_only",
        "orb_one_and_done_position_effect": "first_entry_only_no_force_flatten",
        "orb_one_and_done_reset_rule": "reset_on_next_session_start",
        "orb_one_and_done_data_family": "no_previous_day_or_higher_timeframe_context",
        "orb_session_scope": ORB_SESSION_SCOPE_CONTRACT,
        "orb_extended_hours_policy": ORB_EXTENDED_HOURS_POLICY_CONTRACT,
        "orb_min_range_pct": f"{_arg_or_default(args, 'orb_min_range_pct', defaults.orb_min_range_pct):.4f}",
        "orb_max_range_pct": f"{_arg_or_default(args, 'orb_max_range_pct', defaults.orb_max_range_pct):.4f}",
        "orb_range_size_rule": "when configured, OR width divided by the first session open must stay within the min/max range pct gate",
        "orb_min_breakout_pct": f"{_arg_or_default(args, 'orb_min_breakout_pct', defaults.orb_min_breakout_pct):.4f}",
        "orb_breakout_distance_rule": "when configured, close must finish at least orb_min_breakout_pct above OR high before the breakout is accepted",
        "orb_full_bar_above_range": "enabled"
        if getattr(args, "orb_full_bar_above_range", False)
        else "disabled",
        "orb_full_bar_rule": "when enabled, the breakout candle low must stay above OR high so the full bar remains outside the opening range",
        "orb_min_breakout_body_pct": f"{_arg_or_default(args, 'orb_min_breakout_body_pct', defaults.orb_min_breakout_body_pct):.4f}",
        "orb_breakout_body_rule": "when configured, breakout candle body divided by full candle range must be at least orb_min_breakout_body_pct before the breakout is accepted",
        "orb_fresh_breakout_from_or": "enabled"
        if getattr(args, "orb_fresh_breakout_from_or", False)
        else "disabled",
        "orb_fresh_breakout_rule": "when enabled, the previous close must still be inside the OR box before the current bar can count as a fresh breakout",
        "orb_use_opening_range_volume_baseline": "enabled"
        if getattr(args, "orb_use_opening_range_volume_baseline", False)
        else "disabled",
        "orb_volume_baseline_rule": "when enabled, breakout volume is compared against the average volume observed during the opening range instead of the rolling volume SMA baseline",
    }
    if getattr(args, "strategy", "") == "orb-volume-vwap":
        spec.update(_orb_known_sample_market_clock_metadata(args, spec))
        _validate_orb_same_session_contract(spec)
        _validate_orb_retest_contract(spec)
        _validate_orb_signal_window_contract(spec)
        _validate_orb_one_and_done_contract(spec)
    return spec


def orb_runtime_spec_from_bars(
    args: argparse.Namespace,
    bars: list[Bar],
) -> dict[str, str]:
    """
    ?券?瘚?嚗??ORB ?桀???session 韏琿???opening range ?嚗??祆活頛詨 bars ?典? run-level OR range ?曉?瘥?閬?霈?artifact ?賜?仿＊蝷箇甈∟??葉???之撠???    ?嚗rgs ??CLI ?賢?蝛粹?嚗撠?? strategy?rb_opening_range_minutes?rb_session_start_hour?rb_session_start_minute嚗ars ?舀迨甈∪銵蝙?函? OHLCV 摨??ession end / timezone metadata 銝??ㄐ??run-level OR ?曉?瘥?蝞?    ??隤歹?? dict[str, str]嚗銝 ORB 蝑??????intraday timestamp嚗??⊥?敶Ｘ?摰 opening range嚗??蝛?dict嚗?銝餃????    """
    if getattr(args, "strategy", "") != "orb-volume-vwap":
        return {}

    defaults = STRATEGY_PARAMETER_DEFAULTS["orb-volume-vwap"]
    opening_range_minutes = int(
        _arg_or_default(args, "orb_opening_range_minutes", defaults.orb_opening_range_minutes)
    )
    session_start_hour = int(
        _arg_or_default(args, "orb_session_start_hour", defaults.orb_session_start_hour)
    )
    session_start_minute = int(
        _arg_or_default(args, "orb_session_start_minute", defaults.orb_session_start_minute)
    )
    min_range_pct = _arg_or_default(args, "orb_min_range_pct", defaults.orb_min_range_pct)
    max_range_pct = _arg_or_default(args, "orb_max_range_pct", defaults.orb_max_range_pct)
    observed = _observed_opening_range_pcts(
        bars,
        opening_range_minutes=opening_range_minutes,
        session_start_hour=session_start_hour,
        session_start_minute=session_start_minute,
    )
    if not observed:
        return {}

    summary = {
        "orb_observed_range_pct_sessions": str(len(observed)),
        "orb_observed_range_pct_min": f"{min(observed):.4f}",
        "orb_observed_range_pct_max": f"{max(observed):.4f}",
        "orb_observed_range_pct_first": f"{observed[0]:.4f}",
        "orb_observed_range_pct_last": f"{observed[-1]:.4f}",
    }
    summary.update(
        _observed_opening_range_gate_counts(
            observed,
            min_range_pct=min_range_pct,
            max_range_pct=max_range_pct,
        )
    )
    return summary


def _strategy_level_volume_reporting_defaults(
    args: argparse.Namespace,
) -> tuple[int | float | str | None, int | float | str | None]:
    """
    ?券?瘚?嚗???strategy ??血??典?撅?volume wrapper嚗??詨銵其葉?＊蝷箇???靘?嚗??祉??交窒??wrapper ?身?潘?雿?ORB ?冽? wrapper ????寥＊蝷箇??交擃? breakout volume SMA 閬???瑼颯?    ?嚗rgs ??CLI ?賢?蝛粹?嚗撠?? strategy?olume_filter?olume_window ??volume_multiplier 蝑?add_strategy_arguments ????雿?    ??隤歹?? tuple嚗洵銝??蝝閬神??artifact ??volume_window嚗洵鈭?蝝 volume_multiplier嚗甈?銝??典??????閮剖潘?銝蜓???胯?    """
    if getattr(args, "strategy", "") == "orb-volume-vwap" and not getattr(
        args, "volume_filter", False
    ):
        return (
            OrbVolumeVwapStrategy.volume_window,
            OrbVolumeVwapStrategy.volume_multiplier,
        )
    return (
        _arg_or_default(
            args,
            "volume_window",
            VolumeFilteredStrategy.volume_window,
        ),
        _arg_or_default(
            args,
            "volume_multiplier",
            VolumeFilteredStrategy.volume_multiplier,
        ),
    )


def _validate_orb_same_session_contract(spec: dict[str, str]) -> None:
    """
    ?券?瘚?嚗?霅?ORB ??strategy spec 隞雁???same-session only ?弦憟?嚗?瑼Ｘ?箏???session scope ??extended-hours policy ?臬摮嚗???隞颱? previous-day?ap ??overnight family key 瘛瑕??    ?嚗pec ??strategy_spec_from_args 撱箏末??deterministic metadata dict嚗?怎垢???ORB strategy 銝蝙?券炎?乓?    ??隤歹?? None嚗蝻箏?敹? contract 甈??? spec 瘛瑕?桀?蝳迫??previous-day family surface嚗?? ValueError??    """
    if spec.get("orb_session_scope") != ORB_SESSION_SCOPE_CONTRACT:
        raise ValueError("ORB strategy spec lost the same-session scope contract")
    if spec.get("orb_extended_hours_policy") != ORB_EXTENDED_HOURS_POLICY_CONTRACT:
        raise ValueError("ORB strategy spec lost the extended-hours boundary contract")
    for forbidden_prefix in ORB_FORBIDDEN_PREVIOUS_DAY_PREFIXES:
        if any(key.startswith(forbidden_prefix) for key in spec):
            raise ValueError(
                f"ORB strategy spec leaked previous-day family surface: {forbidden_prefix}"
            )


def _validate_orb_prior_day_close_contract(contract: dict[str, str]) -> None:
    """
    ?券?瘚?嚗?霅靘?ORB ?亥??賜洵銝??previous-day scalar ???撠? prior-day close 甇?鞈?憟??臬?芣晾嚗ㄐ?芣炎??research note 撌脫???皞?session???撠??vailability ??fill policy嚗????仿脩??same-session only ??ORB strategy surface??    ?嚗ontract ??prior-day close metadata dict嚗??撠???prior_day_close_regular_session?rior_day_close_source_session?rior_day_close_timezone?rior_day_close_availability ??prior_day_close_fill_policy??    ??隤歹?? None嚗蝻箏?敹?甈???皞???regular session???瘝?撠? ORB market clock?vailability ??available/unavailable_first_session嚗? fill policy 銝 no_forward_fill嚗?? ValueError??    """
    required_keys = (
        "prior_day_close_regular_session",
        "prior_day_close_source_session",
        "prior_day_close_timezone",
        "prior_day_close_availability",
        "prior_day_close_fill_policy",
    )
    missing = [key for key in required_keys if key not in contract]
    if missing:
        raise ValueError(
            f"prior-day close contract is missing required keys: {', '.join(missing)}"
        )
    if contract["prior_day_close_source_session"] != "regular_session":
        raise ValueError("prior-day close contract must use regular_session source")
    if contract["prior_day_close_timezone"] != "orb_session_timezone":
        raise ValueError(
            "prior-day close contract must align timezone with orb_session_timezone"
        )
    if contract["prior_day_close_availability"] not in (
        "available",
        "unavailable_first_session",
    ):
        raise ValueError(
            "prior-day close contract must declare available or unavailable_first_session"
        )
    if contract["prior_day_close_fill_policy"] != "no_forward_fill":
        raise ValueError(
            "prior-day close contract must keep no_forward_fill policy"
        )
    if (
        contract["prior_day_close_availability"] == "unavailable_first_session"
        and contract["prior_day_close_regular_session"] != "unavailable"
    ):
        raise ValueError(
            "prior-day close contract must mark first-session values as unavailable"
        )


def _validate_orb_retest_contract(contract: dict[str, str]) -> None:
    """
    用途與流程：驗證 OR retest / re-break confirmation 目前仍被限制在同 session、
    confirmed-bar-only 的研究邊界，避免後續在沒有明確產品決策時，悄悄把 previous-day
    或 higher-timeframe 語意混入 retest refinement。

    參數：
    - `contract`：ORB `strategy_spec` 的 metadata dict，至少需包含 retest 的 state、
      scope、signal basis、level reference 與 data family 欄位。

    回傳與錯誤：
    - 回傳 `None`。
    - 若 retest contract 遺失必要欄位，或其值偏離目前鎖定的研究邊界，拋出
      `ValueError`。
    """
    required = (
        "orb_retest_confirmation",
        "orb_retest_scope",
        "orb_retest_signal_basis",
        "orb_retest_level_reference",
        "orb_retest_data_family",
    )
    missing = [key for key in required if key not in contract]
    if missing:
        raise ValueError(
            f"ORB retest contract is missing required keys: {', '.join(missing)}"
        )
    if contract["orb_retest_scope"] != "same_session_only":
        raise ValueError("ORB retest contract must stay within same_session_only")
    if contract["orb_retest_signal_basis"] != "confirmed_bar_close_only":
        raise ValueError(
            "ORB retest contract must use confirmed_bar_close_only signal basis"
        )
    if contract["orb_retest_level_reference"] != "opening_range_high_reclaim":
        raise ValueError(
            "ORB retest contract must reference opening_range_high_reclaim"
        )
    if (
        contract["orb_retest_data_family"]
        != "no_previous_day_or_higher_timeframe_context"
    ):
        raise ValueError(
            "ORB retest contract must stay outside previous-day and higher-timeframe context"
        )


def _validate_orb_signal_window_contract(contract: dict[str, str]) -> None:
    """
    用途與流程：驗證 ORB signal window 目前仍被限制在同 session、confirmed-bar-only 的
    entry cutoff contract，避免後續在沒有正式產品決策時，把 intrabar、force-flatten、
    previous-day 或其他更重的 session 控制語意悄悄混進 strategy spec。

    參數：
    - `contract`：ORB `strategy_spec` 的 metadata dict，至少需包含 signal window 的分鐘、
      scope、signal basis、cutoff reference 與 position effect 欄位。

    回傳與錯誤：
    - 回傳 `None`。
    - 若 signal window contract 遺失必要欄位，或其值偏離目前鎖定的研究邊界，拋出
      `ValueError`。
    """
    required = (
        "orb_signal_window_minutes",
        "orb_signal_window_scope",
        "orb_signal_window_signal_basis",
        "orb_signal_window_cutoff_reference",
        "orb_signal_window_position_effect",
    )
    missing = [key for key in required if key not in contract]
    if missing:
        raise ValueError(
            f"ORB signal-window contract is missing required keys: {', '.join(missing)}"
        )
    if contract["orb_signal_window_scope"] != "same_session_only":
        raise ValueError("ORB signal-window contract must stay within same_session_only")
    if contract["orb_signal_window_signal_basis"] != "confirmed_bar_close_only":
        raise ValueError(
            "ORB signal-window contract must use confirmed_bar_close_only signal basis"
        )
    if contract["orb_signal_window_cutoff_reference"] != "session_start_elapsed_minutes":
        raise ValueError(
            "ORB signal-window contract must reference session_start_elapsed_minutes"
        )
    if (
        contract["orb_signal_window_position_effect"]
        != "entry_cutoff_only_no_force_flatten"
    ):
        raise ValueError(
            "ORB signal-window contract must stay as entry_cutoff_only_no_force_flatten"
        )


def _validate_orb_one_and_done_contract(contract: dict[str, str]) -> None:
    """
    用途與流程：驗證 ORB one-and-done 候選目前仍被限制在同 session、confirmed-bar-only 的
    entry-count-control 邊界，並把 guard 範圍固定在 long-only / per-direction first-entry。
    這能避免後續在沒有正式產品決策時，把 cross-session cooldown、entire-session lockout、
    intrabar probe、force-flatten 或 previous-day / higher-timeframe 語意混進 strategy spec。

    參數：
    - `contract`：ORB `strategy_spec` 的 metadata dict，至少需包含 one-and-done 的 mode、
      scope、guard scope、signal basis、position effect、reset rule 與 data family 欄位。

    回傳與錯誤：
    - 回傳 `None`。
    - 若 one-and-done contract 遺失必要欄位，或其值偏離目前鎖定的研究邊界，拋出
      `ValueError`。
    """
    required = (
        "orb_one_and_done_mode",
        "orb_one_and_done_scope",
        "orb_one_and_done_guard_scope",
        "orb_one_and_done_signal_basis",
        "orb_one_and_done_position_effect",
        "orb_one_and_done_reset_rule",
        "orb_one_and_done_data_family",
    )
    missing = [key for key in required if key not in contract]
    if missing:
        raise ValueError(
            f"ORB one-and-done contract is missing required keys: {', '.join(missing)}"
        )
    if contract["orb_one_and_done_mode"] != "research_candidate_only":
        raise ValueError(
            "ORB one-and-done contract must stay as research_candidate_only"
        )
    if contract["orb_one_and_done_scope"] != "same_session_only":
        raise ValueError("ORB one-and-done contract must stay within same_session_only")
    if (
        contract["orb_one_and_done_guard_scope"]
        != "long_only_per_direction_first_entry"
    ):
        raise ValueError(
            "ORB one-and-done contract must stay as long_only_per_direction_first_entry"
        )
    if contract["orb_one_and_done_signal_basis"] != "confirmed_bar_close_only":
        raise ValueError(
            "ORB one-and-done contract must use confirmed_bar_close_only signal basis"
        )
    if contract["orb_one_and_done_position_effect"] != "first_entry_only_no_force_flatten":
        raise ValueError(
            "ORB one-and-done contract must stay as first_entry_only_no_force_flatten"
        )
    if contract["orb_one_and_done_reset_rule"] != "reset_on_next_session_start":
        raise ValueError(
            "ORB one-and-done contract must reset_on_next_session_start"
        )
    if (
        contract["orb_one_and_done_data_family"]
        != "no_previous_day_or_higher_timeframe_context"
    ):
        raise ValueError(
            "ORB one-and-done contract must stay outside previous-day and higher-timeframe context"
        )


def _orb_known_sample_market_clock_metadata(
    args: argparse.Namespace,
    spec: dict[str, str],
) -> dict[str, str]:
    """
    用途與流程：對已知的 ORB intraday 樣本補上 sample-aware market-clock metadata，讓 artifact 可以同時顯示 canonical session/timezone 預期、目前 run 是否 aligned，以及一行可直接給人判讀的 baseline note。
    參數：args 是 CLI 命名空間，至少需包含 csv 路徑；spec 是 strategy_spec_from_args 已建立的 ORB metadata，需包含 orb_session_start_hour、orb_session_start_minute、orb_session_end_hour、orb_session_end_minute 與 orb_session_timezone。
    回傳與錯誤：回傳 dict[str, str]。若 csv 不是已知樣本則回傳空 dict；若是已知樣本則回傳 canonical market-clock expectation、alignment 狀態與 baseline note。本函式本身不負責拒絕不合法 surface，相關錯誤由外層 validator 處理。
    """
    csv_path = getattr(args, "csv", None)
    if not csv_path:
        return {}
    sample_name = Path(csv_path).name
    expected = ORB_KNOWN_SAMPLE_MARKET_CLOCKS.get(sample_name)
    if expected is None:
        return {}

    observed_start = (
        f"{int(spec['orb_session_start_hour']):02d}:{int(spec['orb_session_start_minute']):02d}"
    )
    observed_end = (
        f"{int(spec['orb_session_end_hour']):02d}:{int(spec['orb_session_end_minute']):02d}"
    )
    observed_timezone = spec["orb_session_timezone"]
    aligned = (
        observed_start == expected["session_start"]
        and observed_end == expected["session_end"]
        and observed_timezone == expected["timezone"]
    )
    baseline_note = (
        f"{sample_name} uses {expected['timezone']} "
        f"{expected['session_start']}-{expected['session_end']} as the canonical ORB baseline; "
        f"current run is {'aligned' if aligned else 'mismatch'}."
    )
    return {
        "orb_known_sample_market_clock_name": sample_name,
        "orb_known_sample_market_clock_expected_timezone": expected["timezone"],
        "orb_known_sample_market_clock_expected_session_start": expected[
            "session_start"
        ],
        "orb_known_sample_market_clock_expected_session_end": expected["session_end"],
        "orb_known_sample_market_clock_alignment": "aligned"
        if aligned
        else "mismatch",
        "orb_known_sample_market_clock_rule": "known ORB intraday samples may declare a canonical market-clock expectation; compare orb_session_* metadata with that expectation before interpreting cross-sample results",
        "orb_known_sample_market_clock_baseline_note": baseline_note,
    }



def _arg_or_default(
    args: argparse.Namespace,
    field_name: str,
    default_value: int | float | str | None,
) -> int | float | str | None:
    """
    ?券?瘚?嚗???argparse 甈?嚗? None 閬?蝙?函??交? wrapper default??靘?reporting spec 撖怠撖阡????潦?    ?嚗rgs ??CLI ?賢?蝛粹?嚗ield_name ?舀炬霈????迂嚗efault_value ?航府甈??芾撓?交?????閮剖潘??舐?詨潦?銝脫? None??    ??隤歹?? int?loat?tr ??None嚗甈?銝??其?????default_value嚗???航炊??    """
    value = getattr(args, field_name, None)
    return default_value if value is None else value


def _stringify_optional_number(value: int | float | None) -> str:
    """
    ?券?瘚?嚗??舫??澆??貉???reporting ?舐帘摰撓?箇?摮葡嚗??芸??函??賊??典摰?`disabled` 銵函內嚗??舀毽??`None` ?征摮葡??    ?嚗alue ?臭???CLI ????default ??詻筑暺??None嚗one 隞?”???賣???    ??隤歹?? str嚗one ????`disabled`嚗擗澆??湔??銝脣?嚗?銝餃????    """
    return "disabled" if value is None else str(value)


def _observed_opening_range_pcts(
    bars: list[Bar],
    *,
    opening_range_minutes: int,
    session_start_hour: int,
    session_start_minute: int,
) -> list[float]:
    """
    ?券?瘚?嚗??撓??bars嚗? session 韏琿???OR 閬??瘥?session ??opening range嚗蒂閮? OR 撖砍漲?詨???session 蝚砌??寥??文?????    ?嚗ars ?舀迨甈∪銵蝙?函? OHLCV 摨?嚗pening_range_minutes ??OR 撱箇??摨佗?session_start_hour / session_start_minute ??session 韏琿???    ??隤歹?? list[float]嚗 timestamp 銝??鞈??ession 銝??湔????⊥?嚗府 session ?◤?仿?嚗?銝餃????    """
    observed: list[float] = []
    current_session_id: str | None = None
    current_open: float | None = None
    current_high: float | None = None
    current_low: float | None = None
    current_complete = False

    for bar in bars:
        parsed = _parse_intraday_timestamp_for_spec(bar.timestamp)
        if parsed is None:
            continue
        session_id = parsed.date().isoformat()
        minutes = parsed.hour * 60 + parsed.minute - (
            session_start_hour * 60 + session_start_minute
        )
        if session_id != current_session_id:
            if (
                current_complete
                and current_open is not None
                and current_open > 0
                and current_high is not None
                and current_low is not None
            ):
                observed.append((current_high - current_low) / current_open)
            current_session_id = session_id
            current_open = None
            current_high = None
            current_low = None
            current_complete = False
        if minutes < 0:
            continue
        if minutes < opening_range_minutes:
            if current_open is None:
                current_open = bar.open
            current_high = bar.high if current_high is None else max(current_high, bar.high)
            current_low = bar.low if current_low is None else min(current_low, bar.low)
            if minutes == opening_range_minutes - 1:
                current_complete = True
            continue
        if (
            current_complete
            and current_open is not None
            and current_open > 0
            and current_high is not None
            and current_low is not None
        ):
            observed.append((current_high - current_low) / current_open)
            current_complete = False

    if (
        current_complete
        and current_open is not None
        and current_open > 0
        and current_high is not None
        and current_low is not None
    ):
        observed.append((current_high - current_low) / current_open)
    return observed


def _observed_opening_range_gate_counts(
    observed: list[float],
    *,
    min_range_pct: float | None,
    max_range_pct: float | None,
) -> dict[str, str]:
    """
    ?券?瘚?嚗??桀? ORB range gate 閮剖?嚗?撌脰?皜砍??opening range ?曉?瘥?憿?雿銝????gate ?扼?擃銝???session ?賊?嚗? artifact ?舐?亙???filter 撖阡?閬??啁?璅?????    ?嚗bserved ?臬? session ??OR ?曉?瘥?銵剁?min_range_pct ??max_range_pct ?舐???乩蝙?函??撠??憭?gate嚗???None??    ??隤歹?? dict[str, str]嚗?芾身摰遙雿?gate ??observed ?箇征嚗??喟征 dict嚗?銝餃????    """
    if not observed or (min_range_pct is None and max_range_pct is None):
        return {}

    below_min = 0
    above_max = 0
    within_gate = 0
    for value in observed:
        if min_range_pct is not None and value < min_range_pct:
            below_min += 1
            continue
        if max_range_pct is not None and value > max_range_pct:
            above_max += 1
            continue
        within_gate += 1
    return {
        "orb_observed_range_pct_below_min_sessions": str(below_min),
        "orb_observed_range_pct_within_gate_sessions": str(within_gate),
        "orb_observed_range_pct_above_max_sessions": str(above_max),
    }


def _parse_intraday_timestamp_for_spec(timestamp: str) -> datetime | None:
    """
    ?券?瘚?嚗? CLI reporting ?閬? timestamp 閫????datetime嚗?亙??急???閮? ISO-8601 摮葡嚗???亦?鞈?隤斤??ORB session??    ?嚗imestamp ??bar.timestamp 摮葡??    ??隤歹?? datetime ?拐辣??None嚗撘??急????⊥?閫??????None嚗?銝餃????    """
    if not timestamp or ("T" not in timestamp and " " not in timestamp):
        return None
    candidate = timestamp.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None
