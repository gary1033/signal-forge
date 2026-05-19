from __future__ import annotations

import argparse
from pathlib import Path

from signal_forge.entry_edge import EntryEdgeConfig, EntryEdgeEvaluator
from signal_forge.market_data import load_bars_from_csv, validate_bars
from signal_forge.phase import PhaseConfig, PhaseRunner, parse_phase_mode
from signal_forge.reporting import write_entry_edge_outputs, write_phase_outputs
from signal_forge.strategies import (
    ConfluenceScoreStrategy,
    SmaCrossoverStrategy,
    VwapReversionStrategy,
)
from signal_forge.strategy import Strategy


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="signal-forge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    entry_edge = subparsers.add_parser(
        "entry-edge",
        help="run first-phase pure-long fixed-hold entry edge validation",
    )
    entry_edge.add_argument("--csv", required=True, help="OHLCV CSV path")
    entry_edge.add_argument(
        "--strategy",
        choices=("sma-crossover", "vwap-reversion", "confluence-score"),
        default="sma-crossover",
    )
    entry_edge.add_argument("--output-dir", default="reports/generated")
    entry_edge.add_argument("--run-name")
    entry_edge.add_argument("--hold-bars-per-day", type=int, default=1)
    entry_edge.add_argument("--initial-equity", type=float, default=10_000.0)
    entry_edge.add_argument("--commission-bps", type=float, default=1.0)
    entry_edge.add_argument("--slippage-bps", type=float, default=1.0)
    entry_edge.add_argument("--pass-profit-factor", type=float, default=1.2)
    entry_edge.add_argument("--fast-window", type=int, default=20)
    entry_edge.add_argument("--slow-window", type=int, default=200)
    entry_edge.add_argument("--vwap-window", type=int, default=20)
    entry_edge.add_argument("--rsi-window", type=int, default=14)
    entry_edge.add_argument("--entry-z", type=float, default=1.5)
    entry_edge.add_argument("--exit-z", type=float, default=0.25)
    entry_edge.add_argument("--threshold", type=float, default=3.0)

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
        choices=("sma-crossover", "vwap-reversion", "confluence-score"),
        default="sma-crossover",
    )
    phase.add_argument("--hold-bars-per-day", type=int, default=1)
    phase.add_argument("--fast-window", type=int, default=20)
    phase.add_argument("--slow-window", type=int, default=200)
    phase.add_argument("--vwap-window", type=int, default=20)
    phase.add_argument("--rsi-window", type=int, default=14)
    phase.add_argument("--entry-z", type=float, default=1.5)
    phase.add_argument("--exit-z", type=float, default=0.25)
    phase.add_argument("--threshold", type=float, default=3.0)
    phase.add_argument("--output-dir", default="reports/generated")
    phase.add_argument("--run-name")

    args = parser.parse_args(argv)
    if args.command == "entry-edge":
        return _run_entry_edge(args)
    if args.command == "phase":
        return _run_phase(args)
    raise ValueError(f"unsupported command {args.command}")


def _run_entry_edge(args: argparse.Namespace) -> int:
    bars = load_bars_from_csv(args.csv)
    data_validation = validate_bars(bars)
    strategy = _build_strategy(args)
    config = EntryEdgeConfig(
        initial_equity=args.initial_equity,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
        hold_bars_per_day=args.hold_bars_per_day,
        pass_profit_factor=args.pass_profit_factor,
    )
    result = EntryEdgeEvaluator(config).run(strategy, bars)
    paths = write_entry_edge_outputs(
        result,
        Path(args.output_dir),
        run_name=args.run_name,
        data_validation=data_validation,
        strategy_spec=_strategy_spec(args, strategy),
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
    return 0


def _run_phase(args: argparse.Namespace) -> int:
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


def _build_strategy(args: argparse.Namespace) -> Strategy:
    if args.strategy == "sma-crossover":
        return SmaCrossoverStrategy(
            fast_window=args.fast_window,
            slow_window=args.slow_window,
            allow_short=False,
        )
    if args.strategy == "vwap-reversion":
        return VwapReversionStrategy(
            window=args.vwap_window,
            entry_z=args.entry_z,
            exit_z=args.exit_z,
            allow_short=False,
        )
    if args.strategy == "confluence-score":
        return ConfluenceScoreStrategy(
            fast_window=args.fast_window,
            slow_window=args.slow_window,
            rsi_window=args.rsi_window,
            vwap_window=args.vwap_window,
            threshold=args.threshold,
            allow_short=False,
        )
    raise ValueError(f"unsupported strategy {args.strategy}")


def _strategy_spec(args: argparse.Namespace, strategy: Strategy) -> dict[str, str]:
    return {
        "source_strategy": args.strategy,
        "strategy_impl": strategy.name,
        "entry_side": "long_only",
        "entry_event": "bar close signal where target_position flips from <=0 to >0",
        "excluded_in_phase1": "short/stops/take-profit/filters/scale-in/parameter-optimization",
        "repaint_handling": "phase 1 accepts signals confirmed on closed bars only",
    }


if __name__ == "__main__":
    raise SystemExit(main())
