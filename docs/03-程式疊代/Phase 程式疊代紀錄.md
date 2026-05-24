---
title: Phase 程式疊代紀錄
tags:
  - project/SignalForge
  - iteration
  - phase
status: active
updated: 2026-05-24
---

# Phase 程式疊代紀錄

這份紀錄是 SignalForge Phase 工作流的程式疊代摘要。詳細 automation 實驗表放在 [[../04-實驗記錄/Autoresearch 實驗記錄|Autoresearch 實驗記錄]]；這裡保留工程脈絡、已鎖住的 contract 與下一步開發方向。

## 疊代方法

每次 wakeup 只做一個聚焦改動：

```text
modify -> verify -> keep/discard -> log
```

固定 guard：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
cd C:\Projects\signal-forge
$env:PYTHONPATH = "src"
python tools\phase_readiness_score.py
python -m unittest discover -s tests
git diff --check
```

通過條件：readiness score `110`、unit tests 全部通過、`git diff --check` clean。

## 已完成主線

### 1. Phase mode 與 adapters

- 加入 `PhaseMode = backtest | live`。
- 加入 `PhaseConfig`，由 mode 推導 `dry_run`。
- 加入 `PhaseRunner`，依 mode 路由到 execution adapter。
- 加入 `BacktestExecutionAdapter` 與 `LiveExecutionAdapter`。
- `live` 模式拒絕 `dry_run=False`，並固定 dry-run only。

### 2. Backtest artifact contract

已鎖住的 deterministic outputs：

- Phase summary JSON。
- Phase markdown。
- Entry Edge summary JSON。
- Entry Edge markdown。
- Entry Edge trade log CSV。
- Entry Edge hold comparison JSON / Markdown。
- `*_signals.csv`。
- `*_trace_summary.json`。

這些輸出由 regression tests 與 validator 鎖住，避免 writer drift。

### 3. Signal digest 可稽核性

`*_signals.csv` 已逐步加入：

- `is_long_entry`
- `is_flatten`
- `position_change`
- `previous_target_position`
- `is_hold`
- `hold_side`

Validator 會檢查 timestamp、reason、fixed decimal、position delta、flags、hold side 與 trace summary 一致性。

### 4. Trace summary 可稽核性

`*_trace_summary.json` 已逐步加入：

- `schema_version`
- first / last timestamp
- start / end date
- reason counts
- entry / open / close / flatten counts
- flatten buckets
- hold long / short buckets
- min / max target position
- position bucket counts
- first / last reason
- `signal_digest_sha256`

Reporting 會用 `validate_signal_digest_csv(...)` 對 signals CSV 和 trace summary 做 cross-check。

### 5. Live dry-run safety

`live` 保持：

- 只產生 `OrderIntent`
- `dry_run=True`
- `submitted=False`
- `safety_note` 含 `LIVE_DRY_RUN_ONLY`
- 不接 broker
- 不讀 API key / credential
- 不送出真實訂單

任何碰到 `live` 的改動都必須先確認這些 invariant 沒被破壞。

### 6. Strategy OOP template

- 新增 `StrategyDecision` 與 hook-based `BarByBarStrategy`，由 template 統一 `generate_signals()` 的逐 bar 流程。
- 既有日線策略改為只實作 `prepare_context(...)` 與 `decide_bar(...)`，避免每個策略重複處理 signal 對齊與上一根 target 狀態。
- 新增 `strategies.registry`，CLI 透過 Phase 1 factory 建構 long-only 策略；2026-05-24 起納入 `absolute-momentum` 作為 compare-only 趨勢持有候選。
- `VolumeFilteredStrategy` 維持外層 wrapper，不併入策略本體。
- 新增 template、factory、三策略 regression tests，確保重構不改 target / reason / score contract。

### 7. Entry Edge 多持有期比較

- `entry-edge` 新增 `--hold-bars-list`，支援逗號分隔正整數，例如 `1,3,5,10`。
- 不提供 `--hold-bars-list` 時，原本單一 `--hold-bars-per-day` 的 markdown / summary JSON / trade CSV 輸出不變。
- 提供 `--hold-bars-list` 時，會保留原本單一 hold report，另外輸出 `<run-name>_hold_comparison.json` 與 `<run-name>_hold_comparison.md`。
- comparison row 固定包含 hold bars、decision、Profit Factor status/value、trade count、win rate、average net PnL、max drawdown、ignored/unclosed/overlap counts 與 failure reason。
- 這個功能是為了比較同一策略在不同固定持有期下的 entry-edge 稽核結果，不自動推薦最佳持有期，也不改 SMA Crossover 的 `fast_sma > slow_sma` 訊號語意。

### 8. VWAP Reversion regime filter

- `VwapReversionStrategy` 維持 `BarByBarStrategy` OOP template，只在 `prepare_context(...)` 新增 `regime_sma`，並在 `decide_bar(...)` 判斷可選 regime filter。
- CLI / factory 新增 `--vwap-regime-filter` 與 `--vwap-regime-window`，預設關閉，避免改變既有 VWAP 回測 contract。
- Regime filter 規則是新的 long entry 必須滿足 `close >= sma(close, regime_window)`；若不滿足，reason 為 `regime_downtrend_blocked`。
- 濾網只阻擋 entry，不強制平掉既有持倉；出場仍由原本 `exit_z` / `hold` 語意控制。

### 9. 深度 package 重構與 single-signal Phase contract

- 將 `core`、`backtesting`、`phase`、`reporting`、`data`、`cli` 拆成明確子套件，讓資料型別、策略 contract、entry-edge、Phase adapters、reporting 與 CLI handler 不再擠在頂層單檔。
- 保留舊 public import path：`signal_forge.market_data`、`signal_forge.strategy`、`signal_forge.entry_edge`、`signal_forge.backtester`、`signal_forge.data_fetch` 仍可用；`signal_forge.phase`、`signal_forge.reporting`、`signal_forge.cli` 也維持原 import 名稱。
- 新增 `generate_validated_signals(...)` 與 `build_signal_digests(...)`，集中處理 strategy output 長度驗證、reason normalization 與 SignalDigest 建構。
- `BacktestExecutionAdapter` 現在只呼叫一次 strategy，並把同一份 signals 傳給 `EntryEdgeEvaluator.run_from_signals(...)` 與 digest builder，避免 entry-edge artifact 與 trace artifact 來自不同訊號序列。
- 新增 stateful strategy regression，鎖住 Phase backtest `generate_signals()` 只被呼叫一次；新增 compatibility import regression，鎖住拆包後的 public API。
- 測試 helper 開始集中到 `tests\helpers.py`，避免測試替身與 bar fixture 一直散在不同 test module。

### 10. Target-state 多股票報表

- 新增 `tools\multi_stock_target_state_sweep.py`，用既有 `Backtester` 執行完整 close-to-close target exposure 回測。
- 支援多股票、多策略、多成本倍率，讓 Phase 2 候選可以同時檢查 1x / 2x / 3x 成本壓力。
- Aggregate 固定輸出 positive return count、beat benchmark count、lower drawdown count、average return、average excess、worst MDD、Sharpe、Sortino、Calmar、turnover、time in market、total cost 與 worst drawdown attribution。
- `tests\test_multi_stock_sweep_tool.py` 新增成本倍率 parser 與 target-state aggregate regression。
- 這個工具補上 Phase 1 entry-edge 不能回答的完整持倉問題，但不改 `PhaseRunner` 現有 artifact contract，也不碰 live dry-run 邊界。

### 11. Volatility target 風控 overlay

- 新增 `src\signal_forge\strategies\volatility_target.py`，用 realized close-to-close volatility 將底層策略的非零 `target_position` 縮小到目標年化波動附近。
- `max_scale=1.0` 是預設安全語意：只降曝險、不加槓桿。
- `build_phase1_strategy(...)` 可選擇性套用 volatility target wrapper；target-state sweep 新增 `--volatility-target`、`--volatility-lookback-bars`、`--target-annual-volatility`、`--volatility-min-observations` 與 `--volatility-max-scale`。
- 新增 `tests\test_volatility_target.py`、factory regression 與 target-state parser regression，鎖住縮放公式、wrapper 名稱與 CLI 參數。
- 目前 `absolute-momentum + vol-target` 結果屬 compare-only：可以降低 worst MDD，但 Sharpe / Calmar 與 benchmark-relative 問題尚未解決。

### 12. Target-state drawdown attribution

- `TargetStateRow` 新增最大回撤的 peak、trough、recovery timestamp、duration / recovery bars、trough position 與 peak-to-trough 平均絕對曝險。
- `TargetStateAggregate` 會直接指出同一策略 / 成本組合中 worst MDD 來自哪檔股票與哪段期間。
- Markdown 報表新增 `Drawdown Attribution` 與 `Per Stock Drawdown` 區塊，讓策略優化先定位回撤來源，再決定要加 volatility scaling、drawdown-state exit、per-symbol risk-off 還是 walk-forward / OOS。
- `tests\test_multi_stock_sweep_tool.py` 鎖住 peak / trough / recovery 與曝險計算，避免報表欄位 drift。

### 13. Drawdown risk-off 風控 overlay

- 新增 `src\signal_forge\strategies\drawdown_risk_off.py`，用策略層 proxy equity 追蹤單檔高點回撤，回撤超過門檻後把非零 target 暫時改成 flat。
- wrapper 對齊 `Backtester` close-to-close target exposure 語意：第 `index` 根 bar 先承擔既有 position 從前一根 close 到目前 close 的報酬，再套用目前 signal。
- Risk-off 結束後會用當下 proxy equity 重設本地 high-water mark，避免 flat 期間因舊高點造成永久停用。
- `build_phase1_strategy(...)` 新增可選 `drawdown_risk_off`、`drawdown_risk_off_threshold`、`drawdown_risk_off_bars`，並接入 target-state sweep 的 `--drawdown-risk-off` CLI 參數。
- 新增 `tests\test_drawdown_risk_off.py`、factory regression 與 target-state parser regression，鎖住回撤觸發、standdown rearm、flat reason 保留與參數解析。
- 本輪策略結果屬 compare-only / discard 分流：`dd-risk-off 20%/60` 讓 worst MDD 惡化，discard；`dd-risk-off 25%/120` 與 `vol-target 0.40 + dd-risk-off 25%/120` 能降低 MDD，但仍只有 `1/7` beat buy-and-hold，不能升級主候選。

### 14. Target-state walk-forward / OOS 分段驗證

- `tools\multi_stock_target_state_sweep.py` 新增 `WalkForwardWindow`、`WalkForwardWindowResult` 與 `WalkForwardRetentionRow`，保留既有 full-window `rows` / `aggregates` schema，將 OOS 結果放在額外 JSON 欄位。
- CLI 新增 `--walk-forward-windows`，格式是 `label:start:end,label:start:end`，例如 `is:2020-01-01:2023-12-31,oos:2024-01-01:2026-05-20`。
- Markdown 報表新增 `Walk-forward Windows` 與 `Walk-forward Retention`，用相鄰 window 比較 return retention、Sharpe retention、benchmark excess 與 MDD change。
- `tests\test_multi_stock_sweep_tool.py` 新增 parser、retention 對齊與 OOS CLI regression，確保分段驗證是 deterministic、test-covered 的報表功能。
- 本輪用同一批七檔 TWSE common window 驗證 `absolute-momentum`、`absolute-momentum + vol-target 0.40 + dd-risk-off 25%/120`、`confluence-score + cooldown10`。三者樣本外平均報酬沒有崩潰，但 OOS benchmark-relative 仍不合格，不能升級成穩定營利主候選。

### 15. Relative momentum stock-pool filter

- `tools\multi_stock_target_state_sweep.py` 新增 `build_relative_momentum_allowlist(...)` 與 `RelativeMomentumFilteredStrategy`，以跨股票 lookback return 排名建立每檔股票可持倉 timestamp 白名單。
- CLI 新增 `--relative-momentum-filter`、`--relative-momentum-lookback-bars`、`--relative-momentum-top-n` 與 `--relative-momentum-min-return`，預設關閉，不改既有 target-state sweep 行為。
- Wrapper 語意是：底層策略先產生逐 bar signal；若某 timestamp 不在該 symbol 的相對動能白名單，非零 target 會被改成 `0.0`，reason 為 `relative_momentum_filter_blocked`。
- `tests\test_multi_stock_sweep_tool.py` 新增 parser、allowlist ranking 與 wrapper flatten regression，確保這個股票池濾網是 deterministic、test-covered。
- 研究結果屬 compare-only / discard：2024-2026 OOS 掃描 `lookback=63/126/252` 與 `topN=1/2/3/4/5/7` 後，最佳 active return 仍是 `lookback=126, topN=7`，等同幾乎不做相對排名篩選；較嚴格 top-N 只降低曝險，沒有改善 `Beat B&H`。

### 16. Portfolio-level relative momentum rotation

- 新增 `tools\portfolio_rotation_sweep.py`，將多檔股票視為同一資金池，而不是逐檔各自回測。
- 工具會把 CSV 對齊到共同 timestamp，依 `rebalance_frequency`、`lookback_bars`、`top_n`、`min_return` 產生 long-only 等權配置；未入選資金留現金。
- Benchmark 改為同一股票池的 equal-weight buy-and-hold portfolio，避免用逐檔 B&H 誤判輪動策略。
- 新增可選 market regime overlay：`--market-regime-filter` 與 `--market-regime-sma-bars` 會用等權市場指數跌破 SMA 時留現金，並在 Markdown / JSON 補上 `market_regime_filter`、`market_regime_sma_bars`、`regime_block_count`。SMA84 可把 2021-2022 excess 從 `-24.62%` 改到 `-13.59%`，但 full-window IR 從 `0.858` 降到 `0.544`，因此只保留為 compare-only，不升級主候選。
- 新增可選 portfolio volatility target：`--volatility-target`、`--volatility-lookback-bars`、`--target-annual-volatility`、`--volatility-min-observations`、`--volatility-max-scale` 會在 rebalance date 對已選出投組按 realized volatility 只降曝險、不加槓桿。`lookback=42 / target=20%` full-window IR 只剩約 `0.065`，`2021-2022` excess 仍約 `-22.85%`，因此只保留為 compare-only，不升級主候選。
- 新增可選 breadth filter：`--breadth-filter`、`--breadth-lookback-bars`、`--breadth-min-positive-count`、`--breadth-positive-threshold` 會在 rebalance date 檢查股票池正動能檔數，寬度不足時留現金。`breadth lookback 42 / min positive 2` full-window IR 約 `1.017`、MDD 約 `-21.11%`，是目前最佳折衷；但 `2021-2022` excess 仍約 `-16.91%`，不能宣稱穩定營利。
- 資料池擴大到 14 檔 TWSE 日線後，`breadth lookback 42 / min positive 3` 取代七檔版本成為目前最佳折衷：full-window IR 約 `1.417`、MDD 約 `-23.01%`，1x/2x/3x 成本與 6 個 rolling windows 都保持正 excess。
- `src\signal_forge\data\fetch.py` 修正 TWSE 批次下載可靠性：request 會帶 `SignalForge/1.0 research data fetcher` User-Agent，並對 HTTP 308 redirect 做 bounded follow；`tests\test_data_fetch.py` 鎖住這個 regression。
- `PortfolioRotationResult` 新增 `symbol_attribution`，逐股輸出實際持倉期間數、再平衡入選次數、平均權重、`weight * close-to-close return` 貢獻與絕對貢獻占比。
- `PortfolioRotationResult` 新增 `max_symbol_abs_contribution_symbol`、`max_symbol_abs_contribution_share` 與 `top3_symbol_abs_contribution_share`，讓 full-window 與 rolling window 都能直接檢查是否過度依賴少數股票。
- Markdown 報表新增 `Top Symbol Attribution` 與 `Walk-forward Top Symbol Attribution`，讓 full-window 與 rolling window 都能檢查報酬是否集中在少數股票。
- CLI 支援 `--rebalance-frequency daily|weekly|monthly`、`--lookback-bars`、`--top-n`、`--min-return`、`--cost-multipliers-list`、`--walk-forward-windows` 與 JSON/Markdown 摘要輸出。
- 報表已新增 `annualized_active_return`、`tracking_error`、`information_ratio` 與 `active_max_drawdown`，用 relative equity 檢查主動風險報酬與相對 benchmark 回撤。
- CLI 已新增自動 rolling windows：`--rolling-window-months`、`--rolling-step-months`、`--rolling-min-months`；它會產生 `roll01`、`roll02` 這類日期窗，避免每次手寫少數分段。
- `tests\test_portfolio_rotation_sweep_tool.py` 新增 parser、共同日期對齊、top momentum 選股、benchmark 成本、market regime block、breadth block、volatility scaling、retention 與 symbol attribution regression。
- 本輪結果：原始七檔 `monthly + 21 bars + top3` 在 full-window 與 2024-2026 OOS 很強，但 24 個月 rolling 顯示 `2021-2022` return 約 `-18.74%`、excess 約 `-24.62%`、IR 約 `-0.881`。七檔 `breadth 42/min2` 改善但仍未修好 `2021-2022`。14 檔 `breadth 42/min3 top3` 讓 full-window IR 約 `1.417`、MDD 約 `-23.01%`，且 rolling `6/6` 正 excess；`top4` 把 full-window MDD 改到約 `-18.61%`、active MDD 改到約 `-20.21%`、IR 仍約 `1.401`，因此成為目前風險調整折衷候選。但 concentration guard 顯示 `roll02` 仍高度依賴 `2603`、`roll06` 依賴 `2308`，資料也未還原權息、股票池仍小，所以仍不能宣稱穩定營利。

## 重要 commit 節點

| Commit | 類型 | 摘要 |
|---|---|---|
| `fd8dcfd` | experiment | add free daily data fetch CLI |
| `8206e19` | docs | record trace summary first/last reason |
| `cc6e50b` | experiment | trace summary adds first/last reason |
| `e02e79f` | experiment | csv validator cross-checks min/max target_position |
| `d3f59e5` | docs | add strategy notes sync rule |
| `current` | experiment | reorganize package boundaries and single-signal Phase backtest |

## 目前下一步

- 只擴充 deterministic、test-covered 的 backtest artifacts。
- 優先補強 trace summary 或 validation，不做績效最佳化。
- SMA Crossover 可先用 `--hold-bars-list` 比較一日、三日、五日、十日固定持有期，再決定是否進入完整趨勢持有 / 出場規則設計。
- VWAP Reversion 可比較未啟用與啟用 `--vwap-regime-filter` 的結果，確認簡單趨勢濾網是否降低強下跌中的反向接刀。
- Target-state 主線先以 `absolute-momentum` 作 compare-only 錨點；逐檔 target-state 已證明 benchmark-relative 問題仍存在。Portfolio-level rotation 是目前較有希望的新主線；14 檔 `breadth 42/min3 top4` 是目前風險調整折衷，但 concentration guard 顯示部分 rolling window 仍有單檔集中風險。下一步應測 top-N 以外的 concentration-aware 約束，並用 Information Ratio / active drawdown gate 防止單一 OOS window 過度樂觀。
- OOP template 已完成後，下一步仍要分開討論 SMA Crossover、VWAP Reversion、Confluence Score、Absolute Momentum 的策略語意修改。
- 若新增策略或改策略邏輯，同步更新 [[../策略筆記/策略筆記索引|策略筆記]]。
- push 前先把 Obsidian 筆記同步進 repo `docs/`。
