---
title: Confluence Score
tags:
  - project/SignalForge
  - trading/strategy
  - trading/confluence
status: research
updated: 2026-05-24
repo_impl: C:\Projects\signal-forge\src\signal_forge\strategies\confluence_score.py
---

# Confluence Score

## 快速定位

| 問題 | 答案 |
|---|---|
| CLI 名稱 | `confluence-score` |
| 適用資料 | 日線 OHLCV |
| 策略型態 | long-only 多條件打分 |
| 實作位置 | `src\signal_forge\strategies\confluence_score.py` |
| 參數入口 | `src\signal_forge\cli\strategy_options.py` |

## 先懂這些詞

- **Confluence**：多個條件同時支持同一方向。
- **Score threshold**：分數達到門檻才進場。
- **RSI**：衡量近期漲跌強弱的震盪指標。
- **VWAP / SMA**：用平均成本與均線確認價格位置。

## 策略假設

單一指標很容易被雜訊騙到；如果趨勢、價格位置、VWAP、RSI 與量能方向同時偏多，訊號品質可能比單一 SMA 或單一 VWAP 更穩。這個策略把多個條件加總成分數，達門檻才 long。

## 進出場規則

| 條件類型 | 加分語意 |
|---|---|
| 快均線高於慢均線 | 趨勢偏多 |
| close 高於 slow SMA | 價格仍在中期趨勢上方 |
| close 高於 rolling VWAP | 價格站上平均成交成本 |
| RSI 未過熱且偏強 | 避免只追極端過熱 |
| 成交量支持 | 訊號有參與度 |

分數達到 `threshold` 時 `target_position=1.0`，否則維持 `0.0`。

## 主要參數

| 參數 | 預設 | CLI | 用途 |
|---|---:|---|---|
| `fast_window` | `20` | `--fast-window` | 短期趨勢 |
| `slow_window` | `50` | `--slow-window` | 中期趨勢 |
| `rsi_window` | `14` | `--rsi-window` | RSI 視窗 |
| `vwap_window` | `20` | `--vwap-window` | rolling VWAP 視窗 |
| `threshold` | `3.0` | `--threshold` | 進場分數門檻 |

## 怎麼跑

精簡版：

```powershell
$Csv = "data\processed\TWSE_2330_1D.csv"
python -m signal_forge.cli entry-edge --csv $Csv --strategy confluence-score
```

完整版：

```powershell
python -m signal_forge.cli entry-edge `
  --csv $Csv `
  --strategy confluence-score `
  --fast-window 20 `
  --slow-window 50 `
  --rsi-window 14 `
  --vwap-window 20 `
  --threshold 3.0 `
  --signal-cooldown-bars 10 `
  --hold-bars-list 1,3,5,10 `
  --output-dir reports\generated `
  --run-name tsmc-confluence-cooldown10
```

## 股價走勢解說圖

![[assets/confluence-score-trend-explainer.png]]

圖中用示意走勢說明：多個條件同時偏多時才進場，避免只靠單一指標追價。此圖不是績效保證。

## 風險與限制

- 條件越多不一定越好，可能只是把同一類趨勢訊號重複加權。
- `threshold` 太低會變成泛用趨勢策略，太高會造成交易數不足。
- 需要用 [[Signal Cooldown]] 檢查重複訊號是否只是同一段行情被反覆計算。

## 下一步

- 先用多持有期比較確認訊號是否只在特定 hold bars 有效。
- 若要升級條件，先檢查每個 score component 是否真的補到新資訊。
