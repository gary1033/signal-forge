---
title: ORB + Volume + VWAP
tags:
  - project/SignalForge
  - trading/strategy
  - trading/intraday
status: research
updated: 2026-05-24
repo_impl: C:\Projects\signal-forge\src\signal_forge\strategies\orb_volume_vwap.py
---

# ORB + Volume + VWAP

## 快速定位

| 問題 | 答案 |
|---|---|
| CLI 名稱 | `orb-volume-vwap` |
| 適用資料 | intraday OHLCV，timestamp 必須含時間 |
| 策略型態 | long-only 開盤區間突破 |
| 實作位置 | `src\signal_forge\strategies\orb_volume_vwap.py` |
| 參數入口 | `src\signal_forge\cli\strategy_options.py` |

### 術語速讀

- **Opening Range / OR**：開盤後前 N 分鐘形成的高低區間。
- **Breakout**：價格收盤突破 OR high。
- **Session VWAP**：從當日 session 起點開始累積的 VWAP。
- **Retest confirmation**：先突破，再回踩 OR high 後重新站回，才進場。
- **Signal window**：只接受 session 開始後指定分鐘內的新突破。

## 目前參數

這裡保留目前可重跑的主要參數。README 只放最短命令；要調參、複製完整命令或確認目前採用值時，以本表與本頁「如何運行」為準。

| 目前最佳回測設定 | 值 | 用途 |
|---|---:|---|
| `--hold-bars-per-day` | `5` | 最新 intraday ORB rerun 中相對最好，但 PF 仍小於 1。 |

| 參數 | 預設 | CLI | 用途與調整判斷 |
|---|---:|---|---|
| `opening_range_minutes` | `30` | `--orb-opening-range-minutes` | OR 建立期長度；太短會讓 OR high / low 太敏感，太長會錯過早盤突破。 |
| `session_start` | `09:30` | `--orb-session-start-hour` / `--orb-session-start-minute` | session 起點；台股、美股與期貨市場不同，不能沿用錯誤開盤時間。 |
| `session_end` | 策略 metadata | `--orb-session-end-hour` / `--orb-session-end-minute` | 報表用 regular-session 邊界；目前主要記錄研究假設，不等於已完成 forced-flat 出場。 |
| `session_timezone` | 策略 metadata | `--orb-session-timezone` | 報表用市場時區；用來避免跨市場資料把 session 解讀錯。 |
| `ema_window` | `20` | `--orb-ema-window` | EMA trend confirmation 的趨勢基線；太短會接近價格，太長可能讓早盤訊號暖機不足。 |
| retest | 關閉 | `--orb-retest-confirmation` | 突破後必須回踩再確認；降低假突破但會延後進場，也可能錯過不回踩的強勢行情。 |
| signal window | 關閉 | `--orb-signal-window-minutes` | 限制新 breakout 必須發生在 session 開始後 N 分鐘內；它不會平掉既有持倉。 |
| OR volume baseline | 關閉 | `--orb-use-opening-range-volume-baseline` | 量能改拿 breakout bar 對比 OR 期間平均量；比 rolling volume SMA 更貼近 ORB 語意。 |

## 如何運行

精簡版：

```powershell
$Csv5m = "data\processed\TWSE_2330_5M.csv"
python -m signal_forge.cli entry-edge --csv $Csv5m --strategy orb-volume-vwap
```

完整版：

```powershell
python -m signal_forge.cli entry-edge `
  --csv $Csv5m `
  --strategy orb-volume-vwap `
  --orb-opening-range-minutes 15 `
  --orb-session-start-hour 9 `
  --orb-session-start-minute 0 `
  --orb-session-end-hour 13 `
  --orb-session-end-minute 30 `
  --orb-session-timezone Asia/Taipei `
  --orb-vwap-slope-confirmation `
  --orb-ema-trend-confirmation `
  --orb-ema-window 20 `
  --orb-reject-ema-inside-range `
  --orb-signal-window-minutes 90 `
  --orb-min-range-pct 0.001 `
  --orb-max-range-pct 0.03 `
  --orb-min-breakout-pct 0.0005 `
  --orb-full-bar-above-range `
  --orb-min-breakout-body-pct 0.5 `
  --orb-fresh-breakout-from-or `
  --orb-use-opening-range-volume-baseline `
  --hold-bars-per-day 5 `
  --output-dir reports\generated `
  --run-name tsmc-orb-hold5
```

## 進場流程

| 狀態 / 條件 | 目標曝險 | 維護語意 |
|---|---:|---|
| 開盤區間尚未建立完成 | `0.0` | OR high / low 還在收集期，任何突破判斷都太早。 |
| timestamp 不含 intraday 時間 | `0.0` | ORB 依賴 session 時間；日線資料不能硬套 intraday 規則。 |
| close 未突破 OR high | `0.0` | 價格還在開盤區間內或下方，沒有 breakout entry。 |
| close 突破 OR high 但未站上 session VWAP | `0.0` | 突破位置不足，還要確認價格高於當日平均成交成本。 |
| 啟用量能條件但 breakout volume 不足 | `0.0` | 低量越線容易是假突破，先擋掉而不是追價。 |
| 啟用 retest，第一次突破後尚未回踩確認 | `0.0` | retest 模式下第一次突破只記錄狀態，等回踩後重新站回才進場。 |
| breakout 通過 OR、VWAP、量能與可選 refinement | `1.0` | 價格位置、平均成本、量能與結構條件同時通過，才接受 long。 |
| 新 session 開始 | 重設狀態 | 前一日 OR 與持倉狀態不能直接帶到下一個 session。 |

## 出場流程

新 session 開始時會重設 ORB 狀態；既有 intraday breakout 若進入下一個 session 會先回到 flat。目前 session end / timezone 是報表 metadata，還不是完整 forced-flat 出場系統。

## 它想捕捉的 edge

開盤初期通常是價格重新定價的主戰區。若 OR 建立完成後，價格收盤突破 OR high、站上 session VWAP，且突破 bar 伴隨量能確認，這個突破比單純穿越高點更有參與度。

這個版本仍是 same-session、close-confirmed、long-only 的研究骨架；它不是完整 intraday 交易系統，也沒有真實下單能力。

## 股價走勢解說圖

![[assets/orb-volume-vwap-trend-explainer.png]]

圖中藍色虛線代表 OR high，紫色線代表 session VWAP。只有價格正式突破 OR high、站上 VWAP 且量能放大時，才視為 long entry。此圖不是績效保證。

## 風險與限制

- 日線資料不能用來跑 ORB；timestamp 必須含 intraday 時間。
- 台股、美股、期貨與加密貨幣的 session 起點不同，不能共用同一組時間假設。
- 目前 session end / timezone 主要寫入 artifact metadata，不等於已完成 forced-flat 出場規則。
- ORB refinement 很多，新增前要確認它補到新資訊，而不是重複擋掉同一批突破。

### 後續優化方向

- 先確保 intraday CSV 與 market-clock metadata 可重現。
- 若要新增出場規則，先定義 session close、extended-hours 與 forced-flat 的 reporting contract。

## 最新回測註記（2026-05-21）

| 指標 | 數值 | 解讀 |
|---|---:|---|
| 最新 artifact | `reports\generated\tsmc-orb-rerun-20260521_hold_comparison.md` | 追溯 intraday ORB rerun。 |
| 樣本 | `TWSE_2330_5M.csv`，`2026-02-23` 到 `2026-05-21` | 只是一段 5 分 K intraday 檢查。 |
| 目前最佳設定 | `hold=5` | 測過持有期中相對最好。 |
| PF | `0.852` | 未達 PF `>1.20`。 |
| 交易數 | `24` | 樣本偏少，且 PF 不足。 |
| Win rate | `41.67%` | 沒有穩定勝率優勢。 |
| Max drawdown | `-5.44%` | 回撤不大，但報酬 edge 不成立。 |
| 刪減判斷 | `discard as current main candidate` | 保留 intraday artifact / session contract，不升級策略。 |
