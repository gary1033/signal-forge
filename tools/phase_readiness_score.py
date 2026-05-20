from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# NOTE:
# - 這是 bounded autoresearch 使用的輕量 readiness metric。
# - 規則刻意維持簡單且 deterministic，只檢查必要關鍵字是否存在。
CHECKS: tuple[tuple[str, int, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "phase architecture note",
        10,
        ("docs/01-架構/SignalForge 架構總覽.md",),
        ("PhaseMode", "backtest", "live"),
    ),
    (
        "entry edge evaluator",
        10,
        ("src/signal_forge/backtesting/entry_edge.py",),
        ("EntryEdgeEvaluator", "EntryEdgeConfig", "profit_factor"),
    ),
    (
        "cli entry edge",
        10,
        ("src/signal_forge/cli",),
        ("entry-edge", "write_entry_edge_outputs"),
    ),
    (
        "phase mode types",
        10,
        ("src/signal_forge",),
        ("PhaseMode", "PhaseConfig"),
    ),
    (
        "phase runner",
        15,
        ("src/signal_forge",),
        ("PhaseRunner", "BacktestExecutionAdapter", "LiveExecutionAdapter"),
    ),
    (
        "live dry run safety",
        15,
        ("src/signal_forge", "tests"),
        ("dry_run", "order intent", "LIVE_DRY_RUN_ONLY"),
    ),
    (
        "phase cli",
        10,
        ("src/signal_forge/cli",),
        ("phase", "--mode", "live"),
    ),
    (
        "phase tests",
        15,
        ("tests",),
        ("PhaseRunner", "live", "backtest"),
    ),
    (
        "phase docs",
        10,
        ("README.md", "docs"),
        ("PhaseRunner", "BacktestExecutionAdapter", "LiveExecutionAdapter"),
    ),
    (
        "research notes",
        5,
        ("docs",),
        ("方法", "驗證", "下一步"),
    ),
)


def main() -> int:
    """
    用途與流程：作為命令列或工具入口，解析輸入、呼叫對應流程，最後回傳 process exit code。
    參數：無參數。
    回傳與錯誤：回傳 int；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    score = 0
    for _name, points, paths, needles in CHECKS:
        text = "\n".join(_read_path(path) for path in paths)
        if all(needle in text for needle in needles):
            score += points
    print(score)
    return 0


def _read_path(relative_path: str) -> str:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：relative_path（str）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    path = ROOT / relative_path
    if not path.exists():
        return ""
    if path.is_file():
        return path.read_text(encoding="utf-8", errors="ignore")
    return "\n".join(
        child.read_text(encoding="utf-8", errors="ignore")
        for child in path.rglob("*")
        if child.is_file() and child.suffix in {".py", ".md"}
    )


if __name__ == "__main__":
    raise SystemExit(main())
