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
    allow_short: bool | None = None,
) -> Strategy:
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
    volume_filter: bool = False,
    volume_window: int = 20,
    volume_multiplier: float = 1.2,
) -> Strategy:
    strategy = build_strategy(
        strategy_name,
        fast_window=fast_window,
        slow_window=slow_window,
        vwap_window=vwap_window,
        rsi_window=rsi_window,
        entry_z=entry_z,
        exit_z=exit_z,
        threshold=threshold,
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
    allow_short: bool | None,
) -> Strategy:
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
    allow_short: bool | None,
) -> Strategy:
    kwargs: dict[str, object] = {
        "window": vwap_window,
        "entry_z": entry_z,
        "exit_z": exit_z,
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
    allow_short: bool | None,
) -> Strategy:
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
    return strategy_name.strip().lower()


STRATEGY_REGISTRY: dict[str, StrategyBuilder] = {
    "sma-crossover": _build_sma_crossover,
    "vwap-reversion": _build_vwap_reversion,
    "confluence-score": _build_confluence_score,
}
