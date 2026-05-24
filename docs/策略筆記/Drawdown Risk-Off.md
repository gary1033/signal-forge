---
title: Drawdown Risk-Off
tags:
  - project/SignalForge
  - trading/strategy
  - trading/risk
status: research
updated: 2026-05-24
repo_impl: C:\Projects\signal-forge\src\signal_forge\strategies\drawdown_risk_off.py
---

# Drawdown Risk-Off

## 快速定位

| 問題 | 答案 |
|---|---|
| CLI 參數 | `--drawdown-risk-off` |
| 是否為獨立 `--strategy` | 否，這是 risk overlay |
| 適用工具 | `tools\multi_stock_target_state_sweep.py` |
| 實作位置 | `src\signal_forge\strategies\drawdown_risk_off.py` |

## 先懂這些詞

- **Proxy equity**：用策略自身目標曝險估算的單檔資金曲線。
- **High-water mark**：proxy equity 曾達到的最高點。
- **Risk-off bars**：觸發回撤後維持 flat 的 bar 數。

## 策略假設

若單檔策略已從自身高點回撤超過門檻，短期內可能處於失效狀態。Drawdown Risk-Off 會暫停該檔非零曝險一段時間，測試是否能降低最差回撤。

## 控制規則

| 判定點 | 輸出 | 維護語意 |
|---|---:|---|
| proxy equity 回撤未破門檻 | 保持底層訊號 | 策略自身尚未進入明確失效狀態，不干預底層進出場。 |
| 回撤達 `drawdown_threshold` | 啟動 risk-off | 從 high-water mark 回撤超過門檻時，視為需要暫停曝險。 |
| risk-off 期間底層訊號為 long | 改成 `0.0` | 底層策略即使重新偏多，也要等風控冷卻期結束才恢復。 |
| risk-off 期滿 | 重設局部 high-water mark | 避免舊高點永久壓制策略，讓後續重新開始追蹤局部回撤。 |

## 主要參數

| 參數 | 預設 | CLI | 用途與調整判斷 |
|---|---:|---|---|
| `drawdown_threshold` | `0.20` | `--drawdown-risk-off-threshold` | 觸發 risk-off 的回撤門檻；太低會頻繁停用策略，太高可能等到大回撤後才反應。 |
| `risk_off_bars` | `60` | `--drawdown-risk-off-bars` | 觸發後維持 flat 的時間；越長越保守，但也越容易錯過反彈或新趨勢。 |

## 怎麼跑

精簡版：

```powershell
python tools\multi_stock_target_state_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --strategy absolute-momentum `
  --drawdown-risk-off
```

完整版：

```powershell
python tools\multi_stock_target_state_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --strategy absolute-momentum `
  --drawdown-risk-off `
  --drawdown-risk-off-threshold 0.25 `
  --drawdown-risk-off-bars 120 `
  --cost-multipliers-list 1,2,3 `
  --summary-json reports\generated\drawdown-risk-off.json `
  --summary-md reports\generated\drawdown-risk-off.md
```

## 股價走勢解說圖

![[assets/drawdown-risk-off-explainer.png]]

此圖借用趨勢持有示意：Drawdown Risk-Off 只在策略自身回撤後暫停曝險，不代表能避開所有下跌。

## 風險與限制

- 可能在回撤後才退出，錯過接下來反彈。
- 門檻太低會頻繁 risk-off，門檻太高可能沒有防護效果。
- 這是 per-symbol overlay，不等於 portfolio-level regime filter。

## 下一步

- 對 `threshold` 與 `risk_off_bars` 做小範圍 sweep，避免只因單一樣本好看就升級。
