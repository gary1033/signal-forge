---
title: Portfolio Rotation Group Gates
tags:
  - project/SignalForge
  - trading/strategy
  - trading/portfolio
  - trading/risk
status: research
updated: 2026-05-24
repo_impl: C:\Projects\signal-forge\tools\portfolio_rotation_sweep.py
---

# Portfolio Rotation Group Gates

## 快速定位

| 問題 | 答案 |
|---|---|
| 相關工具 | `tools\portfolio_rotation_sweep.py` |
| 是否為獨立策略 | 否，這是 portfolio rotation gate |
| 必要輸入 | 多檔 CSV；group gate 需要 `--symbol-group SYMBOL:GROUP` |
| 診斷工具 | `tools\portfolio_rotation_group_regime_validation.py`、`tools\portfolio_rotation_group_breadth_validation.py` |

### 術語速讀

- **Group**：自訂產業或股票群組，例如 `semiconductor`、`financial`。
- **Group breadth**：同一群組內有多少成員也呈現正動能。
- **Group regime**：同一群組等權平均是否也處於正動能。
- **Group contribution**：已實現報酬有多少來自同一群組。

## 目前參數

這裡保留目前可重跑的主要參數。README 只放最短命令；要調參、複製完整命令或確認目前採用值時，以本表與本頁「如何運行」為準。

| 目前最佳回測設定 | 值 | 用途 |
|---|---:|---|
| `--group-breadth-lookback-bars` | `21` | 目前最強 group breadth 視窗。 |
| `--group-breadth-min-positive-share` | `0.50` | 群組內至少半數正動能。 |
| `--group-regime-lookback-bars` | `21` | 目前最強 group regime 視窗。 |
| `--group-regime-min-return` | `0` | 群組等權報酬需為正。 |

| 參數 | 預設 | 用途與調整判斷 |
|---|---:|---|
| `--symbol-group` | 無 | 必填的 group mapping；格式是 `SYMBOL:GROUP`，分組本身就是研究假設，改分組會改變 gate 結果。 |
| `--group-breadth-lookback-bars` | `21` | 群組內部正動能比例的回看期；短期反應快但較噪，長期較穩但可能錯過群組轉弱。 |
| `--group-breadth-min-positive-share` | `0.50` | 群組內正動能比例下限；提高會更嚴格但可能把有效 group regime 一併排除。 |
| `--group-breadth-min-members` | `1` | 群組成員數下限；提高可阻擋單成員依賴，但也可能讓薄群組無法參與。 |
| `--group-regime-lookback-bars` | `63` | 群組等權報酬回看期；短期 gate 較敏感，長期 gate 可能過晚發現轉弱。 |
| `--group-regime-min-return` | `0.0` | 群組等權報酬下限；提高門檻會要求群組本身更強，但也會降低入選機會。 |
| `--group-regime-min-members` | `1` | 群組 regime 計算的成員數下限；用來控制單檔 proxy group 的可靠性。 |

## 如何運行

精簡版：

```powershell
python tools\portfolio_rotation_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --symbol-group 2330:semiconductor `
  --symbol-group 2454:semiconductor `
  --symbol-group 2317:electronics `
  --group-breadth-filter `
  --group-regime-filter `
  --summary-json reports\generated\portfolio-group-gates.json `
  --summary-md reports\generated\portfolio-group-gates.md
```

完整版：

```powershell
python tools\portfolio_rotation_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --symbol-group 2330:semiconductor `
  --symbol-group 2454:semiconductor `
  --symbol-group 2317:electronics `
  --symbol-group 2308:electronics `
  --rebalance-frequency monthly `
  --lookback-bars 21 `
  --top-n 3 `
  --breadth-filter `
  --breadth-lookback-bars 42 `
  --breadth-min-positive-count 2 `
  --group-breadth-filter `
  --group-breadth-lookback-bars 21 `
  --group-breadth-min-positive-share 0.50 `
  --group-breadth-min-members 1 `
  --group-regime-filter `
  --group-regime-lookback-bars 21 `
  --group-regime-min-return 0 `
  --group-regime-min-members 1 `
  --max-selections-per-group 2 `
  --summary-json reports\generated\portfolio-group-gates-full.json `
  --summary-md reports\generated\portfolio-group-gates-full.md
```

## 進場流程

| Gate | CLI | 控制語意 | 維護語意 |
|---|---|---|---|
| Group breadth | `--group-breadth-filter` | 候選股票所屬群組內部正動能比例不足時排除 | 檢查候選不是只靠單一同組成員撐起排名；若群組內大多數成員都弱，候選也不放行。 |
| Group regime | `--group-regime-filter` | 候選股票所屬群組等權 lookback return 不足時排除 | 檢查候選所屬產業或群組本身是否仍在正趨勢，避免弱勢群組內的相對強股被誤選。 |
| Group cap | `--max-selections-per-group` | 每次 rebalance 限制同組最多入選檔數 | 控制持倉分散度，避免 top-N 全被同一 group 佔滿。 |
| Single-member guard | `--min-symbols-per-selected-group` | 群組成員數不足時排除 | 阻擋只有一檔股票的 group 被誤讀成有群組代表性。 |
| Group contribution | `--group-contribution-lookback-bars` + `--max-group-contribution-share` | 若近期已實現貢獻過度集中，暫時排除該群組 | 只用已完成持倉貢獻作下一次 rebalance 的 gate，不可偷看完整 window 結果。 |

## 出場流程

Group gates 不自創出場價格；每次 rebalance 時若既有持股不再通過 group breadth、group regime、group cap 或 contribution gate，就從下一期權重中移除。

## 它想捕捉的 edge

Portfolio rotation 可能看起來有效，但實際上只依賴少數產業或單一 group 的 regime。Group gates 用來檢查並限制這種集中度：不是新增 alpha，而是防止選股結果過度依賴窄群組。

## 股價走勢解說圖

![[assets/portfolio-rotation-group-gates-explainer.png]]

此圖借用 portfolio rotation 示意：group gates 只限制候選與曝險集中度，不代表能保證降低回撤。

## 風險與限制

- group mapping 是研究假設；分組錯誤會直接改變結果。
- Gate 過嚴可能把真正有效的 group regime 也排除。
- Gate 改善集中度不等於改善報酬，必須同時看 IR、MDD、rolling/OOS 與 attribution。

### 後續優化方向

- 對每個 group gate 候選都補 `group_regime_validation` 與 `group_breadth_validation` artifact。
- 若 gate 只改善單一集中度欄位但犧牲 rolling edge，應維持 compare-only 或 discard。

## 最新回測註記（2026-05-24）

| 指標 | 數值 | 解讀 |
|---|---:|---|
| 最新 artifact | `reports\generated\twse35-batch-adjusted-portfolio-rotation-lb21-skip10-top4-gb21-share050-m1-greg21-r000-liq500m-promotion-gate-20260524.md` | 追溯 group gate promotion gate。 |
| Gate 組合 | `gb21/share0.50/min1 + greg21/r0.00` | 目前最強 group breadth/regime 組合。 |
| Decision | `compare-only` | promotion gate 未過。 |
| Gate pass | `false` | 不能升級主策略。 |
| 1x IR | `2.005` | full-window 主動風險報酬很強。 |
| 3x IR | `1.987` | 成本壓力後仍可讀。 |
| MDD | `-32.85%` | 回撤仍超過升級門檻。 |
| Active MDD | `-19.44%` | 相對 benchmark 回撤仍需控管。 |
| Max rolling top3 group share | `99.09%` | group concentration 尚未解決。 |
| 刪減判斷 | `keep tool / compare-only strategy` | gate 工具保留，但策略仍不能升級。 |
