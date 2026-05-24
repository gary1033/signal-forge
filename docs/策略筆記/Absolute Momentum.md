---
title: Absolute Momentum
tags:
  - project/SignalForge
  - trading/strategy
  - trading/momentum
  - trading/trend
status: research
updated: 2026-05-24
repo_impl: C:\Projects\signal-forge\src\signal_forge\strategies\absolute_momentum.py
---

# Absolute Momentum

## 先懂這些詞

- **Absolute Momentum / 絕對動能**：把現在價格和過去某一天價格相比。如果現在價格高於過去價格，代表這段期間報酬為正；如果低於過去價格，代表動能為負。
- **Momentum window / 動能回看期**：用來比較「今天 close」和「幾天前 close」的天數。SignalForge 第一版預設 `126` 根日線，約半年交易日。
- **Trend SMA / 趨勢均線**：用較長期的簡單移動平均判斷價格是否仍在長期趨勢上方。第一版預設 `200` 根日線。
- **Trend filter / 趨勢濾網**：只在價格站上長期均線時允許做多，避免只因短期反彈就追進長期下跌中的標的。
- **Long-only / 只做多**：策略只輸出 `1.0` 或 `0.0`，不做放空。
- **Warmup / 暖機期**：資料不足以計算動能或 SMA 時，策略保持空手。
- **Volatility target / 波動目標**：用最近一段 close-to-close 報酬估算 realized volatility；若當下波動高於目標年化波動，就把 `target_position` 從 `1.0` 縮小到較低曝險。SignalForge 第一版只降曝險，不加槓桿。

## 策略假設

Absolute Momentum 是長期趨勢持有候選。它假設如果一檔股票在中期回看期內報酬為正，且目前收盤價仍高於長期趨勢均線，該股票比較可能維持偏多狀態；反之則應降低曝險或保持空手。

這個策略用來檢查一個問題：SignalForge 目前的 `confluence-score + hold=10 + signal_cooldown_bars=10` 能降低回撤，但明顯犧牲強趨勢 upside；絕對動能是否能用更長期的 target-state 持有改善相對 buy-and-hold 的落後幅度。

## 進出場條件

SignalForge 第一版使用 deterministic close-confirmed 規則：

- `index < momentum_window` 或 `trend_sma` 尚未算出時，保持空手，reason 是 `warmup`。
- `close / close[momentum_window bars ago] - 1 <= 0` 時，保持空手，reason 是 `absolute_momentum_negative`。
- 中期報酬為正但 `close <= trend_sma` 時，保持空手，reason 是 `trend_filter_blocked`。
- 中期報酬為正且 `close > trend_sma` 時，輸出 `target_position = 1.0`，reason 是 `absolute_momentum_long`。

| 條件 | `target_position` | reason |
|---|---:|---|
| 動能或趨勢均線尚未可計算 | `0.0` | `warmup` |
| 回看報酬小於或等於 0 | `0.0` | `absolute_momentum_negative` |
| 回看報酬為正，但價格未站上長期 SMA | `0.0` | `trend_filter_blocked` |
| 回看報酬為正，且價格站上長期 SMA | `1.0` | `absolute_momentum_long` |

可選風控 overlay：

- `VolatilityTargetStrategy` 不改變是否進場的判斷；只有在底層策略已經輸出非零 target 時，根據最近 realized volatility 調整曝險大小。
- 若 realized volatility 樣本不足，overlay 保持空手，reason 是 `vol_target_warmup`。
- 若 realized volatility 低於目標，曝險最多維持原本的 `1.0`；不把 `target_position` 放大到超過原策略。
- 若 realized volatility 高於目標，`target_position = 原始 target_position * target_annual_volatility / realized_annual_volatility`，並受到 `max_scale` 上限限制。

## 小例子

假設教學參數是 `momentum_window=2`、`trend_window=3`：

| Day | Close | 2 日回看報酬 | 3 日 SMA | 狀態 |
|---:|---:|---:|---:|---|
| 1 | 10 | - | - | warmup |
| 2 | 11 | - | - | warmup |
| 3 | 12 | `20%` | `11` | 動能為正且站上 SMA，持有多單 |
| 4 | 11 | `0%` | `11.33` | 動能不再為正，空手 |
| 5 | 13 | `8.33%` | `12` | 動能為正且站上 SMA，重新持有多單 |

## 主要參數

- `momentum_window`：預設 `126`。在 CLI / factory 中用 `--fast-window` 覆寫。
- `trend_window`：預設 `200`。在 CLI / factory 中用 `--slow-window` 覆寫。
- `allow_short`：不支援。第一版明確拒絕 short mode。
- entry-edge 評估：仍使用 SignalForge Phase 1 的 close signal、next open entry、固定 hold bars。
- 完整持倉檢查：使用 `tools\multi_stock_target_state_sweep.py` 做 close-to-close target exposure、cost stress 與 benchmark-relative 檢查。
- `volatility-target` overlay：目前研究設定使用 `lookback_bars=20`、`min_observations=20`，比較 `target_annual_volatility=0.25/0.30/0.35/0.40`，`max_scale=1.0`。

## 股價走勢解說圖

![[assets/absolute-momentum-trend-explainer.png]]

圖中用合成走勢說明：價格需要同時滿足「中期報酬為正」與「站上長期 SMA」才進入 long 狀態；跌破趨勢或動能轉負時回到空手。此圖為本地生成的教學示意圖，不是真實市場資料，也不代表績效保證。

## 風險與限制

- 趨勢濾網會延後進場，可能錯過初段行情。
- 在快速反轉或盤整市場中，可能反覆進出。
- 只用價格動能，沒有成交量、波動、估值、基本面或市場寬度確認。
- 預設 `126/200` 在目前七檔 TWSE common window 中沒有同時改善 `Avg excess return` 與 `Worst MDD`，因此只能作為 compare-only 候選。
- target-state 持有的 worst MDD 可接近 buy-and-hold，不能直接升級為穩定營利候選。
- volatility target 能降低 worst MDD，但也會犧牲 upside，且目前 Sharpe / Calmar 沒有明顯勝過原始 target-state；因此仍是 compare-only。

## 回測解讀

七檔 TWSE common window、`2020-01-01` 到 `2026-05-20`、1x/3x 成本壓力下，`absolute-momentum` 預設 `126/200` 的完整持倉版本可作為 target-state 比較錨點，但不是主候選：

| 版本 | Cost | Avg return | Avg excess | Worst MDD | Avg Sharpe | Avg Sortino | Avg Calmar | 判斷 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 原始 target-state | `1x` | `225.78%` | `-226.95%` | `-50.74%` | `0.727` | `1.160` | `0.653` | compare-only：報酬較好，但回撤太接近 buy-and-hold |
| Vol target `0.25` | `1x` | `132.44%` | `-320.29%` | `-35.14%` | `0.704` | `1.113` | `0.555` | compare-only：回撤改善最大，但 upside 犧牲太多 |
| Vol target `0.35` | `1x` | `169.42%` | `-283.31%` | `-43.95%` | `0.705` | `1.115` | `0.591` | compare-only：風險/報酬較平衡 |
| Vol target `0.40` | `1x` | `180.83%` | `-271.90%` | `-47.45%` | `0.706` | `1.116` | `0.598` | compare-only：保留最多 upside，但回撤改善有限 |

目前較值得後續追蹤的是 `target_annual_volatility=0.35` 到 `0.40`，因為它們比 Confluence cooldown target-state 的 avg excess 好，且 worst MDD 低於原始 Absolute Momentum；但它們尚未解決只有 `1/7` beat buy-and-hold 的問題。

## 下一步

- 不先擴大 `momentum_window` / `trend_window` 搜尋；避免把 2020-2026 強趨勢樣本擬合成漂亮回測。
- 優先補 drawdown attribution，確認 worst MDD 主要由哪檔股票、哪段期間與哪種 volatility scale 狀態造成。
- 做 walk-forward / OOS，確認 vol target 不是只在單一 regime 中降低回撤。
- 與 `confluence-score + hold=10 + signal_cooldown_bars=10` 固定在同一批七檔股票與同一期間比較。
