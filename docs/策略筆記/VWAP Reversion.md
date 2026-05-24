---
title: VWAP Reversion
tags:
  - project/SignalForge
  - trading/strategy
  - trading/vwap
status: research
updated: 2026-05-24
repo_impl: C:\Projects\signal-forge\src\signal_forge\strategies\vwap_reversion.py
---

# VWAP Reversion

## 快速定位

| 問題 | 答案 |
|---|---|
| CLI 名稱 | `vwap-reversion` |
| 適用資料 | 日線 OHLCV |
| 策略型態 | long-only 均值回歸 baseline |
| 實作位置 | `src\signal_forge\strategies\vwap_reversion.py` |
| 參數入口 | `src\signal_forge\cli\strategy_options.py` |

## 先懂這些詞

- **VWAP**：成交量加權平均價格，用價格和量一起估算市場平均成交成本。
- **Z-score**：目前價格偏離 rolling VWAP 的標準化程度。
- **Regime filter**：只在價格仍高於較長均線時接受回歸訊號，避免在下跌趨勢中接刀。

## 策略假設

當價格短期跌到 rolling VWAP 下方太多，但整體趨勢尚未破壞時，價格可能回到平均成交成本附近。這個策略用來檢查「跌深回彈」是否有足夠 entry edge。

## 進出場規則

| 判定點 | 目標曝險 | 維護語意 |
|---|---:|---|
| VWAP 或標準差尚未暖機 | `0.0` | rolling VWAP 與偏離幅度還不可信時，不把早期資料硬解讀成跌深訊號。 |
| `z_score <= -entry_z` | `1.0` | 價格低於 VWAP 達指定標準化距離，才視為足夠跌深的 long candidate。 |
| 持有中且 `z_score >= -exit_z` | `0.0` | 價格已回到 VWAP 附近，均值回歸假設完成，退出而不是繼續當趨勢單持有。 |
| 啟用 regime filter 且 close 低於 regime SMA | `0.0` | 即使跌深，也先擋掉處於下跌 regime 的接刀訊號。 |

## 主要參數

| 參數 | 預設 | CLI | 用途與調整判斷 |
|---|---:|---|---|
| `vwap_window` | `20` | `--vwap-window` | rolling VWAP 與偏離標準差的計算範圍；太短會讓平均成本跟著價格劇烈晃動，太長會讓回歸訊號反應慢。 |
| `entry_z` | `1.5` | `--entry-z` | 進場偏離門檻；數值越大訊號越少且更極端，數值越小交易數增加但假跌深也會增加。 |
| `exit_z` | `0.25` | `--exit-z` | 出場靠近 VWAP 的程度；越接近 0 越要求回到均值附近，越大則較早離場。 |
| `vwap_regime_filter` | `False` | `--vwap-regime-filter` | 可選接刀防線；啟用後只有 close 仍在 regime SMA 上方才接受 long。 |
| `vwap_regime_window` | `50` | `--vwap-regime-window` | regime SMA 的視窗；調大會更慢確認趨勢，調小會更容易頻繁切換 regime。 |

## 怎麼跑

精簡版：

```powershell
$Csv = "data\processed\TWSE_2330_1D.csv"
python -m signal_forge.cli entry-edge --csv $Csv --strategy vwap-reversion
```

完整版：

```powershell
python -m signal_forge.cli entry-edge `
  --csv $Csv `
  --strategy vwap-reversion `
  --vwap-window 20 `
  --entry-z 1.5 `
  --exit-z 0.25 `
  --vwap-regime-filter `
  --vwap-regime-window 50 `
  --hold-bars-per-day 1 `
  --output-dir reports\generated `
  --run-name tsmc-vwap-regime
```

## 股價走勢解說圖

![[assets/vwap-reversion-trend-explainer.png]]

圖中用示意走勢說明：價格低於 VWAP 太多時才進場，回到 VWAP 附近時離場。此圖不是績效保證。

## 風險與限制

- 強下跌趨勢中，價格可能一直低於 VWAP，均值回歸會變成接刀。
- 日線 VWAP 是 rolling proxy，不等於 intraday session VWAP。
- `entry_z` 越大，交易數越少；越小，訊號越多但假訊號也可能上升。

## 下一步

- 若回撤太集中，先加 `--vwap-regime-filter` 比直接調小 `entry_z` 更容易解釋。
- 若要測量能確認，搭配 [[Volume Filter]]。
