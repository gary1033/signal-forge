---
title: SignalForge 大框架規劃
tags:
  - project/SignalForge
  - planning
  - trading/research
status: active
updated: 2026-05-24
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
- 策略評估：回測、優化、參數調整或找新策略時，先參考 [[策略回測與優化評估準則|策略回測與優化評估準則]]，不能只用單一 PF、勝率或總損益決定 keep。
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
- 升級候選門檻：參考 [[策略回測與優化評估準則|策略回測與優化評估準則]]，至少要同時檢查 PF、expectancy、trade count、max drawdown、多股票 sweep、cost stress 與 benchmark relative return。
- 可選濾網：`--volume-filter` 先以外層 wrapper 實驗成交量確認，預設規則是 `volume >= sma(volume, 20) * 1.2`，預設不啟用。
- 多持有期比較：`entry-edge --hold-bars-list 1,3,5,10` 可在保留原本單一 hold report / JSON / trade CSV 的同時，另外輸出 `*_hold_comparison.json` 與 `*_hold_comparison.md`。這只做稽核比較，不自動挑最佳持有期，也不視為參數最佳化。

### Phase 2：多日持倉與出場規則

進入 Phase 2 前，要先回答策略到底是在測短期隔日 edge，還是在測中長期持有。Phase 2 候選方向：

- 多個 `hold_bars_per_day`，例如 3、5、10。
- 完整出場規則，而不是固定 N 根 bar。
- 停損、停利、成本敏感度與最大回撤檢查。
- regime filter，例如趨勢、波動或成交量環境。
- 風險調整與穩健性指標，例如 Sharpe、Sortino、Calmar、Information Ratio、walk-forward / OOS 與 drawdown attribution。
- 目前 Phase 2 研究工具包含 `tools\multi_stock_target_state_sweep.py` 與 `tools\portfolio_rotation_sweep.py`。前者評估逐檔 target exposure，後者評估同一資金池的 portfolio-level 輪動；兩者都要檢查 1x / 3x 成本壓力與 walk-forward / OOS 分段。portfolio rotation 的風控 overlay 目前包含 market regime filter、breadth filter、volatility target、單檔連續入選上限與 group cap，並已補逐股 attribution 與 concentration guard，必須用同一套 active-risk 與 concentration gate 比較。

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
- 公開、可重現、可作為回測證據的歷史資料可以納入 Git；`data/raw/` 與 `data/processed/` 不應預設放進 `.gitignore`。
- `data/sample/` 保留小型 deterministic smoke-test 資料。

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
- 依 [[策略回測與優化評估準則|策略回測與優化評估準則]] 判斷該策略目前是 keep、discard 還是 compare-only。

第一批策略：

- [[../策略筆記/SMA Crossover|SMA Crossover]]：趨勢追蹤 baseline。
- [[../策略筆記/VWAP Reversion|VWAP Reversion]]：rolling VWAP 均值回歸。
- [[../策略筆記/Confluence Score|Confluence Score]]：趨勢、VWAP、RSI、量能共振打分。
- [[../策略筆記/Absolute Momentum|Absolute Momentum]]：長期趨勢持有候選，要求回看報酬為正且收盤站上長期 SMA；可搭配 volatility target、drawdown risk-off 與 relative-momentum stock-pool filter，但目前都只作 compare-only，不是主候選。
- [[../策略筆記/Portfolio Relative Momentum Rotation|Portfolio Relative Momentum Rotation]]：投組層級相對動能輪動候選，避免用逐檔 B&H 指標誤判股票池 rotation。

## 已完成里程碑摘要

截至 2026-05-20，Phase 已完成：

- `PhaseMode`、`PhaseConfig`、`PhaseRunner` 與 backtest/live adapters。
- `LiveExecutionAdapter` 只產生 dry-run `OrderIntent`。
- CLI 支援 `phase --mode backtest|live`。
- CLI 支援 `entry-edge` / `phase` 的可選成交量過濾器 `--volume-filter`。
- CLI 支援 VWAP Reversion 的可選趨勢 regime filter：`--vwap-regime-filter --vwap-regime-window 50`。
- 策略開發模板已整理為 hook-based `BarByBarStrategy`，三個既有策略透過 `prepare_context(...)` / `decide_bar(...)` 實作，外部 `Signal` contract 不變。
- Strategy registry / factory 已接上 CLI，Phase 1 factory 固定建構 long-only 策略，並保留 `VolumeFilteredStrategy` wrapper。
- `entry-edge` 支援 `--hold-bars-list`，可用同一個 strategy、資料與成本設定比較多個固定持有期，並輸出 deterministic hold comparison JSON/Markdown。
- `multi_stock_target_state_sweep.py` 支援完整持倉 target-state 多股票報表，輸出 benchmark-relative return、MDD、Sharpe、Sortino、Calmar、turnover、time in market、成本壓力與 worst drawdown attribution。
- `VolatilityTargetStrategy` 支援只降曝險、不加槓桿的 realized-volatility target overlay，並已接入 target-state sweep 的 `--volatility-target`。
- `DrawdownRiskOffStrategy` 支援單檔 proxy equity drawdown-state risk-off overlay，並已接入 target-state sweep 的 `--drawdown-risk-off`。
- `multi_stock_target_state_sweep.py` 支援 `--walk-forward-windows`，可用 `label:start:end` 指定樣本內 / 樣本外分段，並輸出 OOS retention 報表。
- `multi_stock_target_state_sweep.py` 支援 `--relative-momentum-filter`，可用跨股票 lookback return top-N 建立股票池白名單；目前 OOS 參數掃描顯示它降低曝險但沒有改善 benchmark-relative edge。
- `portfolio_rotation_sweep.py` 支援 portfolio-level relative momentum rotation、equal-weight buy-and-hold benchmark、成本壓力、walk-forward / rolling split、自動 rolling window 產生、Information Ratio、tracking error、active max drawdown、market regime filter、breadth filter、volatility target、單檔連續入選上限、group cap 與 liquidity gate；股票池已由 7 檔擴到 14 檔，並暫時擴到 TWSE23 做 concentration diagnostic。`top4 + breadth 42/min3 + max consecutive 5 + liquidity 500M/20 bars` 目前是最新 execution-aware compare candidate。sector/group cap 已測但未改善 rolling concentration；TWSE23 可降低 concentration 但犧牲 edge 與 drawdown，後續仍需要 adjusted price、canary universe 與更高品質股票池驗證。
- Phase summary JSON 與 markdown exact-text regression。
- Entry Edge summary JSON、markdown、trade log CSV deterministic contract。
- `*_signals.csv` 與 `*_trace_summary.json`。
- reason normalization、timestamp ISO-8601、position delta、hold side、position buckets、CSV hash 等 artifact validation。
- 策略筆記資料夾與策略圖片解說。

完整執行紀錄放在 [[../03-程式疊代/Phase 程式疊代紀錄|Phase 程式疊代紀錄]] 與 [[../04-實驗記錄/Autoresearch 實驗記錄|Autoresearch 實驗記錄]]。

## 下一步候選

- 強化 trace summary 的位置範圍稽核，例如 `min_previous_target_position` / `max_previous_target_position`。
- 將 score 分布寫入 Confluence Score 相關 artifact，讓多因子訊號更容易稽核。
- 依 [[策略回測與優化評估準則|策略回測與優化評估準則]] 繼續補齊 benchmark-relative metrics；portfolio rotation 已補 IR / tracking error / active drawdown / rolling windows / market regime compare tool / breadth filter / volatility target compare tool / symbol attribution / concentration guard / 單檔連續入選上限 / group cap / TWSE23 擴大股票池診斷 / liquidity gate。下一步重點轉向 adjusted price、較慢批次完成 TWSE30+、canary universe、group-level attribution，或更具體的 re-entry 條件。
- 使用 `entry-edge --hold-bars-list` 先檢查 SMA Crossover 是否被一日 entry-edge 低估，再決定是否進入完整趨勢持有 / 出場規則設計。
- 針對 VWAP Reversion 比較未啟用與啟用 `--vwap-regime-filter` 的結果，確認簡單趨勢濾網是否能減少強下跌中的反向接刀。
- 針對 Absolute Momentum 的 benchmark-relative 問題做下一層驗證：`vol-target 0.40 + dd-risk-off 25%/120` 可降低回撤但 2024-2026 OOS 是 `0/7` beat B&H；relative-momentum top-N 股票池也沒有改善 `Beat B&H`。下一步應測 re-entry 條件、weekly rebalance 或市場 regime，不要只靠降曝險或 top-N 過濾。
- 針對 portfolio rotation，下一步不要直接宣稱穩定營利；14 檔 `breadth 42/min3` 雖讓 `top3` full-window IR 約 `1.417` 並讓 1x/2x/3x 成本與 6 個 rolling windows 都保持正 excess，但 concentration guard 顯示 `roll02` 高度依賴 `2603`、`roll06` 依賴 `2308`，且 TWSE STOCK_DAY 資料未還原權息。`top4 + max consecutive 5 + liquidity 500M/20 bars` 已成為最新 execution-aware compare candidate，full IR 約 `1.521`、min rolling IR 約 `0.814`、3x 成本後 IR 約 `1.490`，但 rolling concentration 仍未解；sector/group cap 已測，`groupcap2` 未降低 max rolling top-3 share。TWSE23 擴大股票池可降低 max rolling top-3 share，但 min rolling excess / IR 轉弱且部分設定 MDD 惡化。後續應測 adjusted price、較慢批次完成 TWSE30+、canary universe 或 group-level attribution。
- 在 OOP template 穩定後，再逐一討論三種策略的下一步修改，避免一次混入模板重構與策略語意變更。
- 維持 live dry-run only，直到回測穩定且另行審核 broker 介面。
