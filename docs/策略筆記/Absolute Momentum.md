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

## 先懂這些詞

- **Absolute momentum**：只看股票自己相對過去是否上漲，不和其他股票排名。
- **Momentum window**：計算過去報酬的回看期。
- **Trend window**：確認價格是否站上長期趨勢線的 SMA 視窗。
- **Target-state**：策略每根 bar 給出目標曝險，回測器按目標曝險計算資金曲線。

## 策略假設

若股票在中長期回看期有正報酬，且目前收盤價仍高於長期 SMA，代表趨勢沒有明顯破壞，可以持有。這個策略比 SMA Crossover 更偏「只在自身動能為正時持有」。

## 進出場規則

| 條件 | 目標曝險 |
|---|---:|
| momentum 或 trend SMA 尚未暖機 | `0.0` |
| `close / close[t - momentum_window] - 1 > 0` 且 `close > trend_sma` | `1.0` |
| 動能不為正，或 close 跌破 trend SMA | `0.0` |

## 主要參數

| 參數 | 預設 | CLI | 用途 |
|---|---:|---|---|
| `momentum_window` | `126` | `--fast-window` | 半年左右的動能回看期 |
| `trend_window` | `200` | `--slow-window` | 長期趨勢確認 |
| `volatility_target` | 關閉 | `--volatility-target` | target-state 風控 overlay，見 [[Volatility Target]] |
| `drawdown_risk_off` | 關閉 | `--drawdown-risk-off` | target-state 風控 overlay，見 [[Drawdown Risk-Off]] |

## 怎麼跑

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

## 股價走勢解說圖

![[assets/absolute-momentum-trend-explainer.png]]

圖中用示意走勢說明：只有自身中期報酬為正、且價格仍在長期均線上方時才持有。此圖不是績效保證。

## 風險與限制

- 趨勢突然反轉時，長期 SMA 會反應慢。
- 只看自身動能，不會自動把資金移到股票池中更強的標的。
- 若要比較股票池內誰更強，改看 [[Relative Momentum Stock-Pool Filter]] 或 [[Portfolio Relative Momentum Rotation]]。

## 下一步

- 用 target-state sweep 檢查成本壓力、MDD、Sortino、Calmar 與 OOS retention。
- 若 overlay 只降低報酬但沒有改善風險，應標示為 compare-only 或 discard。
