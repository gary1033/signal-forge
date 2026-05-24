---
title: Relative Momentum Stock-Pool Filter
tags:
  - project/SignalForge
  - trading/strategy
  - trading/momentum
status: research
updated: 2026-05-24
repo_impl: C:\Projects\signal-forge\tools\multi_stock_target_state_sweep.py
---

# Relative Momentum Stock-Pool Filter

## 快速定位

| 問題 | 答案 |
|---|---|
| CLI 參數 | `--relative-momentum-filter` |
| 是否為獨立 `--strategy` | 否，這是多股票 allowlist filter |
| 適用工具 | `tools\multi_stock_target_state_sweep.py` |
| 實作位置 | `tools\multi_stock_target_state_sweep.py` |

## 先懂這些詞

- **Stock-pool filter**：先決定哪些股票當天允許持倉，再讓底層策略輸出曝險。
- **Top-N allowlist**：同一天只允許相對動能排名前 N 的股票持有。
- **Min return**：股票自身 lookback return 也要高於門檻。

## 策略假設

單檔策略可能同時對很多股票給出 long，但資金應優先配置到同一股票池中近期更強的標的。Relative Momentum Stock-Pool Filter 不改底層策略訊號，只把不在 top-N allowlist 的非零曝險壓成 flat。

## 控制規則

| 判定點 | 輸出 | 維護語意 |
|---|---:|---|
| 股票當天在 top-N 且 lookback return 達門檻 | 保留底層曝險 | 股票同時具備橫向排名優勢與自身正動能，才允許原策略持倉。 |
| 股票不在 allowlist | `0.0` | 底層策略即使偏多，若相對排名不夠強，也不分配曝險。 |
| 股票自身 lookback return 不達門檻 | `0.0` | 避免在整個股票池都弱時，只因相對排名高就持有絕對弱勢股。 |

## 主要參數

| 參數 | 預設 | CLI | 用途與調整判斷 |
|---|---:|---|---|
| `lookback_bars` | `126` | `--relative-momentum-lookback-bars` | 橫向排名的回看期；短期更敏感，長期更平滑但可能落後。 |
| `top_n` | `3` | `--relative-momentum-top-n` | 每天允許持倉的檔數；越小越集中，越大越接近未篩選版本。 |
| `min_return` | `0.0` | `--relative-momentum-min-return` | 自身動能下限；用來阻擋相對排名高但絕對報酬仍不好的股票。 |

## 怎麼跑

精簡版：

```powershell
python tools\multi_stock_target_state_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --strategy absolute-momentum `
  --relative-momentum-filter
```

完整版：

```powershell
python tools\multi_stock_target_state_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --strategy absolute-momentum `
  --relative-momentum-filter `
  --relative-momentum-lookback-bars 126 `
  --relative-momentum-top-n 3 `
  --relative-momentum-min-return 0 `
  --cost-multipliers-list 1,2,3 `
  --summary-json reports\generated\relative-momentum-filter.json `
  --summary-md reports\generated\relative-momentum-filter.md
```

## 股價走勢解說圖

![[assets/relative-momentum-stock-pool-filter-explainer.png]]

此圖借用股票池輪動示意：allowlist filter 只限制哪些股票可持倉，不等於完整 portfolio rotation。

## 風險與限制

- 它仍是 per-symbol target-state 回測，不是同一資金池的 portfolio-level allocation。
- 若要真正比較投組輪動績效，應使用 [[Portfolio Relative Momentum Rotation]]。
- Top-N 太小容易集中，太大可能和未篩選差異不大。

## 下一步

- 用它作為單檔策略到 portfolio rotation 之間的過渡檢查，不要把它誤讀成完整投組策略。
