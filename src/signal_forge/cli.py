from __future__ import annotations

import argparse
import os
from pathlib import Path

from signal_forge.data_fetch import fetch_market_data
from signal_forge.entry_edge import (
    EntryEdgeConfig,
    EntryEdgeEvaluator,
    run_entry_edge_hold_comparison,
)
from signal_forge.market_data import (
    MarketDataValidationError,
    load_bars_from_csv,
    validate_bars,
)
from signal_forge.phase import PhaseConfig, PhaseRunner, parse_phase_mode
from signal_forge.reporting import (
    write_entry_edge_comparison_outputs,
    write_entry_edge_outputs,
    write_phase_outputs,
)
from signal_forge.strategies import (
    SUPPORTED_STRATEGY_NAMES,
    build_phase1_strategy,
)
from signal_forge.strategy import Strategy


def main(argv: list[str] | None = None) -> int:
    """
    用途與流程：作為命令列或工具入口，解析輸入、呼叫對應流程，最後回傳 process exit code。
    參數：argv（list[str] | None）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 int；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    parser = argparse.ArgumentParser(prog="signal-forge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    entry_edge = subparsers.add_parser(
        "entry-edge",
        help="run first-phase pure-long fixed-hold entry edge validation",
    )
    entry_edge.add_argument("--csv", required=True, help="OHLCV CSV path")
    entry_edge.add_argument(
        "--strategy",
        choices=SUPPORTED_STRATEGY_NAMES,
        default="sma-crossover",
    )
    entry_edge.add_argument("--output-dir", default="reports/generated")
    entry_edge.add_argument("--run-name")
    entry_edge.add_argument("--hold-bars-per-day", type=int, default=1)
    entry_edge.add_argument(
        "--hold-bars-list",
        help="comma-separated positive fixed-hold bars for comparison reports",
    )
    entry_edge.add_argument("--initial-equity", type=float, default=10_000.0)
    entry_edge.add_argument("--commission-bps", type=float, default=1.0)
    entry_edge.add_argument("--slippage-bps", type=float, default=1.0)
    entry_edge.add_argument("--pass-profit-factor", type=float, default=1.2)
    entry_edge.add_argument("--fast-window", type=int, default=20)
    entry_edge.add_argument("--slow-window", type=int, default=200)
    entry_edge.add_argument("--vwap-window", type=int, default=20)
    entry_edge.add_argument(
        "--vwap-regime-filter",
        action="store_true",
        help="enable close >= SMA regime filter for VWAP long entries",
    )
    entry_edge.add_argument("--vwap-regime-window", type=int, default=50)
    entry_edge.add_argument("--rsi-window", type=int, default=14)
    entry_edge.add_argument("--entry-z", type=float, default=1.5)
    entry_edge.add_argument("--exit-z", type=float, default=0.25)
    entry_edge.add_argument("--threshold", type=float, default=3.0)
    entry_edge.add_argument(
        "--volume-filter",
        action="store_true",
        help="enable relative volume filter for long signals",
    )
    entry_edge.add_argument("--volume-window", type=int, default=20)
    entry_edge.add_argument("--volume-multiplier", type=float, default=1.2)

    phase = subparsers.add_parser(
        "phase",
        help="run phase mode through backtest or live dry-run adapters",
    )
    phase.add_argument("--csv", required=True, help="OHLCV CSV path")
    phase.add_argument(
        "--mode",
        choices=("backtest", "live"),
        default="backtest",
        help="phase mode; live is dry-run only",
    )
    phase.add_argument(
        "--strategy",
        choices=SUPPORTED_STRATEGY_NAMES,
        default="sma-crossover",
    )
    phase.add_argument("--hold-bars-per-day", type=int, default=1)
    phase.add_argument("--fast-window", type=int, default=20)
    phase.add_argument("--slow-window", type=int, default=200)
    phase.add_argument("--vwap-window", type=int, default=20)
    phase.add_argument(
        "--vwap-regime-filter",
        action="store_true",
        help="enable close >= SMA regime filter for VWAP long entries",
    )
    phase.add_argument("--vwap-regime-window", type=int, default=50)
    phase.add_argument("--rsi-window", type=int, default=14)
    phase.add_argument("--entry-z", type=float, default=1.5)
    phase.add_argument("--exit-z", type=float, default=0.25)
    phase.add_argument("--threshold", type=float, default=3.0)
    phase.add_argument(
        "--volume-filter",
        action="store_true",
        help="enable relative volume filter for long signals",
    )
    phase.add_argument("--volume-window", type=int, default=20)
    phase.add_argument("--volume-multiplier", type=float, default=1.2)
    phase.add_argument("--output-dir", default="reports/generated")
    phase.add_argument("--run-name")

    fetch_data = subparsers.add_parser(
        "fetch-data",
        help="download free daily OHLCV data into SignalForge CSV format",
    )
    fetch_data.add_argument("--market", choices=("twse", "us"), required=True)
    fetch_data.add_argument("--symbol", required=True)
    fetch_data.add_argument("--start", required=True, help="YYYY-MM-DD")
    fetch_data.add_argument("--end", required=True, help="YYYY-MM-DD")
    fetch_data.add_argument(
        "--output-root",
        default=".",
        help="repository root that contains data/raw and data/processed",
    )
    fetch_data.add_argument(
        "--stooq-api-key",
        default=None,
        help="optional free Stooq API key; also read from STOOQ_API_KEY",
    )

    args = parser.parse_args(argv)
    if args.command == "entry-edge":
        return _run_entry_edge(args)
    if args.command == "phase":
        return _run_phase(args)
    if args.command == "fetch-data":
        return _run_fetch_data(args)
    raise ValueError(f"unsupported command {args.command}")


def _run_entry_edge(args: argparse.Namespace) -> int:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：args（argparse.Namespace）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 int；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    bars = load_bars_from_csv(args.csv)
    data_validation = validate_bars(bars)
    strategy = _build_strategy(args)
    strategy_spec = _strategy_spec(args, strategy)
    config = EntryEdgeConfig(
        initial_equity=args.initial_equity,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
        hold_bars_per_day=args.hold_bars_per_day,
        pass_profit_factor=args.pass_profit_factor,
    )
    hold_bars_list = _parse_hold_bars_list(args.hold_bars_list)
    result = EntryEdgeEvaluator(config).run(strategy, bars)
    paths = write_entry_edge_outputs(
        result,
        Path(args.output_dir),
        run_name=args.run_name,
        data_validation=data_validation,
        strategy_spec=strategy_spec,
    )
    comparison_paths = None
    if hold_bars_list is not None:
        comparison = run_entry_edge_hold_comparison(
            strategy,
            bars,
            config,
            hold_bars_list,
        )
        comparison_paths = write_entry_edge_comparison_outputs(
            comparison,
            Path(args.output_dir),
            run_name=args.run_name,
            data_validation=data_validation,
            strategy_spec=strategy_spec,
        )

    profit_factor = (
        "Infinity"
        if result.profit_factor_status == "infinite"
        else "undefined"
        if result.profit_factor is None
        else f"{result.profit_factor:.3f}"
    )
    print(f"strategy={result.strategy_name}")
    print(f"decision={result.decision}")
    print(f"profit_factor={profit_factor}")
    print(f"trades={result.trade_count}")
    print(f"markdown={paths.markdown}")
    print(f"summary_json={paths.summary_json}")
    print(f"trade_log_csv={paths.trade_log_csv}")
    if comparison_paths is not None:
        print(f"hold_comparison_markdown={comparison_paths.markdown}")
        print(f"hold_comparison_json={comparison_paths.summary_json}")
    return 0


def _run_phase(args: argparse.Namespace) -> int:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：args（argparse.Namespace）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 int；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    bars = load_bars_from_csv(args.csv)
    strategy = _build_strategy(args)
    mode = parse_phase_mode(args.mode)
    result = PhaseRunner().run(
        PhaseConfig(
            mode=mode,
            strategy=args.strategy,
            csv_path=args.csv,
            hold_bars_per_day=args.hold_bars_per_day,
        ),
        strategy,
        bars,
    )
    paths = write_phase_outputs(
        result,
        Path(args.output_dir),
        run_name=args.run_name,
    )

    print(f"phase={result.mode}")
    print(f"adapter={result.adapter_name}")
    print(f"dry_run={result.dry_run}")
    if result.entry_edge_result is not None:
        print(f"entry_edge_trades={result.entry_edge_result.trade_count}")
        print(f"entry_edge_decision={result.entry_edge_result.decision}")
    else:
        intents = result.order_intents or []
        print(f"order_intents={len(intents)}")
        for index, intent in enumerate(intents, start=1):
            print(
                f"intent_{index}="
                f"{intent.timestamp},{intent.side},"
                f"target={intent.target_position},"
                f"dry_run={intent.dry_run},"
                f"submitted={intent.submitted}"
            )
    print(f"phase_markdown={paths.markdown}")
    print(f"phase_summary_json={paths.summary_json}")
    return 0


def _run_fetch_data(args: argparse.Namespace) -> int:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：args（argparse.Namespace）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 int；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    try:
        result = fetch_market_data(
            market=args.market,
            symbol=args.symbol,
            start=args.start,
            end=args.end,
            output_root=args.output_root,
            stooq_api_key=args.stooq_api_key or os.environ.get("STOOQ_API_KEY"),
        )
    except (MarketDataValidationError, ValueError) as exc:
        print(f"error={exc}")
        return 2
    print(f"market={result.market}")
    print(f"symbol={result.symbol}")
    print(f"start={result.start}")
    print(f"end={result.end}")
    print(f"rows={result.row_count}")
    print(f"raw_csv={result.raw_csv}")
    print(f"processed_csv={result.processed_csv}")
    print(f"manifest_json={result.manifest_json}")
    return 0


def _build_strategy(args: argparse.Namespace) -> Strategy:
    """
    用途與流程：依 CLI args 透過 Phase 1 factory 建立 long-only strategy，並傳入 VWAP regime 與成交量 wrapper 設定。
    參數：args（argparse.Namespace）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 Strategy；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
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


def _parse_hold_bars_list(value: str | None) -> tuple[int, ...] | None:
    """
    用途與流程：解析外部輸入文字或 CSV 欄位，轉成程式內部可驗證的型別與格式。
    參數：value（str | None）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 tuple[int, ...] | None；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    if value is None:
        return None
    parts = [part.strip() for part in value.split(",")]
    if not parts or any(part == "" for part in parts):
        raise ValueError("--hold-bars-list must be a comma-separated list of positive integers")
    try:
        hold_values = tuple(int(part) for part in parts)
    except ValueError as exc:
        raise ValueError(
            "--hold-bars-list must be a comma-separated list of positive integers"
        ) from exc
    if any(value <= 0 for value in hold_values):
        raise ValueError("--hold-bars-list values must be positive integers")
    return hold_values


def _strategy_spec(args: argparse.Namespace, strategy: Strategy) -> dict[str, str]:
    """
    用途與流程：整理 CLI strategy 來源、實作名稱、Phase 1 long-only 邊界與可選濾網設定，寫入 entry-edge reporting。
    參數：args（argparse.Namespace）由呼叫端傳入，需符合函式 contract；strategy（Strategy）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 dict[str, str]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
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


if __name__ == "__main__":
    raise SystemExit(main())
