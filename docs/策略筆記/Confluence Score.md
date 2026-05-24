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

### 術語速讀

- **Confluence**：多個條件同時支持同一方向。
- **Score threshold**：分數達到門檻才進場。
- **RSI**：衡量近期漲跌強弱的震盪指標。
- **VWAP / SMA**：用平均成本與均線確認價格位置。

## 目前參數

這裡保留目前可重跑的主要參數。README 只放最短命令；要調參、複製完整命令或確認目前採用值時，以本表與本頁「如何運行」為準。

| 目前最佳回測設定 | 值 | 用途 |
|---|---:|---|
| `--hold-bars-per-day` | `10` | 最新 entry-edge 強錨點。 |
| `--signal-cooldown-bars` | `10` | 降低重複 entry overlap 的目前可讀設定。 |

| 參數 | 預設 | CLI | 用途與調整判斷 |
|---|---:|---|---|
| `fast_window` | `20` | `--fast-window` | 短期趨勢 component；越短越容易補捉早期轉強，也越容易把雜訊加分。 |
| `slow_window` | `50` | `--slow-window` | 中期趨勢 component；用來當快線與價格位置的共同基準。 |
| `rsi_window` | `14` | `--rsi-window` | 動能與過熱 component；調整時要觀察它是否真的補充新資訊，而不是重複趨勢條件。 |
| `vwap_window` | `20` | `--vwap-window` | 平均成交成本 component；調太短會接近價格本身，調太長會讓成本基準落後。 |
| `threshold` | `3.0` | `--threshold` | 進場分數門檻；提高會減少交易並要求更多條件共振，降低會讓策略更接近泛用趨勢追蹤。 |

## 如何運行

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

## 進場流程

| 條件類型 | 加分語意 | 維護語意 |
|---|---|---|
| 快均線高於慢均線 | 趨勢偏多 | 檢查短期趨勢是否真的優於中期基準，避免單純看當根 K 棒。 |
| close 高於 slow SMA | 價格仍在中期趨勢上方 | 即使快線轉強，也要求現價沒有跌回主要趨勢基準下方。 |
| close 高於 rolling VWAP | 價格站上平均成交成本 | 用成交量加權成本確認價格位置，不只靠均線。 |
| RSI 未過熱且偏強 | 避免只追極端過熱 | RSI 用來避免在過熱區硬追，也避免弱勢反彈被誤判成趨勢。 |
| 成交量支持 | 訊號有參與度 | 量能條件用來確認訊號不是低量漂移，但不能單獨當作進場理由。 |

分數達到 `threshold` 時 `target_position=1.0`，否則維持 `0.0`。

## 出場流程

分數低於 `threshold` 時輸出 flat；Phase 1 long-only 不處理 short。若搭配 `Signal Cooldown`，cooldown 只封鎖新的 entry，不會把已接受的持倉強制平倉。

## 它想捕捉的 edge

單一指標很容易被雜訊騙到；如果趨勢、價格位置、VWAP、RSI 與量能方向同時偏多，訊號品質可能比單一 SMA 或單一 VWAP 更穩。這個策略把多個條件加總成分數，達門檻才 long。

## 股價走勢解說圖

![[assets/confluence-score-trend-explainer.png]]

圖中用示意走勢說明：多個條件同時偏多時才進場，避免只靠單一指標追價。此圖不是績效保證。

## 風險與限制

- 條件越多不一定越好，可能只是把同一類趨勢訊號重複加權。
- `threshold` 太低會變成泛用趨勢策略，太高會造成交易數不足。
- 需要用 [[Signal Cooldown]] 檢查重複訊號是否只是同一段行情被反覆計算。

### 後續優化方向

- 先用多持有期比較確認訊號是否只在特定 hold bars 有效。
- 若要升級條件，先檢查每個 score component 是否真的補到新資訊。

## 最新回測註記（2026-05-24）

| 指標 | 數值 | 解讀 |
|---|---:|---|
| 最新 artifacts | `reports\generated\twse-multistock-baseline-20260523.md`、`reports\generated\twse-target-state-confluence-coststress-20260524.md` | 分別檢查 entry-edge 與完整持倉。 |
| Entry-edge 目前最佳設定 | `hold=10` | entry 訊號在 10 bars 較可讀。 |
| Entry-edge Aggregate PF | `2.299` | 單看 entry-edge 很強。 |
| Entry-edge 通過股票 | `7/7` | 跨股票 entry-edge 穩定。 |
| Entry-edge 交易數 | `349` | 樣本量可讀。 |
| Target-state 平均報酬 | `176.57%` | 絕對報酬不差。 |
| Beat B&H | `0/7` | 完整持倉輸給 buy-and-hold。 |
| Avg excess | `-276.16%` | 主動績效不足。 |
| Worst MDD | `-51.40%` | 完整持倉風險仍大。 |
| 刪減判斷 | `compare-only` | 保留為 entry-edge / wrapper 測試底層，不直接升級。 |
