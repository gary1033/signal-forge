---
title: Confluence Score
tags:
  - project/SignalForge
  - trading/strategy
  - trading/multi-factor
status: research
updated: 2026-05-20
repo_impl: C:\Projects\signal-forge\src\signal_forge\strategies\confluence_score.py
---

# Confluence Score

## 先懂這些詞

- **Confluence / 共振**：多個條件同時指向同一個方向。例如趨勢偏多、價格在均線上方、動能也偏強，就叫偏多條件共振。
- **Score / 分數**：把每個條件轉成加分或扣分。分數越高，代表越多條件偏多；分數越低，代表越多條件偏空。
- **Threshold / 門檻**：分數要高到什麼程度才行動。這個策略預設 `threshold=3.0`，代表至少要累積到 3 分才做多。
- **SMA（Simple Moving Average，簡單移動平均）**：最近 N 天收盤價平均。`fast_sma` 比較短、反應較快；`slow_sma` 比較長、反應較慢。
- **VWAP（Volume Weighted Average Price，成交量加權平均價）**：成交量越大的價格權重越高，用來近似一段期間內市場主要成交成本。
- **Rolling VWAP / 滾動 VWAP**：每一天只看最近 N 天重新計算 VWAP。這裡用來判斷價格是在近期成交成本上方還是下方。
- **RSI（Relative Strength Index，相對強弱指標）**：衡量近期上漲與下跌力量的動能指標。這份策略用 `RSI >= 55` 當偏多動能，`RSI <= 45` 當偏空動能。
- **Volume confirms / 量能確認**：如果今天成交量高於近期平均，且價格上漲，就視為上漲有量能支持；如果放量下跌，就視為偏空確認。
- **`target_position` / 目標部位**：策略想要的持倉狀態。`1.0` 代表應該持有多單，`0.0` 代表空手，`-1.0` 代表做空；目前 CLI 固定 long-only，所以只看 `1.0` 和 `0.0`。
- **Warmup / 暖機期**：資料還不夠算 SMA、RSI、VWAP 或平均成交量的期間。

## 策略假設

Confluence Score 是多條件打分策略。它不依賴單一指標，而是把趨勢、價格位置、VWAP、RSI 動能與量能確認加總成 score。只有當多個條件同時偏多，分數達到 threshold，才產生做多訊號。

策略假設是：單一指標很容易誤判，但多個互補條件同時成立時，進場品質應更高。風險是因子越多，越容易變成主觀調參或 overfit；score 高只代表條件共振，不代表一定有 edge。

## 進出場條件

warmup 階段若任一指標尚未形成，輸出 `target_position=0.0`，reason 為 `warmup`。

形成指標後，每根 bar 依下列條件加減分：

- `fast_sma > slow_sma`：`+1`，reason 加 `trend_up`；否則 `-1`，reason 加 `trend_down`。
- `close > slow_sma`：`+1`，reason 加 `above_slow_sma`；否則 `-1`，reason 加 `below_slow_sma`。
- `close > vwap`：`+1`，reason 加 `above_vwap`；否則 `-1`，reason 加 `below_vwap`。
- `rsi >= 55`：`+1`，reason 加 `momentum_positive`。
- `rsi <= 45`：`-1`，reason 加 `momentum_negative`。
- 若當日量大於 fast-window 平均量，且收盤高於前一日收盤：`+1`，reason 加 `volume_confirms_up`。
- 若當日量大於 fast-window 平均量，且收盤低於前一日收盤：`-1`，reason 加 `volume_confirms_down`。

當 `score >= threshold` 時，`target_position=1.0`。實作在 `allow_short=True` 且 `score <= -threshold` 時可做空；目前 CLI 固定 long-only，所以不啟用 short。

## 主要參數

- `fast_window` / CLI `--fast-window`：預設 `20`。
- `slow_window` / CLI `--slow-window`：預設 `200`。
- `rsi_window` / CLI `--rsi-window`：預設 `14`。
- `vwap_window` / CLI `--vwap-window`：預設 `20`。
- `threshold` / CLI `--threshold`：預設 `3.0`。
- `allow_short`：實作預設支援，但 CLI 目前固定 `False`。
- entry-edge 評估：訊號於 bar close 後確認，下一根 open 進場，固定持有 `hold_bars_per_day=1` 後以 exit bar close 出場。

## 股價走勢解說圖

![[assets/confluence-score-trend-explainer.png]]

圖中用合成走勢說明：主圖呈現 price、SMA 與 VWAP；下方面板顯示 score bars。只有當多個條件共振，使 score 超過門檻時，才標示 entry。此圖為 image generation 產生的教學示意圖，不是真實市場資料，也不代表績效保證。

## 風險與限制

- 因子越多，越容易 overfit。
- 權重目前都是固定 `+1/-1`，沒有經過嚴格因子貢獻驗證。
- threshold 若靠單一標的調整，容易變成資料配適。
- 交易頻率較高，對成本與滑價更敏感。
- 目前不含停損、停利、部位管理或 regime filter。

## 下一步

- 檢查 score 組成，拆解哪些 reason 對勝率或 PF 有實際貢獻。
- 測試不同 threshold 與交易頻率、最大回撤之間的關係。
- 將 score 分布寫入 backtest artifact，讓多因子訊號更容易稽核。
