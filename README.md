# SignalForge

SignalForge is a research-oriented trading signal sandbox. It supports a Phase workflow that can switch between:

- `backtest`: prioritized for stability, repeatability, and verification.
- `live`: DRY-RUN ONLY until backtests are stable (no broker, no API keys, no real orders).

## Live safety (must hold)

In `live` mode, the system must only produce order intent (dry-run) artifacts:

- `dry_run=True`
- `submitted=False`
- no broker connections
- no credential loading
- no real order submission

## Quickstart (PowerShell)

```powershell
# Metric
python tools\phase_readiness_score.py

# Guard
$env:PYTHONPATH='src'
python -m unittest discover -s tests
git diff --check

# Phase examples
python -m signal_forge.cli phase `
  --csv data\sample\phase1_demo_ohlcv.csv `
  --mode backtest `
  --strategy sma-crossover `
  --fast-window 2 `
  --slow-window 3 `
  --output-dir reports\generated `
  --run-name phase-backtest-demo

python -m signal_forge.cli phase `
  --csv data\sample\phase1_demo_ohlcv.csv `
  --mode live `
  --strategy sma-crossover `
  --fast-window 2 `
  --slow-window 3 `
  --output-dir reports\generated `
  --run-name phase-live-demo
```

## Phase concepts

- `PhaseConfig`: shared config for `backtest` and `live` (live enforces dry-run).
- `PhaseRunner`: routes to an execution adapter by mode.
  - `BacktestExecutionAdapter`: produces verifiable backtest results via `EntryEdgeEvaluator`.
  - `LiveExecutionAdapter`: produces only dry-run `OrderIntent` artifacts (not submitted).

## Autoresearch docs

- `docs/phase-roadmap.md`
- `docs/phase-iteration-log.md`
- `docs/phase-autoresearch-results.md`
