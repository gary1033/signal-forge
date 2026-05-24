---
title: Portfolio Rotation Adjusted Grid Search
tags:
  - project/SignalForge
  - trading/backtest
  - strategy/evaluation
status: active
updated: 2026-05-24
---

# Portfolio Rotation Adjusted Grid Search

## 目的

上一輪已把 TWSE14 adjusted-ratio、batch manifest 與 raw/adjusted comparison gate 正式化。這輪不改核心策略語意，而是新增 deterministic 參數掃描工具，讓 portfolio rotation 的下一步不再靠人工挑單一設定。

研究假設：

> 若 `top4 + breadth42/min3 + max consecutive 5 + liquidity 500M/20 bars` 在 adjusted-ratio 下最弱 rolling IR 只剩 `0.104`，就應該先用小型網格掃描確認是否存在更穩的 top-N / breadth / consecutive cap 組合，再談新策略或擴大股票池。

## 程式改動

- 新增 `tools/portfolio_rotation_grid_search.py`。
- 新增 `tests/test_portfolio_rotation_grid_search_tool.py`。
- 工具會掃描：
  - `top_n`
  - `breadth_min_positive_count`
  - `max_consecutive_selections_per_symbol`
  - `min_average_traded_value`
- 每個候選都同時檢查：
  - full-window primary cost 指標
  - stress cost 指標
  - rolling windows 的最弱 IR、最弱 excess、最差 MDD
  - rolling top-3 symbol / group contribution concentration
- 排名順序先看是否通過 gate，再看 failure reason 數量、最弱 rolling IR、full IR、rolling MDD 與 concentration。

## 掃描命令

```powershell
python tools\portfolio_rotation_grid_search.py `
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
  --top-n-list 3,4,5 `
  --breadth-min-positive-count-list 2,3,4,5 `
  --max-consecutive-selections-list 4,5,6 `
  --min-average-traded-value-list 500000000 `
  --cost-multipliers-list 1,3 `
  --rolling-window-months 24 `
  --rolling-step-months 12 `
  --rolling-min-months 12 `
  --symbol-group 1301:plastics `
  --symbol-group 1303:plastics `
  --symbol-group 2303:semiconductor `
  --symbol-group 2308:electronics `
  --symbol-group 2317:electronics `
  --symbol-group 2330:semiconductor `
  --symbol-group 2382:electronics `
  --symbol-group 2412:telecom `
  --symbol-group 2454:semiconductor `
  --symbol-group 2603:shipping `
  --symbol-group 2881:financial `
  --symbol-group 2882:financial `
  --symbol-group 2891:financial `
  --symbol-group 3711:semiconductor `
  --summary-json reports\generated\twse14-adjusted-portfolio-rotation-grid-search-20260524.json `
  --summary-md reports\generated\twse14-adjusted-portfolio-rotation-grid-search-20260524.md
```

## 掃描結果

本輪掃描 `36` 個 adjusted-ratio 候選，沒有任何候選通過全部 gate。主要失敗原因仍是 group contribution concentration，部分設定還同時觸發 drawdown 或 rolling IR / rolling excess gate。

目前排名前幾名：

| Rank | Setting | Full IR | Full excess | MDD | 3x IR | Min rolling IR | Min rolling excess | Max rolling top3 group | Decision |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| `1` | `top3 / breadth4 / maxconsec5 / liq500M` | `1.141` | `1406.71%` | `-22.67%` | `1.114` | `0.264` | `10.73%` | `97.38%` | compare-only |
| `2` | `top3 / breadth3 / maxconsec5 / liq500M` | `1.158` | `1474.59%` | `-33.53%` | `1.130` | `0.346` | `14.13%` | `94.99%` | compare-only |
| `3` | `top3 / breadth3 / maxconsec6 / liq500M` | `1.205` | `1596.40%` | `-31.32%` | `1.177` | `0.278` | `9.90%` | `94.99%` | compare-only |
| `6` | current baseline `top4 / breadth3 / maxconsec5 / liq500M` | `1.156` | `1160.72%` | `-27.97%` | `1.125` | `0.104` | `1.54%` | `94.77%` | compare-only |

## 解讀

1. **沒有升級為 keep 的候選**：36 個 adjusted-ratio 組合全部仍是 compare-only，不能宣稱穩定營利。
2. **`top3 / breadth4 / maxconsec5` 是較好的下一個 compare anchor**：相對 current baseline，它把 min rolling IR 從 `0.104` 提到 `0.264`，MDD 從 `-27.97%` 改到 `-22.67%`，但 full IR 從 `1.156` 小降到 `1.141`。
3. **group concentration 仍是主瓶頸**：最佳排名的 max rolling top3 group share 仍高達 `97.38%`，比 current baseline 的 `94.77%` 更集中，所以不能只看 rolling IR 改善。
4. **追求更高 full IR 會推高風險**：`top3 / breadth3 / maxconsec5` 有更高 min rolling IR `0.346`，但 full MDD 到 `-33.53%`，超過 `30%` drawdown gate。

## Keep / Discard 判斷

- **Keep code**：grid search 工具與 regression tests。它把 adjusted 參數搜尋從人工比較升級成 deterministic artifact。
- **Keep diagnostic**：`top3 / breadth4 / maxconsec5 / liq500M` 可作下一個 compare anchor，因為 adjusted min rolling IR 與 MDD 都比 current baseline 好。
- **Do not promote strategy**：所有掃描結果都未通過 group concentration gate；目前仍不是穩定營利證明。
- **Next**：針對 `top3 / breadth4 / maxconsec5 / liq500M` 做 raw/adjusted comparison artifact，並優先測 group regime validation 或更高品質股票池，而不是繼續只擴 top-N / breadth / consecutive cap 網格。
