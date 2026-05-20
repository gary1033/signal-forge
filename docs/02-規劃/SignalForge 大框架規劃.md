---
title: SignalForge 大框架規劃
tags:
  - project/SignalForge
  - planning
  - trading/research
status: active
updated: 2026-05-20
aliases:
  - SignalForge 規劃
  - SignalForge Roadmap
---

# SignalForge 大框架規劃

SignalForge 的大方向是把交易想法整理成可驗證研究流程，而不是直接做策略績效最佳化或真實下單。第一階段主軸是資料、策略蒸餾、entry-edge 回測與 deterministic artifacts；`live` 只保留 dry-run intent 作為未來介面雛形。

## 方向原則

- `backtest`：優先穩定、可重複、可驗證；輸出要有固定 contract，方便 regression test。
- `live`：回測穩定前只允許 dry-run；只產生 order intent，不接 broker、不讀 API key、不送真實訂單。
- 策略研究：先拆清楚訊號假設，再做可重複回測，不先做參數最佳化。
- 文件管理：Obsidian 是筆記主來源；push 前同步到 repo `docs/`。

## Phase 分期

### Phase 1：策略蒸餾與 entry-edge

目標是把 TradingView 或其他策略想法拆成可測的 long-only entry signal。

固定評估規則：

- 訊號於 bar close 後成立。
- 下一根 bar open 進場。
- 固定持有 `hold_bars_per_day`。
- exit bar close 離場。
- 只測純多進場；short、停損、停利、加碼、完整出場先記錄但不納入第一階段。
- 第一階段篩選門檻：`Profit Factor > 1.2`。

### Phase 2：多日持倉與出場規則

進入 Phase 2 前，要先回答策略到底是在測短期隔日 edge，還是在測中長期持有。Phase 2 候選方向：

- 多個 `hold_bars_per_day`，例如 3、5、10。
- 完整出場規則，而不是固定 N 根 bar。
- 停損、停利、成本敏感度與最大回撤檢查。
- regime filter，例如趨勢、波動或成交量環境。

### Phase 3：Live intent schema

Phase 3 只討論 dry-run intent schema 與安全稽核，不直接接 broker。

必須維持：

- `dry_run=True`
- `submitted=False`
- `LIVE_DRY_RUN_ONLY`
- 不讀 credential
- 不送真實訂單

## 資料準備規格

SignalForge 固定使用 OHLCV CSV：

```text
timestamp,open,high,low,close,volume
```

資料規則：

- `timestamp` 必須遞增且不可重複。
- `open/high/low/close` 必須為正數。
- `high` 不得低於 `open` 或 `close`。
- `low` 不得高於 `open` 或 `close`。
- `volume` 不得為負數。
- 原始資料放 `data/raw/`，清洗後資料放 `data/processed/`。
- 只有小型、可公開、可重現的 sample 才放 `data/sample/` 並納入 Git。

內建下載工具：

```powershell
python -m signal_forge.cli fetch-data `
  --market twse `
  --symbol 2330 `
  --start 2024-01-01 `
  --end 2024-01-31
```

美股第一版支援 Stooq daily CSV，但 Stooq 單檔 CSV 端點目前要求免費 API key。Yahoo Finance / yfinance 與 Alpha Vantage 先保留為後續 provider，不在第一版加入外部 dependency 或交易 credential。

## 策略蒸餾規則

每個策略先整理成獨立策略筆記，並保留：

- 策略名稱與 repo 實作位置。
- 原始想法來源，例如 TradingView 腳本或研究假設。
- Pine Script 版本與是否使用 `request.security`、pivot、realtime bar、lookahead。
- 純多進場條件。
- short、濾網、停損、停利、加碼、出場與倉位規則。
- SignalForge 採用的第一階段參數。
- 回測期間、資料來源、輸出 artifact 與驗證命令。

第一批策略：

- [[../策略筆記/SMA Crossover|SMA Crossover]]：趨勢追蹤 baseline。
- [[../策略筆記/VWAP Reversion|VWAP Reversion]]：rolling VWAP 均值回歸。
- [[../策略筆記/Confluence Score|Confluence Score]]：趨勢、VWAP、RSI、量能共振打分。

## 已完成里程碑摘要

截至 2026-05-20，Phase 已完成：

- `PhaseMode`、`PhaseConfig`、`PhaseRunner` 與 backtest/live adapters。
- `LiveExecutionAdapter` 只產生 dry-run `OrderIntent`。
- CLI 支援 `phase --mode backtest|live`。
- Phase summary JSON 與 markdown exact-text regression。
- Entry Edge summary JSON、markdown、trade log CSV deterministic contract。
- `*_signals.csv` 與 `*_trace_summary.json`。
- reason normalization、timestamp ISO-8601、position delta、hold side、position buckets、CSV hash 等 artifact validation。
- 策略筆記資料夾與策略圖片解說。

完整執行紀錄放在 [[../03-程式疊代/Phase 程式疊代紀錄|Phase 程式疊代紀錄]] 與 [[../04-實驗記錄/Autoresearch 實驗記錄|Autoresearch 實驗記錄]]。

## 下一步候選

- 強化 trace summary 的位置範圍稽核，例如 `min_previous_target_position` / `max_previous_target_position`。
- 將 score 分布寫入 Confluence Score 相關 artifact，讓多因子訊號更容易稽核。
- 針對 SMA Crossover 建立多日持倉或完整趨勢持有評估，避免只用一日 entry-edge 誤判策略用途。
- 針對 VWAP Reversion 加入 regime filter，避免強趨勢下反向接刀。
- 維持 live dry-run only，直到回測穩定且另行審核 broker 介面。
