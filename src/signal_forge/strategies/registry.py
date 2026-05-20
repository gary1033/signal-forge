from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from signal_forge.strategies.confluence_score import ConfluenceScoreStrategy
from signal_forge.strategies.sma_crossover import SmaCrossoverStrategy
from signal_forge.strategies.volume_filter import VolumeFilteredStrategy
from signal_forge.strategies.vwap_reversion import VwapReversionStrategy
from signal_forge.strategy import Strategy


StrategyBuilder = Callable[..., Strategy]

SUPPORTED_STRATEGY_NAMES = (
    "sma-crossover",
    "vwap-reversion",
    "confluence-score",
)


@dataclass(frozen=True)
class StrategyParameterDefaults:
    fast_window: int
    slow_window: int
    vwap_window: int
    rsi_window: int
    entry_z: float
    exit_z: float
    threshold: float
    vwap_regime_window: int


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
    allow_short: bool | None = None,
) -> Strategy:
    """
    用途與流程：依策略名稱與參數建立 registry 中支援的策略實例。
    參數：strategy_name 是 registry key；各技術指標參數傳入 None 表示使用該策略自己的 default，只有明確給值才覆寫；vwap_regime_filter 控制 VWAP long entry 是否要求 close >= regime SMA；allow_short 為 None 時交給各策略 builder 決定預設多空語意。
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
    volume_filter: bool = False,
    volume_window: int | None = None,
    volume_multiplier: float | None = None,
) -> Strategy:
    """
    用途與流程：建立 Phase 1 long-only 策略，必要時包上成交量濾網 wrapper。
    參數：strategy_name 是 registry key；策略參數為 None 時使用該策略 default，Phase 1 只強制 allow_short=False；volume_filter 控制是否套用成交量 wrapper，volume_window 與 volume_multiplier 為 None 時使用 wrapper default。
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
        allow_short=False,
    )
    if not volume_filter:
        return strategy

    return VolumeFilteredStrategy(
        strategy,
        volume_window=VolumeFilteredStrategy.volume_window
        if volume_window is None
        else volume_window,
        volume_multiplier=VolumeFilteredStrategy.volume_multiplier
        if volume_multiplier is None
        else volume_multiplier,
    )


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
}
