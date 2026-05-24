---
title: Signal Cooldown
tags:
  - project/SignalForge
  - trading/strategy
  - trading/filter
status: research
updated: 2026-05-24
repo_impl: C:\Projects\signal-forge\src\signal_forge\strategies\signal_cooldown.py
---

# Signal Cooldown

## 快速定位

| 問題 | 答案 |
|---|---|
| CLI 參數 | `--signal-cooldown-bars` |
| 是否為獨立 `--strategy` | 否，這是 wrapper |
| 適用工具 | `entry-edge`、`phase`、`tools\multi_stock_target_state_sweep.py` |
| 實作位置 | `src\signal_forge\strategies\signal_cooldown.py` |

## 先懂這些詞

- **Cooldown**：接受一次新進場後，暫時封鎖後續新進場。
- **New long entry**：目標曝險從非 long 變成 long。
- **Overlap**：同一段行情反覆產生很接近的 entry 訊號。

## 策略假設

若底層策略在同一段行情裡密集重複進場，entry-edge 結果可能被高度重疊的訊號放大。Signal Cooldown 用固定 bar 數封鎖新進場，檢查策略 edge 是否仍然存在。

## 控制規則

| 判定點 | 輸出 | 維護語意 |
|---|---:|---|
| 沒有新 long entry | 保持原訊號 | Cooldown 不處理 flat、出場或既有持倉延續，只處理新進場。 |
| 新 long entry 且不在 cooldown 內 | 保留 long，啟動 cooldown | 第一個被接受的 entry 代表一段新行情開始，後續 N 根 bar 進入防重複狀態。 |
| 新 long entry 但仍在 cooldown 內 | `0.0` | 同一段行情太密集的新 entry 會被視為 overlap，改成 flat。 |
| 已持有中的延續訊號 | 保持原訊號 | 已經接受的 long 不會因 cooldown 被強制平倉，避免把去重工具誤用成出場規則。 |

## 主要參數

| 參數 | 預設 | CLI | 用途與調整判斷 |
|---|---:|---|---|
| `cooldown_bars` | 無預設，需手動指定 | `--signal-cooldown-bars` | 接受 long entry 後封鎖幾根 bar；值越大越能降低 overlap，但也越可能錯過新的獨立機會。 |

## 怎麼跑

精簡版：

```powershell
python -m signal_forge.cli entry-edge `
  --csv data\processed\TWSE_2330_1D.csv `
  --strategy confluence-score `
  --signal-cooldown-bars 10
```

完整版：

```powershell
python tools\multi_stock_target_state_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --strategy confluence-score `
  --signal-cooldown-bars 10 `
  --cost-multipliers-list 1,2,3 `
  --summary-json reports\generated\confluence-cooldown-target-state.json `
  --summary-md reports\generated\confluence-cooldown-target-state.md
```

## 股價走勢解說圖

![[assets/signal-cooldown-explainer.png]]

此圖借用多條件訊號示意：Cooldown 只處理重複 entry 的間隔，不代表績效保證。

## 風險與限制

- Cooldown 太短可能沒有實質效果，太長可能錯過新的獨立行情。
- 它不會自動停損，也不會改變既有持倉延續。
- 這是訊號去重工具，不是 alpha 來源。

## 下一步

- 對同一策略比較 `0 / 5 / 10 / 20` bars，確認 edge 是否只來自密集重複訊號。
