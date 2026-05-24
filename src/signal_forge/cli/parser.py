from __future__ import annotations

import argparse

from signal_forge.cli.strategy_options import add_strategy_arguments


def build_parser() -> argparse.ArgumentParser:
    """
    用途與流程：建立 signal-forge CLI 的 argparse parser，集中定義 fetch-data、entry-edge 與 phase 指令。
    參數：無參數。
    回傳與錯誤：回傳 argparse.ArgumentParser；只建立 parser，不解析 argv 也不執行命令。
    """
    parser = argparse.ArgumentParser(prog="signal-forge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    entry_edge = subparsers.add_parser(
        "entry-edge",
        help="run first-phase pure-long fixed-hold entry edge validation",
    )
    entry_edge.add_argument("--csv", required=True, help="OHLCV CSV path")
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
    entry_edge.add_argument(
        "--transaction-tax-bps",
        type=float,
        default=0.0,
        help="sell-side transaction tax in basis points; default keeps legacy reports unchanged",
    )
    entry_edge.add_argument("--pass-profit-factor", type=float, default=1.2)
    add_strategy_arguments(entry_edge)

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
    phase.add_argument("--hold-bars-per-day", type=int, default=1)
    add_strategy_arguments(phase)
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
    return parser
