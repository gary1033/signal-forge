---
title: Portfolio Relative Momentum Rotation
tags:
  - project/SignalForge
  - trading/strategy
  - trading/momentum
  - trading/portfolio
status: research
updated: 2026-05-24
repo_impl: C:\Projects\signal-forge\tools\portfolio_rotation_sweep.py
---

# Portfolio Relative Momentum Rotation

## 先懂這些詞

- **Portfolio rotation / 投組輪動**：不是逐檔股票各自判斷 long/flat，而是在同一個股票池內定期重新分配資金，讓資金集中到當下排名較好的標的。
- **Relative momentum / 相對動能**：把多檔股票在同一日期的近期報酬互相比較，偏好近期漲幅較強的股票。
- **Absolute momentum gate / 絕對動能門檻**：除了排名高，也要求該股票自己的近期報酬大於門檻；若沒有股票通過，資金可以留在現金。
- **Rebalance / 再平衡**：固定頻率重新計算排名與目標權重，例如每週或每月一次。
- **Equal-weight benchmark / 等權買進持有基準**：把資金平均分配到同一批股票並長期持有，用來檢查輪動是否真的有 portfolio-level active return。
- **Market regime filter / 市場狀態濾網**：用同一股票池的等權 normalized price index 當市場 proxy；若 index 低於自己的 SMA，該次 rebalance 改持現金。這是風險 overlay，不是新的選股 alpha。
- **Volatility target / 波動目標降曝險**：用已選出投組的近期 realized volatility 估算目前風險，若高於目標年化波動，就按比例縮小目標權重。SignalForge 版本預設 `max_scale=1.0`，所以只降曝險、不加槓桿。
- **Turnover / 週轉率**：每次再平衡時權重變化的總量。週轉率越高，交易成本與滑價風險越大。
- **Information Ratio / 資訊比率**：把策略相對 benchmark 的年化 active return 除以 tracking error，用來看每承擔一單位主動風險是否真的換到超額報酬。
- **Active max drawdown / 相對最大回撤**：用策略權益相對 benchmark 權益的 normalized relative equity 計算回撤，觀察策略相對基準是否曾長時間失速。

## 策略假設

這個策略把前一輪的「相對動能股票池篩選」提升到 portfolio 層級評估。核心假設是：如果目標是用相對動能在股票池內挑強勢股，就不應該再把每檔股票各自拿去和自己的 buy-and-hold 比；應該看整個輪動投組是否勝過同一股票池的 equal-weight buy-and-hold。

SignalForge 第一版採用 long-only、cash-allowed 的 deterministic 版本：定期排名、只持有 top-N、沒有 short、沒有槓桿、沒有 broker 連線。

## 進出場條件

每個 rebalance timestamp 執行：

1. 對每檔股票計算 `close[t] / close[t - lookback_bars] - 1`。
2. 排除近期報酬小於或等於 `min_return` 的股票。
3. 在剩下股票中依近期報酬由高到低排序。
4. 選前 `top_n` 檔股票。
5. 入選股票等權配置；未入選股票權重為 `0.0`。
6. 若沒有股票通過門檻，投組維持現金。

| 條件 | 目標權重 |
|---|---:|
| 股票進入 top-N 且近期報酬大於門檻 | `1 / 入選檔數` |
| 股票落榜 | `0.0` |
| 全部股票近期報酬不大於門檻 | 全部 `0.0`，投組留現金 |

## 主要參數

- `rebalance_frequency`：預設研究候選使用 `monthly`。
- `lookback_bars`：預設研究候選使用 `21`，約一個月交易日。
- `top_n`：預設研究候選使用 `3`。
- `min_return`：目前使用 `0.0`，代表只持有近期報酬為正的股票。
- `cost_multipliers`：固定用 `1x` 與 `3x` 成本壓力檢查。
- benchmark：同一批股票的 equal-weight buy-and-hold portfolio。

## 股價走勢解說圖

![[assets/portfolio-relative-momentum-rotation-explainer.png]]

圖中用合成走勢說明：每個月重新排名，投組集中到相對動能較強的 top-3 股票，並和同一股票池的 equal-weight buy-and-hold 比較。此圖為本地生成的教學示意圖，不是真實市場資料，也不代表績效保證。

## 風險與限制

- 這是 portfolio-level 策略，不能用逐檔 `Beat B&H` 判斷成敗；必須用投組對投組的 benchmark。
- 21 日 lookback 反應較快，但更可能吃到短期反轉、交易成本與換股噪音。
- 月再平衡降低交易頻率，但也可能錯過月內趨勢反轉。
- 股票池只有七檔 TWSE 大型股，樣本太小，還不能證明策略在更廣股票池穩定有效。
- 24 個月 rolling 檢查已發現 2021-2022 失敗 window，代表策略可能需要 market regime 或 risk-off 條件，不能只看 2024-2026 強勢期。
- 可選 `--market-regime-filter --market-regime-sma-bars 84` 已測：它把 2021-2022 excess 從約 `-24.62%` 改到約 `-13.59%`，但 full-window IR 從約 `0.858` 降到約 `0.544`，所以只能作 compare-only 風控工具，不能當作目前主候選改善。
- 可選 `--volatility-target --volatility-lookback-bars 42 --target-annual-volatility 0.20` 已測：full excess 只剩約 `43.00%`、IR 約 `0.065`，2021-2022 excess 仍約 `-22.85%`，所以也只能作 compare-only 風控工具，不能當作目前主候選改善。
- 目前沒有現金利息、股利、稅務、流動性容量、漲跌停無法成交或實際下單約束。
- 這輪是回測研究與 dry-run 筆記，不是投資建議，也不是穩定營利證明。

## 下一步

- 針對 2021-2022 失敗 window 測更具體的 risk-off / re-entry overlay 或更大股票池；不要只繼續調 market regime SMA 長度、target volatility 或 volatility lookback。
- 已加入 Information Ratio、tracking error 與 active drawdown；後續調參必須同時看這三個欄位，不只看 total return。
- 擴大股票池或加入市場 regime benchmark，確認結果不只靠少數大贏家。
- 不急著加入更複雜的風控；先確認 `monthly + 21 bars + top3` 是否在更多資料窗仍保留 active return。

## 參考來源

- Goyal and Jegadeesh, Cross-Sectional and Time-Series Tests of Return Predictability: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2610288
- Antonacci, Absolute Momentum: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2244633
- Jegadeesh and Titman, Returns to Buying Winners and Selling Losers: https://www.jstor.org/stable/2328882
