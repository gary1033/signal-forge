---
title: Portfolio Relative Momentum Rotation
tags:
  - project/SignalForge
  - trading/strategy
  - trading/momentum
  - trading/portfolio
status: research
updated: 2026-05-24
repo_impl: C:\Projects\signal-forge\tools\portfolio_rotation_sweep.py
---

# Portfolio Relative Momentum Rotation

## 快速定位

| 問題 | 答案 |
|---|---|
| CLI 工具 | `tools\portfolio_rotation_sweep.py` |
| 適用資料 | 多檔日線 OHLCV |
| 策略型態 | 股票池內 long-only 相對動能輪動 |
| Benchmark | 同股票池 equal-weight buy-and-hold |
| 進階 gate | [[Portfolio Rotation Group Gates]] |

## 先懂這些詞

- **Portfolio rotation**：定期在股票池內重新分配資金，不是每檔股票各自和自己比較。
- **Relative momentum**：同一日期比較多檔股票的近期報酬，選排名較高者。
- **Rebalance**：固定週期重新排名與調整權重。
- **Top-N**：每次最多持有幾檔股票。
- **Cash allowed**：沒有股票通過條件時可留現金。
- **Attribution**：把報酬拆回個股或群組，檢查是否依賴少數贏家。

## 策略假設

若股票池內存在可持續的相對強弱，資金應該集中到近期表現較強的標的，而不是等權持有全部股票。這個策略的成敗必須用整個投組和 equal-weight benchmark 比，不應只看單一股票勝負。

## 進出場規則

每個 rebalance timestamp 執行：

1. 對每檔股票計算 lookback return。
2. 若設定 `ranking_skip_bars`，先排除最近 N 根 bar 再計算排名。
3. 排除報酬不高於 `min_return` 的股票。
4. 套用 market breadth、group、liquidity、cooldown 等 gate。
5. 依 ranking score 選前 `top_n`。
6. 入選股票等權配置；未入選股票權重為 `0.0`。
7. 沒有股票通過時，全投組留現金。

## 主要參數

| 參數 | 預設 | 用途 |
|---|---:|---|
| `--rebalance-frequency` | `weekly` | daily / weekly / monthly 再平衡 |
| `--lookback-bars` | `126` | 相對動能回看期 |
| `--ranking-skip-bars` | `0` | 排除最近 N 根 bar 後排名 |
| `--ranking-mode` | `total-return` | 可改 `group-residual` |
| `--top-n` | `3` | 每次最多持有檔數 |
| `--min-return` | `0.0` | 絕對動能下限 |
| `--cost-multipliers-list` | `1` | 成本壓力倍率 |
| `--volatility-target` | 關閉 | 投組層級降曝險 overlay |

## 怎麼跑

精簡版：

```powershell
python tools\portfolio_rotation_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --summary-json reports\generated\portfolio-rotation-default.json `
  --summary-md reports\generated\portfolio-rotation-default.md
```

完整版請看 repo 根目錄 `README.md` 的「Portfolio rotation」段落；group gate 版本必須提供 `--symbol-group SYMBOL:GROUP`。

## 股價走勢解說圖

![[assets/portfolio-relative-momentum-rotation-explainer.png]]

圖中用示意走勢說明：每次 rebalance 都重新排名，資金移到相對動能較強的股票，並和同股票池等權持有比較。此圖不是績效保證。

## 風險與限制

- 股票池太小時，結果容易被少數個股或少數產業主導。
- 未調整價資料可能高估策略品質，需做 raw / adjusted 對照。
- 高 turnover 會放大手續費、滑價與稅費。
- 只看 full-window 報酬不夠，必須檢查 rolling / OOS、MDD、IR、attribution 與成本壓力。

## 下一步

- 對每個候選先跑 universe audit，再跑 sweep / grid search。
- group breadth / group regime / group contribution 的使用方式集中在 [[Portfolio Rotation Group Gates]]。
