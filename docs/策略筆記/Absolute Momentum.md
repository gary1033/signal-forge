---
title: Absolute Momentum
tags:
  - project/SignalForge
  - trading/strategy
  - trading/momentum
status: research
updated: 2026-05-24
repo_impl: C:\Projects\signal-forge\src\signal_forge\strategies\absolute_momentum.py
---

# Absolute Momentum

## 快速定位

| 問題 | 答案 |
|---|---|
| CLI 名稱 | `absolute-momentum` |
| 適用資料 | 日線 OHLCV |
| 策略型態 | long-only 長期趨勢持有候選 |
| 實作位置 | `src\signal_forge\strategies\absolute_momentum.py` |
| 多股票工具 | `tools\multi_stock_target_state_sweep.py` |

### 術語速讀

- **Absolute momentum**：只看股票自己相對過去是否上漲，不和其他股票排名。
- **Momentum window**：計算過去報酬的回看期。
- **Trend window**：確認價格是否站上長期趨勢線的 SMA 視窗。
- **Target-state**：策略每根 bar 給出目標曝險，回測器按目標曝險計算資金曲線。

## 目前參數

這裡保留目前可重跑的主要參數。README 只放最短命令；要調參、複製完整命令或確認目前採用值時，以本表與本頁「如何運行」為準。

| 目前最佳回測設定 | 值 | 用途 |
|---|---:|---|
| `--fast-window` | `126` | 對應 `momentum_window`，目前長期動能錨點。 |
| `--slow-window` | `200` | 對應 `trend_window`，目前長期趨勢濾網。 |

| 參數 | 預設 | CLI | 用途與調整判斷 |
|---|---:|---|---|
| `momentum_window` | `126` | `--fast-window` | 自身動能回看期；越短越像中短線 momentum，越長越偏長期趨勢確認。 |
| `trend_window` | `200` | `--slow-window` | 長期趨勢濾網；它用來防止只因短期反彈就持有長期弱勢股。 |
| `volatility_target` | 關閉 | `--volatility-target` | target-state 風控 overlay；只縮小非零曝險，用來測風險調整後是否改善，見 [[Volatility Target]]。 |
| `drawdown_risk_off` | 關閉 | `--drawdown-risk-off` | target-state 風控 overlay；以單檔 proxy equity 回撤暫停持倉，見 [[Drawdown Risk-Off]]。 |

## 如何運行

精簡版：

```powershell
$Csv = "data\processed\TWSE_2330_1D.csv"
python -m signal_forge.cli entry-edge --csv $Csv --strategy absolute-momentum
```

完整版：

```powershell
python tools\multi_stock_target_state_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --strategy absolute-momentum `
  --cost-multipliers-list 1,2,3 `
  --volatility-target `
  --volatility-lookback-bars 20 `
  --target-annual-volatility 0.40 `
  --drawdown-risk-off `
  --drawdown-risk-off-threshold 0.25 `
  --drawdown-risk-off-bars 120 `
  --relative-momentum-filter `
  --relative-momentum-lookback-bars 126 `
  --relative-momentum-top-n 3 `
  --summary-json reports\generated\absolute-momentum-target-state.json `
  --summary-md reports\generated\absolute-momentum-target-state.md
```

## 進場流程

| 判定點 | 目標曝險 | 維護語意 |
|---|---:|---|
| momentum 或 trend SMA 尚未暖機 | `0.0` | 回看報酬或長期趨勢基準缺資料時，不提前建立持倉。 |
| `close / close[t - momentum_window] - 1 > 0` 且 `close > trend_sma` | `1.0` | 股票自身中期報酬為正，且價格仍站上長期趨勢，才允許完整 long。 |
| 動能不為正，或 close 跌破 trend SMA | `0.0` | 任一條件失效都代表趨勢持有假設不足，回到 flat。 |

## 出場流程

只要自身動能不再為正，或 close 跌破 trend SMA，就回到 `target_position=0.0`。它沒有固定停利，退出完全由動能與趨勢濾網決定。

## 它想捕捉的 edge

若股票在中長期回看期有正報酬，且目前收盤價仍高於長期 SMA，代表趨勢沒有明顯破壞，可以持有。這個策略比 SMA Crossover 更偏「只在自身動能為正時持有」。

## 股價走勢解說圖

![[assets/absolute-momentum-trend-explainer.png]]

圖中用示意走勢說明：只有自身中期報酬為正、且價格仍在長期均線上方時才持有。此圖不是績效保證。

## 風險與限制

- 趨勢突然反轉時，長期 SMA 會反應慢。
- 只看自身動能，不會自動把資金移到股票池中更強的標的。
- 若要比較股票池內誰更強，改看 [[Relative Momentum Stock-Pool Filter]] 或 [[Portfolio Relative Momentum Rotation]]。

### 後續優化方向

- 用 target-state sweep 檢查成本壓力、MDD、Sortino、Calmar 與 OOS retention。
- 若 overlay 只降低報酬但沒有改善風險，應標示為 compare-only 或 discard。

## 最新回測註記（2026-05-24）

| 指標 | 數值 | 解讀 |
|---|---:|---|
| 最新 artifacts | `reports\generated\twse-target-state-absolute-momentum-oos-20260524.md`、`reports\generated\twse-absolute-momentum-entry-edge-20260524.md` | 以 target-state/OOS 為主要判斷。 |
| 目前參數 | `momentum_window=126`、`trend_window=200` | 目前長期動能錨點。 |
| 1x 平均報酬 | `225.78%` | 絕對報酬是 target-state 中較好的錨點。 |
| Beat B&H | `1/7` | 相對 benchmark 不足。 |
| Avg excess | `-226.95%` | 主動績效仍落後。 |
| Worst MDD | `-50.74%` | 最差回撤仍接近 B&H 風險。 |
| OOS Beat B&H | `1/7` | 樣本外沒有改善。 |
| OOS Avg excess | `-105.25%` | 樣本外仍輸 benchmark。 |
| 刪減判斷 | `compare-only` | 保留長期趨勢錨點，不升級成主策略。 |
