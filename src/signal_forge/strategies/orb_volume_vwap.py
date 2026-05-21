from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from signal_forge.indicators import ema, sma
from signal_forge.market_data import Bar, volumes
from signal_forge.strategy import BarByBarStrategy, StrategyDecision


@dataclass(frozen=True)
class OrbVolumeVwapContext:
    session_ids: list[str | None]
    session_changed: list[bool]
    minutes_from_session_start: list[int | None]
    opening_range_high: list[float | None]
    opening_range_low: list[float | None]
    opening_reference_price: list[float | None]
    opening_range_pct: list[float | None]
    opening_range_average_volume: list[float | None]
    session_vwap: list[float | None]
    trend_ema: list[float | None]
    average_volume: list[float | None]
    breakout_armed: list[bool]
    retest_ready: list[bool]
    breakout_arm_index: list[int | None]


@dataclass(frozen=True)
class OrbVolumeVwapStrategy(BarByBarStrategy[OrbVolumeVwapContext]):
    opening_range_minutes: int = 30
    session_start_hour: int = 9
    session_start_minute: int = 30
    session_end_hour: int = 16
    session_end_minute: int = 0
    session_timezone: str = "America/New_York"
    signal_window_minutes: int | None = None
    ema_window: int = 20
    volume_window: int = 20
    volume_multiplier: float = 1.5
    require_vwap_confirmation: bool = True
    require_vwap_slope_confirmation: bool = False
    require_ema_trend_confirmation: bool = False
    reject_ema_inside_opening_range: bool = False
    require_retest_confirmation: bool = False
    min_opening_range_pct: float | None = None
    max_opening_range_pct: float | None = None
    min_breakout_pct: float = 0.0
    require_full_bar_above_range: bool = False
    min_breakout_body_pct: float = 0.0
    require_fresh_breakout_from_or: bool = False
    use_opening_range_volume_baseline: bool = False

    @property
    def name(self) -> str:
        """
        用途與流程：組合穩定的策略名稱，讓 CLI、artifact 與測試可追蹤實際使用的 ORB、量能與 VWAP 設定。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        vwap_flag = "with_vwap" if self.require_vwap_confirmation else "no_vwap"
        vwap_slope_flag = "_vslope" if self.require_vwap_slope_confirmation else ""
        ema_flag = f"_ema{self.ema_window}" if self.require_ema_trend_confirmation else ""
        ema_box_flag = "_emabox" if self.reject_ema_inside_opening_range else ""
        retest_flag = "with_retest" if self.require_retest_confirmation else "no_retest"
        close_flag = "fullbar" if self.require_full_bar_above_range else "closeonly"
        fresh_flag = "_fresh" if self.require_fresh_breakout_from_or else ""
        or_volume_flag = "_orvol" if self.use_opening_range_volume_baseline else ""
        signal_window_flag = (
            "" if self.signal_window_minutes is None else f"_sigw{self.signal_window_minutes}"
        )
        range_flag = ""
        if self.min_opening_range_pct is not None or self.max_opening_range_pct is not None:
            min_flag = "none" if self.min_opening_range_pct is None else f"{self.min_opening_range_pct:.3f}"
            max_flag = "none" if self.max_opening_range_pct is None else f"{self.max_opening_range_pct:.3f}"
            range_flag = f"_orpct{min_flag}-{max_flag}"
        breakout_flag = "" if self.min_breakout_pct <= 0 else f"_obp{self.min_breakout_pct:.3f}"
        body_flag = "" if self.min_breakout_body_pct <= 0 else f"_body{self.min_breakout_body_pct:.2f}"
        return (
            f"orb_volume_vwap_ss{self.session_start_hour:02d}{self.session_start_minute:02d}_"
            f"or{self.opening_range_minutes}{range_flag}{breakout_flag}{body_flag}{fresh_flag}{or_volume_flag}{signal_window_flag}{vwap_slope_flag}{ema_flag}{ema_box_flag}_{close_flag}_vw{self.volume_window}_vm{self.volume_multiplier:.2f}_"
            f"{vwap_flag}_{retest_flag}_long_only"
        )

    def prepare_context(self, bars: list[Bar]) -> OrbVolumeVwapContext:
        """
        用途與流程：預先整理每根 bar 的 session 身分、相對 session 起點分鐘數、開盤區間上下界、session 開盤參考價、OR 寬度百分比、OR 平均量能、session VWAP、rolling EMA 與 rolling 平均量能，讓逐 bar 決策只專注判斷 breakout 是否成立；session end 與 timezone 設定目前作為 ORB regular-session contract 的顯式 metadata，先不直接改動持有或 forced-flat 語意。
        參數：self 表示目前物件實例；bars（list[Bar]）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 OrbVolumeVwapContext；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        average_volume = sma(volumes(bars), self.volume_window)
        trend_ema = ema([bar.close for bar in bars], self.ema_window)
        session_ids: list[str | None] = []
        session_changed: list[bool] = []
        minutes_from_session_start: list[int | None] = []
        opening_range_high: list[float | None] = []
        opening_range_low: list[float | None] = []
        opening_reference_price: list[float | None] = []
        opening_range_pct: list[float | None] = []
        opening_range_average_volume: list[float | None] = []
        session_vwap: list[float | None] = []
        breakout_armed: list[bool] = []
        retest_ready: list[bool] = []
        breakout_arm_index: list[int | None] = []

        previous_session_id: str | None = None
        current_or_high: float | None = None
        current_or_low: float | None = None
        current_opening_reference_price: float | None = None
        current_or_volume_total = 0.0
        current_or_volume_count = 0
        session_price_volume = 0.0
        session_volume_total = 0.0
        current_breakout_armed = False
        current_retest_ready = False
        current_breakout_arm_index: int | None = None

        for index, bar in enumerate(bars):
            parsed_timestamp = _parse_intraday_timestamp(bar.timestamp)
            session_id = parsed_timestamp.date().isoformat() if parsed_timestamp is not None else None
            is_new_session = session_id != previous_session_id
            session_ids.append(session_id)
            session_changed.append(is_new_session)

            if is_new_session:
                current_or_high = None
                current_or_low = None
                current_opening_reference_price = None
                current_or_volume_total = 0.0
                current_or_volume_count = 0
                session_price_volume = 0.0
                session_volume_total = 0.0
                current_breakout_armed = False
                current_retest_ready = False
                current_breakout_arm_index = None

            if parsed_timestamp is None:
                minutes_from_session_start.append(None)
                opening_range_high.append(None)
                opening_range_low.append(None)
                opening_reference_price.append(None)
                opening_range_pct.append(None)
                opening_range_average_volume.append(None)
                session_vwap.append(None)
                breakout_armed.append(False)
                retest_ready.append(False)
                breakout_arm_index.append(None)
                previous_session_id = session_id
                continue

            minutes = (
                parsed_timestamp.hour * 60
                + parsed_timestamp.minute
                - (self.session_start_hour * 60 + self.session_start_minute)
            )
            minutes_from_session_start.append(minutes)

            if minutes < 0:
                opening_range_high.append(None)
                opening_range_low.append(None)
                opening_reference_price.append(None)
                opening_range_pct.append(None)
                opening_range_average_volume.append(None)
                session_vwap.append(None)
                breakout_armed.append(False)
                retest_ready.append(False)
                breakout_arm_index.append(None)
                previous_session_id = session_id
                continue

            typical_price = (bar.high + bar.low + bar.close) / 3.0
            session_price_volume += typical_price * bar.volume
            session_volume_total += bar.volume
            session_vwap.append(
                typical_price
                if session_volume_total == 0
                else session_price_volume / session_volume_total
            )

            if minutes < self.opening_range_minutes:
                if current_opening_reference_price is None:
                    current_opening_reference_price = bar.open
                current_or_high = (
                    bar.high if current_or_high is None else max(current_or_high, bar.high)
                )
                current_or_low = (
                    bar.low if current_or_low is None else min(current_or_low, bar.low)
                )
                current_or_volume_total += bar.volume
                current_or_volume_count += 1
                opening_range_high.append(current_or_high)
                opening_range_low.append(current_or_low)
            else:
                opening_range_high.append(current_or_high)
                opening_range_low.append(current_or_low)
            opening_reference_price.append(current_opening_reference_price)
            opening_range_pct.append(
                _compute_opening_range_pct(
                    current_or_high,
                    current_or_low,
                    current_opening_reference_price,
                )
            )
            opening_range_average_volume.append(
                None
                if current_or_volume_count == 0
                else current_or_volume_total / current_or_volume_count
            )

            if (
                minutes >= self.opening_range_minutes
                and current_or_high is not None
                and bar.close > current_or_high
                and not current_breakout_armed
            ):
                current_breakout_armed = True
                current_breakout_arm_index = index
            if (
                current_breakout_armed
                and current_breakout_arm_index is not None
                and index > current_breakout_arm_index
                and current_or_high is not None
                and bar.low <= current_or_high
                and bar.close >= current_or_high
            ):
                current_retest_ready = True

            breakout_armed.append(current_breakout_armed)
            retest_ready.append(current_retest_ready)
            breakout_arm_index.append(current_breakout_arm_index)

            previous_session_id = session_id

        return OrbVolumeVwapContext(
            session_ids=session_ids,
            session_changed=session_changed,
            minutes_from_session_start=minutes_from_session_start,
            opening_range_high=opening_range_high,
            opening_range_low=opening_range_low,
            opening_reference_price=opening_reference_price,
            opening_range_pct=opening_range_pct,
            opening_range_average_volume=opening_range_average_volume,
            session_vwap=session_vwap,
            trend_ema=trend_ema,
            average_volume=average_volume,
            breakout_armed=breakout_armed,
            retest_ready=retest_ready,
            breakout_arm_index=breakout_arm_index,
        )

    def decide_bar(
        self,
        *,
        index: int,
        bar: Bar,
        bars: list[Bar],
        context: OrbVolumeVwapContext,
        previous_target_position: float,
    ) -> StrategyDecision:
        """
        用途與流程：依 intraday session 建立 ORB 開盤區間，並在區間完成後檢查 OR 寬度百分比、突破距離門檻、是否屬於從 OR 盒子內部發動的 fresh breakout、是否仍在允許接受新 breakout 的 signal window 內、突破 candle 是否整根站上區間、breakout candle body ratio、close 突破、量能放大、VWAP 位置、可選的 VWAP slope 確認、可選的 EMA 趨勢確認，以及可選的「EMA 不得落在 opening range 盒子內」結構 gate 是否同時成立，輸出 long-only target 與阻擋原因；若啟用 OR volume baseline，breakout 量能會改成相對於 opening range 平均量能，而不是 rolling volume SMA。session end 與 timezone 目前只作為 regular-session contract metadata，不在這個決策函式內直接觸發 forced flat。
        參數：self 表示目前物件實例；index（int）由呼叫端傳入，需符合函式 contract；bar（Bar）由呼叫端傳入，需符合函式 contract；bars（list[Bar]）由呼叫端傳入，需符合函式 contract；context（OrbVolumeVwapContext）由呼叫端傳入，需符合函式 contract；previous_target_position（float）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 StrategyDecision；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        minutes = context.minutes_from_session_start[index]
        opening_range_high = context.opening_range_high[index]
        opening_range_low = context.opening_range_low[index]
        opening_range_pct = context.opening_range_pct[index]
        opening_range_average_volume = context.opening_range_average_volume[index]
        session_vwap = context.session_vwap[index]
        trend_ema = context.trend_ema[index]
        average_volume = context.average_volume[index]

        if context.session_changed[index] and previous_target_position > 0:
            return StrategyDecision(0.0, "session_reset", 0.0)
        if minutes is None:
            return StrategyDecision(0.0, "session_timestamp_required", 0.0)
        if minutes < 0:
            return StrategyDecision(0.0, "outside_session", 0.0)
        if minutes < self.opening_range_minutes:
            return StrategyDecision(0.0, "opening_range_building", 0.0)
        if opening_range_high is None or session_vwap is None:
            return StrategyDecision(0.0, "opening_range_unavailable", 0.0)
        if (
            self.min_opening_range_pct is not None
            and opening_range_pct is not None
            and opening_range_pct < self.min_opening_range_pct
        ):
            return StrategyDecision(0.0, "opening_range_too_narrow", opening_range_pct)
        if (
            self.max_opening_range_pct is not None
            and opening_range_pct is not None
            and opening_range_pct > self.max_opening_range_pct
        ):
            return StrategyDecision(0.0, "opening_range_too_wide", opening_range_pct)

        if self.use_opening_range_volume_baseline:
            volume_baseline = opening_range_average_volume
        else:
            volume_baseline = average_volume
        if volume_baseline is None:
            if not self.use_opening_range_volume_baseline:
                return StrategyDecision(0.0, "volume_warmup", 0.0)
            return StrategyDecision(0.0, "breakout_volume_baseline_unavailable", 0.0)
        volume_ratio = 0.0 if not volume_baseline else bar.volume / volume_baseline
        if previous_target_position > 0:
            return StrategyDecision(1.0, "hold_intraday_breakout", volume_ratio)
        if bar.close <= opening_range_high:
            return StrategyDecision(0.0, "below_or_high", volume_ratio)
        if (
            self.signal_window_minutes is not None
            and minutes >= self.signal_window_minutes
        ):
            return StrategyDecision(0.0, "outside_signal_window", float(minutes))
        breakout_pct = (bar.close - opening_range_high) / opening_range_high
        if self.min_breakout_pct > 0 and breakout_pct < self.min_breakout_pct:
            return StrategyDecision(0.0, "breakout_distance_too_small", breakout_pct)
        if self.require_fresh_breakout_from_or and not _previous_close_is_inside_or(
            index=index,
            bars=bars,
            context=context,
            opening_range_high=opening_range_high,
            opening_range_low=opening_range_low,
        ):
            return StrategyDecision(0.0, "breakout_not_fresh_from_or", breakout_pct)
        if self.require_full_bar_above_range and bar.low <= opening_range_high:
            return StrategyDecision(0.0, "breakout_bar_reentered_range", breakout_pct)
        breakout_body_pct = _compute_candle_body_pct(bar)
        if self.min_breakout_body_pct > 0 and breakout_body_pct < self.min_breakout_body_pct:
            return StrategyDecision(0.0, "breakout_body_too_small", breakout_body_pct)
        if self.require_vwap_confirmation and bar.close <= session_vwap:
            return StrategyDecision(0.0, "breakout_below_vwap", volume_ratio)
        if self.require_vwap_slope_confirmation:
            vwap_slope = _current_session_vwap_slope(index=index, context=context)
            if vwap_slope is None or vwap_slope <= 0:
                return StrategyDecision(
                    0.0,
                    "breakout_vwap_slope_blocked",
                    0.0 if vwap_slope is None else vwap_slope,
                )
        if self.reject_ema_inside_opening_range:
            if trend_ema is None:
                return StrategyDecision(0.0, "breakout_ema_reference_unavailable", 0.0)
            if (
                opening_range_low is not None
                and opening_range_low <= trend_ema <= opening_range_high
            ):
                return StrategyDecision(0.0, "ema_inside_opening_range", trend_ema)
        if self.require_ema_trend_confirmation:
            if trend_ema is None or bar.close <= trend_ema:
                return StrategyDecision(
                    0.0,
                    "breakout_below_ema",
                    0.0 if trend_ema is None else trend_ema,
                )
            ema_slope = _current_session_ema_slope(index=index, context=context)
            if ema_slope is None or ema_slope <= 0:
                return StrategyDecision(
                    0.0,
                    "breakout_ema_slope_blocked",
                    0.0 if ema_slope is None else ema_slope,
                )
        if bar.volume < volume_baseline * self.volume_multiplier:
            return StrategyDecision(0.0, "breakout_volume_blocked", volume_ratio)
        if self.require_retest_confirmation:
            if not context.breakout_armed[index]:
                return StrategyDecision(0.0, "breakout_not_armed", volume_ratio)
            if not context.retest_ready[index]:
                return StrategyDecision(0.0, "waiting_for_retest_confirmation", volume_ratio)
            if bar.low > opening_range_high:
                return StrategyDecision(0.0, "retest_not_touched", volume_ratio)
            return StrategyDecision(1.0, "orb_retest_vwap_breakout", volume_ratio)
        return StrategyDecision(1.0, "orb_volume_vwap_breakout", volume_ratio)


def _parse_intraday_timestamp(timestamp: str) -> datetime | None:
    """
    用途與流程：將策略輸入的 timestamp 解析成 intraday datetime；只接受含時間資訊的 ISO-8601 字串，避免把日線資料誤當成 ORB session 資料。
    參數：timestamp（str）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 datetime | None；格式不含時間或無法解析時回傳 None，不主動丟錯。
    """
    if not timestamp or ("T" not in timestamp and " " not in timestamp):
        return None
    candidate = timestamp.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _compute_opening_range_pct(
    opening_range_high: float | None,
    opening_range_low: float | None,
    opening_reference_price: float | None,
) -> float | None:
    """
    用途與流程：將 OR 高低差換算成相對於 session 第一根開盤價的百分比，供 OR range size filter 判斷區間是否過窄或過寬。
    參數：opening_range_high 與 opening_range_low 是目前已形成的 OR 上下界；opening_reference_price 是 session 第一根 bar 的開盤參考價。
    回傳與錯誤：回傳 float | None；當 OR 尚未形成或參考價缺失/非正數時回傳 None，不主動拋錯。
    """
    if (
        opening_range_high is None
        or opening_range_low is None
        or opening_reference_price is None
        or opening_reference_price <= 0
    ):
        return None
    return (opening_range_high - opening_range_low) / opening_reference_price


def _compute_candle_body_pct(bar: Bar) -> float:
    """
    用途與流程：把單根 breakout candle 的實體長度換算成整根 K 棒 range 的比例，供 ORB 的 body strength filter 判斷這次突破是否夠乾淨。
    參數：bar（Bar）由呼叫端傳入，需包含 open、high、low、close；若高低價沒有形成正 range，函式會把 body ratio 視為 0。
    回傳與錯誤：回傳 float，範圍介於 0 到 1；若 bar range 為 0 或負值，不主動丟錯，直接回傳 0.0。
    """
    candle_range = bar.high - bar.low
    if candle_range <= 0:
        return 0.0
    return abs(bar.close - bar.open) / candle_range


def _previous_close_is_inside_or(
    *,
    index: int,
    bars: list[Bar],
    context: OrbVolumeVwapContext,
    opening_range_high: float | None,
    opening_range_low: float | None,
) -> bool:
    """
    用途與流程：判斷目前 breakout 的前一根 close 是否仍位於同一個 session 的 OR 盒子內部，供 fresh breakout gate 阻擋那些價格早已在區間外游走的遲到突破。
    參數：index 是目前 breakout bar 的位置；bars 是完整 OHLCV 序列；context 提供 session 切換資訊；opening_range_high 與 opening_range_low 是目前 session 已形成的 OR 邊界。
    回傳與錯誤：回傳 bool；若缺少前一根 bar、換 session、或 OR 邊界尚未完整，直接回傳 False，不主動丟錯。
    """
    if (
        index <= 0
        or context.session_changed[index]
        or opening_range_high is None
        or opening_range_low is None
    ):
        return False
    previous_close = bars[index - 1].close
    return opening_range_low <= previous_close <= opening_range_high


def _current_session_vwap_slope(
    *,
    index: int,
    context: OrbVolumeVwapContext,
) -> float | None:
    """
    用途與流程：計算目前 bar 的 session VWAP 相對前一根同 session bar 的變化量，供 ORB 的 VWAP slope confirmation 判斷 breakout 當下的 VWAP 是否仍在上升。
    參數：index 是目前 breakout bar 的位置；context 提供 session 切換資訊與逐 bar session VWAP 序列。
    回傳與錯誤：回傳 float | None；若缺少前一根同 session VWAP、剛好跨 session、或任一 VWAP 不可用，則回傳 None，不主動拋錯。
    """
    if index <= 0 or context.session_changed[index]:
        return None
    current_session_vwap = context.session_vwap[index]
    previous_session_vwap = context.session_vwap[index - 1]
    if current_session_vwap is None or previous_session_vwap is None:
        return None
    return current_session_vwap - previous_session_vwap


def _current_session_ema_slope(
    *,
    index: int,
    context: OrbVolumeVwapContext,
) -> float | None:
    """
    用途與流程：計算目前 bar 的 rolling EMA 相對前一根同 session bar 的變化量，供 ORB 的 EMA trend confirmation 判斷 breakout 當下的 EMA 是否仍在上升。
    參數：index 是目前 breakout bar 的位置；context 提供 session 切換資訊與逐 bar EMA 序列。
    回傳與錯誤：回傳 float | None；若缺少前一根同 session EMA、剛好跨 session、或任一 EMA 不可用，則回傳 None，不主動拋錯。
    """
    if index <= 0 or context.session_changed[index]:
        return None
    current_trend_ema = context.trend_ema[index]
    previous_trend_ema = context.trend_ema[index - 1]
    if current_trend_ema is None or previous_trend_ema is None:
        return None
    return current_trend_ema - previous_trend_ema
