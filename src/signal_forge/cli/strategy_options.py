from __future__ import annotations

import argparse

from signal_forge.strategies import STRATEGY_PARAMETER_DEFAULTS, build_phase1_strategy
from signal_forge.strategies.volume_filter import VolumeFilteredStrategy
from signal_forge.strategy import Strategy


def add_strategy_arguments(parser: argparse.ArgumentParser) -> None:
    """
    用途與流程：把 entry-edge 與 phase 共用的策略參數集中掛到 argparse parser，避免兩個 command 重複維護。
    參數：parser 是目標 argparse.ArgumentParser，呼叫後會被加入策略名稱、SMA、VWAP、RSI、volume filter 等 options。
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


def build_strategy_from_args(args: argparse.Namespace) -> Strategy:
    """
    用途與流程：依 CLI args 透過 Phase 1 factory 建立 long-only strategy，並套用 VWAP regime 與成交量 wrapper 設定。
    參數：args 是 argparse 解析出的命名空間，需包含 add_strategy_arguments 建立的欄位。
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
        volume_filter=getattr(args, "volume_filter", False),
        volume_window=getattr(args, "volume_window", None),
        volume_multiplier=getattr(args, "volume_multiplier", None),
    )


def strategy_spec_from_args(args: argparse.Namespace, strategy: Strategy) -> dict[str, str]:
    """
    用途與流程：整理 CLI strategy 來源、實作名稱、Phase 1 long-only 邊界與可選濾網設定，寫入 entry-edge reporting。
    參數：args 是 CLI 命名空間；strategy 是已建立的策略或 wrapper 實例。
    回傳與錯誤：回傳 deterministic dict[str, str]；不讀取檔案或外部狀態。
    """
    defaults = STRATEGY_PARAMETER_DEFAULTS[args.strategy]
    volume_window = _arg_or_default(
        args,
        "volume_window",
        VolumeFilteredStrategy.volume_window,
    )
    volume_multiplier = _arg_or_default(
        args,
        "volume_multiplier",
        VolumeFilteredStrategy.volume_multiplier,
    )
    return {
        "source_strategy": args.strategy,
        "strategy_impl": strategy.name,
        "entry_side": "long_only",
        "entry_event": "bar close signal where target_position flips from <=0 to >0",
        "excluded_in_phase1": "short/stops/take-profit/filters/scale-in/parameter-optimization",
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
    }


def _arg_or_default(
    args: argparse.Namespace,
    field_name: str,
    default_value: int | float,
) -> int | float:
    """
    用途與流程：讀取 argparse 欄位，將 None 視為「使用策略或 wrapper default」，供 reporting spec 寫出實際生效值。
    參數：args 是 CLI 命名空間；field_name 是欲讀取的參數名稱；default_value 是該欄位未輸入時的有效預設值。
    回傳與錯誤：回傳 int 或 float；若欄位不存在也會回傳 default_value，不拋出錯誤。
    """
    value = getattr(args, field_name, None)
    return default_value if value is None else value
