from __future__ import annotations

from collections.abc import Callable

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


def build_strategy(
    strategy_name: str,
    *,
    fast_window: int = 20,
    slow_window: int = 200,
    vwap_window: int = 20,
    rsi_window: int = 14,
    entry_z: float = 1.5,
    exit_z: float = 0.25,
    threshold: float = 3.0,
    vwap_regime_filter: bool = False,
    vwap_regime_window: int = 50,
    allow_short: bool | None = None,
) -> Strategy:
    """
    用途與流程：依策略名稱與參數建立 registry 中支援的策略實例。
    參數：strategy_name（str）由呼叫端傳入，需符合函式 contract；fast_window（int）由呼叫端傳入，需符合函式 contract；slow_window（int）由呼叫端傳入，需符合函式 contract；vwap_window（int）由呼叫端傳入，需符合函式 contract；rsi_window（int）由呼叫端傳入，需符合函式 contract；entry_z（float）由呼叫端傳入，需符合函式 contract；exit_z（float）由呼叫端傳入，需符合函式 contract；threshold（float）由呼叫端傳入，需符合函式 contract；vwap_regime_filter（bool）控制 VWAP long entry 是否要求 close >= regime SMA；vwap_regime_window（int）是 regime SMA 週期；allow_short（bool | None）由呼叫端傳入，需符合函式 contract
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
    fast_window: int = 20,
    slow_window: int = 200,
    vwap_window: int = 20,
    rsi_window: int = 14,
    entry_z: float = 1.5,
    exit_z: float = 0.25,
    threshold: float = 3.0,
    vwap_regime_filter: bool = False,
    vwap_regime_window: int = 50,
    volume_filter: bool = False,
    volume_window: int = 20,
    volume_multiplier: float = 1.2,
) -> Strategy:
    """
    用途與流程：建立 Phase 1 long-only 策略，必要時包上成交量濾網 wrapper。
    參數：strategy_name（str）由呼叫端傳入，需符合函式 contract；fast_window（int）由呼叫端傳入，需符合函式 contract；slow_window（int）由呼叫端傳入，需符合函式 contract；vwap_window（int）由呼叫端傳入，需符合函式 contract；rsi_window（int）由呼叫端傳入，需符合函式 contract；entry_z（float）由呼叫端傳入，需符合函式 contract；exit_z（float）由呼叫端傳入，需符合函式 contract；threshold（float）由呼叫端傳入，需符合函式 contract；vwap_regime_filter（bool）控制 VWAP long entry 是否要求 close >= regime SMA；vwap_regime_window（int）是 regime SMA 週期；volume_filter（bool）由呼叫端傳入，需符合函式 contract；volume_window（int）由呼叫端傳入，需符合函式 contract；volume_multiplier（float）由呼叫端傳入，需符合函式 contract
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
        volume_window=volume_window,
        volume_multiplier=volume_multiplier,
    )


def _build_sma_crossover(
    *,
    fast_window: int,
    slow_window: int,
    vwap_window: int,
    rsi_window: int,
    entry_z: float,
    exit_z: float,
    threshold: float,
    vwap_regime_filter: bool,
    vwap_regime_window: int,
    allow_short: bool | None,
) -> Strategy:
    """
    用途與流程：依 registry 或 reporting 需求組合內部資料結構，集中維護建構規則。
    參數：fast_window（int）由呼叫端傳入，需符合函式 contract；slow_window（int）由呼叫端傳入，需符合函式 contract；vwap_window（int）由呼叫端傳入，需符合函式 contract；rsi_window（int）由呼叫端傳入，需符合函式 contract；entry_z（float）由呼叫端傳入，需符合函式 contract；exit_z（float）由呼叫端傳入，需符合函式 contract；threshold（float）由呼叫端傳入，需符合函式 contract；vwap_regime_filter（bool）此策略不使用；vwap_regime_window（int）此策略不使用；allow_short（bool | None）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 Strategy；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    return SmaCrossoverStrategy(
        fast_window=fast_window,
        slow_window=slow_window,
        allow_short=False if allow_short is None else allow_short,
    )


def _build_vwap_reversion(
    *,
    fast_window: int,
    slow_window: int,
    vwap_window: int,
    rsi_window: int,
    entry_z: float,
    exit_z: float,
    threshold: float,
    vwap_regime_filter: bool,
    vwap_regime_window: int,
    allow_short: bool | None,
) -> Strategy:
    """
    用途與流程：依 registry 或 reporting 需求組合內部資料結構，集中維護建構規則。
    參數：fast_window（int）由呼叫端傳入，需符合函式 contract；slow_window（int）由呼叫端傳入，需符合函式 contract；vwap_window（int）由呼叫端傳入，需符合函式 contract；rsi_window（int）由呼叫端傳入，需符合函式 contract；entry_z（float）由呼叫端傳入，需符合函式 contract；exit_z（float）由呼叫端傳入，需符合函式 contract；threshold（float）由呼叫端傳入，需符合函式 contract；vwap_regime_filter（bool）控制 VWAP long entry 是否要求 close >= regime SMA；vwap_regime_window（int）是 regime SMA 週期；allow_short（bool | None）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 Strategy；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    kwargs: dict[str, object] = {
        "window": vwap_window,
        "entry_z": entry_z,
        "exit_z": exit_z,
        "regime_filter": vwap_regime_filter,
        "regime_window": vwap_regime_window,
    }
    if allow_short is not None:
        kwargs["allow_short"] = allow_short
    return VwapReversionStrategy(**kwargs)


def _build_confluence_score(
    *,
    fast_window: int,
    slow_window: int,
    vwap_window: int,
    rsi_window: int,
    entry_z: float,
    exit_z: float,
    threshold: float,
    vwap_regime_filter: bool,
    vwap_regime_window: int,
    allow_short: bool | None,
) -> Strategy:
    """
    用途與流程：依 registry 或 reporting 需求組合內部資料結構，集中維護建構規則。
    參數：fast_window（int）由呼叫端傳入，需符合函式 contract；slow_window（int）由呼叫端傳入，需符合函式 contract；vwap_window（int）由呼叫端傳入，需符合函式 contract；rsi_window（int）由呼叫端傳入，需符合函式 contract；entry_z（float）由呼叫端傳入，需符合函式 contract；exit_z（float）由呼叫端傳入，需符合函式 contract；threshold（float）由呼叫端傳入，需符合函式 contract；vwap_regime_filter（bool）此策略不使用；vwap_regime_window（int）此策略不使用；allow_short（bool | None）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 Strategy；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    kwargs: dict[str, object] = {
        "fast_window": fast_window,
        "slow_window": slow_window,
        "rsi_window": rsi_window,
        "vwap_window": vwap_window,
        "threshold": threshold,
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
