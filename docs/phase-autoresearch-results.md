# Phase Autoresearch Results

This document summarizes the current Phase readiness state, verification commands, and the per-wakeup run log.

## Current status

- Branch: `main`
- Remote: `origin/main`
- Readiness score: `110`
- Guard: unit tests pass
- Live mode: dry-run order intent only (`dry_run=True`, `submitted=False`)

## Verification commands (PowerShell)

```powershell
python tools\phase_readiness_score.py
$env:PYTHONPATH='src'; python -m unittest discover -s tests
git diff --check
```

## Automation Run Log

| Wakeup (Asia/Taipei) | Milestone | Metric | Guard | Decision | Commit / Push | Notes |
|---|---|---|---|---|---|---|
| 2026-05-19 16:27 | Docs encoding + readiness needle | 110 -> 110 | pass | keep | see `git log -1 --oneline` | includes `50ade1b` |
| 2026-05-19 16:42 | Stable live dry-run marker (`LIVE_DRY_RUN_ONLY`) | 110 -> 110 | pass | keep | see `git log -1 --oneline` (pushed to `origin/main`) | ASCII marker for safety/audit invariants |
| 2026-05-19 16:57 | ASCII-only `OrderIntent.safety_note` invariants | 110 -> 110 | pass | keep | see `git log -1 --oneline` (pushed to `origin/main`) | Avoid terminal/encoding-dependent safety text |
| 2026-05-19 17:13 | Backtest Phase report contract regression test | 110 -> 110 | pass | keep | see `git log -1 --oneline` (pushed to `origin/main`) | Fixed bars -> stable summary/markdown invariants |
| 2026-05-19 17:27 | Phase report summary schema validation | 110 -> 110 | pass | keep | see `git log -1 --oneline` (pushed to `origin/main`) | Enforce deterministic Phase summary JSON contract |
| 2026-05-19 17:42 | Reporting: stable JSON key ordering (`sort_keys=True`) | 110 -> 110 | pass | keep | `3d99839` (pushed) | Deterministic diffs for report JSON |
| 2026-05-19 18:02 | Entry Edge report ASCII-only labels | 110 -> 110 | pass | keep | `d54d9e7` (pushed) | Windows-friendly backtest report output |
| 2026-05-19 18:12 | Backtest determinism: Phase summary JSON text contract | 110 -> 110 | pass | keep | `c69428c` (pushed) | Assert exact JSON formatting (sorted keys + newline) |
| 2026-05-19 18:28 | Backtest determinism: Phase markdown text contract | 110 -> 110 | pass | keep | `773e52b` (pushed) | Assert exact markdown output (stable lines + trailing newline) |
| 2026-05-19 18:42 | Phase summary: enforce live/backtest invariants | 110 -> 110 | pass | keep | see `git log -1 --oneline` (pushed) | Live: dry-run + submitted=False only; Backtest: requires entry_edge |
| 2026-05-19 18:57 | Live determinism: Phase report contract regression test | 110 -> 110 | pass | keep | `55d37ac` (pushed) | Assert exact live summary/markdown text (safe order intent only) |
| 2026-05-19 19:13 | Backtest portability: ASCII-only warning + sample risk | 110 -> 110 | pass | keep | see `git log -1 --oneline` (pushed) | Avoid Windows terminal encoding garbling in report text |
