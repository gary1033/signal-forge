from __future__ import annotations

from signal_forge.cli.commands import (
    parse_hold_bars_list,
    run_entry_edge_command,
    run_fetch_data_command,
    run_phase_command,
)
from signal_forge.cli.parser import build_parser
from signal_forge.cli.strategy_options import (
    build_strategy_from_args,
    strategy_spec_from_args,
)
from signal_forge.data_fetch import fetch_market_data


def main(argv: list[str] | None = None) -> int:
    """
    用途與流程：SignalForge CLI 入口，解析 argv 後依 command 分派到對應 handler。
    參數：argv 是命令列參數清單；None 時由 argparse 讀取 process argv。
    回傳與錯誤：成功回傳 handler 的 int exit code；未知 command 會拋出 ValueError。
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "entry-edge":
        return run_entry_edge_command(args)
    if args.command == "phase":
        return run_phase_command(args)
    if args.command == "fetch-data":
        return run_fetch_data_command(args)
    raise ValueError(f"unsupported command {args.command}")


# Backward-compatible private aliases used by older tests and scripts.
_build_strategy = build_strategy_from_args
_parse_hold_bars_list = parse_hold_bars_list
_run_entry_edge = run_entry_edge_command
_run_fetch_data = run_fetch_data_command
_run_phase = run_phase_command
_strategy_spec = strategy_spec_from_args

__all__ = [
    "build_parser",
    "build_strategy_from_args",
    "fetch_market_data",
    "main",
    "parse_hold_bars_list",
    "run_entry_edge_command",
    "run_fetch_data_command",
    "run_phase_command",
    "strategy_spec_from_args",
]
