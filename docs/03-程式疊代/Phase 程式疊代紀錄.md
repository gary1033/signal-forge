---
title: Phase 程式疊代紀錄
tags:
  - project/SignalForge
  - iteration
  - phase
status: active
updated: 2026-05-20
---

# Phase 程式疊代紀錄

這份紀錄是 SignalForge Phase 工作流的程式疊代摘要。詳細 automation 實驗表放在 [[../04-實驗記錄/Autoresearch 實驗記錄|Autoresearch 實驗記錄]]；這裡保留工程脈絡、已鎖住的 contract 與下一步開發方向。

## 疊代方法

每次 wakeup 只做一個聚焦改動：

```text
modify -> verify -> keep/discard -> log
```

固定 guard：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
cd C:\Projects\signal-forge
$env:PYTHONPATH = "src"
python tools\phase_readiness_score.py
python -m unittest discover -s tests
git diff --check
```

通過條件：readiness score `110`、unit tests 全部通過、`git diff --check` clean。

## 已完成主線

### 1. Phase mode 與 adapters

- 加入 `PhaseMode = backtest | live`。
- 加入 `PhaseConfig`，由 mode 推導 `dry_run`。
- 加入 `PhaseRunner`，依 mode 路由到 execution adapter。
- 加入 `BacktestExecutionAdapter` 與 `LiveExecutionAdapter`。
- `live` 模式拒絕 `dry_run=False`，並固定 dry-run only。

### 2. Backtest artifact contract

已鎖住的 deterministic outputs：

- Phase summary JSON。
- Phase markdown。
- Entry Edge summary JSON。
- Entry Edge markdown。
- Entry Edge trade log CSV。
- Entry Edge hold comparison JSON / Markdown。
- `*_signals.csv`。
- `*_trace_summary.json`。

這些輸出由 regression tests 與 validator 鎖住，避免 writer drift。

### 3. Signal digest 可稽核性

`*_signals.csv` 已逐步加入：

- `is_long_entry`
- `is_flatten`
- `position_change`
- `previous_target_position`
- `is_hold`
- `hold_side`

Validator 會檢查 timestamp、reason、fixed decimal、position delta、flags、hold side 與 trace summary 一致性。

### 4. Trace summary 可稽核性

`*_trace_summary.json` 已逐步加入：

- `schema_version`
- first / last timestamp
- start / end date
- reason counts
- entry / open / close / flatten counts
- flatten buckets
- hold long / short buckets
- min / max target position
- position bucket counts
- first / last reason
- `signal_digest_sha256`

Reporting 會用 `validate_signal_digest_csv(...)` 對 signals CSV 和 trace summary 做 cross-check。

### 5. Live dry-run safety

`live` 保持：

- 只產生 `OrderIntent`
- `dry_run=True`
- `submitted=False`
- `safety_note` 含 `LIVE_DRY_RUN_ONLY`
- 不接 broker
- 不讀 API key / credential
- 不送出真實訂單

任何碰到 `live` 的改動都必須先確認這些 invariant 沒被破壞。

### 6. Strategy OOP template

- 新增 `StrategyDecision` 與 hook-based `BarByBarStrategy`，由 template 統一 `generate_signals()` 的逐 bar 流程。
- 三個既有策略改為只實作 `prepare_context(...)` 與 `decide_bar(...)`，避免每個策略重複處理 signal 對齊與上一根 target 狀態。
- 新增 `strategies.registry`，CLI 透過 Phase 1 factory 建構 long-only 策略。
- `VolumeFilteredStrategy` 維持外層 wrapper，不併入策略本體。
- 新增 template、factory、三策略 regression tests，確保重構不改 target / reason / score contract。

### 7. Entry Edge 多持有期比較

- `entry-edge` 新增 `--hold-bars-list`，支援逗號分隔正整數，例如 `1,3,5,10`。
- 不提供 `--hold-bars-list` 時，原本單一 `--hold-bars-per-day` 的 markdown / summary JSON / trade CSV 輸出不變。
- 提供 `--hold-bars-list` 時，會保留原本單一 hold report，另外輸出 `<run-name>_hold_comparison.json` 與 `<run-name>_hold_comparison.md`。
- comparison row 固定包含 hold bars、decision、Profit Factor status/value、trade count、win rate、average net PnL、max drawdown、ignored/unclosed/overlap counts 與 failure reason。
- 這個功能是為了比較同一策略在不同固定持有期下的 entry-edge 稽核結果，不自動推薦最佳持有期，也不改 SMA Crossover 的 `fast_sma > slow_sma` 訊號語意。

## 重要 commit 節點

| Commit | 類型 | 摘要 |
|---|---|---|
| `fd8dcfd` | experiment | add free daily data fetch CLI |
| `8206e19` | docs | record trace summary first/last reason |
| `cc6e50b` | experiment | trace summary adds first/last reason |
| `e02e79f` | experiment | csv validator cross-checks min/max target_position |
| `d3f59e5` | docs | add strategy notes sync rule |

## 目前下一步

- 只擴充 deterministic、test-covered 的 backtest artifacts。
- 優先補強 trace summary 或 validation，不做績效最佳化。
- SMA Crossover 可先用 `--hold-bars-list` 比較一日、三日、五日、十日固定持有期，再決定是否進入完整趨勢持有 / 出場規則設計。
- OOP template 已完成後，下一步仍要分開討論 SMA Crossover、VWAP Reversion、Confluence Score 的策略語意修改。
- 若新增策略或改策略邏輯，同步更新 [[../策略筆記/策略筆記索引|策略筆記]]。
- push 前先把 Obsidian 筆記同步進 repo `docs/`。
