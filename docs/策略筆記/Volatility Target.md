---
title: Volatility Target
tags:
  - project/SignalForge
  - trading/strategy
  - trading/risk
status: research
updated: 2026-05-24
repo_impl: C:\Projects\signal-forge\src\signal_forge\strategies\volatility_target.py
---

# Volatility Target

## 快速定位

| 問題 | 答案 |
|---|---|
| CLI 參數 | `--volatility-target` |
| 是否為獨立 `--strategy` | 否，這是 risk overlay |
| 適用工具 | `tools\multi_stock_target_state_sweep.py`、`tools\portfolio_rotation_sweep.py` |
| 實作位置 | `src\signal_forge\strategies\volatility_target.py`、`tools\portfolio_rotation_sweep.py` |

## 先懂這些詞

- **Realized volatility**：用近期 close-to-close return 算出的已實現波動。
- **Target annual volatility**：希望曝險後的年化波動上限。
- **Scale**：把原本目標曝險乘上一個小於等於 1 的倍率。

## 策略假設

當近期波動過高時，同樣的 long signal 承擔的風險更大。Volatility Target 不改變底層方向，只把非零曝險往下縮，測試「降曝險」是否能改善 MDD、Sortino 或 Calmar。

## 控制規則

| 判定點 | 輸出 | 維護語意 |
|---|---:|---|
| 底層訊號為 flat | 保持 `0.0` | Overlay 不創造新方向，只處理原本已經要持有的曝險大小。 |
| 樣本不足 | `0.0` 或等候暖機 | 沒有足夠 close-to-close return 時，不用不穩定波動估計持倉。 |
| realized volatility 低於目標 | 保留原曝險，上限為 `max_scale` | 目前風險沒有超標，維持底層策略曝險；預設仍不放大到超過 1。 |
| realized volatility 高於目標 | 按比例降低曝險 | 用 `target_vol / realized_vol` 計算 scale，只降曝險、不改訊號方向。 |

## 主要參數

| 參數 | 預設 | CLI | 用途與調整判斷 |
|---|---:|---|---|
| `lookback_bars` | target-state `20`；portfolio `21` | `--volatility-lookback-bars` | realized volatility 的估算視窗；短視窗更快降曝險但容易過度反應，長視窗較穩但反應慢。 |
| `target_annual_volatility` | `0.20` | `--target-annual-volatility` | 目標年化波動；降低會更保守，提高則更接近原始策略曝險。 |
| `min_observations` | 同 lookback 或未指定 | `--volatility-min-observations` | 啟用縮放前需要的最少報酬樣本；用來避免剛開始幾根 bar 的估計不穩。 |
| `max_scale` | `1.0` | `--volatility-max-scale` | 曝險上限；預設 1.0 表示不加槓桿，只允許縮小持倉。 |

## 怎麼跑

精簡版：

```powershell
python tools\multi_stock_target_state_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --strategy absolute-momentum `
  --volatility-target
```

完整版：

```powershell
python tools\portfolio_rotation_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --volatility-target `
  --volatility-lookback-bars 21 `
  --target-annual-volatility 0.20 `
  --volatility-min-observations 21 `
  --volatility-max-scale 1.0 `
  --summary-json reports\generated\portfolio-vol-target.json `
  --summary-md reports\generated\portfolio-vol-target.md
```

## 股價走勢解說圖

![[assets/volatility-target-explainer.png]]

此圖借用趨勢持有示意：Volatility Target 只調整持倉大小，不保證降低所有回撤。

## 風險與限制

- 降曝險通常也會降低報酬，不能只因 MDD 變小就升級策略。
- 波動估算落後於市場，快速崩跌時可能來不及反應。
- `max_scale=1.0` 是安全邊界；不要在未審核前改成加槓桿。

## 下一步

- 同時看 excess return、MDD、Sortino、Calmar 與 OOS retention，再決定 keep / discard / compare-only。
