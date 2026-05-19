from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# NOTE:
# - 這是 bounded autoresearch 使用的輕量 readiness metric。
# - 規則刻意維持簡單且 deterministic，只檢查必要關鍵字是否存在。
CHECKS: tuple[tuple[str, int, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "phase roadmap",
        10,
        ("docs/phase-roadmap.md",),
        ("PhaseMode", "backtest", "live"),
    ),
    (
        "entry edge evaluator",
        10,
        ("src/signal_forge/entry_edge.py",),
        ("EntryEdgeEvaluator", "EntryEdgeConfig", "profit_factor"),
    ),
    (
        "cli entry edge",
        10,
        ("src/signal_forge/cli.py",),
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
        ("src/signal_forge/cli.py",),
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
    score = 0
    for _name, points, paths, needles in CHECKS:
        text = "\n".join(_read_path(path) for path in paths)
        if all(needle in text for needle in needles):
            score += points
    print(score)
    return 0


def _read_path(relative_path: str) -> str:
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
