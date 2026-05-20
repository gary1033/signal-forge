from __future__ import annotations

import argparse
import os
from pathlib import Path

from signal_forge.cli.strategy_options import (
    build_strategy_from_args,
    strategy_spec_from_args,
)
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


def run_entry_edge_command(args: argparse.Namespace) -> int:
    """
    用途與流程：執行 entry-edge CLI 指令，載入資料、建立策略、跑單一持有期與可選多持有期比較並寫出 artifacts。
    參數：args 是 argparse 解析後的 command namespace。
    回傳與錯誤：成功回傳 0；資料或策略錯誤會由底層函式拋出 ValueError/MarketDataValidationError。
    """
    bars = load_bars_from_csv(args.csv)
    data_validation = validate_bars(bars)
    strategy = build_strategy_from_args(args)
    strategy_spec = strategy_spec_from_args(args, strategy)
    config = EntryEdgeConfig(
        initial_equity=args.initial_equity,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
        hold_bars_per_day=args.hold_bars_per_day,
        pass_profit_factor=args.pass_profit_factor,
    )
    hold_bars_list = parse_hold_bars_list(args.hold_bars_list)
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


def run_phase_command(args: argparse.Namespace) -> int:
    """
    用途與流程：執行 phase CLI 指令，依 mode 路由到 backtest 或 live dry-run 並寫出 Phase artifacts。
    參數：args 是 argparse 解析後的 command namespace。
    回傳與錯誤：成功回傳 0；mode、資料或輸出 contract 不合法時由底層函式拋出 ValueError。
    """
    bars = load_bars_from_csv(args.csv)
    strategy = build_strategy_from_args(args)
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


def run_fetch_data_command(args: argparse.Namespace) -> int:
    """
    用途與流程：執行 fetch-data CLI 指令，下載免費日線資料並寫入 raw/processed CSV 與 manifest。
    參數：args 是 argparse 解析後的 command namespace。
    回傳與錯誤：成功回傳 0；市場資料驗證或參數錯誤會被轉成 error=... 並回傳 2。
    """
    try:
        from signal_forge.cli import fetch_market_data

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


def parse_hold_bars_list(value: str | None) -> tuple[int, ...] | None:
    """
    用途與流程：解析 --hold-bars-list 的逗號分隔文字，轉成正整數 tuple 供 comparison runner 使用。
    參數：value 是 CLI 字串或 None；None 表示不啟用多持有期比較。
    回傳與錯誤：回傳 tuple[int, ...] 或 None；空欄位、非整數或非正數會拋出 ValueError。
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
