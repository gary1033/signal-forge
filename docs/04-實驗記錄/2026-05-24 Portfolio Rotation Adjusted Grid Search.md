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

## 2026-05-24 follow-up：top3 / breadth4 raw-adjusted comparison

### 目的

上一段 grid search 把 `top3 / breadth4 / maxconsec5 / liq500M` 標成下一個 compare anchor，但當時還缺 raw / adjusted 對照 artifact。本段補上同一設定在未調整 TWSE 價格與 TWSE14 adjusted batch 價格下的 deterministic comparison，確認它是否真的比 current baseline 更值得繼續追蹤。

### 產生 artifact

```powershell
python tools\compare_portfolio_rotation_reports.py `
  --raw-summary-json reports\generated\twse14-portfolio-rotation-monthly-lb21-top3-breadth42-min4-maxconsec5-liq500m-rolling24m-20260524.json `
  --adjusted-summary-json reports\generated\twse14-batch-adjusted-portfolio-rotation-monthly-lb21-top3-breadth42-min4-maxconsec5-liq500m-rolling24m-20260524.json `
  --adjusted-batch-manifest-json reports\generated\adjusted-data\TWSE14_adjusted_batch_manifest_20260524.json `
  --raw-label raw-twse `
  --adjusted-label adjusted-ratio-batch `
  --rolling-cost-label 1x `
  --output-json reports\generated\twse14-raw-vs-batch-adjusted-portfolio-rotation-lb21-top3-breadth4-liq500m-compare-20260524.json `
  --output-md reports\generated\twse14-raw-vs-batch-adjusted-portfolio-rotation-lb21-top3-breadth4-liq500m-compare-20260524.md
```

### 主要結果

| Scope | Raw | Adjusted | Delta |
|---|---:|---:|---:|
| Full 1x return | `1559.26%` | `1890.64%` | `+331.38%` |
| Full 1x excess | `1223.08%` | `1406.71%` | `+183.63%` |
| Full 1x IR | `1.236` | `1.141` | `-0.095` |
| Full 1x MDD | `-21.93%` | `-22.67%` | `-0.73%` |
| Full top3 group share | `91.64%` | `92.78%` | `+1.14%` |
| Weakest adjusted rolling IR | n/a | `roll02 = 0.264` | n/a |

Rolling 1x 對照中，adjusted 版本的最弱 window 仍是 `roll02`：excess `10.73%`、IR `0.264`、MDD `-18.94%`。相對 current baseline adjusted `top4 / breadth3 / maxconsec5 / liq500M` 的 `roll02 IR 0.104` 與 `MDD -27.97%`，這個 anchor 的 rolling robustness 較好；但 adjusted rolling top3 group share 最高仍到 `97.38%`，集中度比 current baseline 更差。

### Keep / Discard 判斷

- **Keep artifact**：raw / adjusted comparison 已補齊，後續可直接用這組 artifact 比較 `top3/breadth4` 與 current baseline。
- **Keep diagnostic**：`top3 / breadth4 / maxconsec5 / liq500M` 比 current baseline 更適合作為下一個 compare anchor，因為 adjusted min rolling IR 與 MDD 較好。
- **Do not promote strategy**：group concentration gate 仍失敗，adjusted top3 group share full-window `92.78%`，rolling 最高 `97.38%`；這不是穩定營利證明。
- **Next**：不要繼續只微調 top-N / breadth / consecutive cap。下一步應做 group regime validation 或更高品質股票池，目標是降低 rolling group contribution concentration，同時保留 adjusted min rolling excess、IR 與可接受 MDD。

## 2026-05-24 follow-up：group regime validation

### 目的

上一段確認 `top3 / breadth4 / maxconsec5 / liq500M` 的 adjusted rolling robustness 比 current baseline 好，但 group concentration 仍是主瓶頸。本段新增 deterministic group regime validation artifact，用同一份 adjusted summary 檢查每個 full / rolling window 的群組貢獻是否只是長期高曝險造成，還是特定群組在該 window 的 realized return 主導。

### 程式改動

- 新增 `tools/portfolio_rotation_group_regime_validation.py`。
- 新增 `tests/test_portfolio_rotation_group_regime_validation_tool.py`。
- 工具會讀取 portfolio rotation summary JSON，針對指定 `cost_label` 輸出：
  - 最大貢獻群組與貢獻占比。
  - 最大貢獻群組的平均權重。
  - 貢獻占比減平均權重的 contribution-exposure gap。
  - 最大平均曝險群組。
  - top3 group contribution share 與 top3 group average weight。
  - dominance type：`return_regime_dominated`、`exposure_dominated` 或 `mixed`。
  - gate failure reason。

### 產生 artifact

```powershell
python tools\portfolio_rotation_group_regime_validation.py `
  --summary-json reports\generated\twse14-batch-adjusted-portfolio-rotation-monthly-lb21-top3-breadth42-min4-maxconsec5-liq500m-rolling24m-20260524.json `
  --cost-label 1x `
  --max-top3-group-share 0.90 `
  --max-contribution-exposure-gap 0.30 `
  --output-json reports\generated\twse14-batch-adjusted-portfolio-rotation-lb21-top3-breadth4-liq500m-group-regime-validation-20260524.json `
  --output-md reports\generated\twse14-batch-adjusted-portfolio-rotation-lb21-top3-breadth4-liq500m-group-regime-validation-20260524.md
```

### 主要結果

| Metric | Value |
|---|---:|
| Gate pass | `false` |
| High concentration windows | `7 / 7` |
| Return-regime dominated windows | `7 / 7` |
| Exposure dominated windows | `0 / 7` |
| Worst top3 group window | `roll03 = 97.38%` |
| Weakest IR window | `roll02 = 0.264` |

重點 rolling windows：

| Window | Max contrib group | Contrib share | Avg weight | Gap | Max exposure group | Top3 group | Dominance |
|---|---|---:|---:|---:|---|---:|---|
| `roll02` | `shipping` | `70.86%` | `10.43%` | `60.43%` | `financial` | `93.36%` | `return_regime_dominated` |
| `roll03` | `electronics` | `61.84%` | `12.02%` | `49.81%` | `semiconductor` | `97.38%` | `return_regime_dominated` |
| `roll06` | `electronics` | `63.61%` | `30.40%` | `33.20%` | `electronics` | `94.99%` | `return_regime_dominated` |

### 解讀

1. **不是單純高曝險問題**：全部 `7 / 7` 視窗都被分類為 `return_regime_dominated`。例如 `roll02` 最大貢獻是 `shipping`，但最大平均曝險是 `financial`；`shipping` 平均權重只有 `10.43%`，卻貢獻 `70.86%` 的絕對貢獻占比。
2. **硬壓 group exposure 未必有效**：若問題來自特定 window 的 realized return，而不是長期平均權重，單純 group cap 或固定刪 group 容易傷害 edge，這和前面的 group cap / dominant group exclusion 診斷一致。
3. **下一步要改驗證方向**：比起繼續微調 `top_n`、breadth 或 max consecutive，下一步應優先做更高品質股票池或 group regime validation 延伸，例如檢查不同產業 regime proxy、rolling breadth by group、或要求每個 rolling window 的 top3 group contribution share 下降到 gate 內。

### Keep / Discard 判斷

- **Keep code**：group regime validation 工具與 regression tests。它把群組集中度來源從人工解讀升級為可重跑 artifact。
- **Keep diagnostic**：`top3 / breadth4 / maxconsec5 / liq500M` 的 rolling IR / MDD tradeoff 仍較 current baseline 好，但群組 regime 依賴沒有改善。
- **Do not promote strategy**：`7 / 7` 視窗都 high concentration 且 return-regime dominated，不可宣稱穩定營利。
- **Next**：轉向更高品質股票池、group-level breadth / regime validation，或直接設計能限制 realized group contribution concentration 的 gate；不要再只擴同一組 top-N / breadth / max-consecutive grid。
