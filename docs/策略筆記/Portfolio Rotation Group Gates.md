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

## 先懂這些詞

- **Group**：自訂產業或股票群組，例如 `semiconductor`、`financial`。
- **Group breadth**：同一群組內有多少成員也呈現正動能。
- **Group regime**：同一群組等權平均是否也處於正動能。
- **Group contribution**：已實現報酬有多少來自同一群組。

## 策略假設

Portfolio rotation 可能看起來有效，但實際上只依賴少數產業或單一 group 的 regime。Group gates 用來檢查並限制這種集中度：不是新增 alpha，而是防止選股結果過度依賴窄群組。

## 控制規則

| Gate | CLI | 控制語意 |
|---|---|---|
| Group breadth | `--group-breadth-filter` | 候選股票所屬群組內部正動能比例不足時排除 |
| Group regime | `--group-regime-filter` | 候選股票所屬群組等權 lookback return 不足時排除 |
| Group cap | `--max-selections-per-group` | 每次 rebalance 限制同組最多入選檔數 |
| Single-member guard | `--min-symbols-per-selected-group` | 群組成員數不足時排除 |
| Group contribution | `--group-contribution-lookback-bars` + `--max-group-contribution-share` | 若近期已實現貢獻過度集中，暫時排除該群組 |

## 主要參數

| 參數 | 預設 | 用途 |
|---|---:|---|
| `--symbol-group` | 無 | `SYMBOL:GROUP` 映射 |
| `--group-breadth-lookback-bars` | `21` | group breadth 回看期 |
| `--group-breadth-min-positive-share` | `0.50` | 群組內正動能比例下限 |
| `--group-breadth-min-members` | `1` | 群組最少成員數 |
| `--group-regime-lookback-bars` | `63` | group regime 回看期 |
| `--group-regime-min-return` | `0.0` | 群組等權報酬下限 |
| `--group-regime-min-members` | `1` | 群組最少成員數 |

## 怎麼跑

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

## 股價走勢解說圖

![[assets/portfolio-relative-momentum-rotation-explainer.png]]

此圖借用 portfolio rotation 示意：group gates 只限制候選與曝險集中度，不代表能保證降低回撤。

## 風險與限制

- group mapping 是研究假設；分組錯誤會直接改變結果。
- Gate 過嚴可能把真正有效的 group regime 也排除。
- Gate 改善集中度不等於改善報酬，必須同時看 IR、MDD、rolling/OOS 與 attribution。

## 下一步

- 對每個 group gate 候選都補 `group_regime_validation` 與 `group_breadth_validation` artifact。
- 若 gate 只改善單一集中度欄位但犧牲 rolling edge，應維持 compare-only 或 discard。
