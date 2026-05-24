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

### 術語速讀

- **Wrapper**：不自己產生原始策略，而是包在底層策略外面修改訊號。
- **Volume SMA**：最近 N 根成交量平均。
- **Relative volume**：當前成交量相對於成交量均線的倍數。

## 目前參數

這裡保留目前可重跑的主要參數。README 只放最短命令；要調參、複製完整命令或確認目前採用值時，以本表與本頁「如何運行」為準。

| 目前最佳回測設定 | 值 | 用途 |
|---|---:|---|
| `--volume-window` | `20` | 目前 wrapper A/B 使用的均量基準。 |
| `--volume-multiplier` | `1.2` | 目前 wrapper A/B 使用的放量門檻。 |

| 參數 | 預設 | CLI | 用途與調整判斷 |
|---|---:|---|---|
| `volume_window` | `20` | `--volume-window` | 成交量基準視窗；短視窗更快反應近期量能變化，長視窗更穩但容易忽略短期成交結構。 |
| `volume_multiplier` | `1.2` | `--volume-multiplier` | 放量倍數門檻；提高會保留更少但更有量能的訊號，降低則更接近原策略。 |

## 如何運行

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

## 進場流程

| 判定點 | 輸出 | 維護語意 |
|---|---:|---|
| 底層策略不是 long | 保持原訊號 | Volume Filter 只處理 long entry quality，不把 flat 訊號改成交易。 |
| 成交量 SMA 尚未暖機 | `0.0` | 沒有均量基準時不接受 long，避免前幾根資料造成假放量。 |
| `volume >= sma(volume, volume_window) * volume_multiplier` | 保留 long | 當前量能達到相對門檻，代表訊號至少有成交量參與。 |
| 成交量不足 | `0.0` | 底層策略雖然偏多，但缺少量能確認，因此改成 flat。 |

## 出場流程

Volume Filter 不自創出場；它只把底層 long 訊號在量能不足時改成 flat。底層策略本來的 flat 或出場訊號會原樣保留。

## 它想捕捉的 edge

底層策略給出 long 訊號後，如果成交量沒有放大，這個訊號可能缺乏參與度。Volume Filter 只保留成交量達門檻的 long signal，其他 long signal 會改成 flat。

## 股價走勢解說圖

![[assets/volume-filter-explainer.png]]

此圖借用多條件訊號示意：Volume Filter 只處理訊號是否有量能確認，不代表策略績效保證。

## 風險與限制

- 放量不一定是好訊號，也可能是恐慌賣壓或事件衝擊。
- `volume_multiplier` 太高會讓交易數不足。
- 不應只看 PF，仍要檢查 trade count、MDD、成本壓力與多股票穩健性。

### 後續優化方向

- 比較同一底層策略在開關 volume filter 前後，訊號數是否只是被壓縮，還是真的改善 edge。

## 最新回測註記（2026-05-21）

| 指標 | 數值 | 解讀 |
|---|---:|---|
| 最新 artifact | `reports\generated\tsmc-volume-filter-comparison.md` | 追溯 volume wrapper A/B 比較。 |
| 樣本 | 台積電日線 `2010-01-04` 到 `2026-05-20` | 單檔 wrapper 檢查。 |
| 目前參數 | `volume_window=20`、`volume_multiplier=1.2` | 目前可重跑的量能門檻。 |
| Filtered 版本 | 3 組 | 都未達 PF `>1.2`。 |
| 最佳候選 | `confluence-score + volume filter` | 相對最好但仍不合格。 |
| PF | `1.080` | 未通過。 |
| Max drawdown | `-18.18%` | 回撤沒有換來足夠 PF。 |
| 刪減判斷 | `compare-only / not upgrade` | 保留 wrapper 工具，不視為策略升級。 |
