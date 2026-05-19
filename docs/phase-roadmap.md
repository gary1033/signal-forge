# SignalForge Phase Roadmap

This roadmap drives bounded autoresearch. The goal is to keep Phase readiness high while guaranteeing a safe split between `backtest` and `live`.

## Direction

- `backtest`: prioritize stability and verifiability (repeatable runs, fixed output contracts).
- `live`: DRY-RUN ONLY until backtests are stable (order intent only; no broker/API keys/real orders).

## Types and architecture (keyword: PhaseMode)

- `PhaseMode`: `backtest` / `live`
- `PhaseConfig`: shared config (live enforces dry-run)
- `PhaseRunner`: routes execution by mode
  - `BacktestExecutionAdapter`: backtest execution path
  - `LiveExecutionAdapter`: live dry-run path (order intent only)
- `OrderIntent`: includes `LIVE_DRY_RUN_ONLY` marker in `safety_note` for stable auditing across OS/encodings

## Milestones

Done (2026-05-19):
1. Phase mode + config (`PhaseMode`, `PhaseConfig`) with live dry-run guard
2. Phase runner + adapters (`PhaseRunner`, `BacktestExecutionAdapter`, `LiveExecutionAdapter`)
3. Live adapter stub: dry-run `OrderIntent` only (not submitted)
4. CLI: `phase --mode backtest|live` (live is dry-run)
5. Phase report: includes mode/adapter/dry-run metadata
6. Failure modes: unknown mode / hold period / bar validation + tests
7. Docs: Phase workflow documented for PowerShell
8. Backtest regression: Phase report contract test (fixed bars -> stable summary/markdown)
9. Phase report: validate summary JSON schema (contract guardrail)
10. Reporting: stable JSON key ordering for deterministic diffs
11. Backtest portability: Entry Edge report + CLI strategy spec ASCII-only (Windows-friendly)
12. Backtest determinism: Phase summary JSON text contract (sorted keys + newline)
13. Backtest determinism: Phase markdown text contract (exact text + trailing newline)
14. Phase report: enforce cross-field invariants (live dry-run only; backtest requires entry_edge)
15. Live determinism: Phase summary + markdown text contract (order intent regression)
16. Backtest portability: ASCII-only warning + sample risk text (avoid encoding-dependent garbling)
17. Backtest determinism: Entry Edge outputs contract (summary JSON + markdown + trade log CSV)
18. Backtest portability: Entry Edge failure_reason is ASCII-only and deterministic
19. CLI correctness: backtest uses `dry_run=False`; live uses `dry_run=True` in `PhaseConfig`
20. Backtest trace visibility: Phase report emits deterministic `*_signals.csv` (per-bar signal digest)

Next candidates (keep live safety unchanged):
- Coverage/trace visibility without any real trading integration
