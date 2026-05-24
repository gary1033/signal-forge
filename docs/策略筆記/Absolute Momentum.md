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
- **Drawdown risk-off / 回撤風控**：用策略自己的 proxy equity 追蹤單檔高點回撤；若回撤超過門檻，就暫時把非零部位改成空手，等待固定 bar 數後再重新允許底層策略進場。
- **Relative momentum / 相對動能**：把同一日期的多檔股票依過去一段期間報酬排序，只允許排名前幾名且自身報酬為正的股票保留非零部位。它是股票池篩選，不是保證會勝過 buy-and-hold。

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
- `DrawdownRiskOffStrategy` 不改變底層動能進場條件；它只在 wrapper 追蹤到 proxy equity 從本地高點回撤超過門檻時，把非零 target 改成 `0.0`，reason 是 `drawdown_risk_off`。
- Drawdown risk-off 期間結束後，wrapper 會用當下 proxy equity 重設本地 high-water mark，避免因舊高點造成永久空手；這是可回測的研究假設，不代表真實停損保證。
- `RelativeMomentumFilteredStrategy` 不改變底層 Absolute Momentum 的 long/flat 判斷；它先用多檔股票同日 lookback return 排名建立白名單，只有 top-N 且 lookback return 大於 `min_return` 的 symbol 可以保留非零 target。
- 若底層策略輸出非零 target，但該 symbol 當日不在相對動能白名單，wrapper 會把 target 改成 `0.0`，reason 是 `relative_momentum_filter_blocked`。

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
- `drawdown-risk-off` overlay：目前研究設定比較 `drawdown_threshold=0.10/0.15/0.20/0.25/0.30` 與 `risk_off_bars=20/40/60/120`；較可追蹤的版本是 `0.25/120`，但仍只屬 compare-only。
- `relative-momentum-filter` overlay：目前研究設定比較 `lookback_bars=63/126/252`、`top_n=1/2/3/4/5/7`、`min_return=0.0`；這是股票池白名單，不是完整 portfolio allocation。

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
- drawdown attribution 顯示 worst MDD 集中在 `2454`，且 vol target `0.40` 在 trough 當天仍是滿倉 `1.000`，代表單純波動縮放沒有完全處理長回撤狀態。
- 單獨 drawdown risk-off 可以降低部分版本的 worst MDD，但容易錯過後續趨勢或把最差回撤轉移到其他股票；`20%/60 bars` 甚至讓 worst MDD 惡化，因此不可直接升級。
- `vol-target 0.40 + drawdown-risk-off 25%/120 bars` 是目前較好的 drawdown-control compare-only 組合，但 `Beat B&H` 仍只有 `1/7`，且 `2454` trough 當天仍是滿倉 `1.000`。
- walk-forward / OOS 顯示 2024-2026 樣本外總報酬仍為正，但 benchmark-relative 沒有改善；原始 Absolute Momentum OOS 只有 `1/7` beat B&H，疊加 `vol-target 0.40 + drawdown-risk-off 25%/120` 後變成 `0/7` beat B&H。
- relative-momentum stock-pool filter 在 2024-2026 OOS 中沒有改善 active return；嚴格 top-N 主要降低 time-in-market，但 `Beat B&H` 仍沒有變好。

## 回測解讀

七檔 TWSE common window、`2020-01-01` 到 `2026-05-20`、1x/3x 成本壓力下，`absolute-momentum` 預設 `126/200` 的完整持倉版本可作為 target-state 比較錨點，但不是主候選：

| 版本 | Cost | Avg return | Avg excess | Worst MDD | Avg Sharpe | Avg Sortino | Avg Calmar | 判斷 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 原始 target-state | `1x` | `225.78%` | `-226.95%` | `-50.74%` | `0.727` | `1.160` | `0.653` | compare-only：報酬較好，但回撤太接近 buy-and-hold |
| Vol target `0.25` | `1x` | `132.44%` | `-320.29%` | `-35.14%` | `0.704` | `1.113` | `0.555` | compare-only：回撤改善最大，但 upside 犧牲太多 |
| Vol target `0.35` | `1x` | `169.42%` | `-283.31%` | `-43.95%` | `0.705` | `1.115` | `0.591` | compare-only：風險/報酬較平衡 |
| Vol target `0.40` | `1x` | `180.83%` | `-271.90%` | `-47.45%` | `0.706` | `1.116` | `0.598` | compare-only：保留最多 upside，但回撤改善有限 |
| DD risk-off `20%/60` | `1x` | `142.47%` | `-310.26%` | `-59.40%` | `0.535` | `0.852` | `0.386` | discard：回撤惡化且 2454 trough 仍滿倉 |
| DD risk-off `25%/120` | `1x` | `207.18%` | `-245.55%` | `-46.95%` | `0.682` | `1.093` | `0.599` | compare-only：MDD 低於 raw / vol-target 0.40，但風險調整仍降 |
| Vol target `0.40` + DD risk-off `25%/120` | `1x` | `188.37%` | `-264.36%` | `-44.93%` | `0.738` | `1.176` | `0.620` | compare-only：本輪較佳風控組合，但仍只有 `1/7` beat B&H |

目前較值得後續追蹤的是 `target_annual_volatility=0.35` 到 `0.40`，因為它們比 Confluence cooldown target-state 的 avg excess 好，且 worst MDD 低於原始 Absolute Momentum；但它們尚未解決只有 `1/7` beat buy-and-hold 的問題。

### Drawdown attribution 補充

| 版本 | Cost | Worst symbol | Worst MDD | Peak | Trough | Recovery | Trough position | Avg abs position |
|---|---:|---|---:|---|---|---|---:|---:|
| 原始 target-state | `1x` | `2454` | `-50.74%` | `2024-06-20` | `2025-12-24` | `2026-05-04` | `1.000` | `0.574` |
| Vol target `0.40` | `1x` | `2454` | `-47.45%` | `2024-06-20` | `2025-12-24` | `2026-05-05` | `1.000` | `0.515` |
| DD risk-off `25%/120` | `1x` | `2303` | `-46.95%` | `2021-04-26` | `2025-09-23` | unrecovered | `1.000` | `0.244` |
| Vol target `0.40` + DD risk-off `25%/120` | `1x` | `2454` | `-44.93%` | `2024-06-20` | `2025-12-24` | `2026-05-04` | `1.000` | `0.248` |

這代表 vol target 與 drawdown risk-off 都能降低 peak-to-trough 的平均曝險，但在最大回撤 trough 當天仍可能是滿倉。下一步若要改善穩定性，方向應該是更明確的 exit / re-entry state、再平衡門檻、股票池過濾或 OOS 檢查，而不是只調 `target_annual_volatility` 或 risk-off bars。

### Walk-forward / OOS 補充

同一批七檔 TWSE common window 切成 `is:2020-01-01:2023-12-31` 與 `oos:2024-01-01:2026-05-20` 後，結果顯示策略沒有樣本外報酬崩潰，但仍沒有形成穩定 benchmark edge。

| 版本 | Cost | IS avg return | IS avg excess | IS beat B&H | IS worst MDD | OOS avg return | OOS avg excess | OOS beat B&H | OOS worst MDD | 判斷 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 原始 target-state | `1x` | `36.76%` | `-43.54%` | `2/7` | `-40.50%` | `84.58%` | `-105.25%` | `1/7` | `-36.32%` | compare-only：OOS 報酬較強，但 active return 仍負 |
| 原始 target-state | `3x` | `35.49%` | `-44.67%` | `2/7` | `-41.17%` | `83.31%` | `-106.29%` | `1/7` | `-36.93%` | compare-only：成本壓力後仍未形成 benchmark edge |
| Vol target `0.40` + DD risk-off `25%/120` | `1x` | `41.12%` | `-39.18%` | `2/7` | `-27.81%` | `62.17%` | `-127.67%` | `0/7` | `-27.20%` | compare-only：回撤較低，但 OOS 完全沒有 beat B&H |
| Vol target `0.40` + DD risk-off `25%/120` | `3x` | `39.83%` | `-40.32%` | `2/7` | `-28.21%` | `61.05%` | `-128.55%` | `0/7` | `-27.54%` | compare-only：成本後仍穩，但 active return 更弱 |

這輪結論是：風控 overlay 讓 OOS worst MDD 從原始版本約 `-36%` 降到約 `-27%`，但代價是 OOS avg return 降低，且 `Beat B&H` 從 `1/7` 變成 `0/7`。因此它只能作為 drawdown-control 對照，不能升級為穩定營利候選。

### Relative momentum stock-pool filter 補充

這輪參考 time-series momentum、absolute momentum 與 cross-sectional momentum 文獻，把「自己的趨勢為正」和「同池股票中相對強」合併成可回測假設：底層 Absolute Momentum 先判斷 long/flat，再用同日 lookback return top-N 當股票池白名單。

2024-2026 OOS 以七檔 TWSE、1x/3x 成本壓力掃描 `lookback=63/126/252` 與 `topN=1/2/3/4/5/7`。結果是：

| Lookback | Top N | Cost | OOS Avg return | OOS Avg excess | OOS Beat B&H | OOS Worst MDD | 判斷 |
|---:|---:|---:|---:|---:|---:|---:|---|
| `126` | `7` | `1x` | `84.58%` | `-105.25%` | `1/7` | `-36.32%` | 近似不篩選，仍只是原始 Absolute Momentum 的 compare-only 錨點 |
| `252` | `7` | `1x` | `81.35%` | `-108.48%` | `1/7` | `-32.88%` | 回撤稍低，但 active return 更差 |
| `126` | `3` | `1x` | `65.21%` | `-124.63%` | `0/7` | `-32.95%` | 降曝險但沒有 benchmark edge |
| `252` | `1` | `1x` | `50.66%` | `-139.18%` | `0/7` | `-17.21%` | 回撤最低之一，但報酬與 active return 犧牲過大 |

Keep / discard 判斷：

- **Keep as tool**：相對動能白名單與 CLI 參數，因為它是 deterministic、test-covered，之後可用於其他策略或 portfolio allocation 實驗。
- **Discard as strategy improvement**：目前 top-N stock-pool filter 沒有改善 OOS `Beat B&H` 或 avg excess，不能作為 Absolute Momentum 主線升級。

## 下一步

- 不先擴大 `momentum_window` / `trend_window` 搜尋；避免把 2020-2026 強趨勢樣本擬合成漂亮回測。
- 不把 `DD risk-off 20%/60` 作為候選；它已經被 1x/3x cost stress 證明會惡化 worst MDD。
- 保留 `DD risk-off 25%/120` 與 `vol-target 0.40 + DD risk-off 25%/120` 為 compare-only；OOS 已證明它們主要改善回撤，不改善 benchmark-relative edge。
- 後續若要深化，優先改善 OOS `Beat B&H` 與 active return，而不是只降低 MDD。
- 若繼續做風控，優先測 re-entry 條件、weekly rebalance 或市場 regime；relative-momentum top-N 股票池已測過，不能重複當成主要突破口。
- 與 `confluence-score + hold=10 + signal_cooldown_bars=10` 固定在同一批七檔股票與同一期間比較。

## 參考來源

- Moskowitz, Ooi and Pedersen, Time Series Momentum: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2089463
- Antonacci, Absolute Momentum: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2244633
- Jegadeesh and Titman, Returns to Buying Winners and Selling Losers: https://www.jstor.org/stable/2328882
