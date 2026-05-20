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
- 若新增策略或改策略邏輯，同步更新 [[../策略筆記/策略筆記索引|策略筆記]]。
- push 前先把 Obsidian 筆記同步進 repo `docs/`。
