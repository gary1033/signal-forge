---
title: Autoresearch 實驗記錄
tags:
  - project/SignalForge
  - experiment
  - autoresearch
status: active
updated: 2026-05-20
---

# Autoresearch 實驗記錄

這份筆記彙整 SignalForge bounded autoresearch 的執行結果。完整逐列 audit trail 原本來自 `phase-iteration-log.md` 與 `phase-autoresearch-results.md`，現在整理為實驗記錄資料夾的一份 canonical 筆記。

## 實驗契約

- 主線：回測可驗證性。
- 方法：`modify -> verify -> keep/discard -> log`。
- 每次 wakeup 只做一個聚焦改動。
- 不做策略績效最佳化。
- 不新增 broker。
- 不新增 API key / credential 讀取。
- 不新增真實下單介面。
- 不碰 live 送單能力。

## 固定驗證

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
cd C:\Projects\signal-forge
$env:PYTHONPATH = "src"
python tools\phase_readiness_score.py
python -m unittest discover -s tests
git diff --check
```

目前目標：readiness score 維持 `110`，unit tests 全部通過。

## 實驗結果摘要

2026-05-19 到 2026-05-20 的 autoresearch 主線，主要把 Phase 從「可以切 mode」推進到「backtest 與 live 的輸出 contract 都能被 regression tests 鎖住」。

已完成類別：

- Phase mode / config / runner / adapters。
- Live dry-run safety marker：`LIVE_DRY_RUN_ONLY`。
- Phase summary JSON schema 與 exact-text contract。
- Phase markdown exact-text contract。
- Entry Edge outputs deterministic contract。
- Signal digest CSV：entry、flatten、hold、position change、hold side。
- Trace summary JSON：schema version、counts、timestamp、reason、position buckets、CSV hash。
- Cross-check validator：signals CSV 與 trace summary 完全對齊。
- Strategy OOP template：`BarByBarStrategy`、`StrategyDecision`、strategy registry / factory、三策略 regression tests。

## 近期實驗表

| 時間 | 目標 | 結果 | 決策 |
|---|---|---|---|
| 2026-05-19 16:27 | 文件 encoding 與 readiness needle 整理 | 110；tests OK | keep |
| 2026-05-19 17:13 | Backtest Phase report golden regression | 110；tests OK | keep |
| 2026-05-19 18:57 | Live Phase report contract regression | 110；tests OK | keep |
| 2026-05-19 20:14 | Backtest trace visibility：`*_signals.csv` | 110；tests OK | keep |
| 2026-05-19 21:42 | Backtest `*_trace_summary.json` | 110；tests OK | keep |
| 2026-05-20 03:36 | Cross-check backtest artifacts | 110；tests OK | keep |
| 2026-05-20 05:22 | Backtest timestamp ISO-8601 稽核 | 110；tests OK | keep |
| 2026-05-20 08:20 | Trace summary 加入 `signal_digest_sha256` | 110；tests OK | keep |
| 2026-05-20 09:22 | Phase markdown 顯示 trace schema 與 position buckets | 110；tests OK | keep |
| 2026-05-20 10:26 | Trace summary first/last reason 稽核 | 110；tests OK | keep |
| 2026-05-20 22:50 | OOP strategy template 與 registry | 83 tests OK | keep |

## 最新已知狀態

- Branch：`main`
- Remote：`origin/main`
- Readiness score：`110`
- Live mode：dry-run order intent only。
- 最新已知測試基線：`83 tests OK`，以當輪實際測試輸出為準。

## 實驗下一步

- 增加 `min_previous_target_position` / `max_previous_target_position` 類型欄位，讓 trace summary 的前一根部位範圍更好稽核。
- 繼續補強 Phase markdown 的人工可讀性，但必須有 exact-text regression test。
- OOP template 已鎖住後，三種策略的下一步修改應分開討論與測試，避免混入模板重構。
- 若要做策略研究實驗，結果放入 `04-實驗記錄/`，策略語意同步到 `策略筆記/`。
