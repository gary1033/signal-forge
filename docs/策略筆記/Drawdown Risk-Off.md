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

### 術語速讀

- **Proxy equity**：用策略自身目標曝險估算的單檔資金曲線。
- **High-water mark**：proxy equity 曾達到的最高點。
- **Risk-off bars**：觸發回撤後維持 flat 的 bar 數。

## 目前參數

這裡保留目前可重跑的主要參數。README 只放最短命令；要調參、複製完整命令或確認目前採用值時，以本表與本頁「如何運行」為準。

| 目前最佳回測設定 | 值 | 用途 |
|---|---:|---|
| `--drawdown-risk-off-threshold` | `0.25` | `20%/60` 已 discard 後保留的較可讀門檻。 |
| `--drawdown-risk-off-bars` | `120` | 目前較可讀的 risk-off 維持期。 |

| 參數 | 預設 | CLI | 用途與調整判斷 |
|---|---:|---|---|
| `drawdown_threshold` | `0.20` | `--drawdown-risk-off-threshold` | 觸發 risk-off 的回撤門檻；太低會頻繁停用策略，太高可能等到大回撤後才反應。 |
| `risk_off_bars` | `60` | `--drawdown-risk-off-bars` | 觸發後維持 flat 的時間；越長越保守，但也越容易錯過反彈或新趨勢。 |

## 如何運行

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

## 進場流程

| 判定點 | 輸出 | 維護語意 |
|---|---:|---|
| proxy equity 回撤未破門檻 | 保持底層訊號 | 策略自身尚未進入明確失效狀態，不干預底層進出場。 |
| 回撤達 `drawdown_threshold` | 啟動 risk-off | 從 high-water mark 回撤超過門檻時，視為需要暫停曝險。 |
| risk-off 期間底層訊號為 long | 改成 `0.0` | 底層策略即使重新偏多，也要等風控冷卻期結束才恢復。 |
| risk-off 期滿 | 重設局部 high-water mark | 避免舊高點永久壓制策略，讓後續重新開始追蹤局部回撤。 |

## 出場流程

觸發 risk-off 後，底層 long 會在指定 bars 內被壓成 flat；冷卻期結束後才恢復接收底層訊號。它是回撤後暫停，不是預測式逃頂。

## 它想捕捉的 edge

若單檔策略已從自身高點回撤超過門檻，短期內可能處於失效狀態。Drawdown Risk-Off 會暫停該檔非零曝險一段時間，測試是否能降低最差回撤。

## 股價走勢解說圖

![[assets/drawdown-risk-off-explainer.png]]

此圖借用趨勢持有示意：Drawdown Risk-Off 只在策略自身回撤後暫停曝險，不代表能避開所有下跌。

## 風險與限制

- 可能在回撤後才退出，錯過接下來反彈。
- 門檻太低會頻繁 risk-off，門檻太高可能沒有防護效果。
- 這是 per-symbol overlay，不等於 portfolio-level regime filter。

### 後續優化方向

- 對 `threshold` 與 `risk_off_bars` 做小範圍 sweep，避免只因單一樣本好看就升級。

## 最新回測註記（2026-05-24）

| 指標 | 數值 | 解讀 |
|---|---:|---|
| 最新 artifacts | `reports\generated\twse-target-state-absolute-momentum-ddriskoff25b120-20260524.md`、`reports\generated\twse-target-state-absolute-momentum-voltarget040-ddriskoff25b120-oos-20260524.md` | 追溯單獨 risk-off 與疊加 OOS。 |
| 目前參數 | `drawdown_threshold=0.25`、`risk_off_bars=120` | `20%/60` 已 discard。 |
| 1x 平均報酬 | `207.18%` | 比原始 absolute momentum 低。 |
| Beat B&H | `1/7` | 相對 benchmark 未改善。 |
| Avg excess | `-245.55%` | 主動績效仍落後。 |
| Worst MDD | `-46.95%` | 有降低部分回撤。 |
| 疊加 vol-target OOS Beat B&H | `0/7` | 樣本外沒有相對優勢。 |
| 疊加 vol-target OOS Avg excess | `-127.67%` | 樣本外仍落後。 |
| 刪減判斷 | `compare-only` | 保留 `25%/120` 研究，`20%/60` 不再作升級方向。 |
