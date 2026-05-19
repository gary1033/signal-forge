# SignalForge

SignalForge 是研究導向的交易訊號沙盒，用來把 TradingView / Pine Script 的策略想法拆成可驗證的 Python 研究流程。現在的主線是 Phase 工作流，可以在兩種模式之間切換：

- `backtest`：優先穩定性、可重複性與機械驗證。
- `live`：回測穩定前只允許 dry-run，不接 broker、不讀 API key、不送真實訂單。

## Live 安全邊界

`live` 模式目前只能產生 order intent，也就是乾跑用的下單意圖紀錄。以下條件必須永遠成立：

- `dry_run=True`
- `submitted=False`
- 不建立 broker 連線
- 不讀取 credential
- 不送出真實訂單

## 快速執行（PowerShell）

```powershell
# readiness metric
python tools\phase_readiness_score.py

# guard
$env:PYTHONPATH='src'
python -m unittest discover -s tests
git diff --check

# Phase backtest 範例
python -m signal_forge.cli phase `
  --csv data\sample\phase1_demo_ohlcv.csv `
  --mode backtest `
  --strategy sma-crossover `
  --fast-window 2 `
  --slow-window 3 `
  --output-dir reports\generated `
  --run-name phase-backtest-demo

# Phase live dry-run 範例
python -m signal_forge.cli phase `
  --csv data\sample\phase1_demo_ohlcv.csv `
  --mode live `
  --strategy sma-crossover `
  --fast-window 2 `
  --slow-window 3 `
  --output-dir reports\generated `
  --run-name phase-live-demo
```

## Phase 核心概念

- `PhaseConfig`：`backtest` / `live` 共用設定；`dry_run` 由 mode 推導，避免 CLI 與核心設定各自維護一份語意。
- `PhaseRunner`：依照 mode 路由到對應 execution adapter。
  - `BacktestExecutionAdapter`：透過 `EntryEdgeEvaluator` 產生可驗證的回測結果。
  - `LiveExecutionAdapter`：只產生 dry-run `OrderIntent`，不送出訂單。
- `OrderIntent`：live dry-run 的意圖紀錄；`safety_note` 會帶有 `LIVE_DRY_RUN_ONLY` 方便稽核。

## Autoresearch 筆記

- `docs/phase-roadmap.md`
- `docs/phase-iteration-log.md`
- `docs/phase-autoresearch-results.md`
