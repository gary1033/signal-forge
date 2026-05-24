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
- 目前 Phase 2 研究工具包含 `tools\multi_stock_target_state_sweep.py` 與 `tools\portfolio_rotation_sweep.py`。前者評估逐檔 target exposure，後者評估同一資金池的 portfolio-level 輪動；兩者都要檢查 1x / 3x 成本壓力與 walk-forward / OOS 分段。portfolio rotation 的風控與排名 overlay 目前包含 market regime filter、breadth filter、volatility target、ranking skip、ranking mode（`total-return` / `group-residual`）、單檔連續入選上限、group cap、單成員群組 gate、realized group contribution gate、re-entry cooldown gate 與 liquidity gate，並已補逐股 attribution、group attribution、group exposure summary 與 concentration guard，必須用同一套 active-risk、symbol concentration、group contribution concentration 與 group exposure concentration gate 比較。

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

調整價研究工具：

```powershell
python tools\build_twse_adjusted_ohlcv.py `
  --symbol 2330 `
  --source-csv data\processed\TWSE_2330_1D.csv `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --output-csv reports\generated\adjusted-data\TWSEADJ_2330_1D.csv `
  --manifest-json reports\generated\adjusted-data\TWSEADJ_2330_1D_manifest.json
```

這個工具只用 Yahoo chart 的 `adjclose / close` 當調整比例，套回 TWSE source CSV 的 OHLC；volume 保留 TWSE source CSV 口徑，並在 manifest 記錄 `adjustment_method`、`adjustment_source`、`price_source_csv`、`volume_source`、`missing_adjustment_count` 與 `skipped_row_count`。它不是新的行情 provider，也不讀 API key，只是為 portfolio rotation 的 raw / adjusted-ratio 對照提供可重跑資料流程。

TWSE14 adjusted 批次重建工具：

```powershell
python tools\build_twse_adjusted_ohlcv_batch.py `
  --symbols-list 1301,1303,2303,2308,2317,2330,2382,2412,2454,2603,2881,2882,2891,3711 `
  --source-dir data\processed `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --output-dir reports\generated\adjusted-data `
  --batch-manifest-json reports\generated\adjusted-data\TWSE14_adjusted_batch_manifest_20260524.json
```

Batch manifest 目前可重建 14 檔 adjusted CSV 與 14 份 per-symbol manifest，總 rows `21479`、缺 Yahoo ratio `26`、skip rows `2482`。後續 portfolio rotation 評估必須能追到這個 batch manifest 或同等 manifest，不應再使用無來源說明的暫存 adjusted CSV。

Raw / adjusted portfolio rotation 比較工具：

```powershell
python tools\compare_portfolio_rotation_reports.py `
  --raw-summary-json reports\generated\twse14-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-liq500m-group-exposure-rolling24m-20260524.json `
  --adjusted-summary-json reports\generated\twse14-batch-adjusted-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-liq500m-rolling24m-20260524.json `
  --adjusted-batch-manifest-json reports\generated\adjusted-data\TWSE14_adjusted_batch_manifest_20260524.json `
  --raw-label raw-twse `
  --adjusted-label adjusted-ratio-batch `
  --rolling-cost-label 1x `
  --output-json reports\generated\twse14-raw-vs-batch-adjusted-portfolio-rotation-lb21-top4-liq500m-compare-20260524.json `
  --output-md reports\generated\twse14-raw-vs-batch-adjusted-portfolio-rotation-lb21-top4-liq500m-compare-20260524.md
```

這個工具把 raw 與 adjusted summary 對齊後輸出 deterministic JSON / Markdown，比較 total return、benchmark excess、Information Ratio、MDD、active MDD、symbol concentration 與 group concentration。2026-05-24 對照顯示同一 execution-aware candidate 從 raw `IR 1.521 / MDD -18.61%` 降成 adjusted `IR 1.156 / MDD -27.97%`，最弱 rolling IR 從 `0.814` 降到 `0.104`；因此後續 portfolio rotation 優化必須先通過 raw/adjusted comparison gate。

Group regime validation 工具：

```powershell
python tools\portfolio_rotation_group_regime_validation.py `
  --summary-json reports\generated\twse14-batch-adjusted-portfolio-rotation-monthly-lb21-top3-breadth42-min4-maxconsec5-liq500m-rolling24m-20260524.json `
  --cost-label 1x `
  --max-top3-group-share 0.90 `
  --max-contribution-exposure-gap 0.30 `
  --output-json reports\generated\twse14-batch-adjusted-portfolio-rotation-lb21-top3-breadth4-liq500m-group-regime-validation-20260524.json `
  --output-md reports\generated\twse14-batch-adjusted-portfolio-rotation-lb21-top3-breadth4-liq500m-group-regime-validation-20260524.md
```

這個工具把 portfolio rotation 的 group contribution concentration 和 group exposure 對齊，判斷 rolling concentration 是長期高曝險、特定 group realized return regime，還是混合來源。2026-05-24 `top3 / breadth4 / maxconsec5 / liq500M` adjusted anchor 的結果是 full + 6 個 rolling windows 全部 high concentration，且 `7 / 7` 都是 `return_regime_dominated`；因此下一步不應只做 group cap 或固定刪群組，而要轉向更高品質股票池、group-level breadth / regime validation，或能直接限制 realized group contribution concentration 的 gate。

Group breadth validation 工具：

```powershell
python tools\portfolio_rotation_group_breadth_validation.py `
  --summary-json reports\generated\twse14-batch-adjusted-portfolio-rotation-monthly-lb21-top3-breadth42-min4-maxconsec5-liq500m-rolling24m-20260524.json `
  --csv reports\generated\adjusted-data\TWSEADJ_1301_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_1303_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2303_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2308_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2317_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2330_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2382_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2412_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2454_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2603_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2881_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2882_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2891_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_3711_1D.csv `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-label 1x `
  --output-json reports\generated\twse14-batch-adjusted-portfolio-rotation-lb21-top3-breadth4-liq500m-group-breadth-validation-20260524.json `
  --output-md reports\generated\twse14-batch-adjusted-portfolio-rotation-lb21-top3-breadth4-liq500m-group-breadth-validation-20260524.md
```

這個工具把 dominant contribution group 內部的成員動能廣度也寫成 deterministic gate。它會輸出 group 成員數、rebalance 樣本數、平均正動能成員比例、多數成員正動能比例、全成員同向比例與平均成員 lookback return。2026-05-24 `top3 / breadth4 / maxconsec5 / liq500M` adjusted anchor 的結果仍未通過：`7 / 7` high concentration，`4 / 7` 是 broad group momentum，`2 / 7` 是 `shipping` 單成員 dominant，`1 / 7` 是 `electronics` narrow breadth。這表示下一步不能只說「群組有 regime」；必須區分單成員群組、窄廣度群組與真正廣泛群組動能，再決定是否做更高品質股票池、TWSE30+ 或 realized group contribution concentration gate。

Portfolio promotion gate 工具：

```powershell
python tools\portfolio_rotation_promotion_gate.py `
  --summary-json reports\generated\twse14-batch-adjusted-portfolio-rotation-monthly-lb21-top3-breadth42-min4-maxconsec5-liq500m-rolling24m-20260524.json `
  --raw-adjusted-comparison-json reports\generated\twse14-raw-vs-batch-adjusted-portfolio-rotation-lb21-top3-breadth4-liq500m-compare-20260524.json `
  --group-regime-validation-json reports\generated\twse14-batch-adjusted-portfolio-rotation-lb21-top3-breadth4-liq500m-group-regime-validation-20260524.json `
  --group-breadth-validation-json reports\generated\twse14-batch-adjusted-portfolio-rotation-lb21-top3-breadth4-liq500m-group-breadth-validation-20260524.json `
  --output-json reports\generated\twse14-batch-adjusted-portfolio-rotation-lb21-top3-breadth4-liq500m-promotion-gate-20260524.json `
  --output-md reports\generated\twse14-batch-adjusted-portfolio-rotation-lb21-top3-breadth4-liq500m-promotion-gate-20260524.md
```

這個工具把 portfolio summary、raw/adjusted comparison、group regime validation 與 group breadth validation 合併成單一升級 gate。2026-05-24 adjusted `top3 / breadth4 / maxconsec5 / liq500M` 的結果是 `compare-only`：full 1x IR 約 `1.141`、3x IR 約 `1.114`，但 min rolling IR 只有約 `0.264`，max rolling top3 symbol share 約 `81.40%`，max rolling top3 group share 約 `97.38%`，且 group regime / breadth gate 都失敗。後續若要宣稱策略升級，必須讓這份 promotion gate 或同等 gate 通過，而不是只引用單一 summary 的漂亮 full-window 指標。

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
- `portfolio_rotation_sweep.py` 支援 portfolio-level relative momentum rotation、equal-weight buy-and-hold benchmark、成本壓力、walk-forward / rolling split、自動 rolling window 產生、Information Ratio、tracking error、active max drawdown、market regime filter、breadth filter、volatility target、ranking skip、ranking mode、單檔連續入選上限、group cap、單成員群組 gate、realized group contribution gate、re-entry cooldown gate 與 liquidity gate；股票池已由 7 檔擴到 14 檔，並暫時擴到 TWSE23 做 concentration diagnostic。`top4 + breadth 42/min3 + max consecutive 5 + liquidity 500M/20 bars` 目前是 execution-aware compare candidate。sector/group cap 已測但未改善 rolling concentration；group attribution / exposure 顯示部分 window 是群組 regime return 主導；dominant group exclusion 顯示固定刪除 `shipping`、`electronics` 或 `semiconductor` 都不能同時改善 edge、回撤與 concentration；`min_symbols_per_selected_group=2` 也已測，會排除 `shipping/2603` 但讓 adjusted `roll02` excess 轉負、IR 轉為約 `-0.994`，因此這個設定 discard；`ranking_skip_bars=10` 已測，TWSE16 adjusted full IR 改到約 `1.186`、3x IR 約 `1.158`，但 min rolling IR 仍約 `-0.856`、min rolling excess 約 `-22.55%` 且 max rolling top3 group share 到 `100%`，因此只作 compare-only；`ranking_skip_bars=21` discard；`ranking_mode=group-residual` 已測，`skip10 + group-residual` full IR 約 `1.059`、3x IR 約 `1.031`、MDD 約 `-35.83%`，並未改善 rolling group concentration，因此只保留為 deterministic compare tool，不能取代 `skip10 total-return` 錨點。TWSE23 可降低 concentration 但犧牲 edge 與 drawdown；Canary9 held-out universe 顯示 full excess 約 `-0.91%`、MDD 約 `-44.29%`；adjusted-ratio 版本顯示 full IR 降到約 `1.156`、MDD 惡化到約 `-27.97%`、min rolling IR 只剩約 `0.104`；TWSE35 adjusted baseline 目前是最強 expanded-universe compare-only anchor，但 realized group contribution gate 第一輪仍未通過 promotion gate：`gcontrib21/share0.90` full IR 約 `1.742`、MDD 約 `-32.91%`，但 min rolling IR 約 `-0.022`、min rolling excess 約 `-5.93%`；re-entry cooldown 第一輪也只到 compare-only：`reentry6` 把 MDD 改到約 `-28.76%`、min rolling excess 約 `18.63%`，但 full IR 降到約 `1.046`、min rolling IR 約 `0.4996`，group gate 仍失敗。`tools\build_twse_adjusted_ohlcv.py` 與 `tools\build_twse_adjusted_ohlcv_batch.py` 已正式化 adjusted price 資料來源、per-symbol manifest 與 TWSE14 / TWSE35 batch manifest，`tools\portfolio_rotation_group_regime_validation.py` 已正式化 group contribution vs exposure 診斷，`tools\portfolio_rotation_group_breadth_validation.py` 已正式化 dominant group 內部廣度診斷；後續仍需要更高品質股票池，而不是只掃 contribution threshold 或 re-entry cooldown 長度。
- `tools\portfolio_rotation_promotion_gate.py` 已正式化升級判斷：同時讀 portfolio summary、raw/adjusted comparison、group regime validation 與 group breadth validation，輸出單一 `keep` / `compare-only` 結論。2026-05-24 adjusted `top3 / breadth4 / maxconsec5 / liq500M` promotion gate 仍是 `compare-only`，主要失敗點是 min rolling IR、rolling symbol/group concentration、group regime 與 group breadth。
- Phase summary JSON 與 markdown exact-text regression。
- Entry Edge summary JSON、markdown、trade log CSV deterministic contract。
- `*_signals.csv` 與 `*_trace_summary.json`。
- reason normalization、timestamp ISO-8601、position delta、hold side、position buckets、CSV hash 等 artifact validation。
- 策略筆記資料夾與策略圖片解說。

完整執行紀錄放在 [[../03-程式疊代/Phase 程式疊代紀錄|Phase 程式疊代紀錄]] 與 [[../04-實驗記錄/Autoresearch 實驗記錄|Autoresearch 實驗記錄]]。

## 下一步候選

- 強化 trace summary 的位置範圍稽核，例如 `min_previous_target_position` / `max_previous_target_position`。
- 將 score 分布寫入 Confluence Score 相關 artifact，讓多因子訊號更容易稽核。
- 依 [[策略回測與優化評估準則|策略回測與優化評估準則]] 繼續補齊 benchmark-relative metrics；portfolio rotation 已補 IR / tracking error / active drawdown / rolling windows / market regime compare tool / breadth filter / volatility target compare tool / ranking skip / ranking mode / symbol attribution / group attribution / group exposure summary / concentration guard / 單檔連續入選上限 / group cap / 單成員群組 gate / realized group contribution gate / re-entry cooldown gate / TWSE23 / TWSE35 擴大股票池診斷 / liquidity gate / dominant group exclusion 診斷 / canary universe 診斷 / adjusted price 診斷 / group regime validation / group breadth validation / promotion gate / universe audit，並已把 adjusted price 資料來源正式化為可重跑 per-symbol manifest、TWSE14 / TWSE35 batch manifest 與 raw/adjusted comparison artifact。TWSE23 universe audit 顯示 23 檔中只有 16 檔通過歷史長度、流動性與群組成員數；補齊 `1101,2327,2357,2379` adjusted CSV 後，TWSE16 adjusted batch manifest 共有 24391 rows、missing adjustment 30、skipped rows 2486，但同一族 rotation gate 仍因 `roll02` 失效而不能升級。`ranking_skip_bars=10` 是目前唯一有改善 full IR 的 skip 版本，但仍未通過 rolling 與 group concentration gate；`ranking_mode=group-residual` 對 TWSE16 反而傷害 full-window IR 與 MDD，只能作未來大股票池 compare dimension。TWSE35 adjusted baseline 把 full IR 改到 `1.685`、3x IR `1.668`、min rolling IR `0.429`、min rolling excess `11.33%`，但 MDD / active MDD 偏高且 max rolling top3 group share 仍到 `100%`，promotion gate 仍是 `compare-only`；TWSE35 `min_symbols_per_selected_group=2` 也讓 min rolling IR 轉為 `-1.482`，因此硬擋單成員群組 discard as improvement。realized group contribution gate 第一輪雖讓 `gcontrib21/share0.90` full IR 到 `1.742` 且 active MDD 改到 `-25.13%`，但 min rolling excess 轉為 `-5.93%`，所以只能 keep tool、discard current upgrade。re-entry cooldown 第一輪讓 `reentry6` 改善 drawdown 與 rolling excess，但 full IR 下降、min rolling IR 仍低於 `0.5`，group gates 仍失敗；下一步重點轉向更高品質股票池或改善 group breadth / single-member 替代性，而不是只調 contribution threshold 或 cooldown 長度。
- 使用 `entry-edge --hold-bars-list` 先檢查 SMA Crossover 是否被一日 entry-edge 低估，再決定是否進入完整趨勢持有 / 出場規則設計。
- 針對 VWAP Reversion 比較未啟用與啟用 `--vwap-regime-filter` 的結果，確認簡單趨勢濾網是否能減少強下跌中的反向接刀。
- 針對 Absolute Momentum 的 benchmark-relative 問題做下一層驗證：`vol-target 0.40 + dd-risk-off 25%/120` 可降低回撤但 2024-2026 OOS 是 `0/7` beat B&H；relative-momentum top-N 股票池也沒有改善 `Beat B&H`。下一步應測 re-entry 條件、weekly rebalance 或市場 regime，不要只靠降曝險或 top-N 過濾。
- 針對 portfolio rotation，下一步不要直接宣稱穩定營利；14 檔 `breadth 42/min3` 雖讓 `top3` full-window IR 約 `1.417` 並讓 1x/2x/3x 成本與 6 個 rolling windows 都保持正 excess，但 concentration guard 顯示 `roll02` 高度依賴 `2603`、`roll06` 依賴 `2308`。`top4 + max consecutive 5 + liquidity 500M/20 bars` 是 execution-aware compare candidate，未調整價 full IR 約 `1.521`、min rolling IR 約 `0.814`、3x 成本後 IR 約 `1.490`，但 rolling concentration 仍未解；sector/group cap 已測，`groupcap2` 未降低 max rolling top-3 share。group exposure 診斷顯示 `roll02` 的最大貢獻群組是 `shipping`、但最大平均曝險是 `financial`；dominant group exclusion 也顯示固定刪除 `shipping` 會讓 rolling edge 失效，固定刪除 `electronics` 會讓 full-window edge 大幅衰退，固定刪除 `semiconductor` 則惡化回撤與 concentration。`min_symbols_per_selected_group=2` 進一步確認硬擋單成員群組也會讓 adjusted `roll02` 失效，不能當主規則。TWSE23 擴大股票池可降低 max rolling top-3 share，但 min rolling excess / IR 轉弱且部分設定 MDD 惡化；Canary9 held-out universe full excess 轉負、MDD 約 `-44.29%`；TWSE14 batch adjusted-ratio 版本 full IR 仍只有約 `1.156`、MDD 惡化到約 `-27.97%`、min rolling IR 只剩約 `0.104`，且 top3 group share 約 `91.29%`。補齊 4 檔 adjusted 後，TWSE16 `top4 / breadth42-min3 / maxconsec5 / liq500M` adjusted full IR `0.863`、3x IR `0.832`，但 `roll02` excess `-29.26%`、IR `-1.123`，promotion gate 仍失敗；36 組 `topN 3/4/5 x breadth 3/4/5/6 x maxconsec 4/5/6` 小網格全數 compare-only。`ranking_skip_bars=10` 可改善 full-window 指標，但 rolling IR / excess 仍為負且 group concentration 仍破表，所以只是 compare-only；`ranking_skip_bars=21` discard。`ranking_mode=group-residual` 參考 residual / industry momentum 假設，但 TWSE16 `skip10 + group-residual` 的 full IR 降到約 `1.059`、MDD 惡化到約 `-35.83%`，且 group concentration 沒修好，因此 discard as current improvement，只保留工具。TWSE35 expanded universe 讓 `skip10` 的 rolling 指標從負值改善為正值，但 promotion gate 仍因 drawdown 與 group concentration 失敗，`mingrp2` 也把 `roll02` 打回負值。realized contribution gate 已測，21-bar / 90% 版本改善 full IR 與 active MDD，但 min rolling IR / excess 轉負，不能升級；re-entry cooldown 也已測，能改善 drawdown 與 rolling excess，但 min rolling IR 與 group gates 仍不合格。後續不要再在同一 TWSE16 小股票池微調 top-N / breadth / max consecutive / skip / residual ranking，也不要把 TWSE35 full-window IR、contribution-gate full IR 或 re-entry drawdown 改善當成升級證明；應改往更高品質股票池與 group breadth / single-member 替代性。
- 在 OOP template 穩定後，再逐一討論三種策略的下一步修改，避免一次混入模板重構與策略語意變更。
- 維持 live dry-run only，直到回測穩定且另行審核 broker 介面。
