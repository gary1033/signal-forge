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
- **Group exposure / 群組曝險**：把同一群組的平均權重加總，檢查報酬集中是否來自長期高曝險，還是來自特定群組在持有期間的 realized return 過強。
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
- 群組歸因與群組曝險診斷已補上。`top4 + breadth42/min3 + max consecutive 5 + liquidity 500M/20 bars` 的 full-window 最大貢獻群組是 `electronics`，絕對貢獻占比約 `33.90%`；前三群組 `electronics / semiconductor / shipping` 合計約 `89.27%`。但 full-window 最大平均曝險群組是 `semiconductor`，平均權重約 `30.33%`，前三群組平均曝險約 `65.99%`。rolling 診斷更集中：`roll02` 的 `shipping` 群組貢獻約 `75.64%`，但最大平均曝險反而是 `financial`、約 `15.64%`，代表部分 concentration 來自 regime return，不是單純長期高曝險。
- Dominant group exclusion 已測。移除 `shipping` 後 full IR 仍約 `1.255`，但 min rolling excess 轉為 `-4.68%`、min rolling IR 轉為 `-0.185`，表示 `shipping/2603` 是 2021-2022 window 的關鍵保護來源。移除 `electronics` 後 full IR 只剩約 `0.650`，MDD 惡化到約 `-27.31%`，表示 electronics 是 full-window edge 核心。移除 `semiconductor` 後 min rolling excess 仍為正、約 `26.86%`，但 MDD / active MDD 惡化到約 `-25.31%` / `-26.64%`，且 max rolling top-3 group share 升到約 `98.68%`。因此固定刪群組不是目前升級方向。
- Canary universe 已測。把同一組 `top4 + breadth42/min3 + max consecutive 5 + liquidity 500M/20 bars` 套到新增 9 檔股票後，full-window return 只有約 `14.92%`、excess 約 `-0.91%`、IR 約 `-0.002`，MDD 約 `-44.29%`；rolling 最差 excess 約 `-33.45%`、IR 約 `-1.645`，max rolling top-3 symbol share 約 `89.54%`、group share 約 `98.45%`。這表示目前候選沒有通過 held-out 股票池驗證，不能視為已泛化策略。
- Adjusted price 診斷已測。以 Yahoo `adjclose / close` 作調整係數、套回 TWSE 原始 OHLC 並保留 TWSE volume 後，同一組候選 full-window return 約 `1644.65%`、excess 約 `1160.72%`、IR 約 `1.156`，MDD 約 `-27.97%`；最弱 rolling excess 只剩約 `1.54%`、IR 約 `0.104`。這表示未調整價版本的 `IR 1.521` / `MDD -18.61%` 過度樂觀，後續策略品質判斷要優先看 adjusted-ratio 版本。
- Adjusted price 資料來源已正式化為 `tools\build_twse_adjusted_ohlcv.py` 與 `tools\build_twse_adjusted_ohlcv_batch.py`。工具會用 Yahoo chart `adjclose / close` 調整比例套回 TWSE source OHLC，保留 TWSE source volume，並寫出 per-symbol manifest 與 TWSE14 batch manifest，讓後續 raw / adjusted-ratio 對照可以重跑與稽核。2026-05-24 TWSE14 batch 結果是 14 檔、21479 rows、missing adjustment 26、skipped rows 2482。
- Raw / adjusted 比較 artifact 已正式化為 `tools\compare_portfolio_rotation_reports.py`。同一組候選的 deterministic 對照顯示 raw 1x `IR 1.521 / MDD -18.61%` 會降成 adjusted 1x `IR 1.156 / MDD -27.97%`，full-window excess delta 是 `-248.99%`，最弱 rolling window `roll02` 的 IR delta 是 `-0.711`。後續如果沒有這類比較 artifact 或同等 raw/adjusted gate，不應宣稱策略品質改善。
- Adjusted 參數掃描已正式化為 `tools\portfolio_rotation_grid_search.py`。2026-05-24 掃描 `top_n=3/4/5`、`breadth_min=2/3/4/5`、`max_consecutive=4/5/6` 與 `liquidity=500M` 共 `36` 組後，沒有任何候選通過全部 gate。最佳 compare-only 錨點是 `top3 / breadth4 / maxconsec5 / liq500M`：full IR 約 `1.141`、MDD 約 `-22.67%`、3x IR 約 `1.114`、min rolling IR 約 `0.264`，比 current baseline 的 min rolling IR `0.104` 與 MDD `-27.97%` 好，但 max rolling top3 group share 仍約 `97.38%`，所以不能升級。
- `top3 / breadth4 / maxconsec5 / liq500M` 的 raw / adjusted comparison artifact 已補上。這組設定在 raw 版 full 1x `IR 1.236 / MDD -21.93%`，adjusted 版 full 1x `IR 1.141 / MDD -22.67%`，adjusted excess 反而較高但 IR 小降；最弱 adjusted rolling IR 是 `roll02 = 0.264`，比 current baseline 的 `0.104` 好。不過 adjusted full-window top3 group share 仍約 `92.78%`，rolling 最高約 `97.38%`，因此它只能升為下一個 compare anchor，不能升級為 keep。
- Group regime validation 已正式化為 `tools\portfolio_rotation_group_regime_validation.py`。針對 adjusted `top3 / breadth4 / maxconsec5 / liq500M` 的 artifact 顯示 gate 失敗：full + 6 個 rolling windows 全部 high concentration，`7 / 7` 都是 `return_regime_dominated`，不是單純長期高曝險。最弱 IR window 是 `roll02 = 0.264`，其中 `shipping` 平均權重只有約 `10.43%`，但貢獻占比約 `70.86%`；最嚴重 top3 group window 是 `roll03 = 97.38%`。這表示單純 group cap 或固定刪 group 很可能傷害 edge，下一步要改做更高品質股票池或 group-level regime / breadth validation。
- Group breadth validation 已正式化為 `tools\portfolio_rotation_group_breadth_validation.py`。同一組 adjusted `top3 / breadth4 / maxconsec5 / liq500M` 的 artifact 顯示 gate 仍失敗：`7 / 7` high concentration，`4 / 7` 是 broad group momentum，`2 / 7` 是 `shipping` 單成員 dominant，`1 / 7` 是 `electronics` narrow breadth。最弱 breadth window 是 `roll03`，electronics 平均正動能成員比例約 `58.82%`；最弱 IR window 仍是 `roll02 = 0.264`，且 dominant group 是單成員 `shipping`。這代表目前問題不是只靠 group cap 能修，也不是單純要找更高總報酬，而是要改善股票池品質、降低 realized group contribution concentration，並處理單成員群組風險。
- Promotion gate 已正式化為 `tools\portfolio_rotation_promotion_gate.py`。它把 adjusted summary、raw/adjusted comparison、group regime validation 與 group breadth validation 合併成單一 `keep` / `compare-only` gate。2026-05-24 adjusted `top3 / breadth4 / maxconsec5 / liq500M` 的結果仍是 `compare-only`：full 1x IR 約 `1.141`、3x IR 約 `1.114`，但 min rolling IR 只有約 `0.264`，max rolling top3 symbol share 約 `81.40%`，max rolling top3 group share 約 `97.38%`，且 group regime / breadth gate 都失敗。
- `top_n=4` 可把 full-window top-3 絕對貢獻占比降到約 `48.32%`，但 max rolling top-3 share 仍約 `81.68%`，所以它改善 full-window 集中度，還沒有解決最關鍵的 rolling concentration。
- `top4 + breadth42/min3 + max consecutive 5` 是目前 TWSE14 績效 compare candidate：full-window IR 約 `1.515`、MDD 約 `-18.61%`、active MDD 約 `-20.21%`、min rolling IR 約 `0.814`；但 max rolling top-3 share 仍約 `82.62%`。
- 新增 liquidity gate 後，`top4 + breadth42/min3 + max consecutive 5 + liquidity 500M/20 bars` 暫時是 execution-aware compare candidate：full-window return 約 `1745.89%`、excess 約 `1409.71%`、IR 約 `1.521`、MDD 約 `-18.61%`、active MDD 約 `-19.81%`，3x 成本後 IR 仍約 `1.490`。但 max rolling top-3 share 仍約 `82.62%`，所以它不是 concentration 修復。
- 擴到 TWSE23 後，concentration 明顯下降但 edge 變弱：`top4/min3/maxconsec5` 的 max rolling top-3 share 降到約 `65.32%`，但 full IR 降到約 `1.179`、MDD 惡化到約 `-36.64%`、min rolling excess 約 `-17.99%`。`top5/min5` 的 max rolling top-3 share 進一步降到約 `56.62%`，但 min rolling IR 約 `-0.265`，所以只能作 concentration diagnostic。
- 因為分段貢獻仍偏集中、調整價版本明顯降級、股票池仍小，所以仍不能宣稱穩定營利。
- 目前沒有現金利息、股利、稅務、流動性容量、漲跌停無法成交或實際下單約束。
- 這輪是回測研究與 dry-run 筆記，不是投資建議，也不是穩定營利證明。

## 下一步

- 已測 `top4 + breadth 42/min3` 的單檔連續入選上限。`max consecutive 5` 讓 full-window IR 約 `1.515`、min rolling IR 約 `0.814`，比無上限 `top4` 更強；但 max rolling top-3 share 仍約 `82.62%`，沒有真正壓低 rolling concentration。
- 已測 sector/group cap。`groupcap2` full IR 約 `1.449`，但 min rolling IR 降到約 `0.610`，max rolling top-3 share 仍約 `81.68%`；`groupcap1` 傷害 edge。因此 group cap 只保留為可測工具，不作目前主候選。
- 已測 TWSE23 擴大股票池。它把 rolling concentration 往下壓，但同時讓 min rolling excess / IR 轉弱，因此不升級；下一步不要只把股票池加大，應改善股票池品質、資料調整與流動性條件。
- 已測 liquidity / capacity gate。`500M/20 bars` 幾乎不傷害原策略並小幅改善 active MDD，因此升為 execution-aware compare candidate；`1B` 雖提高報酬但回撤與 rolling IR tradeoff 較差，`2B` 明確 discard。
- 已測 dominant group exclusion。固定移除單一群組不是解法：`no shipping` 讓 rolling edge 失效，`no electronics` 讓 full-window edge 大幅衰退，`no semiconductor` 雖保留 rolling edge 但回撤與 concentration 惡化。
- 已測 canary universe。Canary9 的 full-window excess / IR 轉負，MDD 到約 `-44.29%`，rolling concentration 比 TWSE14 baseline 更糟，因此目前策略仍是 compare-only。
- 已測 adjusted price，且已用 batch manifest 重建 TWSE14 adjusted CSV 後重跑同一候選。以 Yahoo 調整係數套回 TWSE OHLCV 後，full IR 仍只有約 `1.156`，MDD 惡化到約 `-27.97%`，min rolling IR 只剩約 `0.104`，top3 group share 約 `91.29%`，因此目前策略品質要按 adjusted-ratio 版本降級解讀。
- Raw / adjusted comparison artifact 已補上。下一步優先用這個 artifact 作為策略品質 gate，再較慢批次完成 TWSE30+、更高品質股票池、group regime validation 或更嚴格的流動性/容量條件，目標是同時降低 rolling `max_symbol_abs_contribution_share`、`top3_symbol_abs_contribution_share`、`max_group_abs_contribution_share`、`top3_group_abs_contribution_share` 與 group exposure concentration，並保留正 min rolling excess 與可接受 active drawdown。
- Adjusted grid search、`top3 / breadth4 / maxconsec5 / liq500M` raw/adjusted comparison artifact、group regime validation 與 group breadth validation 已補上。下一步不要繼續擴同一組 top-N / breadth / max-consecutive 小網格；優先做更高品質股票池、TWSE30+ raw/adjusted 共同 gate，或直接設計能限制 realized group contribution concentration / 單成員群組依賴的 gate。
- Promotion gate 已補上。下一輪策略若要升級，不只要報 summary 指標，還要讓 promotion gate 同時通過 rolling IR、rolling excess、drawdown、symbol concentration、group concentration、raw/adjusted 降級、group regime 與 group breadth 檢查。
- 再檢查流動性、容量與調整價資料穩定性；不要只追求更高 total return 或微調 breadth threshold。
- 已加入 Information Ratio、tracking error 與 active drawdown；後續調參必須同時看這三個欄位，不只看 total return。
- 擴大股票池或加入市場 regime benchmark 時，要同時要求 min rolling excess、Information Ratio、active drawdown 與 concentration gate 過關，確認結果不只靠少數大贏家。
- 目前主比較錨點分成四個：`top3 + breadth 42/min3` 是最高報酬錨點；`top4 + breadth 42/min3` 是風險調整折衷錨點；`top4 + breadth 42/min3 + max consecutive 5` 是績效 compare candidate；`top4 + breadth 42/min3 + max consecutive 5 + liquidity 500M/20 bars` 是 execution-aware compare candidate。`groupcap1/2`、更高 liquidity 門檻、TWSE23 擴大股票池、group attribution、group exposure、dominant group exclusion、canary universe 與 adjusted batch 診斷保留為 discard / compare-only / diagnostic 對照；其中 adjusted-ratio 版本應成為後續品質判斷的主要風險版本，不取代核心錨點，也不是穩定營利證明。

## 參考來源

- Goyal and Jegadeesh, Cross-Sectional and Time-Series Tests of Return Predictability: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2610288
- Antonacci, Absolute Momentum: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2244633
- Jegadeesh and Titman, Returns to Buying Winners and Selling Losers: https://www.jstor.org/stable/2328882
- Keller and Keuning, Protective Asset Allocation (PAA): https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2759734
- Keller and Keuning, Breadth Momentum and Vigilant Asset Allocation (VAA): https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3002624
- Keller and Keuning, Defensive Asset Allocation (DAA): https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3212862
- Moskowitz and Grinblatt, Do Industries Explain Momentum?: https://doi.org/10.1111/0022-1082.00146
