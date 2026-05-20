from __future__ import annotations

import argparse

from signal_forge.strategies import build_phase1_strategy
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
    parser.add_argument("--fast-window", type=int, default=20)
    parser.add_argument("--slow-window", type=int, default=200)
    parser.add_argument("--vwap-window", type=int, default=20)
    parser.add_argument(
        "--vwap-regime-filter",
        action="store_true",
        help="enable close >= SMA regime filter for VWAP long entries",
    )
    parser.add_argument("--vwap-regime-window", type=int, default=50)
    parser.add_argument("--rsi-window", type=int, default=14)
    parser.add_argument("--entry-z", type=float, default=1.5)
    parser.add_argument("--exit-z", type=float, default=0.25)
    parser.add_argument("--threshold", type=float, default=3.0)
    parser.add_argument(
        "--volume-filter",
        action="store_true",
        help="enable relative volume filter for long signals",
    )
    parser.add_argument("--volume-window", type=int, default=20)
    parser.add_argument("--volume-multiplier", type=float, default=1.2)


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
        vwap_regime_window=getattr(args, "vwap_regime_window", 50),
        volume_filter=getattr(args, "volume_filter", False),
        volume_window=getattr(args, "volume_window", 20),
        volume_multiplier=getattr(args, "volume_multiplier", 1.2),
    )


def strategy_spec_from_args(args: argparse.Namespace, strategy: Strategy) -> dict[str, str]:
    """
    用途與流程：整理 CLI strategy 來源、實作名稱、Phase 1 long-only 邊界與可選濾網設定，寫入 entry-edge reporting。
    參數：args 是 CLI 命名空間；strategy 是已建立的策略或 wrapper 實例。
    回傳與錯誤：回傳 deterministic dict[str, str]；不讀取檔案或外部狀態。
    """
    return {
        "source_strategy": args.strategy,
        "strategy_impl": strategy.name,
        "entry_side": "long_only",
        "entry_event": "bar close signal where target_position flips from <=0 to >0",
        "excluded_in_phase1": "short/stops/take-profit/filters/scale-in/parameter-optimization",
        "repaint_handling": "phase 1 accepts signals confirmed on closed bars only",
        "volume_filter": "enabled" if getattr(args, "volume_filter", False) else "disabled",
        "volume_window": str(getattr(args, "volume_window", 20)),
        "volume_multiplier": f"{getattr(args, 'volume_multiplier', 1.2):.2f}",
        "volume_rule": "volume >= sma(volume, volume_window) * volume_multiplier",
        "vwap_regime_filter": "enabled"
        if getattr(args, "vwap_regime_filter", False)
        else "disabled",
        "vwap_regime_window": str(getattr(args, "vwap_regime_window", 50)),
        "vwap_regime_rule": "long entries require close >= sma(close, vwap_regime_window) when enabled",
    }
