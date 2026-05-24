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

## 先懂這些詞

- **Opening Range / OR**：開盤後前 N 分鐘形成的高低區間。
- **Breakout**：價格收盤突破 OR high。
- **Session VWAP**：從當日 session 起點開始累積的 VWAP。
- **Retest confirmation**：先突破，再回踩 OR high 後重新站回，才進場。
- **Signal window**：只接受 session 開始後指定分鐘內的新突破。

## 策略假設

開盤初期通常是價格重新定價的主戰區。若 OR 建立完成後，價格收盤突破 OR high、站上 session VWAP，且突破 bar 伴隨量能確認，這個突破比單純穿越高點更有參與度。

這個版本仍是 same-session、close-confirmed、long-only 的研究骨架；它不是完整 intraday 交易系統，也沒有真實下單能力。

## 進出場規則

| 狀態 / 條件 | 目標曝險 |
|---|---:|
| 開盤區間尚未建立完成 | `0.0` |
| timestamp 不含 intraday 時間 | `0.0` |
| close 未突破 OR high | `0.0` |
| close 突破 OR high 但未站上 session VWAP | `0.0` |
| 啟用量能條件但 breakout volume 不足 | `0.0` |
| 啟用 retest，第一次突破後尚未回踩確認 | `0.0` |
| breakout 通過 OR、VWAP、量能與可選 refinement | `1.0` |
| 新 session 開始 | 重設狀態 |

## 主要參數

| 參數 | 預設 | CLI | 用途 |
|---|---:|---|---|
| `opening_range_minutes` | `30` | `--orb-opening-range-minutes` | OR 建立期 |
| `session_start` | `09:30` | `--orb-session-start-hour` / `--orb-session-start-minute` | session 起點 |
| `session_end` | 策略 metadata | `--orb-session-end-hour` / `--orb-session-end-minute` | 報表用 regular-session 邊界 |
| `session_timezone` | 策略 metadata | `--orb-session-timezone` | 報表用市場時區 |
| `ema_window` | `20` | `--orb-ema-window` | EMA trend confirmation |
| retest | 關閉 | `--orb-retest-confirmation` | 等回踩再確認 |
| signal window | 關閉 | `--orb-signal-window-minutes` | 限制新 breakout 時間 |
| OR volume baseline | 關閉 | `--orb-use-opening-range-volume-baseline` | 用 OR 平均量能作 breakout baseline |

## 怎麼跑

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
  --hold-bars-per-day 6 `
  --output-dir reports\generated `
  --run-name tsmc-orb-full
```

## 股價走勢解說圖

![[assets/orb-volume-vwap-trend-explainer.png]]

圖中藍色虛線代表 OR high，紫色線代表 session VWAP。只有價格正式突破 OR high、站上 VWAP 且量能放大時，才視為 long entry。此圖不是績效保證。

## 風險與限制

- 日線資料不能用來跑 ORB；timestamp 必須含 intraday 時間。
- 台股、美股、期貨與加密貨幣的 session 起點不同，不能共用同一組時間假設。
- 目前 session end / timezone 主要寫入 artifact metadata，不等於已完成 forced-flat 出場規則。
- ORB refinement 很多，新增前要確認它補到新資訊，而不是重複擋掉同一批突破。

## 下一步

- 先確保 intraday CSV 與 market-clock metadata 可重現。
- 若要新增出場規則，先定義 session close、extended-hours 與 forced-flat 的 reporting contract。
