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

### 術語速讀

- **Portfolio rotation**：定期在股票池內重新分配資金，不是每檔股票各自和自己比較。
- **Relative momentum**：同一日期比較多檔股票的近期報酬，選排名較高者。
- **Rebalance**：固定週期重新排名與調整權重。
- **Top-N**：每次最多持有幾檔股票。
- **Cash allowed**：沒有股票通過條件時可留現金。
- **Attribution**：把報酬拆回個股或群組，檢查是否依賴少數贏家。

## 目前參數

這裡保留目前可重跑的主要參數。README 只放最短命令；要調參、複製完整命令或確認目前採用值時，以本表與本頁「如何運行」為準。

| 目前最佳回測設定 | 值 | 用途 |
|---|---:|---|
| `--rebalance-frequency` | `monthly` | 目前 TWSE35 adjusted 最強錨點。 |
| `--lookback-bars` | `21` | 約一個月相對動能。 |
| `--ranking-skip-bars` | `10` | 避免追最近 10 bars 過熱反彈。 |
| `--top-n` | `4` | 每次最多持有 4 檔。 |
| `--breadth-lookback-bars / min-positive-count` | `42 / 3` | 股票池寬度 gate。 |
| `--min-average-traded-value` | `500000000` | 流動性 gate。 |
| `--group-breadth-lookback-bars / share` | `21 / 0.50` | 群組內部廣度 gate。 |
| `--group-regime-lookback-bars / min-return` | `21 / 0` | 群組趨勢 gate。 |

| 參數 | 設定 | 意義 |
|---|---:|---|
| 股票池 | `TWSE35` | 35 檔台股大型股 adjusted OHLCV。 |
| Rebalance | `monthly` | 每月換股一次，降低過度交易。 |
| Lookback | `21 bars` | 約一個交易月的相對動能。 |
| Ranking skip | `10 bars` | 排名時跳過最近 10 根 K，避免追太短線的過熱反彈。 |
| Top N | `4` | 每次最多持有 4 檔。 |
| Breadth filter | `42 bars / min 3` | 整體股票池至少要有 3 檔中期正動能，否則不進場。 |
| Max consecutive | `5` | 同一檔股票最多連續入選 5 次，避免單檔長期主導。 |
| Liquidity gate | `20 bars / 500M` | 近 20 日平均成交金額要超過 5 億，避免流動性太差。 |
| Group breadth | `21 bars / 50%` | 候選股票所屬產業裡，至少一半成員要有正動能。 |
| Group regime | `21 bars / > 0` | 候選股票所屬產業本身的等權報酬要為正。 |

## 如何運行

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

完整 TWSE35 adjusted 強錨點參數已集中在本頁「目前參數」；要重跑時依該表補完整股票池與 `--symbol-group SYMBOL:GROUP`。README 只保留小型股票池的最短啟動命令。

## 進場流程

每月再平衡日依序做這些檢查：

1. 檢查整體市場寬度：如果 35 檔裡中期正動能股票太少，就不進場或維持現金。
2. 計算每檔股票的相對動能：用約 21 個交易日報酬作排名基礎，但跳過最近 10 天，避免追太近的噪音。
3. 檢查流動性：近 20 日平均成交金額低於 5 億的股票不選。
4. 檢查產業內部健康度：如果某檔股票很強，但它的產業裡其他股票大多不強，就擋掉。
5. 檢查產業本身趨勢：如果該產業等權報酬不是正的，也擋掉。
6. 選出前 4 檔：通過所有 gate 後，挑排名最高的 4 檔。
7. 等權配置：每檔約 25% 權重；如果不足 4 檔，剩餘資金留現金。

## 出場流程

這個候選沒有傳統停損停利，主要靠每月再平衡出場：

- 股票不再排名前段，就賣出。
- 股票被 liquidity、breadth 或 group gate 擋掉，就賣出或不再續抱。
- 同一檔連續入選超過上限，會暫停一次。
- 如果沒有足夠合格標的，資金留現金。

## 它想捕捉的 edge

- 強勢股票短中期可能延續強勢。
- 產業動能比單一股票動能更可信。
- 如果某檔股票強，但產業內部不健康，可能是假突破或單一事件。
- 跳過最近 10 天可以降低追高短線反轉風險。
- 流動性與分散限制可降低策略只靠冷門小股或單一股票撐績效的風險。

## 股價走勢解說圖

![[assets/portfolio-relative-momentum-rotation-explainer.png]]

圖中用示意走勢說明：每次 rebalance 都重新排名，資金移到相對動能較強的股票，並和同股票池等權持有比較。此圖不是績效保證。

## 風險與限制

雖然回測報酬很強，但這組候選仍只能標記為 `compare-only`，不能升級成正式穩定營利策略：

- 最大回撤仍約 `-32.85%`。
- 報酬仍集中在少數產業，rolling top3 group share 最高約 `99.09%`。
- Group regime / breadth diagnostics 仍失敗，代表產業集中與單成員依賴還沒完全解掉。
- 因此目前結論是：這是很強的研究候選，不是可直接 live 的主策略。

- 股票池太小時，結果容易被少數個股或少數產業主導。
- 未調整價資料可能高估策略品質，需做 raw / adjusted 對照。
- 高 turnover 會放大手續費、滑價與稅費。
- 只看 full-window 報酬不夠，必須檢查 rolling / OOS、MDD、IR、attribution 與成本壓力。

### 後續優化方向

- 對每個候選先跑 universe audit，再跑 sweep / grid search。
- group breadth / group regime / group contribution 的使用方式集中在 [[Portfolio Rotation Group Gates]]。

## 最新回測註記（2026-05-24）

| 指標 | 數值 | 解讀 |
|---|---:|---|
| 最新 artifacts | `reports\generated\twse35-batch-adjusted-portfolio-rotation-monthly-lb21-skip10-top4-breadth42-min3-maxconsec5-gb21-share050-m1-greg21-r000-liq500m-rolling24m-20260524.md`、`reports\generated\twse35-batch-adjusted-portfolio-rotation-lb21-skip10-top4-gb21-share050-m1-greg21-r000-liq500m-promotion-gate-20260524.md` | 追溯 TWSE35 adjusted strongest anchor 與 promotion gate。 |
| 目前最強設定 | `monthly + lookback21 + skip10 + top4 + breadth42/min3 + maxconsec5 + liq500M + group breadth21/share0.50 + group regime21/r0.00` | 目前 portfolio-level 最強錨點。 |
| 1x full IR | `2.005` | full-window 主動風險報酬很強。 |
| 3x IR | `1.987` | 成本壓力後仍可讀。 |
| Full excess | `3888.38%` | 相對等權 B&H 的 full-window 超額很高。 |
| MDD | `-32.85%` | 絕對回撤仍高。 |
| Active MDD | `-19.44%` | 相對 benchmark 回撤仍需控管。 |
| Min rolling IR | `1.034` | rolling IR 比前期候選改善。 |
| Min rolling excess | `48.53%` | rolling excess 為正。 |
| 刪減判斷 | `compare-only` | 目前最強 anchor，但 promotion gate 因 drawdown、concentration、group diagnostics 仍失敗。 |
