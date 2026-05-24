from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from signal_forge.strategies.absolute_momentum import AbsoluteMomentumStrategy
from signal_forge.strategies.confluence_score import ConfluenceScoreStrategy
from signal_forge.strategies.orb_volume_vwap import OrbVolumeVwapStrategy
from signal_forge.strategies.signal_cooldown import SignalCooldownStrategy
from signal_forge.strategies.sma_crossover import SmaCrossoverStrategy
from signal_forge.strategies.volume_filter import VolumeFilteredStrategy
from signal_forge.strategies.vwap_reversion import VwapReversionStrategy
from signal_forge.strategy import Strategy


StrategyBuilder = Callable[..., Strategy]

SUPPORTED_STRATEGY_NAMES = (
    "sma-crossover",
    "vwap-reversion",
    "confluence-score",
    "absolute-momentum",
    "orb-volume-vwap",
)


@dataclass(frozen=True)
class StrategyParameterDefaults:
    """
    用途與流程：集中保存 CLI / reporting 需要顯示的策略預設參數，避免 parser、factory 與 summary 各自硬編一份預設值。
    參數：fast_window、slow_window、vwap_window、rsi_window、entry_z、exit_z、threshold、vwap_regime_window 對應既有策略欄位；orb_opening_range_minutes、orb_session_start_hour、orb_session_start_minute、orb_session_end_hour、orb_session_end_minute、orb_session_timezone、orb_signal_window_minutes、orb_ema_window、orb_require_ema_trend_confirmation 與 orb_reject_ema_inside_opening_range 對應 ORB intraday session / market-clock / trend-confirmation / 結構 gate 預設值。
    回傳與錯誤：這是 dataclass，不直接回傳值；建立實例時若欄位型別不符，會由 Python dataclass 與型別使用情境自行回報錯誤。
    """
    fast_window: int
    slow_window: int
    vwap_window: int
    rsi_window: int
    entry_z: float
    exit_z: float
    threshold: float
    vwap_regime_window: int
    orb_opening_range_minutes: int
    orb_session_start_hour: int
    orb_session_start_minute: int
    orb_session_end_hour: int
    orb_session_end_minute: int
    orb_session_timezone: str
    orb_require_vwap_slope_confirmation: bool
    orb_ema_window: int
    orb_require_ema_trend_confirmation: bool
    orb_reject_ema_inside_opening_range: bool
    orb_signal_window_minutes: int | None
    orb_min_range_pct: float
    orb_max_range_pct: float
    orb_min_breakout_pct: float
    orb_require_full_bar_above_range: bool
    orb_min_breakout_body_pct: float
    orb_require_fresh_breakout_from_or: bool
    orb_use_opening_range_volume_baseline: bool


STRATEGY_PARAMETER_DEFAULTS: dict[str, StrategyParameterDefaults] = {
    "sma-crossover": StrategyParameterDefaults(
        fast_window=SmaCrossoverStrategy.fast_window,
        slow_window=SmaCrossoverStrategy.slow_window,
        vwap_window=20,
        rsi_window=14,
        entry_z=1.5,
        exit_z=0.25,
        threshold=3.0,
        vwap_regime_window=50,
        orb_opening_range_minutes=0,
        orb_session_start_hour=0,
        orb_session_start_minute=0,
        orb_session_end_hour=0,
        orb_session_end_minute=0,
        orb_session_timezone="n/a",
        orb_require_vwap_slope_confirmation=False,
        orb_ema_window=0,
        orb_require_ema_trend_confirmation=False,
        orb_reject_ema_inside_opening_range=False,
        orb_signal_window_minutes=None,
        orb_min_range_pct=0.0,
        orb_max_range_pct=0.0,
        orb_min_breakout_pct=0.0,
        orb_require_full_bar_above_range=False,
        orb_min_breakout_body_pct=0.0,
        orb_require_fresh_breakout_from_or=False,
        orb_use_opening_range_volume_baseline=False,
    ),
    "vwap-reversion": StrategyParameterDefaults(
        fast_window=20,
        slow_window=200,
        vwap_window=VwapReversionStrategy.window,
        rsi_window=14,
        entry_z=VwapReversionStrategy.entry_z,
        exit_z=VwapReversionStrategy.exit_z,
        threshold=3.0,
        vwap_regime_window=VwapReversionStrategy.regime_window,
        orb_opening_range_minutes=0,
        orb_session_start_hour=0,
        orb_session_start_minute=0,
        orb_session_end_hour=0,
        orb_session_end_minute=0,
        orb_session_timezone="n/a",
        orb_require_vwap_slope_confirmation=False,
        orb_ema_window=0,
        orb_require_ema_trend_confirmation=False,
        orb_reject_ema_inside_opening_range=False,
        orb_signal_window_minutes=None,
        orb_min_range_pct=0.0,
        orb_max_range_pct=0.0,
        orb_min_breakout_pct=0.0,
        orb_require_full_bar_above_range=False,
        orb_min_breakout_body_pct=0.0,
        orb_require_fresh_breakout_from_or=False,
        orb_use_opening_range_volume_baseline=False,
    ),
    "confluence-score": StrategyParameterDefaults(
        fast_window=ConfluenceScoreStrategy.fast_window,
        slow_window=ConfluenceScoreStrategy.slow_window,
        vwap_window=ConfluenceScoreStrategy.vwap_window,
        rsi_window=ConfluenceScoreStrategy.rsi_window,
        entry_z=1.5,
        exit_z=0.25,
        threshold=ConfluenceScoreStrategy.threshold,
        vwap_regime_window=50,
        orb_opening_range_minutes=0,
        orb_session_start_hour=0,
        orb_session_start_minute=0,
        orb_session_end_hour=0,
        orb_session_end_minute=0,
        orb_session_timezone="n/a",
        orb_require_vwap_slope_confirmation=False,
        orb_ema_window=0,
        orb_require_ema_trend_confirmation=False,
        orb_reject_ema_inside_opening_range=False,
        orb_signal_window_minutes=None,
        orb_min_range_pct=0.0,
        orb_max_range_pct=0.0,
        orb_min_breakout_pct=0.0,
        orb_require_full_bar_above_range=False,
        orb_min_breakout_body_pct=0.0,
        orb_require_fresh_breakout_from_or=False,
        orb_use_opening_range_volume_baseline=False,
    ),
    "absolute-momentum": StrategyParameterDefaults(
        fast_window=AbsoluteMomentumStrategy.momentum_window,
        slow_window=AbsoluteMomentumStrategy.trend_window,
        vwap_window=20,
        rsi_window=14,
        entry_z=1.5,
        exit_z=0.25,
        threshold=3.0,
        vwap_regime_window=50,
        orb_opening_range_minutes=0,
        orb_session_start_hour=0,
        orb_session_start_minute=0,
        orb_session_end_hour=0,
        orb_session_end_minute=0,
        orb_session_timezone="n/a",
        orb_require_vwap_slope_confirmation=False,
        orb_ema_window=0,
        orb_require_ema_trend_confirmation=False,
        orb_reject_ema_inside_opening_range=False,
        orb_signal_window_minutes=None,
        orb_min_range_pct=0.0,
        orb_max_range_pct=0.0,
        orb_min_breakout_pct=0.0,
        orb_require_full_bar_above_range=False,
        orb_min_breakout_body_pct=0.0,
        orb_require_fresh_breakout_from_or=False,
        orb_use_opening_range_volume_baseline=False,
    ),
    "orb-volume-vwap": StrategyParameterDefaults(
        fast_window=0,
        slow_window=0,
        vwap_window=0,
        rsi_window=0,
        entry_z=0.0,
        exit_z=0.0,
        threshold=0.0,
        vwap_regime_window=0,
        orb_opening_range_minutes=OrbVolumeVwapStrategy.opening_range_minutes,
        orb_session_start_hour=OrbVolumeVwapStrategy.session_start_hour,
        orb_session_start_minute=OrbVolumeVwapStrategy.session_start_minute,
        orb_session_end_hour=OrbVolumeVwapStrategy.session_end_hour,
        orb_session_end_minute=OrbVolumeVwapStrategy.session_end_minute,
        orb_session_timezone=OrbVolumeVwapStrategy.session_timezone,
        orb_require_vwap_slope_confirmation=False,
        orb_ema_window=OrbVolumeVwapStrategy.ema_window,
        orb_require_ema_trend_confirmation=False,
        orb_reject_ema_inside_opening_range=False,
        orb_signal_window_minutes=None,
        orb_min_range_pct=0.0,
        orb_max_range_pct=0.0,
        orb_min_breakout_pct=0.0,
        orb_require_full_bar_above_range=False,
        orb_min_breakout_body_pct=0.0,
        orb_require_fresh_breakout_from_or=False,
        orb_use_opening_range_volume_baseline=False,
    ),
}


def build_strategy(
    strategy_name: str,
    *,
    fast_window: int | None = None,
    slow_window: int | None = None,
    vwap_window: int | None = None,
    rsi_window: int | None = None,
    entry_z: float | None = None,
    exit_z: float | None = None,
    threshold: float | None = None,
    vwap_regime_filter: bool = False,
    vwap_regime_window: int | None = None,
    orb_retest_confirmation: bool = False,
    orb_opening_range_minutes: int | None = None,
    orb_session_start_hour: int | None = None,
    orb_session_start_minute: int | None = None,
    orb_session_end_hour: int | None = None,
    orb_session_end_minute: int | None = None,
    orb_session_timezone: str | None = None,
    orb_vwap_slope_confirmation: bool = False,
    orb_ema_window: int | None = None,
    orb_ema_trend_confirmation: bool = False,
    orb_reject_ema_inside_opening_range: bool = False,
    orb_signal_window_minutes: int | None = None,
    orb_min_range_pct: float | None = None,
    orb_max_range_pct: float | None = None,
    orb_min_breakout_pct: float | None = None,
    orb_full_bar_above_range: bool = False,
    orb_min_breakout_body_pct: float | None = None,
    orb_fresh_breakout_from_or: bool = False,
    orb_use_opening_range_volume_baseline: bool = False,
    allow_short: bool | None = None,
) -> Strategy:
    """
    用途與流程：依策略名稱與參數建立 registry 中支援的策略實例。
    參數：strategy_name 是 registry key；各技術指標參數傳入 None 表示使用該策略自己的 default，只有明確給值才覆寫；absolute-momentum 使用 fast_window 作為動能回看期、slow_window 作為長期趨勢 SMA；vwap_regime_filter 控制 VWAP long entry 是否要求 close >= regime SMA；orb_opening_range_minutes 與 orb_session_start_hour/minute 用來參數化 ORB 的開盤區間與 session 起點；orb_session_end_hour/minute 與 orb_session_timezone 用來顯式記錄 ORB regular-session 的結束邊界與 market-clock timezone，但這一步先不直接改變持有或 forced-flat 語意；orb_vwap_slope_confirmation 允許要求 breakout 當下的 session VWAP 相對前一根同 session bar 持續上升；orb_ema_window 與 orb_ema_trend_confirmation 允許要求 breakout 當下價格站在 rolling EMA 上方，且該 EMA 相對前一根同 session bar 仍在上升；orb_reject_ema_inside_opening_range 允許要求 EMA 不得落在 OR 盒子內，避免結構上模糊的 breakout；orb_signal_window_minutes 允許限制 ORB 只在 session 開始後某段時間內接受新的 breakout；orb_min_range_pct / orb_max_range_pct 則控制 OR 寬度相對於開盤參考價的允許範圍；orb_min_breakout_pct 允許要求 close 至少超出 OR high 一定百分比才算有效突破；orb_full_bar_above_range 允許要求 breakout candle 的 low 也要站在 OR high 上方；orb_min_breakout_body_pct 允許要求 breakout candle 的 body 佔整根 K 棒 range 達到最小比例；orb_fresh_breakout_from_or 允許要求 breakout 前一根 close 仍位於 OR 盒子內；orb_use_opening_range_volume_baseline 允許把 breakout 量能改成相對於 OR 平均量能；allow_short 為 None 時交給各策略 builder 決定預設多空語意。
    回傳與錯誤：回傳 Strategy；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    normalized = _normalize_strategy_name(strategy_name)
    try:
        builder = STRATEGY_REGISTRY[normalized]
    except KeyError as exc:
        raise ValueError(f"unsupported strategy {strategy_name}") from exc

    return builder(
        fast_window=fast_window,
        slow_window=slow_window,
        vwap_window=vwap_window,
        rsi_window=rsi_window,
        entry_z=entry_z,
        exit_z=exit_z,
        threshold=threshold,
        vwap_regime_filter=vwap_regime_filter,
        vwap_regime_window=vwap_regime_window,
        orb_retest_confirmation=orb_retest_confirmation,
        orb_opening_range_minutes=orb_opening_range_minutes,
        orb_session_start_hour=orb_session_start_hour,
        orb_session_start_minute=orb_session_start_minute,
        orb_session_end_hour=orb_session_end_hour,
        orb_session_end_minute=orb_session_end_minute,
        orb_session_timezone=orb_session_timezone,
        orb_vwap_slope_confirmation=orb_vwap_slope_confirmation,
        orb_ema_window=orb_ema_window,
        orb_ema_trend_confirmation=orb_ema_trend_confirmation,
        orb_reject_ema_inside_opening_range=orb_reject_ema_inside_opening_range,
        orb_signal_window_minutes=orb_signal_window_minutes,
        orb_min_range_pct=orb_min_range_pct,
        orb_max_range_pct=orb_max_range_pct,
        orb_min_breakout_pct=orb_min_breakout_pct,
        orb_full_bar_above_range=orb_full_bar_above_range,
        orb_min_breakout_body_pct=orb_min_breakout_body_pct,
        orb_fresh_breakout_from_or=orb_fresh_breakout_from_or,
        orb_use_opening_range_volume_baseline=orb_use_opening_range_volume_baseline,
        allow_short=allow_short,
    )


def build_phase1_strategy(
    strategy_name: str,
    *,
    fast_window: int | None = None,
    slow_window: int | None = None,
    vwap_window: int | None = None,
    rsi_window: int | None = None,
    entry_z: float | None = None,
    exit_z: float | None = None,
    threshold: float | None = None,
    vwap_regime_filter: bool = False,
    vwap_regime_window: int | None = None,
    orb_retest_confirmation: bool = False,
    orb_opening_range_minutes: int | None = None,
    orb_session_start_hour: int | None = None,
    orb_session_start_minute: int | None = None,
    orb_session_end_hour: int | None = None,
    orb_session_end_minute: int | None = None,
    orb_session_timezone: str | None = None,
    orb_vwap_slope_confirmation: bool = False,
    orb_ema_window: int | None = None,
    orb_ema_trend_confirmation: bool = False,
    orb_reject_ema_inside_opening_range: bool = False,
    orb_signal_window_minutes: int | None = None,
    orb_min_range_pct: float | None = None,
    orb_max_range_pct: float | None = None,
    orb_min_breakout_pct: float | None = None,
    orb_full_bar_above_range: bool = False,
    orb_min_breakout_body_pct: float | None = None,
    orb_fresh_breakout_from_or: bool = False,
    orb_use_opening_range_volume_baseline: bool = False,
    volume_filter: bool = False,
    volume_window: int | None = None,
    volume_multiplier: float | None = None,
    signal_cooldown_bars: int | None = None,
) -> Strategy:
    """
    用途與流程：建立 Phase 1 long-only 策略，必要時依序包上成交量濾網與進場冷卻 wrapper。
    參數：strategy_name 是 registry key；策略參數為 None 時使用該策略 default，Phase 1 只強制 allow_short=False；absolute-momentum 使用 fast_window / slow_window 對應動能回看期與趨勢 SMA；orb_opening_range_minutes、orb_session_start_hour/minute、orb_session_end_hour/minute、orb_session_timezone、orb_vwap_slope_confirmation、orb_ema_window、orb_ema_trend_confirmation、orb_reject_ema_inside_opening_range、orb_signal_window_minutes、orb_min/max_range_pct、orb_min_breakout_pct、orb_full_bar_above_range、orb_min_breakout_body_pct、orb_fresh_breakout_from_or 與 orb_use_opening_range_volume_baseline 只對 ORB 策略生效；其中 session end / timezone 目前先作為 regular-session contract metadata；volume_filter 控制是否套用成交量 wrapper，volume_window 與 volume_multiplier 為 None 時使用 wrapper default；signal_cooldown_bars 為正整數時會封鎖接受 long entry 後指定 bar 數內的新 long entry。
    回傳與錯誤：回傳 Strategy；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    strategy = build_strategy(
        strategy_name,
        fast_window=fast_window,
        slow_window=slow_window,
        vwap_window=vwap_window,
        rsi_window=rsi_window,
        entry_z=entry_z,
        exit_z=exit_z,
        threshold=threshold,
        vwap_regime_filter=vwap_regime_filter,
        vwap_regime_window=vwap_regime_window,
        orb_retest_confirmation=orb_retest_confirmation,
        orb_opening_range_minutes=orb_opening_range_minutes,
        orb_session_start_hour=orb_session_start_hour,
        orb_session_start_minute=orb_session_start_minute,
        orb_session_end_hour=orb_session_end_hour,
        orb_session_end_minute=orb_session_end_minute,
        orb_session_timezone=orb_session_timezone,
        orb_vwap_slope_confirmation=orb_vwap_slope_confirmation,
        orb_ema_window=orb_ema_window,
        orb_ema_trend_confirmation=orb_ema_trend_confirmation,
        orb_reject_ema_inside_opening_range=orb_reject_ema_inside_opening_range,
        orb_signal_window_minutes=orb_signal_window_minutes,
        orb_min_range_pct=orb_min_range_pct,
        orb_max_range_pct=orb_max_range_pct,
        orb_min_breakout_pct=orb_min_breakout_pct,
        orb_full_bar_above_range=orb_full_bar_above_range,
        orb_min_breakout_body_pct=orb_min_breakout_body_pct,
        orb_fresh_breakout_from_or=orb_fresh_breakout_from_or,
        orb_use_opening_range_volume_baseline=orb_use_opening_range_volume_baseline,
        allow_short=False,
    )
    if volume_filter:
        strategy = VolumeFilteredStrategy(
            strategy,
            volume_window=VolumeFilteredStrategy.volume_window
            if volume_window is None
            else volume_window,
            volume_multiplier=VolumeFilteredStrategy.volume_multiplier
            if volume_multiplier is None
            else volume_multiplier,
        )
    if signal_cooldown_bars is not None:
        strategy = SignalCooldownStrategy(strategy, cooldown_bars=signal_cooldown_bars)

    return strategy


def _build_sma_crossover(
    *,
    fast_window: int | None,
    slow_window: int | None,
    vwap_window: int | None,
    rsi_window: int | None,
    entry_z: float | None,
    exit_z: float | None,
    threshold: float | None,
    vwap_regime_filter: bool,
    vwap_regime_window: int | None,
    orb_retest_confirmation: bool,
    orb_opening_range_minutes: int | None,
    orb_session_start_hour: int | None,
    orb_session_start_minute: int | None,
    orb_session_end_hour: int | None,
    orb_session_end_minute: int | None,
    orb_session_timezone: str | None,
    orb_vwap_slope_confirmation: bool,
    orb_ema_window: int | None,
    orb_ema_trend_confirmation: bool,
    orb_reject_ema_inside_opening_range: bool,
    orb_signal_window_minutes: int | None,
    orb_min_range_pct: float | None,
    orb_max_range_pct: float | None,
    orb_min_breakout_pct: float | None,
    orb_full_bar_above_range: bool,
    orb_min_breakout_body_pct: float | None,
    orb_fresh_breakout_from_or: bool,
    orb_use_opening_range_volume_baseline: bool,
    allow_short: bool | None,
) -> Strategy:
    """
    用途與流程：依 registry 或 reporting 需求組合內部資料結構，集中維護建構規則。
    參數：fast_window 與 slow_window 為 None 時使用 SMA Crossover default；其他參數保留相同 builder 介面但此策略不使用；allow_short 為 None 時使用 long-only。
    回傳與錯誤：回傳 Strategy；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    return SmaCrossoverStrategy(
        fast_window=SmaCrossoverStrategy.fast_window
        if fast_window is None
        else fast_window,
        slow_window=SmaCrossoverStrategy.slow_window
        if slow_window is None
        else slow_window,
        allow_short=False if allow_short is None else allow_short,
    )


def _build_vwap_reversion(
    *,
    fast_window: int | None,
    slow_window: int | None,
    vwap_window: int | None,
    rsi_window: int | None,
    entry_z: float | None,
    exit_z: float | None,
    threshold: float | None,
    vwap_regime_filter: bool,
    vwap_regime_window: int | None,
    orb_retest_confirmation: bool,
    orb_opening_range_minutes: int | None,
    orb_session_start_hour: int | None,
    orb_session_start_minute: int | None,
    orb_session_end_hour: int | None,
    orb_session_end_minute: int | None,
    orb_session_timezone: str | None,
    orb_vwap_slope_confirmation: bool,
    orb_ema_window: int | None,
    orb_ema_trend_confirmation: bool,
    orb_reject_ema_inside_opening_range: bool,
    orb_signal_window_minutes: int | None,
    orb_min_range_pct: float | None,
    orb_max_range_pct: float | None,
    orb_min_breakout_pct: float | None,
    orb_full_bar_above_range: bool,
    orb_min_breakout_body_pct: float | None,
    orb_fresh_breakout_from_or: bool,
    orb_use_opening_range_volume_baseline: bool,
    allow_short: bool | None,
) -> Strategy:
    """
    用途與流程：依 registry 或 reporting 需求組合內部資料結構，集中維護建構規則。
    參數：vwap_window、entry_z、exit_z、vwap_regime_window 為 None 時使用 VWAP Reversion default；fast/slow/rsi/threshold 保留相同 builder 介面但此策略不使用；allow_short 為 None 時使用策略 constructor default。
    回傳與錯誤：回傳 Strategy；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    kwargs: dict[str, object] = {
        "window": VwapReversionStrategy.window if vwap_window is None else vwap_window,
        "entry_z": VwapReversionStrategy.entry_z if entry_z is None else entry_z,
        "exit_z": VwapReversionStrategy.exit_z if exit_z is None else exit_z,
        "regime_filter": vwap_regime_filter,
        "regime_window": VwapReversionStrategy.regime_window
        if vwap_regime_window is None
        else vwap_regime_window,
    }
    if allow_short is not None:
        kwargs["allow_short"] = allow_short
    return VwapReversionStrategy(**kwargs)


def _build_confluence_score(
    *,
    fast_window: int | None,
    slow_window: int | None,
    vwap_window: int | None,
    rsi_window: int | None,
    entry_z: float | None,
    exit_z: float | None,
    threshold: float | None,
    vwap_regime_filter: bool,
    vwap_regime_window: int | None,
    orb_retest_confirmation: bool,
    orb_opening_range_minutes: int | None,
    orb_session_start_hour: int | None,
    orb_session_start_minute: int | None,
    orb_session_end_hour: int | None,
    orb_session_end_minute: int | None,
    orb_session_timezone: str | None,
    orb_vwap_slope_confirmation: bool,
    orb_ema_window: int | None,
    orb_ema_trend_confirmation: bool,
    orb_reject_ema_inside_opening_range: bool,
    orb_signal_window_minutes: int | None,
    orb_min_range_pct: float | None,
    orb_max_range_pct: float | None,
    orb_min_breakout_pct: float | None,
    orb_full_bar_above_range: bool,
    orb_min_breakout_body_pct: float | None,
    orb_fresh_breakout_from_or: bool,
    orb_use_opening_range_volume_baseline: bool,
    allow_short: bool | None,
) -> Strategy:
    """
    用途與流程：依 registry 或 reporting 需求組合內部資料結構，集中維護建構規則。
    參數：fast_window、slow_window、rsi_window、vwap_window 與 threshold 為 None 時使用 Confluence Score default；entry_z/exit_z/regime 參數保留相同 builder 介面但此策略不使用；allow_short 為 None 時使用策略 constructor default。
    回傳與錯誤：回傳 Strategy；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    kwargs: dict[str, object] = {
        "fast_window": ConfluenceScoreStrategy.fast_window
        if fast_window is None
        else fast_window,
        "slow_window": ConfluenceScoreStrategy.slow_window
        if slow_window is None
        else slow_window,
        "rsi_window": ConfluenceScoreStrategy.rsi_window
        if rsi_window is None
        else rsi_window,
        "vwap_window": ConfluenceScoreStrategy.vwap_window
        if vwap_window is None
        else vwap_window,
        "threshold": ConfluenceScoreStrategy.threshold
        if threshold is None
        else threshold,
    }
    if allow_short is not None:
        kwargs["allow_short"] = allow_short
    return ConfluenceScoreStrategy(**kwargs)


def _build_absolute_momentum(
    *,
    fast_window: int | None,
    slow_window: int | None,
    vwap_window: int | None,
    rsi_window: int | None,
    entry_z: float | None,
    exit_z: float | None,
    threshold: float | None,
    vwap_regime_filter: bool,
    vwap_regime_window: int | None,
    orb_retest_confirmation: bool,
    orb_opening_range_minutes: int | None,
    orb_session_start_hour: int | None,
    orb_session_start_minute: int | None,
    orb_session_end_hour: int | None,
    orb_session_end_minute: int | None,
    orb_session_timezone: str | None,
    orb_vwap_slope_confirmation: bool,
    orb_ema_window: int | None,
    orb_ema_trend_confirmation: bool,
    orb_reject_ema_inside_opening_range: bool,
    orb_signal_window_minutes: int | None,
    orb_min_range_pct: float | None,
    orb_max_range_pct: float | None,
    orb_min_breakout_pct: float | None,
    orb_full_bar_above_range: bool,
    orb_min_breakout_body_pct: float | None,
    orb_fresh_breakout_from_or: bool,
    orb_use_opening_range_volume_baseline: bool,
    allow_short: bool | None,
) -> Strategy:
    """
    用途與流程：建立絕對動能 long-only 策略，把共用 fast/slow 參數映射為動能回看期與趨勢 SMA。
    參數：fast_window 為 None 時使用 AbsoluteMomentumStrategy.momentum_window；slow_window 為 None 時使用 trend_window；其他共用 builder 參數保留介面但此策略不使用；allow_short 若明確要求 True 會被拒絕，避免把第一版趨勢持有候選誤解成多空策略。
    回傳與錯誤：回傳 AbsoluteMomentumStrategy；若要求 short 或視窗非正數，拋出 ValueError。
    """
    if allow_short:
        raise ValueError("absolute-momentum only supports long-only mode")
    return AbsoluteMomentumStrategy(
        momentum_window=AbsoluteMomentumStrategy.momentum_window
        if fast_window is None
        else fast_window,
        trend_window=AbsoluteMomentumStrategy.trend_window
        if slow_window is None
        else slow_window,
    )


def _build_orb_volume_vwap(
    *,
    fast_window: int | None,
    slow_window: int | None,
    vwap_window: int | None,
    rsi_window: int | None,
    entry_z: float | None,
    exit_z: float | None,
    threshold: float | None,
    vwap_regime_filter: bool,
    vwap_regime_window: int | None,
    orb_retest_confirmation: bool,
    orb_opening_range_minutes: int | None,
    orb_session_start_hour: int | None,
    orb_session_start_minute: int | None,
    orb_session_end_hour: int | None,
    orb_session_end_minute: int | None,
    orb_session_timezone: str | None,
    orb_vwap_slope_confirmation: bool,
    orb_ema_window: int | None,
    orb_ema_trend_confirmation: bool,
    orb_reject_ema_inside_opening_range: bool,
    orb_signal_window_minutes: int | None,
    orb_min_range_pct: float | None,
    orb_max_range_pct: float | None,
    orb_min_breakout_pct: float | None,
    orb_full_bar_above_range: bool,
    orb_min_breakout_body_pct: float | None,
    orb_fresh_breakout_from_or: bool,
    orb_use_opening_range_volume_baseline: bool,
    allow_short: bool | None,
) -> Strategy:
    """
    用途與流程：建立 ORB + Volume + VWAP 的 long-only intraday breakout 策略；builder 保留共用介面，並允許由 CLI / factory 控制是否啟用 retest confirmation。
    參數：共用 builder 介面欄位由 registry 傳入，其中本策略忽略 fast/slow/rsi/entry_z/exit_z/threshold/regime 相關參數；orb_retest_confirmation 控制突破後是否必須回踩再確認；orb_opening_range_minutes 與 orb_session_start_hour/minute 允許把開盤區間與 session 起點從硬編碼改為 CLI 可控；orb_session_end_hour/minute 與 orb_session_timezone 允許把 ORB regular-session 的結束邊界與 market-clock timezone 寫進策略設定，但目前先不直接改變持有或 forced-flat 邏輯；orb_vwap_slope_confirmation 允許要求 breakout 當下的 session VWAP 相對前一根同 session bar 保持上升；orb_ema_window 與 orb_ema_trend_confirmation 允許要求 breakout 當下價格站在 rolling EMA 上方，且該 EMA 相對前一根同 session bar 保持上升；orb_reject_ema_inside_opening_range 允許要求 EMA 不得落在 opening range 盒子內，避免 breakout 發生時趨勢基線仍卡在區間中央；orb_signal_window_minutes 允許限制策略只在 session 起始後某段時間內接受新的 breakout；orb_min/max_range_pct 允許限制 OR 寬度相對於 session 開盤參考價的允許區間；orb_min_breakout_pct 允許要求 close 至少超出 OR high 一定百分比才視為有效突破；orb_full_bar_above_range 允許要求 breakout candle 的 low 也要站在 OR high 上方；orb_min_breakout_body_pct 允許要求 breakout candle 的 body ratio 達到最小門檻；orb_fresh_breakout_from_or 允許要求 breakout 必須由 OR 盒子內部發動；orb_use_opening_range_volume_baseline 允許把 breakout 量能改成相對於 OR 平均量能；allow_short 若明確要求 True 會視為不支援的輸入。
    回傳與錯誤：回傳 Strategy；若輸入要求 short，會依原實作拋出 ValueError 或專用驗證例外。
    """
    if allow_short:
        raise ValueError("orb-volume-vwap only supports long-only mode")
    return OrbVolumeVwapStrategy(
        opening_range_minutes=OrbVolumeVwapStrategy.opening_range_minutes
        if orb_opening_range_minutes is None
        else orb_opening_range_minutes,
        session_start_hour=OrbVolumeVwapStrategy.session_start_hour
        if orb_session_start_hour is None
        else orb_session_start_hour,
        session_start_minute=OrbVolumeVwapStrategy.session_start_minute
        if orb_session_start_minute is None
        else orb_session_start_minute,
        session_end_hour=OrbVolumeVwapStrategy.session_end_hour
        if orb_session_end_hour is None
        else orb_session_end_hour,
        session_end_minute=OrbVolumeVwapStrategy.session_end_minute
        if orb_session_end_minute is None
        else orb_session_end_minute,
        session_timezone=OrbVolumeVwapStrategy.session_timezone
        if orb_session_timezone is None
        else orb_session_timezone,
        require_vwap_slope_confirmation=orb_vwap_slope_confirmation,
        ema_window=OrbVolumeVwapStrategy.ema_window
        if orb_ema_window is None
        else orb_ema_window,
        require_ema_trend_confirmation=orb_ema_trend_confirmation,
        reject_ema_inside_opening_range=orb_reject_ema_inside_opening_range,
        signal_window_minutes=orb_signal_window_minutes,
        require_retest_confirmation=orb_retest_confirmation,
        min_opening_range_pct=orb_min_range_pct,
        max_opening_range_pct=orb_max_range_pct,
        min_breakout_pct=0.0 if orb_min_breakout_pct is None else orb_min_breakout_pct,
        require_full_bar_above_range=orb_full_bar_above_range,
        min_breakout_body_pct=0.0
        if orb_min_breakout_body_pct is None
        else orb_min_breakout_body_pct,
        require_fresh_breakout_from_or=orb_fresh_breakout_from_or,
        use_opening_range_volume_baseline=orb_use_opening_range_volume_baseline,
    )


def _normalize_strategy_name(strategy_name: str) -> str:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：strategy_name（str）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    return strategy_name.strip().lower()


STRATEGY_REGISTRY: dict[str, StrategyBuilder] = {
    "sma-crossover": _build_sma_crossover,
    "vwap-reversion": _build_vwap_reversion,
    "confluence-score": _build_confluence_score,
    "absolute-momentum": _build_absolute_momentum,
    "orb-volume-vwap": _build_orb_volume_vwap,
}
