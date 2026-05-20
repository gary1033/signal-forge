---
title: VWAP Reversion
tags:
  - project/SignalForge
  - trading/strategy
  - trading/mean-reversion
status: research
updated: 2026-05-20
repo_impl: C:\Projects\signal-forge\src\signal_forge\strategies\vwap_reversion.py
---

# VWAP Reversion

## 先懂這些詞

- **VWAP（Volume Weighted Average Price，成交量加權平均價）**：不是單純平均價格，而是「成交量越大的價格，權重越高」。白話說，它近似市場在這段期間內主要成交的平均成本。
- **Rolling VWAP / 滾動 VWAP**：每一天只看最近 N 天重新計算 VWAP。例如 `window=20` 時，今天的 rolling VWAP 只看最近 20 天資料；明天會往前滑一天，再用新的最近 20 天重算。它不是從某個固定起點一路累積的 anchored VWAP。
- **Mean reversion / 均值回歸**：價格離某條平均線太遠後，可能往平均線靠回來。這裡的平均線就是 rolling VWAP。
- **Rolling standard deviation / 滾動標準差**：用最近 N 天價格計算波動程度。波動越大，標準差越大；波動越小，標準差越小。
- **z-score / 標準化偏離程度**：用「價格離 VWAP 多遠」除以「最近波動程度」。`z_score=-1.5` 代表價格低於 VWAP，而且偏離幅度大約是 1.5 個標準差。
- **Band / 偏離帶**：用 VWAP 加減 z-score 門檻畫出的上下界。價格跌破下方 band，代表相對 VWAP 跌得太遠；價格漲破上方 band，代表漲得太遠。
- **`entry_z` / 進場門檻**：跌深到什麼程度才進場。預設 `1.5` 表示 `z_score <= -1.5` 才做多。
- **`exit_z` / 出場門檻**：價格回到 VWAP 附近到什麼程度就離場。預設 `0.25` 表示 `abs(z_score) <= 0.25` 時視為已經回到平均附近。
- **`target_position` / 目標部位**：策略想要的持倉狀態。`1.0` 代表應該持有多單，`0.0` 代表空手，`-1.0` 代表做空；目前 CLI 固定 long-only，所以只看 `1.0` 和 `0.0`。
- **Warmup / 暖機期**：資料還不夠算 rolling VWAP 或 rolling standard deviation 的期間。
- **Regime filter / 市場狀態濾網**：先判斷目前是不是適合做均值回歸的市場環境。這份策略的可選濾網用 `close >= SMA(regime_window)` 判斷是否允許新的做多進場。
- **Regime SMA / 市場狀態均線**：用收盤價計算的長一點 SMA。價格低於這條線時，代表可能處於下跌趨勢，跌深不一定會快速反彈。
- **相對成交量 / Relative volume**：把今天成交量和近期平均量比較。可選成交量過濾器用 `volume >= sma(volume, 20) * 1.2` 進一步要求跌深訊號出現時也有足夠量能。

## 策略假設

VWAP Reversion 是均值回歸策略。它把 rolling VWAP 視為一段期間內的成交量加權平均成本，並用 rolling standard deviation 把價格偏離程度轉成 z-score。

策略假設是：當價格短期跌到 VWAP 下方太遠，市場可能出現回到平均成本附近的反彈。這種假設更適合震盪或短期過度反應環境；若市場處於強趨勢下跌，跌破 VWAP band 可能不是反彈機會，而是趨勢延續。

因此這個策略現在可以選擇加上一層簡單的 trend regime filter：只有在 `close >= SMA(regime_window)` 時，才允許新的 long entry。這個濾網不是成交量分析，也不是完整風控；它只是先排除價格低於長期均線時的均值回歸進場。

## 進出場條件

- warmup：rolling VWAP 或 rolling std 尚未形成、或 std 為 0 時，`target_position=0.0`，reason 為 `warmup`。
- 做多：`z_score <= -entry_z` 時，`target_position=1.0`，reason 為 `price_below_vwap_band`。
- 可選 regime filter：啟用 `--vwap-regime-filter` 後，只有新的 long entry 會被檢查；若 regime SMA 尚未形成，reason 為 `regime_warmup`；若 `close < regime_sma`，`target_position=0.0`，reason 為 `regime_downtrend_blocked`。
- 做空：實作在 `allow_short=True` 時，`z_score >= entry_z` 會設為 `target_position=-1.0`，reason 為 `price_above_vwap_band`；目前 CLI 固定 long-only，所以不啟用。
- 出場：`abs(z_score) <= exit_z` 時，`target_position=0.0`，reason 為 `price_reverted_to_vwap`。
- 其他狀態：維持上一個 target，reason 為 `hold`。

Regime filter 只阻擋從空手進入多單，不會因為價格跌破 regime SMA 就強制把既有多單歸零。已經持有時，仍由原本的 `exit_z` 或 `hold` 邏輯決定狀態。

可選的成交量過濾器是外層 wrapper，不改 VWAP Reversion 的 z-score 判斷。啟用 `--volume-filter` 時，原策略若輸出 positive target，但當日成交量未達 `20` 日均量的 `1.2` 倍，wrapper 會把 target 改成 `0.0`。

## 主要參數

- `window` / CLI `--vwap-window`：預設 `20`。
- `entry_z` / CLI `--entry-z`：預設 `1.5`。
- `exit_z` / CLI `--exit-z`：預設 `0.25`。
- `allow_short`：實作預設支援，但 CLI 目前固定 `False`。
- `regime_filter` / CLI `--vwap-regime-filter`：預設關閉。啟用時，新的 long entry 必須滿足 `close >= sma(close, regime_window)`。
- `regime_window` / CLI `--vwap-regime-window`：預設 `50`。
- 可選成交量過濾器：CLI 使用 `--volume-filter --volume-window 20 --volume-multiplier 1.2`，實作位置是 `C:\Projects\signal-forge\src\signal_forge\strategies\volume_filter.py`。
- entry-edge 評估：訊號於 bar close 後確認，下一根 open 進場，固定持有 `hold_bars_per_day=1` 後以 exit bar close 出場。

## 股價走勢解說圖

![[assets/vwap-reversion-trend-explainer.png]]

圖中用合成走勢說明：價格跌到下方 VWAP band 外側時產生 long 訊號；價格回到 VWAP 附近時轉成 exit。此圖為 image generation 產生的教學示意圖，不是真實市場資料，也不代表績效保證。

## 風險與限制

- 強趨勢下跌時可能反向接刀。
- volume 品質會直接影響 VWAP 解讀。
- 放量跌深不一定是反彈訊號，也可能代表賣壓正在放大；成交量過濾器可能讓均值回歸策略更常接到趨勢延續。
- rolling VWAP 只是近似成本線，與 anchored VWAP 不同。
- regime filter 只用 `close >= SMA`，能排除部分下跌趨勢，但不能辨識所有市場狀態，也不是停損。
- 一日持有期可能太短，無法觀察完整回歸路徑。
- 目前不含停損、停利或波動度自適應參數。

## 下一步

- 比較未啟用與啟用 `--vwap-regime-filter` 的 entry-edge 結果，確認簡單趨勢濾網是否真的減少反向接刀。
- 比較成交量過濾器與趨勢 regime filter 的交互效果，避免把放量下跌誤當成反彈確認。
- 測試不同 `entry_z` / `exit_z` 與 `hold_bars_per_day`。
- 比較 rolling VWAP 與 anchored VWAP 的研究價值。
