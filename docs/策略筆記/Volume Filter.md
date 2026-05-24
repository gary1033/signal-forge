---
title: Volume Filter
tags:
  - project/SignalForge
  - trading/strategy
  - trading/filter
status: research
updated: 2026-05-24
repo_impl: C:\Projects\signal-forge\src\signal_forge\strategies\volume_filter.py
---

# Volume Filter

## 快速定位

| 問題 | 答案 |
|---|---|
| CLI 參數 | `--volume-filter` |
| 是否為獨立 `--strategy` | 否，這是 wrapper |
| 適用工具 | `entry-edge`、`phase` |
| 實作位置 | `src\signal_forge\strategies\volume_filter.py` |

## 先懂這些詞

- **Wrapper**：不自己產生原始策略，而是包在底層策略外面修改訊號。
- **Volume SMA**：最近 N 根成交量平均。
- **Relative volume**：當前成交量相對於成交量均線的倍數。

## 策略假設

底層策略給出 long 訊號後，如果成交量沒有放大，這個訊號可能缺乏參與度。Volume Filter 只保留成交量達門檻的 long signal，其他 long signal 會改成 flat。

## 控制規則

| 條件 | 輸出 |
|---|---:|
| 底層策略不是 long | 保持原訊號 |
| 成交量 SMA 尚未暖機 | `0.0` |
| `volume >= sma(volume, volume_window) * volume_multiplier` | 保留 long |
| 成交量不足 | `0.0` |

## 主要參數

| 參數 | 預設 | CLI | 用途 |
|---|---:|---|---|
| `volume_window` | `20` | `--volume-window` | 成交量均線視窗 |
| `volume_multiplier` | `1.2` | `--volume-multiplier` | 放量門檻 |

## 怎麼跑

精簡版：

```powershell
python -m signal_forge.cli entry-edge `
  --csv data\processed\TWSE_2330_1D.csv `
  --strategy sma-crossover `
  --volume-filter
```

完整版：

```powershell
python -m signal_forge.cli entry-edge `
  --csv data\processed\TWSE_2330_1D.csv `
  --strategy confluence-score `
  --volume-filter `
  --volume-window 20 `
  --volume-multiplier 1.2 `
  --hold-bars-list 1,3,5,10 `
  --run-name tsmc-confluence-volume-filter
```

## 股價走勢解說圖

![[assets/confluence-score-trend-explainer.png]]

此圖借用多條件訊號示意：Volume Filter 只處理訊號是否有量能確認，不代表策略績效保證。

## 風險與限制

- 放量不一定是好訊號，也可能是恐慌賣壓或事件衝擊。
- `volume_multiplier` 太高會讓交易數不足。
- 不應只看 PF，仍要檢查 trade count、MDD、成本壓力與多股票穩健性。

## 下一步

- 比較同一底層策略在開關 volume filter 前後，訊號數是否只是被壓縮，還是真的改善 edge。
