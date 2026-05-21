from __future__ import annotations

import argparse
from datetime import datetime

from signal_forge.core.market_data import Bar
from signal_forge.strategies import STRATEGY_PARAMETER_DEFAULTS, build_phase1_strategy
from signal_forge.strategies.orb_volume_vwap import OrbVolumeVwapStrategy
from signal_forge.strategies.volume_filter import VolumeFilteredStrategy
from signal_forge.strategy import Strategy


def add_strategy_arguments(parser: argparse.ArgumentParser) -> None:
    """
    用途與流程：把 entry-edge 與 phase 共用的策略參數集中掛到 argparse parser，避免兩個 command 重複維護。
    參數：parser 是目標 argparse.ArgumentParser，呼叫後會被加入策略名稱、SMA、VWAP、RSI、ORB session 與 volume filter 等 options。
    回傳與錯誤：回傳 None；argparse option 衝突時會由 argparse 拋出例外。
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
        help="require session VWAP to keep rising into the breakout bar before ORB long entry",
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
    用途與流程：依 CLI args 透過 Phase 1 factory 建立 long-only strategy，並套用 VWAP regime、ORB retest、ORB session 起點、session 結束 metadata、session timezone metadata、VWAP slope confirmation、EMA trend confirmation、EMA inside-range 結構 gate、signal window cutoff、ORB range size、ORB breakout distance、ORB full-bar breakout、ORB breakout body strength、ORB fresh-breakout gate、ORB 開盤區間量能 baseline 與成交量 wrapper 設定。
    參數：args 是 argparse 解析出的命名空間，需包含 add_strategy_arguments 建立的欄位，包含 ORB retest、session、session end/timezone metadata、VWAP slope confirmation、EMA trend confirmation、EMA inside-range gate、signal window、range size、breakout distance、full-bar breakout、breakout body strength、fresh-breakout 與開盤區間量能 baseline 參數。
    回傳與錯誤：回傳 Strategy；策略名稱或參數不合法時由 build_phase1_strategy 拋出 ValueError。
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
    )


def strategy_spec_from_args(args: argparse.Namespace, strategy: Strategy) -> dict[str, str]:
    """
    用途與流程：整理 CLI strategy 來源、實作名稱、Phase 1 long-only 邊界與可選濾網設定，寫入 entry-edge reporting；同時依策略類型挑選正確的量能欄位預設值，避免 ORB 的內建 breakout volume gate 被誤記成外層 wrapper 的預設參數。
    參數：args 是 CLI 命名空間；strategy 是已建立的策略或 wrapper 實例；函式會把 ORB 的 session、session end/timezone metadata、VWAP slope confirmation、EMA trend confirmation、EMA inside-range gate、signal window、range gate、breakout distance、full-bar breakout、breakout body strength、fresh-breakout gate、開盤區間量能 baseline 與研究邊界一併寫入 deterministic spec。
    回傳與錯誤：回傳 deterministic dict[str, str]；不讀取檔案或外部狀態。
    """
    defaults = STRATEGY_PARAMETER_DEFAULTS[args.strategy]
    volume_window, volume_multiplier = _strategy_level_volume_reporting_defaults(args)
    return {
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
        "orb_vwap_slope_rule": "when enabled, breakout is only accepted if session VWAP is rising versus the previous bar in the same session",
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
        "orb_session_scope": "regular-session research contract only",
        "orb_extended_hours_policy": "extended-hours bars are outside the current ORB research contract until session/data boundaries are defined explicitly",
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


def orb_runtime_spec_from_bars(
    args: argparse.Namespace,
    bars: list[Bar],
) -> dict[str, str]:
    """
    用途與流程：根據 ORB 目前的 session 起點與 opening range 參數，從本次輸入 bars 推導 run-level OR range 百分比摘要，讓 artifact 能直接顯示當次資料中的區間大小範圍。
    參數：args 是 CLI 命名空間，至少需包含 strategy、orb_opening_range_minutes、orb_session_start_hour、orb_session_start_minute；bars 是此次執行使用的 OHLCV 序列。session end / timezone metadata 不參與這裡的 run-level OR 百分比計算。
    回傳與錯誤：回傳 dict[str, str]；若不是 ORB 策略、資料沒有 intraday timestamp，或無法形成完整 opening range，則回傳空 dict，不主動拋錯。
    """
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
    用途與流程：根據目前 strategy 與是否啟用外層 volume wrapper，挑選報表中應顯示的量能參數來源；一般策略沿用 wrapper 預設值，但 ORB 在未啟用 wrapper 時，需改顯示策略本體的 breakout volume SMA 視窗與倍數門檻。
    參數：args 是 CLI 命名空間；至少需包含 strategy、volume_filter、volume_window 與 volume_multiplier 等 add_strategy_arguments 掛上的欄位。
    回傳與錯誤：回傳 tuple，第一個元素是要寫入 artifact 的 volume_window，第二個元素是 volume_multiplier；若欄位不存在則退回對應預設值，不主動拋錯。
    """
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


def _arg_or_default(
    args: argparse.Namespace,
    field_name: str,
    default_value: int | float | str | None,
) -> int | float | str | None:
    """
    用途與流程：讀取 argparse 欄位，將 None 視為「使用策略或 wrapper default」，供 reporting spec 寫出實際生效值。
    參數：args 是 CLI 命名空間；field_name 是欲讀取的參數名稱；default_value 是該欄位未輸入時的有效預設值，可為數值、字串或 None。
    回傳與錯誤：回傳 int、float、str 或 None；若欄位不存在也會回傳 default_value，不拋出錯誤。
    """
    value = getattr(args, field_name, None)
    return default_value if value is None else value


def _stringify_optional_number(value: int | float | None) -> str:
    """
    用途與流程：把可選的數值參數轉成 reporting 可穩定輸出的字串，讓未啟用的選項用固定 `disabled` 表示，而不是混成 `None` 或空字串。
    參數：value 是來自 CLI 或策略 default 的整數、浮點數或 None；None 代表這個功能未啟用。
    回傳與錯誤：回傳 str；None 會轉成 `disabled`，其餘值則直接做字串化，不主動拋錯。
    """
    return "disabled" if value is None else str(value)


def _observed_opening_range_pcts(
    bars: list[Bar],
    *,
    opening_range_minutes: int,
    session_start_hour: int,
    session_start_minute: int,
) -> list[float]:
    """
    用途與流程：掃描輸入 bars，依 session 起點與 OR 視窗切出每個 session 的 opening range，並計算 OR 寬度相對於 session 第一根開盤價的百分比。
    參數：bars 是此次執行使用的 OHLCV 序列；opening_range_minutes 是 OR 建立期長度；session_start_hour / session_start_minute 是 session 起點。
    回傳與錯誤：回傳 list[float]；若 timestamp 不含時間資訊、session 不完整或開盤參考價無效，該 session 會被略過，不主動拋錯。
    """
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
    用途與流程：依目前 ORB range gate 設定，把已觀測到的 opening range 百分比分類成低於下限、落在 gate 內、或高於上限的 session 數量，讓 artifact 可直接呈現 filter 實際覆蓋到的樣本分布。
    參數：observed 是各 session 的 OR 百分比列表；min_range_pct 與 max_range_pct 是目前策略使用的最小/最大 gate，兩者可為 None。
    回傳與錯誤：回傳 dict[str, str]；若未設定任何 gate 或 observed 為空，回傳空 dict，不主動拋錯。
    """
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
    用途與流程：把 CLI reporting 需要的 timestamp 解析成 datetime；只接受含時間資訊的 ISO-8601 字串，避免把日線資料誤當成 ORB session。
    參數：timestamp 是 bar.timestamp 字串。
    回傳與錯誤：回傳 datetime 物件或 None；格式不含時間或無法解析時回傳 None，不主動拋錯。
    """
    if not timestamp or ("T" not in timestamp and " " not in timestamp):
        return None
    candidate = timestamp.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None
