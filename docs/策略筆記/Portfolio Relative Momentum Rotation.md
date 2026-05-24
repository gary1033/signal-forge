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
- **Breadth filter / 市場寬度濾網**：在 rebalance date 計算股票池中有多少檔股票的近期報酬大於門檻；若正動能檔數不足，代表強勢不夠廣，該次 rebalance 改持現金。
- **Volatility target / 波動目標降曝險**：用已選出投組的近期 realized volatility 估算目前風險，若高於目標年化波動，就按比例縮小目標權重。SignalForge 版本預設 `max_scale=1.0`，所以只降曝險、不加槓桿。
- **Liquidity filter / 流動性濾網**：用近 N 根 `close * volume` 平均成交金額定義股票是否可被選入，避免策略把資金分配到成交金額太低、容量較差或滑價風險較高的標的。
- **Turnover / 週轉率**：每次再平衡時權重變化的總量。週轉率越高，交易成本與滑價風險越大。
- **Information Ratio / 資訊比率**：把策略相對 benchmark 的年化 active return 除以 tracking error，用來看每承擔一單位主動風險是否真的換到超額報酬。
- **Active max drawdown / 相對最大回撤**：用策略權益相對 benchmark 權益的 normalized relative equity 計算回撤，觀察策略相對基準是否曾長時間失速。
- **Symbol attribution / 選股歸因**：把實際持倉期間的 `weight * close-to-close return` 分配回各股票，檢查報酬是否集中在少數高波動股票。
- **Group attribution / 群組歸因**：把同一產業或自訂群組內的逐股貢獻彙總，檢查策略是否從單檔集中轉成 sector / group 集中。
- **Concentration guard / 集中度防線**：把最大單檔、前三檔、最大群組與前三群組貢獻占比拉成一級欄位，避免只看總報酬或 IR 時忽略少數大贏家或少數產業依賴。

## 策略假設

這個策略把前一輪的「相對動能股票池篩選」提升到 portfolio 層級評估。核心假設是：如果目標是用相對動能在股票池內挑強勢股，就不應該再把每檔股票各自拿去和自己的 buy-and-hold 比；應該看整個輪動投組是否勝過同一股票池的 equal-weight buy-and-hold。

SignalForge 第一版採用 long-only、cash-allowed 的 deterministic 版本：定期排名、只持有 top-N、沒有 short、沒有槓桿、沒有 broker 連線。

## 進出場條件

每個 rebalance timestamp 執行：

1. 對每檔股票計算 `close[t] / close[t - lookback_bars] - 1`。
2. 排除近期報酬小於或等於 `min_return` 的股票。
3. 若啟用 breadth filter，另用 `breadth_lookback_bars` 計算股票池中正動能檔數；若低於 `breadth_min_positive_count`，本次 rebalance 全部留現金。
4. 若啟用 liquidity filter，排除近 N 根平均成交金額低於門檻的股票。
5. 在剩下股票中依近期報酬由高到低排序。
6. 選前 `top_n` 檔股票。
7. 入選股票等權配置；未入選股票權重為 `0.0`。
8. 若沒有股票通過門檻，投組維持現金。

| 條件 | 目標權重 |
|---|---:|
| 股票進入 top-N 且近期報酬大於門檻 | `1 / 入選檔數` |
| breadth filter 啟用且正動能檔數不足 | 全部 `0.0`，投組留現金 |
| liquidity filter 啟用且平均成交金額不足 | 該股票不可入選，由下一順位補上 |
| 股票落榜 | `0.0` |
| 全部股票近期報酬不大於門檻 | 全部 `0.0`，投組留現金 |

## 主要參數

- `rebalance_frequency`：預設研究候選使用 `monthly`。
- `lookback_bars`：預設研究候選使用 `21`，約一個月交易日。
- `top_n`：最高報酬錨點是 `3`；目前風險調整折衷候選改看 `4`，因為 full IR 幾乎不變但 MDD、active MDD 與 full-window top-3 concentration 較低。
- `min_return`：目前使用 `0.0`，代表只持有近期報酬為正的股票。
- `breadth_filter`：七檔股票池最佳折衷是 `breadth_lookback_bars=42`、`breadth_min_positive_count=2`；擴大到 14 檔 TWSE 股票池後，目前最佳折衷改為 `breadth_min_positive_count=3`。
- `liquidity_filter`：目前最新 execution-aware compare candidate 使用 `liquidity_lookback_bars=20`、`min_average_traded_value=500,000,000`，代表近 20 根平均成交金額至少約 5 億。
- `cost_multipliers`：固定用 `1x` 與 `3x` 成本壓力檢查。
- benchmark：同一批股票的 equal-weight buy-and-hold portfolio。

## 股價走勢解說圖

![[assets/portfolio-relative-momentum-rotation-explainer.png]]

圖中用合成走勢說明：每個月重新排名，投組集中到相對動能較強的 top-3 股票，並和同一股票池的 equal-weight buy-and-hold 比較。此圖為本地生成的教學示意圖，不是真實市場資料，也不代表績效保證。

## 風險與限制

- 這是 portfolio-level 策略，不能用逐檔 `Beat B&H` 判斷成敗；必須用投組對投組的 benchmark。
- 21 日 lookback 反應較快，但更可能吃到短期反轉、交易成本與換股噪音。
- 月再平衡降低交易頻率，但也可能錯過月內趨勢反轉。
- 股票池已從七檔擴到 14 檔，再暫時擴到 23 檔做 concentration diagnostic；樣本仍偏小，且 TWSE STOCK_DAY 資料未還原權息，還不能證明策略在更廣股票池穩定有效。
- 24 個月 rolling 檢查已發現 2021-2022 失敗 window，代表策略可能需要 market regime 或 risk-off 條件，不能只看 2024-2026 強勢期。
- 可選 `--market-regime-filter --market-regime-sma-bars 84` 已測：它把 2021-2022 excess 從約 `-24.62%` 改到約 `-13.59%`，但 full-window IR 從約 `0.858` 降到約 `0.544`，所以只能作 compare-only 風控工具，不能當作目前主候選改善。
- 可選 `--volatility-target --volatility-lookback-bars 42 --target-annual-volatility 0.20` 已測：full excess 只剩約 `43.00%`、IR 約 `0.065`，2021-2022 excess 仍約 `-22.85%`，所以也只能作 compare-only 風控工具，不能當作目前主候選改善。
- 可選 `--breadth-filter --breadth-lookback-bars 42 --breadth-min-positive-count 2` 在七檔股票池是最佳折衷：full-window IR 約 `1.017`，但 2021-2022 仍輸 benchmark。
- 擴大到 14 檔 TWSE 股票池後，`--breadth-min-positive-count 3` 是目前最佳 breadth gate。`top_n=3` 是最高報酬錨點：full-window return 約 `1974.85%`、excess 約 `1638.67%`、MDD 約 `-23.01%`、IR 約 `1.417`，1x/2x/3x 成本與 6 個 rolling windows 都維持正 excess。
- 同條件下 `top_n=4` 是目前風險調整折衷候選：full-window return 約 `1546.66%`、excess 約 `1210.48%`、MDD 約 `-18.61%`、active MDD 約 `-20.21%`、IR 約 `1.401`；相對 `top_n=3` 犧牲總報酬，但明顯降低回撤且 IR 幾乎不變。
- 選股歸因顯示 full-window 最大貢獻 `2603` 的絕對貢獻占比約 `23.77%`，不是單一股票完全壟斷；但 rolling window 仍有集中風險，`roll02` 的 `2603` 約 `68.75%`、`roll06` 的 `2308` 約 `48.75%`。
- Concentration guard 進一步顯示 full-window top-3 絕對貢獻占比約 `55.04%`；rolling top-3 在 `roll01` 約 `73.33%`、`roll02` 約 `82.56%`、`roll03` 約 `72.39%`，代表部分分段仍過度集中。
- 群組歸因已補上。`top4 + breadth42/min3 + max consecutive 5 + liquidity 500M/20 bars` 的 full-window 最大群組是 `electronics`，絕對貢獻占比約 `33.90%`；前三群組 `electronics / semiconductor / shipping` 合計約 `89.27%`。rolling 診斷更集中：`roll02` 的 `shipping` 群組約 `75.64%`，`roll03` 前三群組約 `96.81%`，`roll05` 的 `electronics` 約 `59.22%`。這表示目前 concentration 問題不只是單檔，還包含產業/群組 regime 依賴。
- `top_n=4` 可把 full-window top-3 絕對貢獻占比降到約 `48.32%`，但 max rolling top-3 share 仍約 `81.68%`，所以它改善 full-window 集中度，還沒有解決最關鍵的 rolling concentration。
- `top4 + breadth42/min3 + max consecutive 5` 是目前 TWSE14 績效 compare candidate：full-window IR 約 `1.515`、MDD 約 `-18.61%`、active MDD 約 `-20.21%`、min rolling IR 約 `0.814`；但 max rolling top-3 share 仍約 `82.62%`。
- 新增 liquidity gate 後，`top4 + breadth42/min3 + max consecutive 5 + liquidity 500M/20 bars` 暫時是 execution-aware compare candidate：full-window return 約 `1745.89%`、excess 約 `1409.71%`、IR 約 `1.521`、MDD 約 `-18.61%`、active MDD 約 `-19.81%`，3x 成本後 IR 仍約 `1.490`。但 max rolling top-3 share 仍約 `82.62%`，所以它不是 concentration 修復。
- 擴到 TWSE23 後，concentration 明顯下降但 edge 變弱：`top4/min3/maxconsec5` 的 max rolling top-3 share 降到約 `65.32%`，但 full IR 降到約 `1.179`、MDD 惡化到約 `-36.64%`、min rolling excess 約 `-17.99%`。`top5/min5` 的 max rolling top-3 share 進一步降到約 `56.62%`，但 min rolling IR 約 `-0.265`，所以只能作 concentration diagnostic。
- 因為分段貢獻仍偏集中、資料未還原權息、股票池仍小，所以仍不能宣稱穩定營利。
- 目前沒有現金利息、股利、稅務、流動性容量、漲跌停無法成交或實際下單約束。
- 這輪是回測研究與 dry-run 筆記，不是投資建議，也不是穩定營利證明。

## 下一步

- 已測 `top4 + breadth 42/min3` 的單檔連續入選上限。`max consecutive 5` 讓 full-window IR 約 `1.515`、min rolling IR 約 `0.814`，比無上限 `top4` 更強；但 max rolling top-3 share 仍約 `82.62%`，沒有真正壓低 rolling concentration。
- 已測 sector/group cap。`groupcap2` full IR 約 `1.449`，但 min rolling IR 降到約 `0.610`，max rolling top-3 share 仍約 `81.68%`；`groupcap1` 傷害 edge。因此 group cap 只保留為可測工具，不作目前主候選。
- 已測 TWSE23 擴大股票池。它把 rolling concentration 往下壓，但同時讓 min rolling excess / IR 轉弱，因此不升級；下一步不要只把股票池加大，應改善股票池品質、資料調整與流動性條件。
- 已測 liquidity / capacity gate。`500M/20 bars` 幾乎不傷害原策略並小幅改善 active MDD，因此升為 execution-aware compare candidate；`1B` 雖提高報酬但回撤與 rolling IR tradeoff 較差，`2B` 明確 discard。
- 下一步優先測 adjusted price、較慢批次完成 TWSE30+、canary universe、group regime / group exposure diagnostic 或流動性/容量條件，目標是同時降低 rolling `max_symbol_abs_contribution_share`、`top3_symbol_abs_contribution_share`、`max_group_abs_contribution_share` 與 `top3_group_abs_contribution_share`，並保留正 min rolling excess 與可接受 active drawdown。
- 再檢查 adjusted price、流動性與容量；不要只追求更高 total return 或微調 breadth threshold。
- 已加入 Information Ratio、tracking error 與 active drawdown；後續調參必須同時看這三個欄位，不只看 total return。
- 擴大股票池或加入市場 regime benchmark 時，要同時要求 min rolling excess、Information Ratio、active drawdown 與 concentration gate 過關，確認結果不只靠少數大贏家。
- 目前主比較錨點分成四個：`top3 + breadth 42/min3` 是最高報酬錨點；`top4 + breadth 42/min3` 是風險調整折衷錨點；`top4 + breadth 42/min3 + max consecutive 5` 是績效 compare candidate；`top4 + breadth 42/min3 + max consecutive 5 + liquidity 500M/20 bars` 是最新 execution-aware compare candidate。`groupcap1/2`、更高 liquidity 門檻、TWSE23 擴大股票池與 group attribution 本輪診斷保留為 discard / compare-only / diagnostic 對照，不取代核心錨點，也不是穩定營利證明。

## 參考來源

- Goyal and Jegadeesh, Cross-Sectional and Time-Series Tests of Return Predictability: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2610288
- Antonacci, Absolute Momentum: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2244633
- Jegadeesh and Titman, Returns to Buying Winners and Selling Losers: https://www.jstor.org/stable/2328882
- Keller and Keuning, Protective Asset Allocation (PAA): https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2759734
- Keller and Keuning, Breadth Momentum and Vigilant Asset Allocation (VAA): https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3002624
- Keller and Keuning, Defensive Asset Allocation (DAA): https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3212862
- Moskowitz and Grinblatt, Do Industries Explain Momentum?: https://doi.org/10.1111/0022-1082.00146
