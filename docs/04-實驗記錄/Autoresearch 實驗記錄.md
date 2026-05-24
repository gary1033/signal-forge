---
title: Autoresearch 實驗記錄
tags:
  - project/SignalForge
  - experiment
  - autoresearch
status: active
updated: 2026-05-24
---

# Autoresearch 實驗記錄

這份筆記彙整 SignalForge bounded autoresearch 的執行結果。完整逐列 audit trail 原本來自 `phase-iteration-log.md` 與 `phase-autoresearch-results.md`，現在整理為實驗記錄資料夾的一份 canonical 筆記。

## 實驗契約

- 主線：回測可驗證性。
- 方法：`modify -> verify -> keep/discard -> log`。
- 每次 wakeup 只做一個聚焦改動。
- 允許策略研究、策略績效最佳化、參數調整與策略更新，但每次改動都要保留可重現驗證與 discard 路徑。
- 任何回測、優化、參數調整或找新策略的輪次，都必須參考 [[../02-規劃/策略回測與優化評估準則|策略回測與優化評估準則]]，並在結果中說明本輪是 keep、discard 還是 compare-only。
- 不新增 broker。
- 不新增 API key / credential 讀取。
- 不新增真實下單介面。
- 不碰 live 送單能力。

## 固定驗證

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
cd C:\Projects\signal-forge
$env:PYTHONPATH = "src"
python tools\phase_readiness_score.py
python -m unittest discover -s tests
git diff --check
```

目前目標：readiness score 維持 `110`，unit tests 全部通過。

## 實驗結果摘要

2026-05-19 到 2026-05-20 的 autoresearch 主線，主要把 Phase 從「可以切 mode」推進到「backtest 與 live 的輸出 contract 都能被 regression tests 鎖住」。

已完成類別：

- Phase mode / config / runner / adapters。
- Live dry-run safety marker：`LIVE_DRY_RUN_ONLY`。
- Phase summary JSON schema 與 exact-text contract。
- Phase markdown exact-text contract。
- Entry Edge outputs deterministic contract。
- Signal digest CSV：entry、flatten、hold、position change、hold side。
- Trace summary JSON：schema version、counts、timestamp、reason、position buckets、CSV hash。
- Cross-check validator：signals CSV 與 trace summary 完全對齊。
- Strategy OOP template：`BarByBarStrategy`、`StrategyDecision`、strategy registry / factory、三策略 regression tests。
- Entry Edge 多持有期比較：`--hold-bars-list`、hold comparison JSON/Markdown exact contract。
- VWAP Reversion regime filter：`--vwap-regime-filter`、`--vwap-regime-window`、entry-only 趨勢濾網 regression。

## 近期實驗表

| 時間 | 目標 | 結果 | 決策 |
|---|---|---|---|
| 2026-05-19 16:27 | 文件 encoding 與 readiness needle 整理 | 110；tests OK | keep |
| 2026-05-19 17:13 | Backtest Phase report golden regression | 110；tests OK | keep |
| 2026-05-19 18:57 | Live Phase report contract regression | 110；tests OK | keep |
| 2026-05-19 20:14 | Backtest trace visibility：`*_signals.csv` | 110；tests OK | keep |
| 2026-05-19 21:42 | Backtest `*_trace_summary.json` | 110；tests OK | keep |
| 2026-05-20 03:36 | Cross-check backtest artifacts | 110；tests OK | keep |
| 2026-05-20 05:22 | Backtest timestamp ISO-8601 稽核 | 110；tests OK | keep |
| 2026-05-20 08:20 | Trace summary 加入 `signal_digest_sha256` | 110；tests OK | keep |
| 2026-05-20 09:22 | Phase markdown 顯示 trace schema 與 position buckets | 110；tests OK | keep |
| 2026-05-20 10:26 | Trace summary first/last reason 稽核 | 110；tests OK | keep |
| 2026-05-20 22:50 | OOP strategy template 與 registry | 83 tests OK | keep |
| 2026-05-20 23:20 | Entry Edge 多持有期比較報表 | 110；87 tests OK | keep |
| 2026-05-20 23:50 | VWAP Reversion 可選 regime filter | 110；tests OK | keep |

## 2026-05-21 研究輪：ORB + Volume + VWAP 候選

這輪先做研究提案，不直接改正式策略程式。主候選鎖定 `Opening Range Breakout + Volume + VWAP`，原因是它和 SignalForge 現有的 long-only、`--volume-filter`、VWAP 對齊語意最接近，若要導入，能沿用既有 `BarByBarStrategy` 模板拆成 `prepare_context(...)` / `decide_bar(...)`。

### 來源

- TradingView open-source：NeuraEdge ORB - Opening Range Breakout Indicator
  https://tw.tradingview.com/script/Sb0YgLYU-NeuraEdge-ORB-Opening-Range-Breakout-Indicator/
- TradingView open-source：ORB + Volume + VWAP Breakout
  https://tw.tradingview.com/script/7khuDtm8-ORB-Volume-VWAP-Breakout/
- TradingView open-source：Anchored VWAP
  https://tw.tradingview.com/script/L1tWQjgR-Anchored-VWAP/

### 候選摘要

- `ORB + Volume + VWAP`：先鎖定開盤區間，再要求 breakout bar 同時滿足相對量能放大與價格站上 session VWAP，屬於很適合 Phase 1 long-only 的進場訊號候選。
- `NeuraEdge ORB`：功能更完整，還帶 retest、FVG、SL/TP 與 performance tracking；但這些內容超出目前 SignalForge Phase 1 的最小導入範圍，直接搬進來會一次混入太多產品判斷。
- `Anchored VWAP`：概念本身可做研究，但 anchor 要綁事件、日期還是 session，屬於需要額外產品判斷的分支，暫不列為本輪執行候選。

### 適配判斷

- 最適合下一輪執行的是 `ORB + Volume + VWAP` 的「簡化 long-only 版本」。
- 第一版可先固定：
  - 只做 long breakout。
  - breakout 以 bar close 確認。
  - volume filter 使用相對量能門檻。
  - VWAP 使用 session VWAP，要求 `close > vwap`。
  - 不帶停損、停利、short、alert webhook、dashboard。
- 這樣可以先驗證「開盤區間突破 + 量能 + VWAP」本身是否值得納入現有 entry-edge 流程，而不是一次引入整套 intraday 交易框架。

### 風險與驗證邊界

- ORB 是 intraday 概念；目前 repo 主要示範資料是日線，若要實作，需要先確認是否引入 intraday OHLCV 樣本，否則只能先完成策略模板與測試替身。
- Session window 是核心語意；不同市場（美股、期貨、台股）開盤定義不同，不能直接硬寫美股 `09:30-10:00` 到通用策略。
- TradingView 腳本常含 intrabar 視覺訊號或 alert 描述；SignalForge 這邊只接受 close-confirmed、non-repainting 的 deterministic signal。
- Anchored VWAP 的 anchor 起點若需要人工事件選擇，會超出目前 automation 可自動決策的範圍。

### 下一步

- 下一輪執行可考慮只做一個最小改動：新增 `orb-volume-vwap` 策略骨架或先建立測試替身與 registry 預留，保持 `BarByBarStrategy` template 對齊。
- 若先不引入新策略，也可先做更小的比較研究：把現有 `--volume-filter` 與 VWAP 語意整理成是否足以近似 ORB 腳本的需求。
- 若要真的進入 ORB 實作，先補一份 intraday 資料需求與 session 定義筆記，再決定資料層怎麼接。

## 2026-05-21 研究輪：ORB 下一步優化方向

這輪延續 ORB 候選，但不再找新策略，而是聚焦「ORB + Volume + VWAP」下一個最值得加的優化。結論是：**優先考慮 retest confirmation，不優先做多時間框架或更多濾網堆疊。**

### 來源

- TradingView open-source：ORB Breakout Strategy with VWAP and Volume Filters
  https://tw.tradingview.com/script/wLSGHPUe-ORB-Breakout-Strategy-with-VWAP-and-Volume-Filters/
- TradingView open-source：ORB Breakout & Retest
  https://tw.tradingview.com/script/tJGpjdb1-ORB-Breakout-Retest/
- TradingView Pine Script docs：Bar states / `barstate.isconfirmed`
  https://www.tradingview.com/pine-script-docs/v5/concepts/bar-states/

### 研究結論

- `ORB Breakout & Retest` 明確把流程拆成「先突破、再回踩、再確認」，核心目的是減少假突破，這和目前 SignalForge 已經有的 close-confirmed、single-signal 模板相容。
- TradingView 官方文件指出 `barstate.isconfirmed` 適合用來避免 repaint；而它**不能**安全地拿去配 `request.security()` 使用。這代表若下一步優化選 retest confirmation，可以沿用目前單時間框架、bar-close confirmed 的 deterministic 邏輯；若直接走多時間框架 ORB，會更容易碰到資料對齊與 repaint 邊界。
- 另一份 ORB 策略頁面同時提到 VWAP slope、candle strength、session close exit 等更多可調濾網，但這些會一次打開太多產品判斷。對目前 automation 來說，retest confirmation 的增量最清楚。

### 對 SignalForge 的含義

- 現在的 `orb_volume_vwap_breakout` 是「第一時間突破就進」。
- 下一個最小可驗證優化，可以改成兩段式狀態：
  1. 記錄某個 session 已經突破 OR high。
  2. 等回踩 OR high 附近後，再出現重新站回 OR high 上方的 close-confirmed bar 才翻成 long。
- 這比直接加入多時間框架或更多 filter 更符合目前 repo 的 deterministic 與 template 邊界。

### 先不做的分支

- **多時間框架 ORB**：需要額外資料來源或 `request.security` 類比邏輯，風險高於本輪預期。
- **VWAP slope / candle strength / ATR / FVG**：都可能有研究價值，但每個都會再增加一層語意與參數面，暫時不是最小下一步。
- **Session close 強制平倉**：這屬於持倉語意決策，要先決定 ORB 在 SignalForge 是 entry-edge 候選還是完整 intraday 持有系統。

## 2026-05-21 研究輪：ORB 持有語意判斷

這輪研究聚焦在 ORB 的持有與離場語意。結論是：**session close exit 很常見，也合理，但它不再只是 filter 或 entry refinement，而是把策略正式推向完整 intraday 持有系統。**

### 來源

- TradingView rangebreakout scripts 總覽
  https://tw.tradingview.com/scripts/rangebreakout/
- TradingView open-source：Opening Range Breakout + VWAP + Volume [ORB Strategy]
  https://tw.tradingview.com/script/hapKLoXr-Opening-Range-Breakout-VWAP-Volume-ORB-Strategy/
- TradingView 開盤區間腳本彙整頁面（含 retest、RTH VWAP、session close flat 描述）
  https://tw.tradingview.com/scripts/opening/

### 研究結論

- 多個 ORB 腳本把「regular trading session 結束前平倉」當成預設流程，因為 ORB 本質常被視為日內動能策略，而不是隔夜持有策略。
- 這和目前 SignalForge 的 ORB 實作不同：現在版本比較像「intraday breakout signal state machine」，有 session reset，但沒有明確的 session close exit 語意。
- 若直接加入 session close exit，策略就不再只是 entry refinement，而會開始定義「持倉多久」、「何時一定離場」這類完整持有規則。

### 對 SignalForge 的含義

- `retest confirmation` 屬於進場品質優化，仍在目前 automation 可安全處理的範圍。
- `session close exit` 則更接近 Phase 2 題目，因為它會影響：
  - ORB 策略是拿來做 entry-edge 候選，還是完整 intraday strategy。
  - 測試資料是否要包含 session 結束 bar。
  - reporting 是否要明確顯示 forced flatten / session close exit。
- 所以它是合理候選，但不應該在沒有額外產品判斷的情況下由 automation 直接硬做。

### 建議排序

1. 先保留現在的可選 retest confirmation，讓 ORB 進場語意穩定。
2. 再決定 ORB 是否要進入「明確 session close exit」版本。
3. 如果要做 session close exit，應一起定義：
   - session 結束時間是否可參數化；
   - session close flat 是 hard rule 還是可選 rule；
   - entry-edge / phase reporting 要怎麼反映 forced exit。

## 2026-05-21 研究輪：ORB session 參數化與 extended-hours

這輪研究聚焦在 ORB 的 session 起點、時區與 extended-hours 處理。結論是：**下一個最合理的工程方向，是把 session start / end / timezone 從內建假設提升成明確設定，否則 ORB 很難脫離美股 `09:30` 假設。**

### 來源

- TradingView openingrange scripts 彙整
  https://tw.tradingview.com/scripts/openingrange/
- TradingView openrange scripts 彙整
  https://tw.tradingview.com/scripts/openrange/
- TradingView sessions scripts 彙整
  https://tw.tradingview.com/scripts/sessions/
- TradingView open-source：Multi-Session ORB
  https://tw.tradingview.com/script/bO5hteNH-Multi-Session-ORB/

### 研究結論

- 多數 ORB 腳本都把 **session window**、**timezone**、甚至 **是否延伸到其他市場時段** 做成顯式設定。
- TradingView 的實務語境裡，extended-hours 常被視為和 regular session 不同的資料區塊；如果不明確定義 session 邊界，ORB 高低點會因資料 feed 與時段切法不同而漂移。
- 這對 SignalForge 的含義很直接：目前 `OrbVolumeVwapStrategy` 內建 `09:30` 只適合當研究起點，不適合視為長期預設真理。

### 對 SignalForge 的含義

- 現在的策略已經能運作，但它在語意上其實是「美股 regular session ORB 假設版」。
- 若要讓 ORB 真正能被台股、美股 extended-hours 關閉版、或其他期貨 session 使用，至少要把這些邊界講清楚：
  - session start hour / minute
  - opening range 持續多久
  - 是否只看 regular session
  - session VWAP 是否隨同一個 session reset
- 這些設定屬於高價值改動，但仍比 `session close exit` 更偏工程參數化，產品風險較低。

### 建議排序

1. 保留目前 ORB + retest confirmation 邏輯不變。
2. 下一個執行輪優先考慮把 session 起點與 OR 長度暴露成更明確的 CLI / strategy spec。
3. extended-hours 是否納入，先以筆記與資料假設界定，不急著直接在策略內做第二套 session 模式。

## 2026-05-21 執行輪：ORB session 起點與 OR 長度參數化

這輪不碰 `session close exit` 或 extended-hours 模式，只做較低風險的工程參數化：把 `OrbVolumeVwapStrategy` 原本寫死的 session 起點與 opening range 長度接進 strategy factory、CLI 與 strategy spec。

### 修改內容

- `OrbVolumeVwapStrategy.name` 現在會把 session 起點編進策略名稱，例如 `ss0930`。
- `build_strategy(...)` / `build_phase1_strategy(...)` 新增：
  - `orb_opening_range_minutes`
  - `orb_session_start_hour`
  - `orb_session_start_minute`
- CLI 新增：
  - `--orb-opening-range-minutes`
  - `--orb-session-start-hour`
  - `--orb-session-start-minute`
- `strategy_spec` 會把 ORB session 相關設定寫出來，避免之後看 artifact 時只知道用了 ORB，卻不知道是從幾點開始建 OR。

### 驗證

- `python tools\phase_readiness_score.py` -> `110`
- `python -m unittest discover -s tests` -> `103 tests OK`
- `git diff --check` -> clean

### 決策

- keep
- 這次改動把 ORB 從「隱含美股 09:30 假設」推進到「至少可明確宣告 session 起點與 OR 長度」。
- `session end` / `timezone` / extended-hours 仍留在下一步，因為它們會牽涉更完整的 session 邊界語意，而不只是 parser plumbing。

## 2026-05-21 研究輪：ORB 的 timezone / regular-hours / extended-hours 邊界

這輪延續 ORB 的 session 主題，但不再改程式，而是確認下一步應該把什麼留在策略參數、什麼留在資料假設。結論是：**`session end` 與 `timezone` 值得進一步參數化；extended-hours 則應先被視為資料邊界，而不是馬上做成策略內第二套模式。**

### 來源

- TradingView Pine Script docs：Sessions
  https://www.tradingview.com/pine-script-docs/v5/concepts/sessions/
- TradingView ORB scripts index
  https://tw.tradingview.com/scripts/orb/
- TradingView opening-range-breakout scripts index
  https://tw.tradingview.com/scripts/opening-range-breakout/

### 研究結論

- TradingView 官方文件把 `time(timeframe, session, timezone)`、`session.ismarket`、`session.ispremarket`、`session.ispostmarket` 都列成 session 判斷的核心工具，表示 session/timezone 在 Pine 世界本來就是一級設定，不只是視覺化細節。
- 官方文件也明確區分 `session.regular` 與 `session.extended`，而且 extended session 需要透過不同的 ticker / `request.security(...)` 取值語意來處理。這代表 extended-hours 不是單純多一個 if 條件，而是資料來源邊界本身不同。
- 多個公開 ORB 腳本都把 `session start hour/minute`、`range duration`、甚至 `box duration` 或 `session preset` 暴露成參數。這支持我們目前已做的 session start / OR 長度參數化，也說明下一步若要補 `session end` 或 `timezone`，在方法論上是合理的。

### 對 SignalForge 的含義

- ORB 現在已經有 `session start` 與 `opening range length`，但還缺：
  - `session end`
  - `timezone`
  - regular-hours-only 是否是明確 contract
- 若現在就把 extended-hours 直接做成策略模式，會同時打開：
  - bar 是否屬於 premarket / postmarket；
  - VWAP 是否跨 extended session 連續累積；
  - OR high / low 是否應包含 premarket 價格；
  - 測試資料是否要切成不同 session 類型。
- 這些都超過本輪 automation 適合自行定版的範圍，所以較合理的做法，是先把它記成研究邊界，而不是急著做第二套 session engine。

### 建議排序

1. 先保留目前 ORB 的 regular-session 研究定位。
2. 若下一輪要再做執行，優先考慮把 `session end` 與 `timezone` 納入 CLI / strategy spec。
3. extended-hours 先只記錄成資料假設與風險邊界，等真的有對應資料樣本與產品判斷，再決定是否要做成可選模式。

## 2026-05-21 執行輪：ORB regular-session 邊界寫入 strategy spec

這輪不改 ORB 的進出場判定，也不新增 extended-hours 模式，只把前一輪研究得到的邊界正式寫進 CLI / artifact contract。目標是讓 summary JSON 與後續報表能直接看出：**目前 ORB 只是 regular-session 研究版本，extended-hours 不在既有保證範圍內。**

### 修改內容

- `strategy_spec` 新增：
  - `orb_session_scope = regular-session research contract only`
  - `orb_extended_hours_policy = extended-hours bars are outside the current ORB research contract until session/data boundaries are defined explicitly`
- CLI regression tests 同步鎖住這兩個欄位，避免未來 artifact 失去這個邊界說明。

### 驗證

- `python tools\phase_readiness_score.py` -> `110`
- `python -m unittest discover -s tests` -> `104 tests OK`
- `git diff --check` -> clean

### 決策

- keep
- 這次改動的價值不是新增功能，而是把 ORB 現階段的研究範圍從「藏在聊天與筆記裡」提升成「artifact 直接可見」。
- `session end` 與 `timezone` 仍留給下一個執行輪；這次先把 contract 補齊，避免在資料邊界尚未定義時讓使用者誤以為 extended-hours 已經被支持。

## 2026-05-21 研究輪：ORB range size / trading cutoff 哪個更適合下一步

這輪研究聚焦在 ORB 的兩種常見細化：**開盤區間大小過濾（range size filter）** 與 **交易截止時間（trading cutoff）**。結論是：**若只選一個較低風險、較接近現有 repo 邊界的下一步，應優先做 range size filter，而不是先做 trading cutoff。**

### 來源

- TradingView open-source：NeuraEdge ORB - Opening Range Breakout Indicator
  https://tw.tradingview.com/script/Sb0YgLYU-NeuraEdge-ORB-Opening-Range-Breakout-Indicator/
- TradingView ORB 腳本彙整頁面
  https://tw.tradingview.com/scripts/opening-range-breakout/
- TradingView 開盤區間腳本彙整頁面
  https://tw.tradingview.com/scripts/opening/

### 研究結論

- `NeuraEdge ORB` 直接把 OR size 和 `ATR(14)` 比較，並指出 `0.5x-1.5x ATR` 常是較合理的區間；同時也明講極小區間容易假突破、極大區間則代表 gap day 或風險已經擴大。
- 另一批 ORB scripts 也會把 `Normal ORB range size` 當成打分條件，和 VWAP alignment、volume boost 並列。這代表「range 是否正常」在 ORB 世界裡不是視覺附註，而是常見的訊號品質條件。
- 相較之下，`trading cutoff hour` 雖然也常見，但它已經開始定義「過了幾點之後不再允許新訊號」，本質上更接近 session policy，而不是純 entry quality filter。

### 對 SignalForge 的含義

- `range size filter` 的優點：
  - 仍是 single-session、single-timeframe 邏輯；
  - 不需要引入 extended-hours 或 session close exit；
  - 可以只用既有 OR high / low，再補一個簡單的 range normalization。
- `trading cutoff` 的風險：
  - 會把策略往「時間治理規則」再推一步；
  - 跟 `session end`、timezone、regular-hours-only contract 更糾纏；
  - 比較像 session policy，不是單純訊號品質。

### 建議排序

1. 下一個較低風險的 ORB 優化，優先考慮「開盤區間大小是否正常」的 filter 或至少先把 OR range 寫進 artifact。
2. `trading cutoff` 可以列為後續候選，但較適合和 `session end`、timezone 一起討論。
3. Gap direction、EMA、FVG 都先放後面，因為它們會同時增加更多前置語意與跨模組依賴。

## 2026-05-21 執行輪：ORB 新增可選 range size filter

這輪沿著前一輪研究，對 `ORB + Volume + VWAP` 補上一個最小、可驗證的 **range size filter**。實作方式不是直接上 ATR，而是先用更保守的定義：**OR 寬度 / session 第一根 bar 開盤價**。只有當這個比例落在設定的最小/最大區間內，突破訊號才允許成立。

### 修改內容

- `OrbVolumeVwapStrategy` 新增：
  - `min_opening_range_pct`
  - `max_opening_range_pct`
- 新增 reason：
  - `opening_range_too_narrow`
  - `opening_range_too_wide`
- CLI 新增：
  - `--orb-min-range-pct`
  - `--orb-max-range-pct`
- `strategy_spec` 新增 OR range 相關欄位與規則描述，讓 artifact 可以直接看出 range size gate 是否啟用。

### 為什麼先做這個版本

- 它仍然是 single-session、single-timeframe 的 entry quality filter。
- 不需要引入 `session end`、timezone policy 或 extended-hours。
- 先把「極窄 / 極寬 OR」這種明顯品質問題擋掉，再決定未來是否要升級成 ATR-normalized 版本。

### 驗證

- `python tools\phase_readiness_score.py` -> `110`
- `python -m unittest discover -s tests` -> `107 tests OK`
- `git diff --check` -> clean

### 決策

- keep
- 這次改動把 ORB 從「只有 breakout + volume + VWAP」推進到「可選擇排除明顯不正常的開盤區間」。
- 是否改成 ATR-normalized、是否把 trading cutoff 一起納入，仍留在下一步，不在這輪擴張。

## 2026-05-21 研究輪：range size filter 之後先做 ATR-normalized 還是 artifact 可視化

這輪研究聚焦在一個很實際的下一步排序問題：`range size filter` 已經有最小版本後，下一步是直接升級成 ATR-normalized，還是先把 OR range 指標寫進 artifact / reporting。結論是：**先做 artifact 可視化，比直接上 ATR-normalized 更合理。**

### 來源

- TradingView ORB scripts index
  https://tw.tradingview.com/scripts/orb/
- TradingView opening-range-breakout scripts index
  https://tw.tradingview.com/scripts/opening-range-breakout/
- TradingView open-source：NeuraEdge ORB - Opening Range Breakout Indicator
  https://tw.tradingview.com/script/Sb0YgLYU-NeuraEdge-ORB-Opening-Range-Breakout-Indicator/

### 研究結論

- 多個 ORB 腳本不只把 `Normal ORB range size` 當濾網，也會把它放進 on-chart score、label 或 dashboard，讓交易者直接看到這一天的 OR 是偏窄、正常還是偏寬。
- `NeuraEdge ORB` 的 ATR-normalized 做法有研究價值，但它背後其實包含兩件事：
  1. 用 ATR 當 normalization；
  2. 把 OR size 當成顯式可讀的評估欄位。
- 對 SignalForge 來說，第 2 點更應該先做。因為如果 artifact 裡看不到 OR range pct，本輪新增的 range size filter 雖然存在，後續分析卻很難知道它到底擋了什麼。

### 對 SignalForge 的含義

- 直接升級 ATR-normalized 的問題：
  - 需要先補一個新的 volatility 指標 helper；
  - 會再打開 window、normalization 基準與 intraday ATR 語意；
  - 但 reporting 端仍然可能看不到當天 OR 到底多大。
- 先做 artifact 可視化的優點：
  - 仍屬 deterministic reporting / trace 可讀性增強；
  - 能直接支撐後續判斷：目前的 `% of first open` 夠不夠用；
  - 若之後真的升級到 ATR-normalized，也更容易做前後比較。

### 建議排序

1. 下一個較低風險的 ORB 執行項目，優先考慮把 `opening_range_pct` 或等價欄位寫進 artifact / reporting。
2. 有了可視化數據後，再決定是否要把 range size gate 升級成 ATR-normalized。
3. `trading cutoff`、gap direction、EMA filter 仍排在後面，因為它們都比這一步更偏策略語意擴張。

## 2026-05-21 執行輪：將 opening_range_pct 寫進 artifact strategy spec

這輪不再改 ORB 的交易判斷，而是把上一輪研究結論落成一個 reporting 改動：**將 run-level 的 `opening_range_pct` 摘要寫進 `summary_json.strategy_spec`**。這樣後續回看 artifact 時，可以直接知道這次資料中的 OR range 大小範圍，而不只是看到 range size filter 有沒有打開。

### 修改內容

- CLI summary `strategy_spec` 新增：
  - `orb_observed_range_pct_sessions`
  - `orb_observed_range_pct_min`
  - `orb_observed_range_pct_max`
  - `orb_observed_range_pct_first`
  - `orb_observed_range_pct_last`
- 這些值是依照目前 ORB 的：
  - `session start`
  - `opening_range_minutes`
  - session 第一根 bar 開盤價
  直接從本次輸入 bars 推導，不改策略本體。
- CLI regression tests 已同步鎖住這些欄位。

### 為什麼這輪先做這個

- 它屬於 deterministic artifact 可視化，不會新增 broker / live / session policy 風險。
- 有了這些 run-level 數字，之後才有基礎判斷：
  - `% of first open` 是否足夠好用；
  - 是否真的需要升級成 ATR-normalized；
  - 哪些資料集經常被 `opening_range_too_narrow` / `opening_range_too_wide` 擋掉。

### 驗證

- `python tools\phase_readiness_score.py` -> `110`
- `python -m unittest discover -s tests` -> `106 tests OK`
- `git diff --check` -> clean

### 決策

- keep
- 這次改動把 ORB 的 range size filter 從「只存在於策略判斷」推進到「artifact 也能直接看到觀測值」。
- ATR-normalized 仍留在下一步；這輪先補觀測證據，不在同一輪再加新的 volatility 語意。

## 2026-05-21 研究輪：opening_range_pct 可視化之後，先做實證比較再決定 ATR-normalized

這輪不改策略碼，而是確認 `orb_observed_range_pct_*` 已經進入 artifact 之後，ORB 的下一步該怎麼排。結論是：**先用這批 run-level 觀測值判斷 `% of first open` 是否夠用，再決定 ATR-normalized 值不值得加入。**

### 來源

- TradingView ORB scripts index
  https://tw.tradingview.com/scripts/orb/
- TradingView opening-range-breakout scripts index
  https://tw.tradingview.com/scripts/opening-range-breakout/
- TradingView open-source：NeuraEdge ORB - Opening Range Breakout Indicator
  https://tw.tradingview.com/script/Sb0YgLYU-NeuraEdge-ORB-Opening-Range-Breakout-Indicator/

### 研究結論

- 多個 ORB 腳本會把 opening range 大小做成 score、label 或 dashboard 欄位，而不是只拿來當一個看不見的 gate。這代表 OR size 先被觀測、再被優化，是更常見的研究順序。
- `NeuraEdge ORB` 的 ATR-normalized 範圍判斷很有參考價值，但它要回答的前提問題其實是：目前用 `% of first open` 算出來的 `opening_range_pct` 是否已經能穩定區分「過窄 / 正常 / 過寬」。
- 既然 artifact 現在已經能寫出 `orb_observed_range_pct_min/max/first/last`，下一步更合理的工作，是先回頭看不同資料集上的觀測值分布與被 filter 擋掉的情況，而不是立刻把另一層 volatility normalization 寫進策略。

### 對 SignalForge 的含義

- 現在的 ORB 已經從「只能開關 filter」提升到「artifact 會留下 range 觀測值」。
- 這表示下一步可以先做比較研究，例如：
  - 哪些資料集的 `orb_observed_range_pct` 長期偏窄；
  - `opening_range_too_narrow` / `opening_range_too_wide` 是否真的常常擋到不合理樣本；
  - `% of first open` 在不同價位股票上是否明顯失真。
- 只有當這些觀測值顯示 `% of first open` 不夠穩定時，ATR-normalized 才從「合理想法」變成「值得實作的下一步」。

### 建議排序

1. 先用目前 artifact 的 `orb_observed_range_pct_*` 做資料回看與比較。
2. 若觀測後發現價格水位效應太強，再把 ATR-normalized gate 升成候選執行項目。
3. 在這之前，先不要同時把 ATR、trading cutoff、session close exit 混進同一輪。

## 2026-05-21 執行輪：將 ORB range gate 分類摘要寫進 artifact

這輪不改 ORB 訊號規則，只補 artifact 可讀性：當 `--orb-min-range-pct` / `--orb-max-range-pct` 啟用時，`strategy_spec` 現在會直接寫出有多少個 session 的 opening range **低於下限、落在 gate 內、或高於上限**。

### 修改內容

- `orb_runtime_spec_from_bars(...)` 新增 gate 分類摘要欄位：
  - `orb_observed_range_pct_below_min_sessions`
  - `orb_observed_range_pct_within_gate_sessions`
  - `orb_observed_range_pct_above_max_sessions`
- 這些值不是策略本體額外推論，而是直接拿已存在的 `orb_observed_range_pct_*` 觀測值，依目前 CLI gate 設定做 deterministic 分類。
- CLI regression tests 新增兩個層次：
  - 既有單一 session fixture 驗證欄位存在且數值正確；
  - 新的雙 session fixture 驗證「一個低於下限、一個落在 gate 內」的分類摘要。

### 為什麼先做這個

- 前一輪研究的重點是「先用 artifact 觀測值做實證比較」；如果 artifact 只寫 min/max/first/last，仍然要手動回推 gate 覆蓋情況。
- 補上分類摘要後，下一輪回看結果時能直接回答：這次的 range filter 幾乎沒擋到東西，還是其實大部分 session 都被擋在 gate 外。
- 這仍屬 reporting / validation 層的可讀性增強，沒有擴張 session policy、extended-hours 或持有語意。

### 驗證

- `python tools\phase_readiness_score.py` -> `110`
- `python -m unittest discover -s tests` -> `107 tests OK`
- `git diff --check` -> clean

### 決策

- keep
- 這次改動讓 ORB range gate 不只「有設定值」，也能在 artifact 直接看出它實際覆蓋到多少 session。

## 2026-05-21 研究輪：ORB 的下一個低風險候選是 breakout distance threshold

這輪延續 ORB，但不再往 ATR-normalized 或 session policy 擴張，而是確認在目前 `volume + VWAP + retest + range gate` 之後，還有沒有更輕量的下一步。結論是：**若要再加一個低風險條件，`breakout distance threshold` 比 trading cutoff、session close exit 或 extended-hours 都更適合。**

### 來源

- TradingView opening-range-breakout scripts index
  https://tw.tradingview.com/scripts/opening-range-breakout/
- TradingView ORB scripts index
  https://tw.tradingview.com/scripts/orb/
- TradingView open-source：NeuraEdge ORB - Opening Range Breakout Indicator
  https://tw.tradingview.com/script/Sb0YgLYU-NeuraEdge-ORB-Opening-Range-Breakout-Indicator/

### 研究結論

- TradingView 的 ORB 彙整頁面裡，常見設定之一就是 `ORB Breakout Distance Required` 與 `Min Breakout % Beyond ORB`。這說明很多實作者不把「剛好收過 OR high」視為足夠，而會要求多出一點距離，避免只吃到貼線雜訊。
- 這種條件和目前 SignalForge 的 ORB 架構相容，因為它仍然是單時間框架、close-confirmed、entry quality filter，不需要引入新的 session engine。
- `NeuraEdge ORB` 也呈現類似精神：不是每個穿越 OR 的動作都該視為有效突破，距離與結構是否夠乾淨本來就是判斷的一部分。

### 對 SignalForge 的含義

- 現在 ORB 的 long 觸發是 `close > OR high`，外加 VWAP、volume、可選 retest 與 range gate。
- 若要再增加一層低風險 refinement，下一個最像「純 entry quality」的選項，是要求：
  - `close >= OR high * (1 + breakout_pct)`，或
  - `close - OR high` 至少超過某個相對門檻。
- 這比 `trading cutoff` 更少牽涉 session policy，也比直接升級 ATR-normalized 更少引入新指標語意。

### 建議排序

1. 先用目前 artifact 的 range gate 摘要回看資料。
2. 若要做下一個小執行項目，優先考慮 `min breakout % beyond OR` 這種距離門檻。
3. ATR-normalized、session close exit、extended-hours 仍先留在更後面的研究分支。

## 2026-05-21 執行輪：ORB 新增可選 breakout distance threshold

這輪把上一輪研究落成一個最小改動：`ORB + Volume + VWAP` 現在可選擇要求 **close 至少超出 OR high 一段最小百分比**，才把突破視為有效。預設仍是 `0.0`，也就是不改既有行為。

### 修改內容

- `OrbVolumeVwapStrategy` 新增 `min_breakout_pct`，並在 `close > OR high` 之後、VWAP / volume 檢查之前先判斷突破距離是否足夠。
- 新增 reason：`breakout_distance_too_small`。
- CLI 新增 `--orb-min-breakout-pct`。
- `strategy_spec` 新增：
  - `orb_min_breakout_pct`
  - `orb_breakout_distance_rule`
- factory / registry / CLI regression / strategy regression 全部同步更新，且維持預設 ORB 名稱與行為不變；只有設定新參數時，strategy name 才會加上 `obp...`。

### 為什麼先做這個

- 它仍是單時間框架、close-confirmed、純 entry quality filter。
- 不需要引入新的 ATR helper、session policy 或持有語意。
- 能直接補上「剛好收過 OR high」與「真正有一段乾淨突破距離」之間的區別。

### 驗證

- `python tools\phase_readiness_score.py` -> `110`
- `python -m unittest discover -s tests` -> `109 tests OK`
- `git diff --check` -> clean

### 決策

- keep
- 這次改動讓 ORB 現在除了 volume、VWAP、retest 與 range gate 外，還能研究「突破距離本身是否足夠」。

## 2026-05-21 研究輪：breakout distance 之後，下一個較輕的候選是 breakout candle strength

這輪延續 ORB 的 entry quality 路線。結論是：**在 breakout distance threshold 之後，下一個仍然維持單時間框架、close-confirmed 邊界的候選，是 breakout candle strength / full-close-above-range，而不是 EMA、gap direction 或 session policy。**

### 來源

- TradingView opening-range-breakout scripts index
  https://tw.tradingview.com/scripts/opening-range-breakout/
- TradingView open-source：ORB 369 - Opening Range Breakout
  https://tw.tradingview.com/script/gOtvISFA-ORB-369-Opening-Range-Breakout/
- TradingView open-source：PumpC Opening Range Breakout (ORB) 5min Range
  https://tw.tradingview.com/script/ZWchgzJq-PumpC-Opening-Range-Breakout-ORB-5min-Range/

### 研究結論

- ORB 彙整頁面裡，常見 filter 不只包含 volume、ATR、distance，也常直接要求 **strong directional candle**，例如 body 佔整根 range 的某個最小比例。
- `ORB 369` 類型腳本更進一步要求 breakout candle **整根站上 OR high**，而不是只有 close 剛好高過去。`PumpC ORB` 也明確檢查前一根是否仍被包在 OR 內，再確認 breakout，核心目標都是減少貼線假突破。
- 這類條件的共同點是：它們依然只使用當前 timeframe 的單根或相鄰 bar 結構，不需要新 session engine，也不需要額外 volatility normalization。

### 對 SignalForge 的含義

- 現在 ORB 已經有：
  - VWAP alignment
  - volume confirmation
  - retest confirmation
  - range size filter
  - breakout distance threshold
- 若還要再加一層低風險 refinement，下一個最自然的是：
  - 要求 breakout candle body ratio 達到某個下限，或
  - 要求 breakout candle low 也站在 OR high 上方，避免只靠 close 勉強越線。
- 這比 EMA 9/21、gap direction、session cutoff 更接近目前 repo 的 deterministic entry-quality 邊界。

### 建議排序

1. 先回看 breakout distance threshold 的實際覆蓋情況。
2. 若要做下一個小執行項目，優先考慮 breakout candle strength 或 full-close-above-range 類型條件。
3. EMA、gap、session close exit、extended-hours 仍先放後面。

## 2026-05-21 執行輪：ORB 新增可選 full-close-above-range 條件

這輪把上一輪研究收斂成一個最小可驗證版本：`ORB + Volume + VWAP` 現在可選擇要求 **breakout candle 的 low 也必須站在 OR high 上方**，才把這根 bar 視為有效突破。預設仍是關閉，所以既有 ORB contract 不變。

### 修改內容

- `OrbVolumeVwapStrategy` 新增 `require_full_bar_above_range`。
- 啟用後，若 breakout bar 雖然 `close > OR high`，但 `low <= OR high`，就回傳 `breakout_bar_reentered_range`，不進場。
- CLI 新增 `--orb-full-bar-above-range`。
- `strategy_spec` 新增：
  - `orb_full_bar_above_range`
  - `orb_full_bar_rule`
- 為了讓 artifact 名稱能區分兩種語意，ORB strategy name 現在明確寫成：
  - 預設 `closeonly`
  - 啟用後 `fullbar`

### 為什麼先做這個

- 它比 body ratio 更保守、也更容易測試，因為不需要再引入第二個數值門檻。
- 它仍是單時間框架、close-confirmed、純 entry quality refinement。
- 這能直接補上「close 有越線，但整根 candle 其實仍有一部分留在區間內」的常見假突破情境。

### 驗證

- `python tools\phase_readiness_score.py` -> `110`
- `python -m unittest discover -s tests` -> `111 tests OK`
- `git diff --check` -> clean

### 決策

- keep
- 這次改動讓 ORB 現在除了 breakout distance 外，也能研究 breakout bar 結構本身是否夠乾淨。

## 2026-05-21 研究輪：full-close-above-range 之後，下一個候選是 candle body strength

這輪延續 ORB 的 breakout 結構研究。結論是：**在 `full-close-above-range` 之後，下一個仍然維持單時間框架、close-confirmed 邊界的候選，是 `candle body strength`，例如要求 breakout candle 的 body 佔整根 range 至少某個最小比例。**

### 來源

- TradingView opening-range-breakout scripts index
  https://tw.tradingview.com/scripts/opening-range-breakout/
- TradingView open-source：ORB Breakout Strategy with VWAP and Volume Filters
  https://tw.tradingview.com/script/wLSGHPUe-ORB-Breakout-Strategy-with-VWAP-and-Volume-Filters/
- TradingView open-source：ORB Breakout
  https://www.tradingview.com/script/KWfBq6HU-ORB-Breakout/

### 研究結論

- TradingView 的 ORB 彙整頁面常把 `Strong Directional Candle` 直接列成 filter，典型做法是要求 **body / candle range** 達到某個下限，例如 `60%+ body ratio`。
- `ORB Breakout Strategy with VWAP and Volume Filters` 也直接提到 `Candle Strength Filter catches weak-momentum breakouts`，表示 candle 結構本身就是常見的弱突破濾網。
- 另一類 ORB 腳本則只要求 `body closes above OR High`。這說明在 ORB 世界裡，breakout candle 的「站上方式」本來就經常被拆成多層：先是 close 越線，再來是整根站穩，最後才是 body 強度。

### 對 SignalForge 的含義

- 現在 ORB 已經有：
  - breakout distance threshold
  - full-close-above-range
- 如果要再加一層更細的結構條件，最自然的是：
  - `candle_body_pct = abs(close - open) / (high - low)`
  - 只在 breakout bar 的 body ratio 達到某個下限時才接受訊號。
- 這比 EMA、gap direction、session cutoff 更接近目前 repo 的 deterministic entry-quality 邊界，也比 ATR-normalized 或 session close exit 輕。

### 建議排序

1. 先回看 `full-close-above-range` 啟用前後的覆蓋率與訊號變化。
2. 若要做下一個小執行項目，優先考慮 `min breakout candle body %`。
3. EMA、gap、session close exit、extended-hours 仍先放後面。

## 2026-05-21 執行輪：ORB 新增可選 breakout candle body strength

這輪把上一輪研究收斂成一個最小可驗證版本：`ORB + Volume + VWAP` 現在可選擇要求 **breakout candle 的 body / full candle range** 達到最小比例，才把這根 bar 視為有效突破。預設仍是關閉，所以既有 ORB contract 不變。

### 修改內容

- `OrbVolumeVwapStrategy` 新增 `min_breakout_body_pct`。
- 啟用後，若 breakout bar 已經收過 OR high，但 `abs(close - open) / (high - low)` 低於門檻，就回傳 `breakout_body_too_small`，不進場。
- CLI 新增 `--orb-min-breakout-body-pct`。
- `strategy_spec` 新增：
  - `orb_min_breakout_body_pct`
  - `orb_breakout_body_rule`
- 為了讓 artifact 名稱能區分不同 refinement，啟用後的 ORB strategy name 會加上 `body...` 片段，例如 `body0.60`。

### 為什麼先做這個

- 它仍是單時間框架、close-confirmed、純 entry quality refinement。
- 它不需要新的 session engine，也不需要引入 ATR-normalized 或持有語意。
- 它能直接補上「有突破、也沒回到區間內，但 breakout candle 本身實體太小」這種弱動能情境。

### 驗證

- `python tools\phase_readiness_score.py` -> `110`
- `python -m unittest discover -s tests` -> `112 tests OK`
- `git diff --check` -> clean

### 決策

- keep
- 這次改動讓 ORB 現在除了 breakout distance 與 full-bar 結構外，也能研究 breakout candle 實體本身是否夠強。

## 2026-05-21 研究輪：body strength 之後，下一個較低風險候選是 fresh breakout from inside OR

這輪延續 ORB 的 breakout 結構研究。結論是：**在 body strength 之後，下一個更貼近 ORB 本體、而且仍維持單時間框架與 close-confirmed 邊界的候選，是 `breakout must start from inside OR`，也就是要求前一根 close 還在 OR 盒子內，這一根才算真正的 fresh breakout。**

### 來源

- TradingView open-source：PumpC Opening Range Breakout (ORB) 5min Range
  https://www.tradingview.com/script/ZWchgzJq-PumpC-Opening-Range-Breakout-ORB-5min-Range/
- TradingView strategy：OR Breakout Retest
  https://www.tradingview.com/script/KU2b95Q8/
- TradingView open-source：ORB Session Breakout
  https://tw.tradingview.com/script/PtyymXpz-ORB-Session-Breakout/

### 研究結論

- PumpC 的 2025-04-29 release note 直接把 alert 邏輯改成：**只有當 breakout 是從 OR 內部發動時才觸發**；也就是前一根 `close[1]` 必須仍被 OR 邊界包住，避免 price 已經在區間外時又反覆觸發無效 breakout。
- `OR Breakout Retest` 也明確寫成 breakout 是「candle body exits the zone」，強調的是 body-based、close-confirmed 的新脫離，而不是任何 wick 穿越都算。
- `ORB Session Breakout` 同樣把重點放在 confirmed close beyond the ORB，而不是盤中刺穿。這代表對 SignalForge 來說，把「是否從 OR 內部發動」補成額外條件，仍然符合現在的 deterministic 邊界。

### 對 SignalForge 的含義

- 現在 ORB 已經有：
  - breakout distance threshold
  - full-bar-above-range
  - breakout candle body strength
- 若還要再補一層較低風險 refinement，下一個更自然的是：
  - `previous close inside OR`，只有當前一根 close 仍在 OR 內時，下一根 close 穿出 OR high 才視為 fresh breakout。
- 這比 EMA、gap direction、session cutoff 或 extended-hours 更貼近 ORB 本體，因為它處理的是「這是不是一次新的突破」，不是更高層的市場 regime 或持有政策。

### 建議排序

1. 先回看 body strength 啟用前後，是否已經大幅減少弱突破。
2. 若要做下一個小執行項目，優先考慮 `breakout starts from inside OR`。
3. EMA、gap、session close exit、extended-hours 仍先放後面。

## 2026-05-21 執行輪：ORB 新增可選 fresh breakout from inside OR

這輪把上一輪研究收斂成一個最小可驗證版本：`ORB + Volume + VWAP` 現在可選擇要求 **前一根 close 仍在 OR 盒子內**，只有這樣，當前這根 close 穿出 OR high 才算 fresh breakout。預設仍是關閉，所以既有 ORB contract 不變。

### 修改內容

- `OrbVolumeVwapStrategy` 新增 `require_fresh_breakout_from_or`。
- 啟用後，若前一根 close 已經在 OR 盒子外，當前這根即使收得更高，也回傳 `breakout_not_fresh_from_or`，不把它視為新的 breakout。
- CLI 新增 `--orb-fresh-breakout-from-or`。
- `strategy_spec` 新增：
  - `orb_fresh_breakout_from_or`
  - `orb_fresh_breakout_rule`
- 為了讓 artifact 名稱能區分不同 refinement，啟用後的 ORB strategy name 會加上 `fresh` 片段。

### 為什麼先做這個

- 它仍是單時間框架、close-confirmed、純 entry quality refinement。
- 它不需要新的 session engine，也不會把 ORB 推進到完整持有或 extended-hours 決策。
- 它能直接補上「價格早已站在區間外，但後續每一根又被看成新 breakout」這個常見的 ORB 判定噪音。

### 驗證

- `python tools\phase_readiness_score.py` -> `110`
- `python -m unittest discover -s tests` -> `115 tests OK`
- `git diff --check` -> clean

### 決策

- keep
- 這次改動讓 ORB 現在除了 breakout distance、full-bar 與 body strength 外，也能研究 breakout 是否真的是從 OR 盒子內部重新發動。

## 2026-05-21 研究輪：fresh breakout 之後，下一個較低風險候選是 OR-specific volume baseline

這輪延續 ORB 的 entry quality 路線。結論是：**在 fresh breakout 之後，下一個仍然維持單時間框架、close-confirmed 邊界的候選，是把 breakout volume 改成相對於 `opening range average volume`，而不是一般 rolling SMA volume。**

### 來源

- TradingView open-source：ORB Breakout
  https://www.tradingview.com/script/KWfBq6HU-ORB-Breakout/
- TradingView open-source：NeuraEdge ORB - Opening Range Breakout Indicator
  https://tw.tradingview.com/script/Sb0YgLYU-NeuraEdge-ORB-Opening-Range-Breakout-Indicator/
- TradingView open-source：PumpC Opening Range Breakout (ORB) 5min Range
  https://tw.tradingview.com/script/ZWchgzJq-PumpC-Opening-Range-Breakout-ORB-5min-Range/

### 研究結論

- `ORB Breakout` 直接把 volume 條件寫成 **`Volume ≥ 1.5× OR avg volume`**，不是相對於一個泛用的 rolling volume 視窗。
- `NeuraEdge ORB` 也把 breakout volume 當成核心確認之一，只是它仍採「突破要有高於平均量的 conviction」這個方向，而不是 session policy 或多時間框架。
- `PumpC ORB` 進一步把 `ORB Volume ATR` 當成獨立觀測量，說明 OR 本身的量能分布常被拿來當 breakout 背景，而不只是拿全局平均量能做比較。

### 對 SignalForge 的含義

- 現在 ORB 的 volume filter 是：
  - `bar.volume / sma(volume, volume_window)`
- 若還要再補一層更貼近 ORB 的 refinement，下一個更自然的是：
  - `bar.volume / average(opening-range volumes)`
- 這比 trading cutoff、session close exit、extended-hours 或 gap direction 更符合目前 repo 的邊界，因為它仍只是單 session、單 timeframe 的 entry-quality filter，而且 OR volume 本來就在 `prepare_context(...)` 可穩定推導。

### 建議排序

1. 先比較 fresh breakout 與 body strength 疊加後的訊號覆蓋率。
2. 若要做下一個小執行項目，優先考慮 `breakout volume relative to OR average volume`。
3. session cutoff、session close exit、extended-hours 仍先放後面。

## 2026-05-21 執行輪：ORB 新增可選 OR-specific volume baseline

這輪把上一輪研究收斂成一個最小可驗證版本：`ORB + Volume + VWAP` 現在可選擇把 breakout volume 改成相對於 **opening range 平均量能**，而不是一般 rolling volume SMA。預設仍是關閉，所以既有 ORB contract 不變。

### 修改內容

- `OrbVolumeVwapStrategy` 新增 `use_opening_range_volume_baseline`。
- 啟用後，breakout volume baseline 會從 `sma(volume, volume_window)` 改成 `average(opening-range volumes)`。
- `decide_bar(...)` 的量能 baseline warmup 邏輯已調整：若啟用 OR volume baseline，就不再被 rolling volume SMA 的 warmup 綁住。
- CLI 新增 `--orb-use-opening-range-volume-baseline`。
- `strategy_spec` 新增：
  - `orb_use_opening_range_volume_baseline`
  - `orb_volume_baseline_rule`
- 為了讓 artifact 名稱能區分不同 refinement，啟用後的 ORB strategy name 會加上 `orvol` 片段。

### 為什麼先做這個

- 它仍是單時間框架、close-confirmed、純 entry quality refinement。
- 它比 trading cutoff、session close exit、extended-hours 或 gap direction 更貼近 ORB 自己的語意。
- 它能補上「rolling SMA volume 被開盤後高量非突破 bar 拉高，結果把原本合理的突破誤擋掉」這類情境。

### 驗證

- factory / regression / CLI 測試已補上：
  - ORB 名稱與 defaults contract
  - OR volume baseline 相對於 rolling volume SMA 的差異情境
  - CLI strategy spec / strategy name 接線
- `python tools\phase_readiness_score.py` -> `110`
- `python -m unittest discover -s tests` -> `117 tests OK`
- `git diff --check` -> clean

### 決策

- keep
- 這次改動讓 ORB 現在除了 fresh breakout、body strength 與 breakout distance 外，也能研究「breakout volume 是不是相對於早盤主戰區真正放量」。

## 最新已知狀態

- Branch：`main`
- Remote：`origin/main`
- Readiness score：`110`
- Live mode：dry-run order intent only。
- 最新已知測試基線：`97 tests OK`，以當輪實際測試輸出為準。
- 最新已知測試基線：`99 tests OK`，以當輪實際測試輸出為準。
- 最新已知測試基線：`103 tests OK`，以當輪實際測試輸出為準。
- 最新已知測試基線：`104 tests OK`，以當輪實際測試輸出為準。
- 最新已知測試基線：`107 tests OK`，以當輪實際測試輸出為準。
- 最新已知測試基線：`106 tests OK`，以當輪實際測試輸出為準。
- 最新已知測試基線：`109 tests OK`，以當輪實際測試輸出為準。
- 最新已知測試基線：`111 tests OK`，以當輪實際測試輸出為準。
- 最新已知測試基線：`112 tests OK`，以當輪實際測試輸出為準。
- 最新已知測試基線：`113 tests OK`，以當輪實際測試輸出為準。
- 最新已知測試基線：`115 tests OK`，以當輪實際測試輸出為準。
- 最新已知測試基線：`113 tests OK`，以當輪實際測試輸出為準。
- 最新已知測試基線：`117 tests OK`，以當輪實際測試輸出為準。
- 最新已知測試基線：`119 tests OK`，以當輪實際測試輸出為準。
- 最新已知測試基線：`119 tests OK`，以當輪實際測試輸出為準。

## 實驗下一步

- 增加 `min_previous_target_position` / `max_previous_target_position` 類型欄位，讓 trace summary 的前一根部位範圍更好稽核。
- 繼續補強 Phase markdown 的人工可讀性，但必須有 exact-text regression test。
- SMA Crossover 先用 `--hold-bars-list` 比較固定持有期，再決定是否需要完整趨勢持有 / 出場規則。
- VWAP Reversion 下一步比較 regime filter 啟用前後的 entry-edge 結果，暫不把成交量 gate 併入策略本體。
- 評估 `ORB + Volume + VWAP` 是否以最小 long-only 版本納入 Phase 1；若要實作，先補 session 定義與 intraday 資料假設。
- ORB 候選的下一步優先考慮 retest confirmation；先不要急著加多時間框架或更多 intraday filter。
- ORB 若要再往下走，下一個大分支是 session close exit；這屬於持有語意決策，不建議 automation 直接自行定版。
- ORB 另一條高價值但相對低風險的路徑，是把 session start / range length / timezone 邊界參數化，減少策略被 `09:30` 假設綁死。
- OR range 已經開始寫進 artifact；下一步是先用 `orb_observed_range_pct_*` 做實證比較，再決定 `% of first open` 是否足夠，或是否值得升級成 ATR-normalized gate。
- ORB range gate 現在也會寫出 low/within/high 分類摘要；下一步可開始用這些欄位比較不同資料集上 gate 的實際覆蓋率。
- ORB 若要再加一個低風險 filter，`min breakout % beyond OR` 會比 trading cutoff 或 session close exit 更接近目前的 entry quality 邊界。
- breakout distance 之後，下一個更輕的 refinement 候選是 breakout candle strength / full-close-above-range，而不是先跳去 EMA、gap 或 session policy。
- full-close-above-range 之後，下一個更細的結構候選是 breakout candle body ratio；這個條件現在已經可用，下一步應優先比較它和 full-bar gate 疊加後的實際覆蓋率。
- `fresh breakout from inside OR` 現在已經可用；下一步應優先比較它和 body strength 疊加後，是互補關係，還是只是擋掉同一批弱突破。
- `OR average volume baseline` 現在已經可用；下一步應優先比較它與 rolling volume SMA 在不同資料集上，到底擋掉的是同一批弱突破，還是真的補到新的 entry-quality 邏輯。
- `signal window cutoff` 現在已經可用；下一步應優先比較它和 fresh breakout、body strength、OR volume baseline 疊加後，到底只是重複擋掉同一批晚到突破，還是真的補到新的 session policy 邏輯。
- `session end/timezone` 現在已經寫進 CLI / strategy spec；下一步應優先比較不同 market-clock 設定下 artifact 的解讀差異，再決定 `session close exit` 是否值得進入可選 policy。
- OOP template 已鎖住後，三種策略的下一步修改應分開討論與測試，避免混入模板重構。
- 若要做策略研究實驗，結果放入 `04-實驗記錄/`，策略語意同步到 `策略筆記/`。

## 2026-05-21 研究輪：OR volume baseline 之後，下一個較合理的是 signal window cutoff，而不是 wick/high-low trigger

這輪延續 ORB 的 intraday session 邊界研究。結論是：**在 OR-specific volume baseline 之後，下一個仍維持單時間框架、close-confirmed、且工程風險相對可控的候選，是 `signal window cutoff`，例如限制 ORB 只在開盤後某段時間內接受新的 breakout；相對地，`high/low` 或 `wick` trigger mode 不適合現在的 SignalForge contract。**

### 來源

- TradingView open-source：ORB Breakout
  https://www.tradingview.com/script/KWfBq6HU-ORB-Breakout/
- TradingView open-source：RPFXBYDAN - ORB (Opening Range Breakout)
  https://www.tradingview.com/script/23PYvshx-RPFXBYDAN-ORB-Opening-Range-Breakout/
- TradingView open-source：ORB Opening Range Breakout LliterH
  https://www.tradingview.com/script/twET9tO7/
- TradingView Pine Script 官方文件：Sessions
  https://www.tradingview.com/pine-script-docs/concepts/sessions/
- TradingView Pine Script 官方文件：Repainting
  https://www.tradingview.com/pine-script-docs/concepts/repainting/

### 研究結論

- `ORB Breakout` 明確把訊號限制在固定的 **signal window** 內，例如 1m 用 `9:31–11:30 ET`、5m 用 `9:35–11:30 ET`；這代表公開 ORB 腳本常把「太晚的 breakout 不再追」視為 session policy，而不是隱性假設。
- `RPFXBYDAN - ORB` 與 `ORB Opening Range Breakout LliterH` 都把 session / timezone / trigger mode 做成顯式設定，代表這一層通常被視為 ORB 核心配置的一部分。
- 但 `RPFXBYDAN - ORB` 同時提供 `close`、`high/low`、`wick` 三種 trigger mode。對 SignalForge 而言，`close` 仍然最符合現在的 bar-close confirmed contract；`high/low` 與 `wick` 雖然常見，卻會把策略往 intrabar 判定推進。
- 官方 `Sessions` 文件明確說明 Pine 可直接用 session string 與 timezone 定義時間邊界；這意味著若未來要補 `session end` / `signal cutoff`，可以維持同時間框架，不需要引入更高風險的多時間框架資料請求。
- 官方 `Repainting` 文件則明確提醒 `request.security()` 在不同時間框架上可能產生 historical / realtime 不一致。對 SignalForge 而言，這再次說明：若只是要補 `signal window cutoff`，不應該順手把設計帶去 HTF/LTF `request.security()`。

### 對 SignalForge 的含義

- 現在 ORB 已經有：
  - session start 參數化
  - OR range gate
  - breakout distance
  - full-bar-above-range
  - breakout body strength
  - fresh breakout
  - OR-specific volume baseline
- 若還要再補一層較低風險 refinement，下一個比較合理的是：
  - `只在 session start 後的某段時間內接受新 breakout`
  - 並把 `session end` / `cutoff time` / `timezone` 一起寫進 strategy spec
- 這比 `wick` / `high-low` trigger mode 更適合現在的 repo，因為它維持 close-confirmed、deterministic、同時間框架；它改的是 **何時允許追突破**，不是 **如何放寬突破定義**。

### 建議排序

1. 先用目前 artifact 比較 `OR average volume baseline` 與 rolling SMA 的實際覆蓋率差異。
2. 若要做下一個小執行項目，優先考慮 `signal window cutoff` 與 `session end/timezone` 的顯式化。
3. `high/low` / `wick` trigger mode 先不要做，避免把 SignalForge 從 close-confirmed 推向 intrabar 語意。

## 2026-05-21 執行輪：ORB 新增可選 signal window cutoff

這輪把上一輪研究收斂成一個最小可驗證版本：`ORB + Volume + VWAP` 現在可選擇只在 session 開始後某段時間內接受**新的 breakout**。這個 cutoff 不會強制平掉已經持有的 long；它只限制「太晚才發生的首次突破」不再被追價。

### 修改內容

- `OrbVolumeVwapStrategy` 新增 `signal_window_minutes`。
- 當 `bar.close > OR high` 但當前分鐘數已達 cutoff 時，策略會回傳 `outside_signal_window`，而不是翻成 long。
- 若上一根已經在 long，超過 cutoff 後仍維持 `hold_intraday_breakout`，不做 forced flatten。
- CLI 新增 `--orb-signal-window-minutes`。
- `strategy_spec` 新增：
  - `orb_signal_window_minutes`
  - `orb_signal_window_rule`
- 為了讓 artifact 名稱能區分不同 refinement，啟用 cutoff 後的 ORB strategy name 會加上 `sigw<minutes>` 片段。

### 為什麼先做這個

- 它仍是單時間框架、close-confirmed、deterministic 的 session policy，不需要引入 `request.security()` 或 intrabar trigger。
- 它比 `wick/high-low trigger mode` 更符合目前 repo 的 contract，因為它沒有放寬 breakout 定義，只是把「多晚還允許追 breakout」寫成顯式規則。
- 它也比直接做 `session close exit` 更輕，因為它不改持有語意，只限制新訊號。

### 驗證

- factory / regression / CLI 測試已補上：
  - ORB 名稱與 defaults contract
  - late breakout cutoff 會阻擋新訊號，但不會強制平掉既有 long
  - CLI strategy spec / strategy name 接線
- `python tools\phase_readiness_score.py` -> `110`
- `python -m unittest discover -s tests` -> `119 tests OK`
- `git diff --check` -> clean

### 決策

- keep
- 這次改動讓 ORB 現在除了 volume、range、body、fresh breakout 等 refinement 外，也能研究「突破太晚是否應該直接放棄追價」。

## 2026-05-21 研究輪：signal window cutoff 之後，先做 session end/timezone 顯式化，不直接做 session close exit

這輪延續 ORB 的時間邊界研究。結論是：**在 signal window cutoff 已經落地之後，下一個較低風險、且更符合目前 SignalForge contract 的方向，是先把 `session end` 與 `timezone` 顯式寫進 CLI / strategy spec；`session close exit` 雖然常見，但它屬於持有與平倉語意，不應在這一步直接定版。**

### 來源

- TradingView open-source：RPFXBYDAN - ORB (Opening Range Breakout)
  https://www.tradingview.com/script/23PYvshx-RPFXBYDAN-ORB-Opening-Range-Breakout/
- TradingView open-source：Opening Range Breakout (ORB) with Fib Retracement
  https://www.tradingview.com/script/32ptXi5r-Opening-Range-Breakout-ORB-with-Fib-Retracement/
- TradingView open-source：Opening-Range Breakout
  https://www.tradingview.com/script/8vjWAdLN-Opening-Range-Breakout/
- TradingView Pine Script 官方文件：Sessions
  https://www.tradingview.com/pine-script-docs/concepts/sessions/
- TradingView Pine Script 官方文件：Repainting
  https://www.tradingview.com/pine-script-docs/concepts/repainting/

### 研究結論

- `RPFXBYDAN - ORB` 把 **Opening Range Session**、**Trading Session**、**Market**、**Your Timezone** 分開處理，代表成熟 ORB 腳本通常把「OR 視窗」和「允許交易的 session」視為兩層不同設定，而不是只靠單一 `09:30` 起點。
- `ORB with Fib Retracement` 也把 `Session time / timezone` 當成核心輸入，表示連偏視覺化的 ORB 工具也會先把時間錨點顯式化。
- `Opening-Range Breakout` 這類完整 strategy 常把 **EOD flat / session close exit** 寫成規則，但那已經是持有與平倉 policy，不只是時間邊界描述。
- TradingView 官方 `Sessions` 文件也明確區分 **named sessions**（如 `regular`、`extended`）與自訂時間字串，說明 regular / extended 本來就不是同一層語意。
- 官方 `Repainting` 文件則再次提醒：若只是補時間邊界，不應順手把問題推向 `request.security()` 多時間框架，否則會增加 historical / realtime 不一致風險。

### 對 SignalForge 的含義

- 現在 ORB 已經能控制：
  - `session start`
  - `opening range minutes`
  - `signal window cutoff`
- 但它還沒有明確回答：
  - 這個策略的 regular session 到幾點結束
  - timezone 是資料欄位固有假設，還是使用者可顯式指定的 contract
  - OR 計算、signal window、未來若有 forced flat，是否共享同一個 session 定義
- 因此下一步更合理的是先把 `session end` 與 `timezone` 寫進 CLI / strategy spec / artifact，讓 ORB 的時間邊界完整可見；這比直接加入 `session close exit` 更穩，因為它先補 contract，再談持有 policy。

### 建議排序

1. 先做 `session end/timezone` 顯式化，讓 ORB 的 market-clock contract 完整可見。
2. 完成後再決定 `session close exit` 要不要作為可選 policy，而不是現在就把它寫死成預設。
3. `wick/high-low trigger mode` 仍放後面，避免把策略從 close-confirmed 推向 intrabar 語意。

## 2026-05-21 執行輪：ORB 新增 session end/timezone 顯式化

這輪把上一輪研究收斂成一個最小可驗證版本：`ORB + Volume + VWAP` 現在可把 **session end** 與 **session timezone** 正式寫進 CLI / strategy spec / artifact contract。這一步先只做時間邊界顯式化，不直接變成 `session close exit` 規則，也不改變既有 long 持有語意。

### 修改內容

- `OrbVolumeVwapStrategy` 新增：
  - `session_end_hour`
  - `session_end_minute`
  - `session_timezone`
- CLI 新增：
  - `--orb-session-end-hour`
  - `--orb-session-end-minute`
  - `--orb-session-timezone`
- `strategy_spec` 新增：
  - `orb_session_end_hour`
  - `orb_session_end_minute`
  - `orb_session_timezone`
  - `orb_session_end_rule`
  - `orb_session_timezone_rule`
- registry / factory / defaults 也同步補上 ORB 的 session end / timezone 預設值，避免 CLI、artifact 與策略物件各自維護不同的 market-clock 假設。

### 為什麼先做這個

- 它是在補 ORB 的時間邊界 contract，而不是偷渡新的平倉 policy。
- 它比直接加 `session close exit` 更穩，因為可以先讓 artifact 明確說出「這個 ORB 版本的 regular session 到哪裡結束、用哪個 timezone 解讀」。
- 它也比做 `wick/high-low trigger mode` 更符合目前 close-confirmed、single-timeframe 的研究邊界。

### 驗證

- factory / CLI 測試已補上：
  - ORB 預設值 registry 與策略物件的 session end / timezone 一致
  - CLI strategy spec 會正確寫出 session end / timezone 與對應規則說明
- `python tools\phase_readiness_score.py` -> `110`
- `python -m unittest discover -s tests` -> `119 tests OK`
- `git diff --check` -> clean

### 決策

- keep
- 這次改動把 ORB 的 market-clock contract 從隱性假設拉成顯式 metadata，為之後是否要做 `session close exit`、extended-hours 或更完整的 regular-session policy 打好基礎。

## 2026-05-21 研究輪：session end/timezone 之後，先做 VWAP slope confirmation，不直接做 session close exit

這輪延續 ORB 的 entry-quality 與持有語意邊界研究。結論是：**在 `session end/timezone` 已經顯式化之後，下一個更合理的低風險候選是 `VWAP slope confirmation`，也就是不只要求價格在 VWAP 上方，還要求 VWAP 本身正在上升；相對地，`session close exit` 仍屬持有 / 平倉 policy，不適合在這一步直接定版。**

### 來源

- TradingView strategy：Opening Range Breakout (ORB)
  https://www.tradingview.com/script/AMsB94Rs-Opening-Range-Breakout-ORB/
- TradingView indicator：ORB + Volume + VWAP Breakout
  https://www.tradingview.com/script/7khuDtm8-ORB-Volume-VWAP-Breakout/
- TradingView indicator：Opening Range Breakout + VWAP + Volume [ORB Strategy]
  https://www.tradingview.com/script/hapKLoXr-Opening-Range-Breakout-VWAP-Volume-ORB-Strategy/
- TradingView Pine Script 官方文件：Repainting
  https://www.tradingview.com/pine-script-docs/concepts/repainting/

### 研究結論

- `Opening Range Breakout (ORB)` 明確提到可選的 **VWAP Trend Filter**：做多不只要求價格在 VWAP 上方，還要求 **VWAP slope 必須是正的**。這表示公開 ORB strategy 已經把它當成一種 entry-quality refinement，而不是持有政策。
- `ORB + Volume + VWAP Breakout` 與 `Opening Range Breakout + VWAP + Volume [ORB Strategy]` 都把 VWAP 視為趨勢對齊的一部分，而不只是單點位置比較。從 SignalForge 角度看，這代表現在的 `close > VWAP` 仍偏向最小版本，還有空間補成「位置 + 方向」兩層確認。
- 從工程風險看，VWAP slope confirmation 仍屬 **同時間框架、close-confirmed** 的判斷，不需要 `request.security()`；相較之下，`session close exit` 會直接改變持有與平倉語意，層級更高。
- TradingView 官方 `Repainting` 文件也再次支持這個排序：只要 VWAP slope 仍用已收盤 bar 的序列做判斷，它不需要引入更高風險的多時間框架資料請求。

### 對 SignalForge 的含義

- 現在 ORB 已經有：
  - `close > VWAP`
  - volume baseline / OR volume baseline
  - range / distance / body / fresh breakout / signal window 等 refinement
  - session end / timezone metadata
- 若還要再補一個低風險 refinement，`VWAP slope confirmation` 很適合放在這一層，因為它仍然是 entry-quality filter：
  - 不是新的持有 policy
  - 不需要新的 session policy
  - 不需要 intrabar trigger
- 這樣的排序也更乾淨：先把「進場品質」補完整，再決定要不要往 `session close exit` 這種持有/離場 policy 前進。

### 建議排序

1. 先做 `VWAP slope confirmation`，把 VWAP 從單純位置條件補成「位置 + 方向」。
2. 完成後再比較它和 body strength、fresh breakout、OR volume baseline 疊加後，是否只是擋掉同一批弱突破。
3. `session close exit` 仍放在後面，等 market-clock contract 與 entry-quality filter 穩定後再討論。

## 2026-05-21 執行輪：ORB 新增可選 VWAP slope confirmation

這輪把上一輪研究收斂成一個最小可驗證版本：`ORB + Volume + VWAP` 現在可選擇把 VWAP 從單純的「位置條件」升級成「位置 + 方向」條件。也就是說，除了要求 breakout 時 `close > VWAP`，現在也可以要求 **session VWAP 相對前一根同 session bar 必須持續上升**，才接受這次 long breakout。

### 修改內容

- `OrbVolumeVwapStrategy` 新增 `require_vwap_slope_confirmation`。
- 啟用後，若 breakout 當下的 session VWAP 相對前一根同 session bar 沒有上升，策略會回傳 `breakout_vwap_slope_blocked`。
- CLI 新增 `--orb-vwap-slope-confirmation`。
- `strategy_spec` 新增：
  - `orb_vwap_slope_confirmation`
  - `orb_vwap_slope_rule`
- 為了讓 artifact 名稱能區分不同 refinement，啟用後的 ORB strategy name 會加上 `vslope` 片段。

### 為什麼先做這個

- 它仍是單時間框架、close-confirmed、純 entry-quality refinement，不需要新的持有或平倉 policy。
- 它比直接加 `session close exit` 更適合現在的 repo，因為它只是在加強突破品質，而不是改變出場語意。
- 它也比 `wick/high-low trigger mode` 更穩，因為它不會把策略推向 intrabar 判定。

### 驗證

- factory / regression / CLI 測試已補上：
  - ORB 名稱與 defaults contract
  - VWAP slope 沒有上升時會阻擋 breakout；上升時保留原本 breakout 行為
  - CLI strategy spec / strategy name 接線
- `python tools\phase_readiness_score.py` -> `110`
- `python -m unittest discover -s tests` -> `121 tests OK`
- `git diff --check` -> clean

### 決策

- keep
- 這次改動讓 ORB 現在不只看「價格是否在 VWAP 上方」，也能研究「VWAP 本身有沒有持續抬升」。

## 2026-05-21 研究輪：VWAP slope confirmation 之後，先做 EMA trend confirmation，不直接做 gap fill bias 或 session close exit

這輪延續 ORB 的趨勢對齊與持有語意邊界研究。結論是：**在 `VWAP slope confirmation` 已經落地之後，下一個更合理的低風險候選是 `EMA trend confirmation`，也就是要求較慢的 intraday EMA 也在往上，且價格維持在 EMA 上方；相對地，`gap fill bias` 會把 prior-day close / RTH 邊界語意拉進來，`session close exit` 則直接進入持有與平倉 policy。**

### 來源

- TradingView indicator：Opening Range Breakout
  https://www.tradingview.com/script/tZtCD3TM-Opening-Range-Breakout/
- TradingView strategy：Opening Range Breakout (ORB)
  https://www.tradingview.com/script/AMsB94Rs-Opening-Range-Breakout-ORB/
- TradingView indicator：BORTORB - Opening Range Breakout Indicator
  https://www.tradingview.com/script/bDkeiwBg-BORTORB-Opening-Range-Breakout-Indicator/
- TradingView Pine Script 官方文件：Repainting
  https://www.tradingview.com/pine-script-docs/concepts/repainting/

### 研究結論

- `Opening Range Breakout` 明確把 **EMA 趨勢確認** 當成 breakout 前的必要條件之一：EMA 必須上升、價格要在 EMA 上方，而且 EMA 也要位於 OR high 上方。這表示公開 ORB 腳本常把「較慢趨勢基線是否同向」當成一層獨立 refinement。
- `Opening Range Breakout (ORB)` 另一條路徑則是 **Gap Fill Filter**，用前一日收盤價決定 long / short 是否符合 gap fill bias。這個方向雖然也屬 deterministic，但它會把 prior-day close、RTH/24h 邊界與 session 切法一起帶進來。
- `BORTORB` 類腳本則更偏向把 reference levels 與 session box 疊上去做 confluence；這些東西有研究價值，但顯然比單純 EMA trend confirmation 更重。
- 從工程風險看，EMA trend confirmation 仍屬 **單時間框架、close-confirmed** 的判斷，不需要 `request.security()`；TradingView 官方 `Repainting` 文件支持這個排序，因為只要繼續用已收盤 bar 計算 EMA，就不會平白引入多時間框架的不一致風險。

### 對 SignalForge 的含義

- 現在 ORB 已經有：
  - VWAP 位置
  - VWAP slope
  - volume / OR volume baseline
  - range / distance / body / fresh breakout / signal window
  - session end / timezone metadata
- 若還要再補一個低風險 refinement，`EMA trend confirmation` 很適合放在這一層，因為它仍然只是 entry-quality filter：
  - 不是新的持有 / 平倉 policy
  - 不需要 prior-day close 或 gap 語意
  - 不需要 intrabar trigger
- 相較之下，`gap fill bias` 會把「前一日收盤價怎麼定義」這個跨 session 問題拉進來；`session close exit` 則直接改變出場語意，兩者都比 EMA trend confirmation 更重。

### 建議排序

1. 先做 `EMA trend confirmation`，把 ORB 的趨勢對齊從「VWAP」擴成「VWAP + 較慢 EMA」。
2. 完成後再比較它和 VWAP slope、body strength、fresh breakout 是否只是重複擋掉同一批弱突破。
3. `gap fill bias` 與 `session close exit` 仍放後面，等 entry-quality filters 收斂後再討論。

## 2026-05-21 執行輪：ORB 新增可選 EMA trend confirmation

這輪把上一輪研究收斂成一個最小可驗證版本：`ORB + Volume + VWAP` 現在可選擇再加上一層 **EMA trend confirmation**。啟用後，策略不只要求 breakout 時 `close > OR high` 且維持既有 VWAP / volume 條件，還會額外要求 **breakout 當下 `close > rolling EMA`**，並把這個 EMA 視窗明確寫進 CLI 與 artifact。

### 修改內容

- `OrbVolumeVwapStrategy` 新增：
  - `ema_window`
  - `require_ema_trend_confirmation`
- 啟用後，若 breakout 當下 `close` 仍未站上 rolling EMA，策略會回傳 `breakout_below_ema`。
- 內部同時保留 `breakout_ema_slope_blocked` 這個 reason，明寫策略對「EMA 本身也應持續上升」的 contract。
- CLI 新增：
  - `--orb-ema-trend-confirmation`
  - `--orb-ema-window`
- `strategy_spec` 新增：
  - `orb_ema_trend_confirmation`
  - `orb_ema_window`
  - `orb_ema_trend_rule`
- 為了讓 artifact 名稱能區分不同 refinement，啟用後的 ORB strategy name 會加上 `ema{window}` 片段，例如 `ema10`。

### 為什麼先做這個

- 它仍是單時間框架、close-confirmed、純 entry-quality refinement，不需要新的持有或平倉 policy。
- 它比 `gap fill bias` 更輕，因為不需要把 prior-day close / gap 語意拉進來。
- 它也比 `session close exit` 更適合現在的 repo，因為它只是加強突破品質，不會改變出場語意。

### 驗證

- factory / regression / CLI 測試已補上：
  - ORB 名稱與 defaults contract
  - EMA trend confirmation 的 CLI 接線與 strategy spec
  - breakout 雖然站上 OR high、但仍未站上 EMA 時會被擋下；站上 EMA 時保留原本 breakout 行為
- `python tools\phase_readiness_score.py` -> `110`
- `python -m unittest discover -s tests` -> `122 tests OK`
- `git diff --check` -> clean

### 決策

- keep
- 這次改動讓 ORB 現在不只看「價格是否突破 OR high 並站上 VWAP」，也能研究「較慢的 intraday EMA 是否已經重新被站上」。下一步應該先比較它和 `VWAP slope`、`body strength`、`fresh breakout` 疊加後，到底是補到新的趨勢對齊資訊，還是只是重複擋掉同一批弱突破。

## 2026-05-21 研究輪：EMA trend confirmation 之後，先做 EMA 相對 OR 位置的結構 gate，不直接做 gap fill bias 或 session close exit

這輪延續 ORB 的趨勢對齊與 session policy 邊界研究。結論是：**在 `EMA trend confirmation` 已經落地之後，下一個更合理的低風險候選，不是直接做 `gap fill bias`、`session close exit`，也不是先擴成多時間框架，而是補一個更貼近 ORB 本體的結構 gate：`EMA relative to opening range`。**

白話講，就是不只問「breakout 當下 close 有沒有站上 EMA」，還問 **EMA 本身相對於 OR 盒子在哪裡**。例如只在 `OR high` 位於 EMA 上方時接受 long，或在 EMA 落在 OR 盒子內部時直接不出訊號。

### 來源

- TradingView indicator：ORB with 100 EMA
  https://www.tradingview.com/script/JHm0ftM9-ORB-with-100-EMA/
- TradingView indicator：ORB 1-Hour High/Low Alert [EMA + SMA]
  https://www.tradingview.com/script/lODBOB7a-ORB-1-Hour-High-Low-Alert-EMA-SMA/
- TradingView Pine Script 官方文件：Repainting
  https://www.tradingview.com/pine-script-docs/concepts/repainting/

### 研究結論

- `ORB with 100 EMA` 把 **EMA 相對 OR 的位置** 當成獨立規則，而不只是一般趨勢濾網：
  - 只在 `OR` 位於 `100EMA` 上方時接受 buy setup。
  - 若 `100EMA` 落在 opening range 盒子內部，則直接不發出訊號。
  這表示公開 ORB 腳本常把「EMA 與 OR 結構的相對位置」視為一個比 `close > EMA` 更貼近 ORB 幾何語意的 gate。
- `ORB 1-Hour High/Low Alert [EMA + SMA]` 進一步顯示，很多 ORB 腳本會把 **VWAP、EMA、SMA** 疊成多層 trend filters；但從 SignalForge 的角度看，下一步若只是再加一條 generic SMA，比較像是繼續堆同類型 moving-average filter，未必比 `EMA 相對 OR 位置` 更有辨識度。
- TradingView 官方 `Repainting` 文件仍支持這個排序：只要這個 gate 繼續建立在同時間框架、已收盤 bar 的 OR 與 EMA 上，就不需要引入 `request.security()`，也不會把研究推向 higher-timeframe / intrabar 的不一致風險。

### 對 SignalForge 的含義

- 現在 ORB 已經有：
  - `close > VWAP`
  - `VWAP slope`
  - `close > EMA`
  - volume / OR volume baseline
  - range / distance / body / fresh breakout / signal window
  - session end / timezone metadata
- 若再補一個低風險 refinement，`EMA relative to OR` 比 `SMA trend confirmation` 更值得優先，因為：
  - 它仍是單時間框架、close-confirmed。
  - 它不是新的持有 / 平倉 policy。
  - 它不是 generic indicator stacking，而是直接利用 **EMA 與 OR 盒子** 的幾何關係定義 breakout 品質。
- 相較之下：
  - `gap fill bias` 會把 prior-day close 與跨 session 邊界一起帶進來。
  - `session close exit` 直接進入持有 / 平倉 policy。
  - `request.security()` 型多時間框架做法則有明確 repaint 風險。

### 建議排序

1. 先做 `EMA relative to OR` 結構 gate，例如：
   - only long when `OR high > EMA`
   - 或當 `EMA` 落在 `OR low ~ OR high` 之間時直接禁訊號
2. 完成後再比較它和 `EMA trend confirmation`、`VWAP slope`、`fresh breakout` 疊加後，是否只是重複擋掉同一批弱突破。
3. `gap fill bias`、`session close exit`、多時間框架版本仍放後面，等 entry-quality filters 收斂後再討論。

## 2026-05-21 執行輪：ORB 新增可選 EMA inside-range 結構 gate

這輪把上一輪研究收斂成一個最小可驗證版本：`ORB + Volume + VWAP` 現在可選擇再加上一條 **EMA inside-range 結構 gate**。啟用後，策略不是只看 breakout 當下 `close` 有沒有站上 EMA，而是直接檢查 **rolling EMA 本身是否還卡在 OR 盒子內**；如果 EMA 仍落在 `OR low ~ OR high` 之間，就把這次 breakout 視為結構仍然模糊，不接受 long entry。

### 修改內容

- `OrbVolumeVwapStrategy` 新增 `reject_ema_inside_opening_range`。
- 啟用後：
  - 若 breakout 當下的 rolling EMA 落在 `opening_range_low ~ opening_range_high` 之間，策略回傳 `ema_inside_opening_range`。
  - 若 EMA 視窗尚未暖機完成，策略回傳 `breakout_ema_reference_unavailable`。
- CLI 新增 `--orb-reject-ema-inside-range`。
- `strategy_spec` 新增：
  - `orb_reject_ema_inside_opening_range`
  - `orb_ema_inside_range_rule`
- 為了讓 artifact 名稱能區分不同 refinement，啟用後的 ORB strategy name 會加上 `emabox` 片段。

### 為什麼先做這個

- 它仍是單時間框架、close-confirmed、純 entry-quality refinement，不需要新的持有或平倉 policy。
- 它比單純再堆一條 generic SMA 更有辨識度，因為它直接利用 **EMA 與 OR 盒子** 的幾何關係。
- 它也比 `gap fill bias`、`session close exit` 或多時間框架版本更輕，因為不需要 prior-day close、session 平倉 policy，或 `request.security()`。

### 驗證

- factory / regression / CLI 測試已補上：
  - ORB 名稱與 defaults contract
  - `EMA inside-range` 的 CLI 接線與 strategy spec
  - breakout 發生時若 EMA 仍在 OR 盒子內會被擋下；若 EMA 已離開 OR 盒子則保留原本 breakout 行為
- `python tools\phase_readiness_score.py` -> `110`
- `python -m unittest discover -s tests` -> `126 tests OK`
- `git diff --check` -> clean

### 決策

- keep
- 這次改動讓 ORB 現在不只看「價格是否突破 OR high 並站上 EMA」，也能研究「EMA 本身相對 OR 盒子的位置是否仍然太模糊」。下一步應先比較它和 `EMA trend confirmation`、`VWAP slope`、`fresh breakout` 疊加後，到底是補到新的結構資訊，還是只是重複擋掉同一批弱突破。

## 2026-05-21 研究輪：EMA inside-range 之後，先做 filter attribution，不直接做 stop / target / session close exit

這輪依照 Codex 每 15 分鐘自動化 prompt 手動執行一次研究輪。結論是：**在 ORB 已經累積多個可選 entry-quality filter 之後，下一個最合理的低風險方向，不是立刻加入 stop loss、take profit、trailing stop 或 session close exit，而是先補 filter attribution / rejection summary，讓 artifact 能說清楚每個 filter 實際擋掉多少訊號。**

### 來源

- TradingView open-source：NeuraEdge ORB - Opening Range Breakout Indicator
  https://www.tradingview.com/script/Sb0YgLYU-NeuraEdge-ORB-Opening-Range-Breakout-Indicator/
- TradingView strategy：Opening Range Breakout (ORB)
  https://www.tradingview.com/script/AMsB94Rs-Opening-Range-Breakout-ORB/
- TradingView indicator：ORB + Volume + VWAP Breakout
  https://www.tradingview.com/script/7khuDtm8-ORB-Volume-VWAP-Breakout/
- TradingView open-source：ORB Breakout Strategy with VWAP and Volume Filters
  https://www.tradingview.com/script/wLSGHPUe-ORB-Breakout-Strategy-with-VWAP-and-Volume-Filters/
- TradingView Pine Script 官方文件：Strategies FAQ
  https://www.tradingview.com/pine-script-docs/faq/strategies/
- TradingView Pine Script 官方文件：Repainting
  https://www.tradingview.com/pine-script-docs/concepts/repainting/

### 研究結論

- 多個 ORB 腳本都會把 stop loss、take profit、reward-to-risk、session close flat 當成完整 strategy 功能；例如有些版本會依 OR range 或 ATR 類概念畫出自動 SL/TP，也有版本會用 OR opposite side 當 stop。這些方向合理，但它們已經不是 entry-quality refinement，而是持有 / 出場 policy。
- TradingView 官方 strategies 文件也把 stop loss / take profit 放在 `strategy.exit(...)` 的範圍，這代表一旦 SignalForge 開始納入 stop / target，就需要新的 execution model、fill assumption、reporting 欄位與 regression contract，而不能只在 `OrbVolumeVwapStrategy.decide_bar(...)` 多回傳一個 reason。
- 目前 SignalForge ORB 已經有很多 entry-side filter：VWAP 位置、VWAP slope、EMA trend、EMA inside-range、range size、breakout distance、full-bar、body strength、fresh breakout、OR volume baseline、signal window。若再直接堆下一個 filter，很容易不知道新條件是真的補到新資訊，還是只是重複擋掉同一批弱突破。
- 因此下一個較適合 automation 的小改動，是在不改交易語意的前提下，讓 backtest artifact 顯示 ORB filter attribution：例如各 reason count、各 filter-blocked count、accepted breakout count、hold count，或更聚焦地把 ORB blocked reasons 分群成 `session / range / structure / volume / trend / retest`。

### 對 SignalForge 的含義

- `filter attribution` 屬於 artifact 可驗證性，不是新策略語意，符合目前 autoresearch 主線「回測可驗證性」。
- 它能回答下一輪真正需要的問題：`EMA inside-range`、`EMA trend`、`VWAP slope`、`fresh breakout` 到底是在補不同資訊，還是同質重複。
- 它也能為之後是否加入 stop / target / session close exit 建立更乾淨的證據基礎。若連 entry filters 的實際阻擋分布都還不清楚，太早做出場 policy 會把問題變得更難歸因。

### 建議排序

1. 先補 ORB filter attribution / rejection summary，優先寫入 deterministic artifact，並用 regression test 鎖住 exact keys。
2. 再用現有 MSFT 5m demo CSV 比較幾組 ORB filter 組合，確認各 filter 是否擋掉不同類型的弱突破。
3. `stop loss / take profit / session close exit` 暫時留在 Phase 2 候選，等 entry-side attribution 清楚後，再一起設計 execution 與 reporting contract。
4. `wick/high-low trigger mode` 仍放後面，避免把 close-confirmed 研究邊界推向 intrabar 語意。

## 2026-05-21 執行輪：ORB trace summary 新增 filter attribution / rejection summary

這輪依照上一輪研究結論，不再新增 stop / target / session close exit，也不再擴 ORB 訊號邏輯，而是把改動收斂在 **deterministic artifact attribution**。目標是讓 `*_trace_summary.json` 與 Phase markdown 能直接說清楚：目前這次 ORB run 到底有多少 accepted breakout、多少 hold、哪些 filter 真正擋下了候選訊號，以及這些拒絕大致落在哪一類。

### 修改內容

- `trace_summary.schema_version` 升級到 `10`。
- 若這批 signal digests 屬於 ORB 語意，`*_trace_summary.json` 會新增 `orb_filter_attribution`：
  - `accepted_entry_count`
  - `blocked_signal_count`
  - `hold_count`
  - `group_counts`
  - `accepted_reason_counts`
  - `blocked_reason_counts`
  - `hold_reason_counts`
- `group_counts` 目前固定分成：
  - `accepted`
  - `hold`
  - `session`
  - `range`
  - `structure`
  - `trend`
  - `volume`
  - `retest`
  - `other`
- `blocked_reason_counts` 只統計真正屬於 filter rejection 的 reason，不把 `opening_range_building` 這類 session bootstrap 狀態混進去；這樣下一輪做 filter overlap / attribution comparison 時，數字比較有判讀價值。
- Phase markdown 若偵測到 `orb_filter_attribution`，會多出 `## ORB Filter Attribution` 區段，直接摘要 accepted / blocked / hold 數量、group 分布與 blocked reasons。

### 驗證

- `python tools\phase_readiness_score.py` -> 待本輪整體 guard 一起確認
- `python -m unittest discover -s tests -p test_reporting.py` -> `29 tests OK`
- `git diff --check` -> 待本輪整體 guard 一起確認

### 決策

- keep
- 這次改動的價值不是再疊一個新 filter，而是把 ORB 目前已經存在的 filter stack 變成更容易比較、歸因與 audit 的 artifact contract。
- 下一輪較合理的方向是進入 **第 3 輪分析比較**：拿既有資料與 artifacts 比較不同 ORB filter 組合，確認 `EMA inside-range`、`EMA trend`、`VWAP slope`、`OR volume baseline` 等條件，到底是在補不同資訊，還是只是重複擋掉同一批弱突破。

## 2026-05-21 分析輪：MSFT 5m ORB filter 組合比較

這輪依照上一輪留下的 attribution contract，直接用 repo 內現成的 `data\processed\ALPHAVANTAGE_MSFT_5M_demo.csv` 比較 5 組 ORB 變體：`base`、`VWAP slope`、`EMA trend`、`EMA inside-range`、`OR volume baseline`。這次不再新增策略邏輯，只用同一份 5 分鐘資料回答兩個問題：

1. 哪些 filter 真的改變了 entry-edge 結果；
2. 哪些 filter 只是增加 blocked count，但沒有換來更好的 PF / drawdown。

### 資料與流程

- 資料檔：`C:\Projects\signal-forge\data\processed\ALPHAVANTAGE_MSFT_5M_demo.csv`
- 範圍：`2026-04-21T04:00:00` -> `2026-05-20T19:55:00`
- bar 數：`4224`
- 每組都同時跑：
  - `entry-edge`
  - `phase --mode backtest`
- 產出：
  - `C:\Projects\signal-forge\reports\generated\msft-orb-filter-analysis-20260521.md`
  - `C:\Projects\signal-forge\reports\generated\msft-orb-filter-analysis-20260521.json`

### 比較摘要

| Config | Decision | PF | Trades | Win rate | Avg net PnL | Max DD | Overlap | Blocked | Accepted | Hold |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| base | FAIL | 0.255 | 14 | 42.86% | -26.59 | -4.63% | 0 | 1462 | 14 | 1164 |
| vwap-slope | FAIL | 0.255 | 14 | 42.86% | -26.59 | -4.63% | 0 | 1462 | 14 | 1164 |
| ema-trend | FAIL | 0.264 | 14 | 50.00% | -26.20 | -4.63% | 0 | 1483 | 14 | 1143 |
| ema-inside-range | PASS | 4.452 | 13 | 38.46% | 16.27 | -0.29% | 0 | 1754 | 13 | 873 |
| or-volume-baseline | FAIL | 0.069 | 12 | 41.67% | -40.09 | -4.95% | 0 | 2023 | 12 | 605 |

### attribution 解讀

- `base` 與 `VWAP slope` 完全一樣：這份 MSFT 樣本裡，`VWAP slope confirmation` 沒有額外擋到任何新訊號，代表它在這個資料窗內只是名義上存在，沒有新增辨識力。
- `EMA trend` 有新增效果，但很弱：只多擋了 `7` 根 `breakout_below_ema`，PF 只從 `0.255` 升到 `0.264`，最大回撤完全沒改善。
- `EMA inside-range` 是唯一明顯改變風險收益輪廓的條件：
  - PF 直接從 `0.255` 拉到 `4.452`
  - 平均淨損益轉正
  - 最大回撤從 `-4.63%` 壓到 `-0.29%`
  - 它主要新增了 `126` 根 `ema_inside_opening_range` blocked signals，且同時把 hold bars 從 `1164` 壓到 `873`
- `OR volume baseline` 雖然更貼近 ORB 語意，但在這份樣本上明顯過嚴：
  - `breakout_volume_blocked` 從 `72` 暴增到 `556`
  - PF 掉到 `0.069`
  - 平均淨損益與最大回撤都更差

### 研究結論

- 目前最值得保留並往後推進的 ORB refinement，不是 `VWAP slope`，也不是 `OR volume baseline`，而是 **`EMA inside-range`**。
- 在這份 MSFT 5m demo 樣本上，`EMA inside-range` 看起來不是和 `EMA trend`、`VWAP slope` 重複擋掉同一批弱突破，而是明確擋下另一群「趨勢基線仍卡在 OR 盒子內」的結構模糊訊號。
- `VWAP slope` 在這份樣本上暫時沒有證據顯示它值得獨立保留；除非換資料後有不同 blocked attribution，否則它目前更像冗餘 gate。
- `OR volume baseline` 目前應視為高風險可選分支，不適合提升成主線預設。

### 下一步

1. 下一輪若進入 code review，優先檢查：
   - `VWAP slope` 是否值得繼續保留在目前主線；
   - ORB filter 命名與 spec 是否開始過度膨脹。
2. 若下一輪回到執行輪，較合理的聚焦改動不是再加新 filter，而是把 `EMA inside-range` 的分析結論更明確寫進 reporting / docs，或補一個 compare helper 讓這種 attribution 比較不用每次手動組命令。
3. 若下一輪回到研究輪，應優先找第二份 intraday 樣本驗證 `EMA inside-range` 是否只是在這份 MSFT demo 上偶然有效。

## 2026-05-21 Code Review 輪：ORB filter stack 技術債盤點

這輪是 review-only，不改策略語意，也不順手補功能。重點是把最近幾輪自動化累積下來的 ORB strategy / reporting / CLI / tests 技術債整理成下一輪可執行的單點修復清單。

### review 範圍

- `src\signal_forge\strategies\orb_volume_vwap.py`
- `src\signal_forge\reporting\_legacy.py`
- `src\signal_forge\cli\strategy_options.py`
- `tests\test_reporting.py`

### findings

1. **高：`OrbVolumeVwapStrategy` 已經同時承載 naming、session context 建構與長串 filter gating，維護邊界開始模糊。**
   - 參考位置：`orb_volume_vwap.py:30-83`, `85-249`, `251-373`
   - 問題不是單一條件錯，而是單一 strategy class 現在同時負責：
     - strategy name 組裝；
     - intraday session / OR / VWAP / EMA / retest state 預計算；
     - breakout gate 的順序與 blocked reason contract。
   - 這會讓後續任何一個 filter 調整都同時碰到 artifact naming、state machine 與決策邏輯，debug 成本偏高。

2. **中：generic reporting 層開始直接吸收 ORB 專屬 attribution taxonomy，策略耦合正在往 `_legacy.py` 擴散。**
   - 參考位置：`_legacy.py:27-68`, `127-189`
   - `_ORB_GROUP_KEYS`、`_ORB_BLOCKED_GROUP_KEYS`、`_ORB_REASON_GROUPS` 與 `_build_orb_filter_attribution(...)` 都放在通用 reporting 檔案裡。
   - 現在還可控，但如果下一步再幫其他策略加類似 attribution，generic reporting 很容易退化成「每個策略各自塞一段特例」。

3. **中：CLI / artifact 的 ORB spec surface 正在快速膨脹，平面 key contract 越來越難讀。**
   - 參考位置：`strategy_options.py:13-147`, `150-193`, `196-369`
   - 單一 ORB 策略現在已經把 session、signal window、range gate、breakout gate、body strength、fresh breakout、volume baseline、EMA/VWAP filters、observed range 摘要都寫成平面欄位。
   - 這讓 summary JSON 很完整，但也提高了：
     - key 命名漂移風險；
     - spec 向後相容成本；
     - 使用者判讀 artifact 的負擔。

4. **低：reporting exact-text regression tests 已經開始偏脆，後續小文案變更的維護成本會升高。**
   - 參考位置：`tests\test_reporting.py:947-990`, `1085-1180`
   - 這些測試對 markdown / JSON 的完整字串做鎖定，對 artifact contract 很有用，但也代表：
     - 小幅 wording 調整就要改大段 golden text；
     - 當 reporting 同時承載更多 ORB 專屬欄位時，測試噪音會跟著放大。

### review 結論

- 目前最該優先處理的不是再加新 filter，而是把 **ORB filter stack 的程式結構與 artifact contract 邊界穩住**。
- 這次 review 沒看到立即性的 correctness bug，也沒有看到會破壞 `live dry-run only` 的風險。
- 但從可維護性角度來看，ORB 已經接近「功能還能加，但每再加一個 gate，維護成本就會比訊號價值上升更快」的臨界點。

### 建議下一步

1. **下一個執行輪**：優先抽出 ORB blocked reason / group mapping helper，至少先把 strategy decision chain 與 reporting attribution taxonomy 的共識邊界固定下來。
2. **下一個分析輪**：延續這次 `EMA inside-range` 的比較，確認 `VWAP slope` 是否應降級成次要分支或移出主線 CLI surface。
3. **後續若再擴 artifact**：優先考慮把 ORB 專屬 reporting 結構收斂成巢狀欄位或策略子區塊，不要無限制增加平面 key。
4. **若要修測試債**：只在 reporting contract 穩住後，再考慮把一部分 exact-text test 改成「結構 + 關鍵文案」混合驗證，避免每次小字串變更都重刷大段 golden。

## 2026-05-21 研究輪：EMA inside-range 與 VWAP slope 的主次排序

這輪不新增策略，也不補新 filter。研究問題只有一個：在目前的 ORB 主線裡，`EMA inside-range` 與 `VWAP slope` 到底誰比較應該留在主線、誰比較適合降成次要分支。

### 參考來源

- TradingView `ORB with 100 EMA`
  https://www.tradingview.com/script/JHm0ftM9-ORB-with-100-EMA/
- TradingView `Opening Range Breakout (ORB)`
  https://www.tradingview.com/script/AMsB94Rs-Opening-Range-Breakout-ORB/
- TradingView `ORB Breakout Strategy with VWAP and Volume Filters`
  https://www.tradingview.com/script/wLSGHPUe-ORB-Breakout-Strategy-with-VWAP-and-Volume-Filters/
- TradingView Pine Script Sessions 文件
  https://www.tradingview.com/pine-script-docs/concepts/sessions/
- TradingView Pine Script Repainting 文件
  https://www.tradingview.com/pine-script-docs/concepts/repainting/

### 外部研究重點

- `ORB with 100 EMA` 的更新說明直接把「**EMA 落在 opening range 盒子內就禁訊號**」當成明確規則，代表這不是抽象的均線偏好，而是公開 ORB 社群裡已經存在的**結構 gate**。
- `Opening Range Breakout (ORB)` 與 `ORB Breakout Strategy with VWAP and Volume Filters` 都把 `VWAP slope` 放在可選的 trend / momentum refinement 位置；它常見，但比較像是「價格在 VWAP 上方之後再加一道方向確認」，不是 ORB 幾何本體的一部分。
- TradingView 的 Sessions 文件也支持把 session/timezone 顯式化處理，讓 OR 與 market-clock 邊界維持單時間框架定義；這意味著 `EMA inside-range` 這種結構 gate 不需要再引入額外 session complexity。
- TradingView 的 Repainting 文件明確提醒 `request.security()` 可能造成 historical / realtime 不一致；因此若要在 ORB 主線裡再選一個優先 refinement，應優先選 **不需要多時間框架**、又能提供新增資訊的條件。

### 與目前本地回測結果對照

- 本地 `MSFT 5m demo` 的 attribution 比較已經顯示：
  - `EMA inside-range` 是唯一把 ORB 從 `FAIL` 拉到 `PASS` 的 refinement。
  - `VWAP slope` 在這份樣本上沒有新增辨識力，結果與 `base` 完全一致。
- 這次外部研究與本地結果是一致的：
  - `EMA inside-range` 更像 **結構性主條件**；
  - `VWAP slope` 更像 **次要趨勢微調條件**。

### 研究結論

- 目前較合理的主線排序應改成：
  1. 保留 `EMA inside-range` 在主線研究清單中的高優先級；
  2. 把 `VWAP slope` 降級成次要、可選、需額外證據才保留的 refinement。
- 換句話說，下一輪若要消化複雜度，**不應優先再幫 `VWAP slope` 擴 artifact surface**，而應優先：
  - 穩住 `EMA inside-range` 的 reporting / attribution / compare helper；
  - 檢查 `VWAP slope` 是否要退居次要參數、比較模式或非預設分支。

### 下一步

1. 若下一輪進入執行輪，優先處理 ORB helper / attribution 邊界，不再擴 `VWAP slope` 的 surface。
2. 若下一輪進入分析輪，應直接比較「移除 `VWAP slope` 後 artifact 是否更乾淨、資訊量是否實際下降」。
3. 若之後換第二份 intraday 樣本，重點不是先驗證所有 filter，而是先驗證 `EMA inside-range` 是否仍能提供獨立資訊。

## 2026-05-21 執行輪：抽出 ORB attribution helper

這輪不改 ORB 策略條件，也不新增 artifact 欄位。唯一的聚焦改動是把 ORB 專屬的 attribution taxonomy 與 validator，從 generic reporting 檔案 `src\signal_forge\reporting\_legacy.py` 抽到專用模組 `src\signal_forge\reporting\_orb_attribution.py`。

### 修改內容

- 新增 `src\signal_forge\reporting\_orb_attribution.py`
  - 收納 `ORB_GROUP_KEYS`
  - 收納 `ORB_BLOCKED_GROUP_KEYS`
  - 收納 `build_orb_filter_attribution(...)`
  - 收納 `validate_orb_filter_attribution_dict(...)`
- `src\signal_forge\reporting\_legacy.py` 改成只 import ORB helper，不再直接承載 ORB taxonomy 常數與 attribution validator 細節。
- `tests\test_reporting.py` 新增 direct-helper test，直接鎖住抽離後的 ORB attribution 輸出 contract。

### 這輪解決的技術債

- 降低 `_legacy.py` 與 ORB 特例的直接耦合。
- 讓 ORB attribution 有明確的模組邊界，下一輪若要再抽 compare helper 或調整 blocked reason mapping，切點會更清楚。
- 用 direct-helper test 補上一層單元測試，避免只靠整合測試間接覆蓋。

### 驗證

- `python tools\phase_readiness_score.py` -> `110`
- `python -m unittest discover -s tests` -> `128 tests OK`
- `git diff --check` -> clean

### 決策

- keep
- 這輪沒有改變 ORB 的交易語意、artifact schema 或 Phase 報表內容；它只整理 reporting 的程式邊界。
- 下一輪較合理的方向是進入 **第 3 輪分析比較**，直接比較「保留 / 移除 `VWAP slope`」後的 artifact 與指標差異，確認它是否真的值得留在主線 surface。

## 2026-05-21 分析輪：`VWAP slope` 在 `EMA inside-range` 主線上的增量

這輪直接回答上一輪留下的問題：如果 `EMA inside-range` 已經啟用，`VWAP slope` 還有沒有額外資訊價值。這次沿用既有 `MSFT 5m demo` 資料，另外重跑兩組配置：

1. `EMA inside-range`
2. `EMA inside-range + VWAP slope`

產出報表放在：

- `reports\generated\msft-orb-vslope-on-ema-box-20260521.md`
- `reports\generated\msft-orb-vslope-on-ema-box-20260521.json`

### 比較摘要

| Config | Decision | PF | Trades | Win rate | Avg net PnL | Max DD | Overlap | Blocked | Accepted | Hold |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ema-inside-range | PASS | 4.452 | 13 | 38.46% | 16.27 | -0.29% | 0 | 1754 | 13 | 873 |
| ema-inside-range + vwap-slope | PASS | 4.546 | 13 | 38.46% | 16.37 | -0.29% | 0 | 1762 | 13 | 865 |

### attribution 解讀

- `VWAP slope` 在 `EMA inside-range` 主線上**不是完全零資訊**：
  - 多了 `2` 根 `breakout_vwap_slope_blocked`
  - `blocked_signal_count` 從 `1754` 增加到 `1762`
  - `hold_count` 從 `873` 降到 `865`
- 但它的增量仍然**很小**：
  - 交易數沒有變
  - 勝率沒有變
  - 最大回撤沒有變
  - PF 只從 `4.452` 小幅升到 `4.546`
  - 平均淨損益只從 `16.27` 小幅升到 `16.37`

### 研究結論

- `VWAP slope` 在 `EMA inside-range` 主線上有**微弱的增量資訊**，所以不能再說它是完全冗餘。
- 但從影響幅度來看，它仍然更適合被視為：
  - **次要 refinement**
  - **可比較分支**
  - 而不是 ORB 主線的核心結構條件
- 因此目前排序應該是：
  1. `EMA inside-range` 保持主線高優先級
  2. `VWAP slope` 保持可選，但不升回核心 surface

### 下一步

1. 下一輪若回到 code review，應檢查 `VWAP slope` 是否值得繼續佔用目前主線 CLI / strategy name surface。
2. 若下一輪回到執行輪，較合理的改動不是再擴 `VWAP slope`，而是讓 compare / reporting 更容易直接看出「微弱增量但非零」這種情況。
3. 若之後換第二份 intraday 樣本，優先驗證這個微弱增量是否可重現；若不可重現，`VWAP slope` 更適合降到實驗分支。

## 2026-05-21 Code Review：ORB attribution helper 抽離後的殘餘技術債

這輪是 review-only，不改策略語意。重點是檢查 `a0fb74d` 之後，ORB attribution helper 雖然已抽出，但還有哪些技術債沒有真正消失。

### Findings

#### 1. `flatten_count` 已成為 validator 的死參數

- 嚴重度：中
- 受影響檔案：`src\signal_forge\reporting\_orb_attribution.py`
- 現況：`validate_orb_filter_attribution_dict(...)` 仍接收 `flatten_count`，但函式一進來就 `del flatten_count`，代表這個參數已經不再參與任何驗證。
- 風險：呼叫端會誤以為 ORB attribution validator 仍有檢查 flatten 關係，但實際上沒有；這會讓 contract surface 比真正需要的更寬，也增加後續重構成本。
- 建議修法：下一個執行輪可把 `flatten_count` 從 helper 與呼叫端簽名一起移除，或明確定義它應該驗證什麼，二選一，不要維持半退役狀態。

#### 2. generic reporting 仍直接知道 ORB markdown schema

- 嚴重度：中
- 受影響檔案：`src\signal_forge\reporting\_legacy.py`
- 現況：taxonomy 與 validator 已抽到 `_orb_attribution.py`，但 markdown rendering 仍在 `_legacy.py` 內手動拆 `accepted/hold/session/range/structure/trend/volume/retest/other` 九個 group，並自己拼 `Blocked reasons` 文字。
- 風險：這表示 ORB 特例只是從「驗證層耦合」移到「呈現層耦合」。未來只要 ORB attribution 顯示格式變動，generic reporting 仍必須跟著改。
- 建議修法：下一輪若要繼續消化耦合，應考慮把 ORB attribution markdown section builder 也抽成 helper，讓 `_legacy.py` 只負責插入區塊，不負責理解 ORB schema 細節。

#### 3. ORB CLI / artifact spec surface 仍在單一平面持續膨脹

- 嚴重度：中
- 受影響檔案：`src\signal_forge\cli\strategy_options.py`
- 現況：ORB 已累積 session start/end/timezone、VWAP slope、EMA trend、EMA inside-range、signal window、range gate、breakout distance、full bar、body strength、fresh breakout、OR volume baseline 等大量平面欄位。
- 風險：CLI 可用，但 artifact `strategy_spec` 與參數命名面積已經很大，後續再加 filter 時，閱讀、比較與維護成本會持續上升。
- 建議修法：不要急著再擴 surface。下一輪若做執行輪，比較合理的是整理 ORB spec grouping 或 helper，而不是再加新的 ORB filter 參數。

#### 4. deterministic reason-count formatting helper 出現重複實作

- 嚴重度：低
- 受影響檔案：`src\signal_forge\reporting\_legacy.py`、`src\signal_forge\reporting\_orb_attribution.py`
- 現況：`_build_reason_count_items(...)` 在 generic reporting 與 ORB helper 各有一份，邏輯都是把 Counter 依 `(-count, reason)` 排序後輸出 deterministic list。
- 風險：目前不是 correctness bug，但若未來排序 contract 或欄位形狀變動，容易發生兩邊修一邊漏一邊。
- 建議修法：除非下一輪剛好需要動到 reason-count contract，否則先記錄即可；等 helper 邊界再穩一點時，再評估是否抽成共用 deterministic formatter。

### Review 結論

- `a0fb74d` 已經把 ORB attribution 的 taxonomy 與 validator 從 `_legacy.py` 拉出來，方向正確。
- 但目前比較接近「**切出第一層 helper**」，不是完全解耦。
- 下一個最值得做的單點修復，不是再擴 `VWAP slope` 或新增 ORB filter，而是：
  1. 收窄 ORB attribution validator 的假 surface；
  2. 再往前抽一層 ORB attribution markdown builder；
  3. 暫停擴大 ORB CLI / artifact 平面欄位。

### 下一步

1. 下一輪若進入研究輪，可先研究 `VWAP slope` 是否值得退出主線 CLI surface，只保留 compare-only 分支。
2. 下一輪若進入執行輪，最合理的單點改動是移除 `flatten_count` 死參數，或把 ORB attribution markdown builder 從 `_legacy.py` 抽離。
3. 下一輪若進入分析輪，可比較 `VWAP slope` 保留在主線 surface 與降級為 compare-only 分支後，artifact 可讀性是否明顯改善。

## 2026-05-21 研究輪：`VWAP slope` 是否值得留在主線 CLI surface

這輪只研究一個排序問題：`VWAP slope` 應該繼續留在 ORB 主線 CLI / strategy surface，還是降級成 compare-only 的次要 refinement。

### 來源

- TradingView `ORB + Volume + VWAP Breakout`
  https://www.tradingview.com/script/7khuDtm8-ORB-Volume-VWAP-Breakout/
- TradingView `Opening Range Breakout + VWAP + Volume [ORB Strategy]`
  https://www.tradingview.com/script/hapKLoXr-Opening-Range-Breakout-VWAP-Volume-ORB-Strategy/
- TradingView `Opening Range Breakout (ORB)`
  https://www.tradingview.com/script/AMsB94Rs-Opening-Range-Breakout-ORB/
- TradingView `ORB with 100 EMA`
  https://www.tradingview.com/script/JHm0ftM9-ORB-with-100-EMA/

### 外部研究重點

- `ORB + Volume + VWAP Breakout` 與 `Opening Range Breakout + VWAP + Volume` 這類腳本，核心都是 **OR break + volume + price relative to VWAP**；`VWAP slope` 即使出現，也更像額外的 direction filter，而不是第一層結構條件。
- `Opening Range Breakout (ORB)` 會把 `VWAP slope` 與 `price > VWAP` 並列成 optional trend filter，語意上仍屬「趨勢微調」，不是 OR 幾何本體。
- `ORB with 100 EMA` 這類腳本則更直接把 `EMA` 與 OR 盒子的相對位置寫成主條件，代表公開 ORB 社群更常把 **結構 gate** 放在主線，把 slope / momentum filter 放在後面。

### 與本地結果對照

- 本地 `MSFT 5m demo` 比較顯示：
  - `EMA inside-range` 能把 ORB 從 `FAIL` 拉到 `PASS`
  - `VWAP slope` 在 `EMA inside-range` 主線上只有**微弱但非零**的增量
- 這和外部腳本排序一致：`VWAP slope` 不是沒價值，但它更像第二層 refinement，而不是該長期佔用主線 surface 的核心條件。

### 研究結論

- 目前較合理的定位是：
  1. `VWAP slope` 保留功能與比較能力；
  2. 但在研究排序上，應降級成 **compare-first / optional refinement**；
  3. 主線 CLI / artifact surface 應優先保留給 `EMA inside-range`、session 邊界、volume baseline 這類更接近 ORB 核心語意的條件。
- 換句話說，`VWAP slope` 現在不是優先刪除目標，但也不應再擴它的 surface 或把它包裝成主線核心條件。

### 下一步

1. 下一輪若進入執行輪，較合理的是把 `VWAP slope` 在 reporting / CLI 中重新標示成 secondary refinement，而不是新增更多相依欄位。
2. 若之後再做分析輪，可直接比較「保留主線 surface」與「降級為 compare-only 記錄」兩種 artifact 可讀性差異。
3. 若第二份 intraday 樣本仍只看到微弱增量，`VWAP slope` 就更適合正式降成 compare-only 分支。

## 2026-05-21 執行輪：把 `VWAP slope` 明確標成 secondary refinement

這輪不改 ORB 交易判斷，也不調整任何 filter 門檻。唯一的聚焦改動是把 `VWAP slope` 在 CLI / artifact contract 內的定位寫清楚，避免它繼續看起來像 ORB 主線核心條件。

### 修改內容

- `src\signal_forge\cli\strategy_options.py`
  - `--orb-vwap-slope-confirmation` 的 help 改成明確說明它是 **secondary refinement**。
  - `strategy_spec_from_args(...)` 新增 `orb_vwap_slope_tier=secondary_refinement`。
  - `orb_vwap_slope_rule` 改成明寫「this secondary refinement」。
- `tests\test_cli.py`
  - 補 assertion，直接鎖 `orb_vwap_slope_tier`
  - 同步更新 `orb_vwap_slope_rule` 的 exact text

### 這輪解決的問題

- 研究上雖然已經知道 `VWAP slope` 應降級成次要 refinement，但如果 artifact 還只寫 `enabled/disabled + rule`，後續閱讀者仍可能把它誤判成和 `EMA inside-range` 同等級的主線條件。
- 把 tier 寫進 deterministic contract 後，分析報表、summary JSON 與後續 compare 流程就能直接知道它是第二層條件，而不是再靠聊天或實驗紀錄補充上下文。

### 驗證

- `python tools\phase_readiness_score.py` -> `110`
- `python -m unittest discover -s tests` -> `128 tests OK`
- `git diff --check` -> clean

### 決策

- keep
- 這輪只整理 surface 語意，不動策略決策鏈。

### 下一步

1. 下一輪若進入分析輪，可直接比較「保留這個 secondary refinement 標示」後，artifact 是否更容易讀出主次層級。
2. 下一輪若進入 review 輪，可檢查 `EMA trend`、`EMA inside-range`、`OR volume baseline` 是否也需要類似的 tier 分層。

## 2026-05-21 分析輪：`orb_vwap_slope_tier` 是否真的提升 artifact 可讀性

這輪不研究新策略，也不再調整 ORB filter。目標只有一個：確認上一輪加進去的 `orb_vwap_slope_tier=secondary_refinement`，是否在**不改績效結論**的前提下，讓 artifact 更容易看出 `VWAP slope` 的主次層級。

### 本輪重跑配置

資料來源固定：

- `data\processed\ALPHAVANTAGE_MSFT_5M_demo.csv`

重跑兩組：

1. `EMA inside-range`
2. `EMA inside-range + VWAP slope`

產出報表：

- `reports\generated\msft-orb-vwap-slope-tier-readability-20260521.md`
- `reports\generated\msft-orb-vwap-slope-tier-readability-20260521.json`

### 比較摘要

| Config | PF | Trades | Win rate | Avg net PnL | Max DD | Overlap | Blocked | Accepted | Hold | VWAP slope flag | VWAP slope tier |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| ema-inside-range | 4.452 | 13 | 38.46% | 16.27 | -0.29% | 0 | 1754 | 13 | 873 | disabled | secondary_refinement |
| ema-inside-range + vwap-slope | 4.546 | 13 | 38.46% | 16.37 | -0.29% | 0 | 1762 | 13 | 865 | enabled | secondary_refinement |

### 與前一份比較報表的關係

- 對照先前的 `msft-orb-vslope-on-ema-box-20260521.json`：
  - `EMA inside-range` 的 PF、交易數、勝率、平均淨損益、最大回撤都**完全相同**
  - `EMA inside-range + VWAP slope` 的 PF、交易數、勝率、平均淨損益、最大回撤也**完全相同**
- 代表上一輪加入的 `orb_vwap_slope_tier` 沒有偷偷改動策略行為；它只改變 artifact 語意。

### 分析結論

- `orb_vwap_slope_tier=secondary_refinement` 是有價值的：
  - 它不改績效結論；
  - 但它讓閱讀 summary JSON / markdown 的人不用再從實驗紀錄反推，直接就知道 `VWAP slope` 是第二層條件。
- 目前 ORB 的 artifact 可讀性因此變得更一致：
  - `EMA inside-range` 仍是主線結構 gate；
  - `VWAP slope` 仍保留，但被正確標成 compare-first / optional 的次要 refinement。

### 下一步

1. 下一輪若進入 review 輪，可檢查 `EMA trend`、`OR volume baseline` 是否也需要類似 tier 標示。
2. 下一輪若進入執行輪，不應再擴 `VWAP slope` 的 surface；較合理的是把同樣的層級語意套用到其他 optional filter。

## 2026-05-21 Code Review：`orb_vwap_slope_tier` 落地後的殘餘 surface 問題

這輪是 review-only，不改 ORB 策略語意。重點不是質疑 `orb_vwap_slope_tier` 本身，而是檢查它落地後，artifact / CLI / tests 是否真的形成一致 contract。

### Findings

#### 1. tier 語意目前只補到 `VWAP slope`，同層 optional filter 仍然沒有對齊

- 嚴重度：中
- 受影響檔案：`src\signal_forge\cli\strategy_options.py`
- 現況：`orb_vwap_slope_tier` 已存在，但同樣屬於 optional refinement 的 `EMA trend`、`OR volume baseline`、`range gate` 等條件，仍只保留 `enabled/disabled + rule`，沒有對應的 tier / role 語意。
- 風險：artifact 會形成不對稱 contract，看起來像只有 `VWAP slope` 需要解釋層級，其他條件卻默認都是主線，這會讓後續比較與閱讀再次漂移。
- 建議修法：若要保留 tier contract，下一輪應該選一組真正同層的 optional filters 一起對齊；否則 `VWAP slope` 會變成特例，而不是通用 contract。

#### 2. `strategy_spec` 仍然是平面 key 擴張，tier 只是再加一層欄位，不是收斂結構

- 嚴重度：中
- 受影響檔案：`src\signal_forge\cli\strategy_options.py`
- 現況：`strategy_spec_from_args(...)` 目前仍把 session、range、volume、trend、structure 全部攤平成單一 dict；`orb_vwap_slope_tier` 的加入讓語意更清楚，但資料結構本身沒有變得更乾淨。
- 風險：只要繼續沿這個模式前進，每新增一個 tier / role key，都會讓平面 namespace 更擁擠，最後又回到「知道比較多，但更難掃讀」的狀態。
- 建議修法：下一輪若再碰 artifact contract，優先考慮 grouping helper 或小型結構分區，而不是一路往平面 `strategy_spec` 疊新欄位。

#### 3. CLI regression 只鎖住 enabled 路徑，沒有鎖住 disabled/default tier contract

- 嚴重度：中
- 受影響檔案：`tests\test_cli.py`
- 現況：目前只有 `test_entry_edge_command_accepts_orb_vwap_slope_confirmation(...)` 直接驗證 `orb_vwap_slope_tier=secondary_refinement`，但沒有對應測試鎖住「未啟用 VWAP slope 時，tier 仍固定存在」的 disabled/default contract。
- 風險：未來若有人把 disabled 路徑的 `orb_vwap_slope_tier` 拿掉、改名，或只在 enabled 時才輸出，現有測試不一定會立刻擋下來。
- 建議修法：若下一輪要穩這個 contract，應補一個 disabled/default case，確認 tier 是 deterministic presence，而不是 conditional field。

#### 4. `strategy_name` 與 `strategy_spec` 的層級語意仍不一致

- 嚴重度：低
- 受影響檔案：`tests\test_cli.py`、相關 ORB strategy naming
- 現況：artifact 已把 `VWAP slope` 標成 `secondary_refinement`，但 `strategy_name` 仍把 `vslope` 直接嵌進主體名稱中，視覺上和 `emabox`、`ema10` 等條件並列。
- 風險：summary JSON 的 `strategy_name` 與 `strategy_spec` 會傳遞兩種不同層級訊號：前者像主線組件，後者說它只是次要 refinement。
- 建議修法：這不需要立刻改，但若之後真的要做更完整的 role/tier contract，就該決定 `strategy_name` 是否也要反映主次層級，或刻意維持 name 只表「有無啟用」而不表「層級」。

### Review 結論

- `orb_vwap_slope_tier` 本身是正確方向，因為它確實提升了 artifact 可讀性。
- 但目前它還只是 **單點語意補丁**，不是完整的 surface contract。
- 若要繼續沿這條路走，下一步應該是：
  1. 選擇是否把 tier/role contract 推成通用規則；
  2. 若要推，先補 disabled/default test，再選一組同層 optional filters 對齊；
  3. 若不推，就應避免再為其他單一 filter 各自新增一套特例欄位。

### 下一步

1. 下一輪若進入研究輪，可先整理 ORB 現有 optional filters 的真正分層，避免憑感覺擴 tier。
2. 下一輪若進入執行輪，最合理的單點修復是補 `orb_vwap_slope_tier` 的 disabled/default regression test。

## 2026-05-21 研究輪：哪些 ORB optional filters 真的適合同一套 tier/role contract

這輪不新增策略，也不改 artifact schema。研究問題只有一個：如果下一輪要把 `tier/role` contract 從 `VWAP slope` 擴出去，哪些 ORB optional filters 真的是同層，哪些其實只是「都可選」但角色不同，不應硬塞同一個 tier。

### 來源

- TradingView `Opening Range Breakout`
  https://www.tradingview.com/script/tZtCD3TM-Opening-Range-Breakout/
- TradingView `Opening Range Breakout (ORB)`
  https://www.tradingview.com/script/AMsB94Rs-Opening-Range-Breakout-ORB/
- TradingView `ORB + Volume + VWAP Breakout`
  https://www.tradingview.com/script/7khuDtm8-ORB-Volume-VWAP-Breakout/
- TradingView `NeuraEdge ORB - Opening Range Breakout Indicator`
  https://www.tradingview.com/script/Sb0YgLYU-NeuraEdge-ORB-Opening-Range-Breakout-Indicator/
- TradingView `ORB - Opening Range Breakout Backtest`
  https://www.tradingview.com/script/DOhV0uXT/

### 外部研究重點

- `Opening Range Breakout` 與 `ORB - Opening Range Breakout Backtest` 都把 **EMA trend** 放在和 `VWAP slope` 很接近的位置：它不是 OR 幾何本體，而是 breakout 後再加一道趨勢對齊。
- `Opening Range Breakout (ORB)` 明確把 **ORB size filter** 視為 optional filter，語意上更像「session shape gate」；它不是 trend refinement，而是在 breakout 發生前先判斷這天的 OR 結構是否值得交易。
- `ORB + Volume + VWAP Breakout` 與 `NeuraEdge ORB` 都把 volume confirmation 當成核心確認之一；但如果 volume baseline 換成 **opening-range average volume**，它比較像「confirmation baseline variant」，不是和 `VWAP slope` 同層的方向 refinement。

### 研究結論

- 若要擴 `tier/role` contract，**最適合先和 `VWAP slope` 對齊的是 `EMA trend`**，因為兩者都屬：
  - breakout 後才判斷；
  - 單時間框架；
  - trend / direction refinement。
- `OR size filter` 雖然也是 optional，但比較像 **session-shape gate**，角色不同。
- `OR volume baseline` 雖然也是 optional，但比較像 **confirmation baseline choice**，不是單純層級高低問題。

### 對下一輪的含義

- 不要把目前 ORB 所有 optional keys 都塞進同一個 `secondary_refinement` bucket。
- 若下一輪真的要把 contract 往前推，較合理的做法是：
  1. 先補 `VWAP slope` 的 disabled/default regression；
  2. 若還要擴 role/tier，先從 `EMA trend` 這種真正同層的條件開始；
  3. 對 `OR size`、`OR volume baseline` 這類角色不同的 filter，應考慮用 **role/family**，而不是只用單一 tier。

### 下一步

1. 下一輪若進入執行輪，先補 `orb_vwap_slope_tier` 的 disabled/default regression test。
2. 若之後要擴充層級 contract，優先研究 `orb_ema_trend_*` 是否應補成和 `VWAP slope` 對稱的 role/tier 欄位。

## 2026-05-21 執行輪：補上 `orb_vwap_slope_tier` 的 disabled/default regression

這輪不改 ORB 策略語意，也不擴 artifact schema；只做一個聚焦修補：把 `orb_vwap_slope_tier` 的 disabled/default contract 補進 CLI regression。

### 修改內容

- 在 `tests\test_cli.py` 新增 `test_entry_edge_command_keeps_orb_vwap_slope_tier_when_disabled(...)`。
- 測試直接驗證未啟用 `--orb-vwap-slope-confirmation` 時：
  - `orb_vwap_slope_confirmation=disabled`
  - `orb_vwap_slope_tier=secondary_refinement`
  - `orb_vwap_slope_rule` 仍固定存在

### 這輪解決的風險

- 先前只有 enabled 路徑會驗 `orb_vwap_slope_tier`，若未來有人把 disabled 路徑的 tier 欄位移除、改名，現有測試不一定會立刻擋下來。
- 補上這個 regression 後，`orb_vwap_slope_tier` 會被鎖成 deterministic presence，而不是 conditional field。

### 下一步

1. 下一輪若進入分析輪，可確認 disabled/default tier contract 補齊後，artifact 可讀性是否已足夠。
2. 若之後要擴 tier/role contract，優先考慮 `EMA trend`，不要直接把 `OR size` 或 `OR volume baseline` 也塞進同一層。

## 2026-05-21 分析輪：disabled/default tier regression 補齊後，artifact 可讀性是否真的有變

這輪不再調整 ORB filter，也不改 artifact schema；只回答一個問題：上一輪補上的 `orb_vwap_slope_tier` disabled/default regression，是否讓 **runtime artifact** 本身變得更清楚，還是只是把原本已經存在的 contract 補進測試覆蓋。

### 比較設定

- 資料檔：`C:\Projects\signal-forge\data\processed\ALPHAVANTAGE_MSFT_5M_demo.csv`
- 比較組合：
  1. `EMA inside-range`
  2. `EMA inside-range + VWAP slope`
- 本輪新產物：
  - `C:\Projects\signal-forge\reports\generated\msft-orb-vwap-slope-default-tier-analysis-20260521.md`
  - `C:\Projects\signal-forge\reports\generated\msft-orb-vwap-slope-default-tier-analysis-20260521.json`

### 結果摘要

- `EMA inside-range`：
  - PF `4.452`
  - Trades `13`
  - Win rate `38.46%`
  - Avg net PnL `16.27`
  - Max DD `-0.29%`
  - blocked `1754`
  - hold `873`
  - `orb_vwap_slope_confirmation=disabled`
  - `orb_vwap_slope_tier=secondary_refinement`
- `EMA inside-range + VWAP slope`：
  - PF `4.546`
  - Trades `13`
  - Win rate `38.46%`
  - Avg net PnL `16.37`
  - Max DD `-0.29%`
  - blocked `1762`
  - hold `865`
  - `orb_vwap_slope_confirmation=enabled`
  - `orb_vwap_slope_tier=secondary_refinement`

### 關鍵判讀

- 對照先前 `msft-orb-tiercheck-20260521-*.json` 基線，兩條路徑的 PF、trade count、win rate、average net PnL、max drawdown 與 `orb_vwap_slope_tier` 都完全一致。
- 代表上一輪 `6bb52e1` 的改動**沒有改變 runtime artifact**；它只是把 disabled/default 路徑也正式納入 regression coverage。
- 因此目前較準確的結論是：
  - `orb_vwap_slope_tier` 的 **artifact 可讀性早就已經足夠**；
  - 上一輪新增的價值是 **contract 信心**，不是新的 artifact 語意。

### 下一步

1. 若之後還要擴 tier/role contract，應優先看 `EMA trend` 這種真正同層的 refinement，而不是先碰 `OR size` 或 `OR volume baseline`。
2. 下一輪若進入 review，可檢查是否需要把這種「disabled 也固定存在的 tier 欄位」推成通用規則。

## 2026-05-21 Code Review：`VWAP slope tier` contract 補齊後的殘餘技術債

這輪是 review-only，不改 ORB 策略語意。重點不是質疑 `orb_vwap_slope_tier` 本身，而是檢查最近幾輪把 tier contract、disabled/default regression 與 readability analysis 串起來之後，還剩下哪些具體債務。

### Finding 1：disabled 路徑仍會顯示「when enabled」規則文案，語意容易誤讀

- 嚴重度：中
- 受影響檔案：`src\signal_forge\cli\strategy_options.py`、`reports\generated\msft-orb-default-tier-contract-20260521-ema-box-entry.md`
- 現況：`orb_vwap_slope_confirmation=disabled` 時，artifact 仍固定輸出 `orb_vwap_slope_rule: when enabled, this secondary refinement ...`。
- 風險：這在機器層面是 deterministic contract，但在人類閱讀層面會讓 disabled 路徑看起來像「規則仍在生效，只是前面多了一句 when enabled」。
- 建議修法：若下一輪要再碰 artifact surface，可考慮把 `rule` 與 `state` 再拆開，例如保留固定規則描述，同時增加更短的 `orb_vwap_slope_effective=disabled/enabled`，或把文案改成較中性的靜態描述。

### Finding 2：`tier` 語意目前只在 entry-edge artifact 明確可見，phase 路徑仍不對稱

- 嚴重度：中
- 受影響檔案：`reports\generated\msft-orb-default-tier-contract-20260521-ema-box-entry.md`、`reports\generated\msft-orb-default-tier-contract-20260521-ema-box-phase.md`
- 現況：entry-edge report 會完整列出 `strategy_spec`，所以能看到 `orb_vwap_slope_tier=secondary_refinement`；但 phase markdown 主體目前沒有把同一層策略語意帶進人類可讀報表。
- 風險：若使用者或未來 automation 主要從 phase report 回看結果，就無法直接看出 `VWAP slope` 是主線條件還是次要 refinement，必須再跳回 entry-edge report 或 JSON。
- 建議修法：若未來要把 role/tier contract 當成正式 surface，應決定 phase markdown 是否也要帶出最小必要的 strategy layer 信息，而不是只讓 entry-edge 看得到。

### Finding 3：`VWAP slope` 已有 tier，但同層候選 `EMA trend` 仍沒有對稱 contract

- 嚴重度：中
- 受影響檔案：`src\signal_forge\cli\strategy_options.py`
- 現況：根據前兩輪研究，`EMA trend` 才是最接近 `VWAP slope` 的同層 refinement；但目前只有 `VWAP slope` 有 `orb_vwap_slope_tier=secondary_refinement`，`EMA trend` 仍只有 enabled/disabled + rule。
- 風險：contract 會傳遞不一致訊號：不是因為兩者層級真的不同，而是因為目前只先補了一個欄位。
- 建議修法：若決定繼續保留 tier/role 方向，下一個最合理的對象應是 `EMA trend`；若不打算繼續擴，則應避免再把 `VWAP slope` 的特例表達擴散成更多單點欄位。

### Finding 4：目前沒有窄範圍 unit test 直接鎖 `strategy_spec_from_args(...)` 的 contract

- 嚴重度：低
- 受影響檔案：`tests\test_cli.py`
- 現況：最近幾輪關於 `orb_vwap_slope_tier` 的驗證全部透過 CLI end-to-end regression 進行，沒有更窄的 `strategy_spec_from_args(...)` 單元測試。
- 風險：CLI regression 當然有效，但 failure localization 較差；未來若只是 `strategy_spec` 文案或 key drift，測試會在較外層爆掉，不容易第一時間定位是 parser、strategy builder 還是 spec 組裝器出問題。
- 建議修法：若下一輪要消化小型測試債，可以補一個直接調 `strategy_spec_from_args(...)` 的 unit-level contract test，讓 `tier/rule/state` 這類 metadata drift 更容易定位。

### Review 結論

- `orb_vwap_slope_tier` 現在已經有足夠的 deterministic coverage，這部分不再是主要風險。
- 真正剩下的問題是 **surface 對稱性與閱讀語意**：
  1. disabled 狀態下的 rule 文案仍容易誤讀；
  2. phase / entry-edge artifact 對 tier 的暴露程度不對稱；
  3. `EMA trend` 是否也要進入同一層 contract 還沒有定案；
  4. 測試仍偏重 CLI E2E，缺少窄範圍 contract 測試。

### 下一步

1. 若下一輪進入研究輪，可先決定 `tier/role` 是否真的要推成通用規則，還是停在 `VWAP slope` 這個特例。
2. 若下一輪進入執行輪，最合理的單點修復是二選一：
   - 補 `strategy_spec_from_args(...)` 的窄範圍 contract test；
   - 或把 disabled 狀態下的 `orb_vwap_slope_rule` 文案改成較中性的靜態描述。

## 2026-05-21 研究輪：`tier/role` contract 應該擴成通用規則，還是停在 `VWAP slope` 特例

這輪不改程式，也不重跑新的 ORB filter 組合。研究問題只有一個：既然 `orb_vwap_slope_tier=secondary_refinement` 已經落地，下一步到底應該把這個 contract 推成通用規則，還是停在單一特例，避免 `strategy_spec` 再膨脹。

### 來源

- TradingView `Opening Range Breakout`
  https://www.tradingview.com/script/tZtCD3TM-Opening-Range-Breakout/
- TradingView `NeuraEdge ORB - Opening Range Breakout Indicator`
  https://www.tradingview.com/script/Sb0YgLYU-NeuraEdge-ORB-Opening-Range-Breakout-Indicator/
- TradingView `Opening Range Breakout + VWAP + Volume [ORB Strategy]`
  https://www.tradingview.com/script/hapKLoXr-Opening-Range-Breakout-VWAP-Volume-ORB-Strategy/
- TradingView `Opening Range Breakout (ORB)`
  https://www.tradingview.com/script/AMsB94Rs-Opening-Range-Breakout-ORB/
- TradingView `BORTORB - Opening Range Breakout Indicator`
  https://www.tradingview.com/script/bDkeiwBg-BORTORB-Opening-Range-Breakout-Indicator/

### 外部研究重點

- `Opening Range Breakout` 直接把 **EMA 趨勢向上、價格在 EMA 上方、EMA 位於 OR high 上方** 當成 breakout trend confirmation；這說明 `EMA trend` 與 `VWAP slope / VWAP alignment` 在外部腳本裡常屬同一層「方向確認」。
- `NeuraEdge ORB` 與 `Opening Range Breakout + VWAP + Volume` 都把 **EMA filter**、**VWAP filter**、**volume confirmation** 分開列成獨立可切換條件，顯示公開 ORB 腳本慣例本來就比較像 **family / role 分組**，不是單一平面 tier。
- `Opening Range Breakout (ORB)` 又再加上 **ORB size** 與 **Gap Fill**。這兩者的語意和 trend confirmation 明顯不同：前者是 session-shape gate，後者是 prior-day context gate。
- `BORTORB` 也把 **volume、VWAP、bar-close quality、golden-hour time window** 並列。這再次說明：optional filters 雖然都可關閉，但本質上屬於不同家族，不適合粗暴塞進同一個 `secondary_refinement` 桶。

### 研究結論

- `tier/role` contract **不適合直接擴成單一通用 tier 規則**。
- 更合理的方向是：
  1. 保留 `VWAP slope` 目前的 `secondary_refinement`，因為它已經對外明確標示成次要條件；
  2. 若要繼續擴，下一個最合理的對象是 `EMA trend`，因為它和 `VWAP slope` 真正同層，都是 breakout 後的 trend/direction refinement；
  3. `OR size`、`OR volume baseline`、`gap fill`、`signal window` 這些應該視為不同 **role/family**，而不是同一個 tier。

### 對下一輪的含義

- 不建議下一輪直接幫所有 ORB optional keys 補一串 `*_tier=secondary_refinement`。
- 若要推 contract，應該先有明確規則：
  - 同層的 direction/trend refinement 才進 tier；
  - 其他不同語意的條件改走 role/family。

### 下一步

1. 下一輪若進入執行輪，最合理的單點修復仍是補 `strategy_spec_from_args(...)` 的窄範圍 contract test，先穩住目前 tier surface。
2. 若之後真的要擴 contract，優先考慮 `EMA trend`，不要先把 `OR size`、`OR volume baseline`、`gap fill` 也塞進 `secondary_refinement`。

## 2026-05-21 執行輪：補上 `strategy_spec_from_args(...)` 的窄範圍 tier contract test

這輪不改 ORB 策略語意，也不改 artifact schema；只做一個聚焦修補：把 `orb_vwap_slope_tier` 從 CLI 端到端測試，再往內收一層，直接鎖到 `strategy_spec_from_args(...)`。

### 修改內容

- `tests\test_cli.py`
  - 新增 `test_strategy_spec_from_args_locks_orb_vwap_slope_tier_contract(...)`
  - 直接建立：
    - disabled 路徑：`orb-volume-vwap`
    - enabled 路徑：`orb-volume-vwap --orb-vwap-slope-confirmation`
  - 再驗證兩條路徑的：
    - `orb_vwap_slope_confirmation`
    - `orb_vwap_slope_tier`
    - `orb_vwap_slope_rule`

### 這輪解決的風險

- 先前所有 `orb_vwap_slope_tier` 驗證都掛在 CLI artifact regression；若只是 `strategy_spec` metadata drift，failure localization 會偏外層。
- 補上這個窄範圍 test 後，未來若是 parser / strategy builder / spec assembler 的邊界出錯，會更容易直接定位到 `strategy_spec_from_args(...)` contract。

### 下一步

1. 下一輪若進入分析輪，可確認這個 unit-level contract test 是否已足夠降低 metadata drift 風險。
2. 若之後仍要擴 tier/role contract，優先考慮 `EMA trend` 是否要補對稱欄位，而不是先碰 `OR size` 或 `OR volume baseline`。

## 2026-05-21 分析輪：`strategy_spec_from_args(...)` 直測補上後，還需要再為 `VWAP slope tier` 重跑更多比較嗎

這輪不改策略，也不再新增 ORB filter 組合。目標只有一個：在上一輪補上 `strategy_spec_from_args(...)` 的 unit-level contract test 後，確認 `VWAP slope tier` 的 runtime regression risk 是否已經足夠下降，避免夜間自動化繼續在同一題上重複消耗回測輪次。

### 比較設定

- 資料檔：`C:\Projects\signal-forge\data\processed\ALPHAVANTAGE_MSFT_5M_demo.csv`
- 比較組合：
  1. `EMA inside-range`
  2. `EMA inside-range + VWAP slope`
- 本輪新產物：
  - `C:\Projects\signal-forge\reports\generated\msft-orb-vwap-slope-contract-coverage-sufficiency-20260521.md`
  - `C:\Projects\signal-forge\reports\generated\msft-orb-vwap-slope-contract-coverage-sufficiency-20260521.json`

### 結果摘要

- `EMA inside-range`
  - PF `4.452`
  - Trades `13`
  - Win rate `38.46%`
  - Avg net PnL `16.27`
  - Max DD `-0.29%`
  - blocked `1754`
  - hold `873`
  - `orb_vwap_slope_confirmation=disabled`
  - `orb_vwap_slope_tier=secondary_refinement`
- `EMA inside-range + VWAP slope`
  - PF `4.546`
  - Trades `13`
  - Win rate `38.46%`
  - Avg net PnL `16.37`
  - Max DD `-0.29%`
  - blocked `1762`
  - hold `865`
  - `orb_vwap_slope_confirmation=enabled`
  - `orb_vwap_slope_tier=secondary_refinement`

### 保護層判讀

目前 `VWAP slope tier` 已有三層保護：

1. CLI artifact regression 已鎖住 disabled / enabled 兩條路徑。
2. 先前分析已確認補 regression 前後，runtime artifact 與 PF / trades / blocked / hold 都沒有改變。
3. 最新單元測試已直接鎖 `strategy_spec_from_args(...)` 的 disabled/enabled state、tier 與 rule。

### 分析結論

- 目前 `orb_vwap_slope_tier` 的 runtime regression risk 已經明顯下降。
- 在沒有新策略語意變更之前，**沒有必要再為 `VWAP slope tier` 單獨重跑更多同型態的 ORB 比較**。
- 後續更值得投入的方向是：
  1. `EMA trend` 是否需要對稱 contract；
  2. disabled 狀態下的 `orb_vwap_slope_rule` 文案是否要改得更中性。

### 下一步

1. 下一輪若進入 review，可判斷 `EMA trend` 對稱 contract 與 disabled rule wording，哪一個債更值得優先處理。
2. 若下一輪進入研究輪，應該把 focus 從 `VWAP slope tier` 移開，改成 `EMA trend` / role-family 邊界。

## 2026-05-21 Code Review：下一個單點修復應優先處理 disabled rule wording，而不是先擴 `EMA trend` 對稱 contract

這輪是 review-only，不改 ORB 策略語意。目標是把最近幾輪收斂出來的兩個小債排出先後順序：

1. disabled 狀態下的 `orb_vwap_slope_rule` 文案仍寫成 `when enabled, ...`
2. `EMA trend` 是否要補成和 `VWAP slope` 對稱的 tier / role contract

### Finding 1：disabled rule wording 是目前 artifact 的直接可讀性問題

- 嚴重度：中
- 受影響檔案：`src\signal_forge\cli\strategy_options.py`
- 現況：即使 `orb_vwap_slope_confirmation=disabled`，artifact 仍固定輸出 `orb_vwap_slope_rule: when enabled, this secondary refinement ...`
- 風險：機器層面沒有歧義，但人類讀 phase / entry-edge artifact 時，容易把它誤解成「規則仍在生效，只是前面補了一句 when enabled」。
- 建議修法：下一個執行輪優先把 `rule` 文案改成較中性的靜態描述，或把規則描述與 state/effective 狀態拆開。

### Finding 2：`EMA trend` 對稱 contract 是更廣的 schema 決策，不適合先於 wording cleanup

- 嚴重度：中
- 受影響檔案：`src\signal_forge\cli\strategy_options.py`、`tests\test_cli.py`
- 現況：研究上已經確認 `EMA trend` 最接近 `VWAP slope` 的同層 refinement，但是否要補 `*_tier` / `*_role` 不只是文案修正，而是 schema 擴張。
- 風險：若現在直接補 `EMA trend` 對稱 contract，會把目前的單點可讀性修補推進成更廣的 surface 設計，容易在還沒定清楚 role/family 規則前又增加平面欄位。
- 建議修法：把這件事留到後續研究或單點設計決策，確認是否真的要從 `VWAP slope` 擴成一個更通用的 role/tier contract。

### 排序結論

- **下一個單點修復應優先處理 disabled rule wording。**
- 理由：
  1. 它是當前 artifact 的直接閱讀問題，今天就會影響人。
  2. 修法局部、風險低，符合夜間 automation 的單點修復邊界。
  3. `EMA trend` 對稱 contract 則是更廣的 schema 問題，應在 wording cleanup 之後再決定要不要做。

### 下一步

1. 下一輪若進入執行輪，優先把 disabled 狀態下的 `orb_vwap_slope_rule` 改成較中性的靜態描述。
2. wording cleanup 完成後，再回頭評估 `EMA trend` 是否值得補對稱 contract，並決定那時要走單一 tier 還是 role/family。

## 2026-05-21 研究輪：`disabled rule wording` 應改成靜態規則描述，而不是延續 `when enabled, ...`

這輪不改程式，只研究 `orb_vwap_slope_rule` 這類 artifact wording 應該往哪種 contract 收斂。結論是：**應優先改成靜態規則描述，並把 enabled / disabled 狀態交給既有 state 欄位表達；不建議繼續維持 `when enabled, ...` 這種混合文案。**

### 來源

- TradingView Pine Script docs：Inputs
  https://www.tradingview.com/pine-script-docs/concepts/inputs/
- TradingView `Opening Range Breakout + VWAP + Volume [ORB Strategy]`
  https://www.tradingview.com/script/hapKLoXr-Opening-Range-Breakout-VWAP-Volume-ORB-Strategy/
- TradingView `Opening Range Breakout`
  https://www.tradingview.com/script/tZtCD3TM-Opening-Range-Breakout/
- TradingView `NeuraEdge ORB - Opening Range Breakout Indicator`
  https://www.tradingview.com/script/Sb0YgLYU-NeuraEdge-ORB-Opening-Range-Breakout-Indicator/

### 外部研究重點

- TradingView 的 `input.*()` 設計把 **設定值本身** 與 **輸入標題/群組** 分開；filter toggle 是獨立 state，不需要把 enabled/disabled 語意混進規則文字裡。
- `Opening Range Breakout + VWAP + Volume [ORB Strategy]` 直接把 `VWAP filter`、`Volume confirmation`、`timezone`、`trade window` 分開列成 inputs / features，說明「是否啟用」與「規則本身」在外部實務上本來就分離。
- `Opening Range Breakout` 與 `NeuraEdge ORB` 也都直接描述 filter 規則本體，例如 EMA 趨勢要上升、價格要站在 EMA / VWAP 正確一側；它們不會把 disabled 狀態寫進規則定義句。

### 對目前 repo 的含義

- 現在 `strategy_spec` 已經有：
  - `orb_vwap_slope_confirmation = enabled|disabled`
  - `orb_vwap_slope_tier = secondary_refinement`
  - `orb_vwap_slope_rule = when enabled, ...`
- 問題不是資訊不夠，而是 `rule` 欄位同時混了：
  1. 規則本體
  2. 啟用條件
- 這讓 disabled 路徑的人類可讀性變差，因為 artifact 會同時說「disabled」又說「when enabled」，語意上是重複而且容易誤讀。

### 研究結論

- 下一個執行輪若做 wording cleanup，較合理的方向是：
  - 保留 `orb_vwap_slope_confirmation = enabled|disabled`
  - 將 `orb_vwap_slope_rule` 改成**靜態規則描述**
    - 例如：`breakout is only valid when session VWAP is rising versus the previous bar in the same session`
- 這樣可把：
  - state：交給 `*_confirmation`
  - rule：交給 `*_rule`
- 不需要先新增新的 `effective` 欄位，因為目前 state contract 已足夠。

### 下一步

1. 下一輪若進入執行輪，優先把 `orb_vwap_slope_rule` 改成中性靜態描述，先不要擴 schema。
2. wording cleanup 完成後，再決定 `orb_ema_trend_rule` 是否要用同樣模式對齊。

## 2026-05-21 執行輪：將 `orb_vwap_slope_rule` 改成中性靜態描述

這輪不改 ORB 策略語意，也不擴 artifact schema；只做一個聚焦修補：把 `orb_vwap_slope_rule` 從 `when enabled, ...` 改成靜態規則描述，讓 rule 與 state 分工更清楚。

### 修改內容

- `src\signal_forge\cli\strategy_options.py`
  - `orb_vwap_slope_rule` 由：
    - `when enabled, this secondary refinement only accepts breakouts if session VWAP is rising versus the previous bar in the same session`
  - 改為：
    - `this secondary refinement only accepts breakouts if session VWAP is rising versus the previous bar in the same session`
- `tests\test_cli.py`
  - 同步更新 `strategy_spec_from_args(...)` 與 CLI artifact regression 的 4 個 exact-text assertion。

### 這輪解決的風險

- 先前 disabled 路徑會同時出現：
  - `orb_vwap_slope_confirmation=disabled`
  - `orb_vwap_slope_rule=when enabled, ...`
- 這在機器層面沒有問題，但在人類閱讀 phase / entry-edge artifact 時，容易誤讀成規則仍在生效。
- 現在 state 與 rule 已明確分工：
  - state：`orb_vwap_slope_confirmation`
  - rule：`orb_vwap_slope_rule`

### 下一步

1. 下一輪若進入分析輪，可確認 wording cleanup 後，artifact 的 disabled/enabled 可讀性是否已足夠，不需要再擴新欄位。
2. 若之後仍要對齊其他 rule wording，優先看 `orb_ema_trend_rule` 是否也值得改成同樣的靜態描述風格。

## 2026-05-21 分析輪：`orb_vwap_slope_rule` wording cleanup 改善可讀性，但不改變 ORB runtime artifact

這輪不新增策略條件，也不改 backtest schema；只驗證上一輪把 `orb_vwap_slope_rule` 從 `when enabled, ...` 改成靜態規則描述之後，是否真的只影響人類可讀性，而不改變 ORB runtime 行為。

### 比較設定

- 資料來源：`data\processed\ALPHAVANTAGE_MSFT_5M_demo.csv`
- 比較組合：
  1. `EMA inside-range`
  2. `EMA inside-range + VWAP slope`
- 本輪新產生的 entry-edge artifact：
  - `reports/generated/msft-orb-wordingcheck-20260521-ema-box.{md,json}`
  - `reports/generated/msft-orb-wordingcheck-20260521-ema-box-vslope.{md,json}`
- 參照既有 attribution 比較：
  - `reports/generated/msft-orb-vslope-on-ema-box-20260521.json`

### 結果

- wording cleanup 後，兩條路徑的 `orb_vwap_slope_rule` 都已改成同一個**靜態規則描述**：
  - `this secondary refinement only accepts breakouts if session VWAP is rising versus the previous bar in the same session`
- `enabled / disabled` 狀態仍由 `orb_vwap_slope_confirmation` 單獨表達：
  - `EMA inside-range`：`disabled`
  - `EMA inside-range + VWAP slope`：`enabled`
- runtime metrics 與 cleanup 前維持一致：
  - `EMA inside-range`
    - PF `4.452`
    - Trades `13`
    - Win rate `38.46%`
    - Avg net PnL `16.27`
    - Max DD `-0.29%`
    - blocked `1754`
    - hold `873`
  - `EMA inside-range + VWAP slope`
    - PF `4.546`
    - Trades `13`
    - Win rate `38.46%`
    - Avg net PnL `16.37`
    - Max DD `-0.29%`
    - blocked `1762`
    - hold `865`
- 因此這次 wording cleanup 的效果是：
  1. **artifact 更容易閱讀**
  2. **runtime 行為不變**
  3. **不需要為這個欄位再擴 schema**

### 解讀

- 先前 disabled 路徑會同時出現：
  - `orb_vwap_slope_confirmation=disabled`
  - `orb_vwap_slope_rule=when enabled, ...`
- 這在機器層面沒有錯，但在人讀 artifact 時容易把 state 與 rule 混在一起。
- 現在 cleanup 後，欄位責任更清楚：
  - state：`orb_vwap_slope_confirmation`
  - tier：`orb_vwap_slope_tier`
  - rule：`orb_vwap_slope_rule`
- 由於 PF、trades、blocked、hold 都和 cleanup 前一致，代表這次變更是**純 contract readability 修補**，不是策略行為調整。

### 下一步

1. `VWAP slope` 這條線目前已經有：
   - CLI artifact regression
   - disabled/default regression
   - `strategy_spec_from_args(...)` 窄範圍 contract test
   - wording cleanup 後的 runtime 不變驗證
2. 在沒有新策略語意變更前，不需要再為 `VWAP slope rule` 單獨重跑更多同型分析。
3. 若後續還要擴 `tier/role` contract，優先看 `EMA trend` 是否值得補對稱表達；若沒有，就把分析輪配額留給新的策略或新的 filter family。

## 2026-05-21 Code Review：`VWAP slope wording` 收斂後，ORB surface 剩下的主要債是對稱性與 exact-text 維護成本

這輪是 review-only，不改 ORB 策略語意。目標是確認上一輪 wording cleanup 完成後，還有哪些殘餘技術債值得排進後續單點修復。

### Finding 1：`VWAP slope` 已有 tier，但 `EMA trend` 仍是同層卻沒有對稱表達

- 嚴重度：中
- 受影響檔案：
  - `src\signal_forge\cli\strategy_options.py`
  - `tests\test_cli.py`
- 現況：
  - `orb_vwap_slope_confirmation`
  - `orb_vwap_slope_tier=secondary_refinement`
  - `orb_vwap_slope_rule`
  已形成完整的 state/tier/rule contract。
  但 `orb_ema_trend_confirmation` 仍只有 state + rule，沒有任何層級語意。
- 風險：
  - 研究上已確認 `EMA trend` 與 `VWAP slope` 屬同層 direction/trend refinement。
  - 現在 artifact 只替 `VWAP slope` 補 tier，會讓 surface 傳遞出「兩者層級不同」的假象。
- 建議修法：
  - 若之後決定保留 tier/role contract，下一個最合理的對象應是 `EMA trend`。
  - 若不打算擴，則應明確承認 `VWAP slope` 目前只是單點特例，不再繼續平面欄位擴張。

### Finding 2：phase markdown 仍看不到 `tier/role`，entry-edge 與 phase 的可讀 surface 不對稱

- 嚴重度：中
- 受影響檔案：
  - `src\signal_forge\reporting\_legacy.py`
- 現況：
  - entry-edge markdown 會完整列出 `strategy_spec`，因此可以看到 `orb_vwap_slope_tier=secondary_refinement`。
  - phase markdown 主體則沒有對應的人類可讀層級摘要。
- 風險：
  - 若後續使用者主要從 phase report 回看 ORB 結果，會不知道哪些 filter 是核心條件、哪些只是次要 refinement。
  - 這不是 runtime bug，而是 reporting surface 不對稱。
- 建議修法：
  - 若未來繼續保留 `tier/role` contract，應決定 phase markdown 是否也要顯示最小必要的層級摘要。

### Finding 3：`strategy_options.py` 的 ORB `strategy_spec` 仍然是平面 key 持續堆疊

- 嚴重度：中
- 受影響檔案：
  - `src\signal_forge\cli\strategy_options.py`
- 現況：
  - ORB 相關欄位已包含 session、timezone、range gate、body strength、fresh breakout、OR volume baseline、EMA/VWAP refinement、tier 等大量平面 key。
- 風險：
  - 每次補一個欄位都需要同步更新 CLI regression、文字 contract、策略筆記與分析報表。
  - schema 雖然還可控，但維護成本已經明顯高於早期 ORB 最小版本。
- 建議修法：
  - 短期內不要再為每個小 filter 任意補新平面欄位。
  - 若未來要繼續擴，應先決定 role/family 是否值得抽象成較穩定的 grouping contract。

### Finding 4：`tests\test_cli.py` 的 exact-text coverage 有價值，但 wording 類修補的維護成本偏高

- 嚴重度：低
- 受影響檔案：
  - `tests\test_cli.py`
- 現況：
  - 這次只是把 `orb_vwap_slope_rule` 從 `when enabled, ...` 改成靜態描述，就需要同步改多個 exact-text assertion。
- 風險：
  - wording 類修補雖然能被完整鎖住，但每次小調整都會帶來較高的 golden text 維護成本。
  - 若未來 `EMA trend`、`role/family` 也跟進，這個成本會繼續往上疊。
- 建議修法：
  - 保留 exact-text test 作為 artifact contract 防線，但對純 metadata wording 的擴張要更保守。
  - 優先把分析輪配額用在真正有新資訊增量的 filter family，而不是繼續放大 wording surface。

### Review 結論

- 目前沒有發現新的 runtime regression 或 deterministic artifact 漂移。
- 這批 ORB surface 的主要剩餘債已從「正確性」轉成「對稱性與維護成本」：
  1. `EMA trend` 是否要補對稱 contract；
  2. phase / entry-edge 的 tier 可讀性是否要對齊；
  3. 平面 `strategy_spec` 是否還要繼續擴張；
  4. exact-text wording 測試的維護成本是否值得。

### 下一步

1. 若下一輪進入研究輪，優先決定 `EMA trend` 是否真的值得補對稱 contract。
2. 若下一輪進入執行輪，不建議先動 schema；較合理的是做更小的 reporting readability 修補，或直接把執行輪配額讓給新的 filter family 分析題。

## 2026-05-21 研究輪：`EMA trend` 暫時不應直接補成和 `VWAP slope` 相同的 `secondary_refinement` contract

這輪不改程式，只回答一個 schema 問題：既然 `VWAP slope` 已經有 `orb_vwap_slope_tier=secondary_refinement`，`EMA trend` 是否也應直接補上一個對稱的 tier 欄位。

### 來源

- TradingView `Opening Range Breakout`
  https://www.tradingview.com/script/tZtCD3TM-Opening-Range-Breakout/
- TradingView `ORB with 100 EMA`
  https://www.tradingview.com/script/JHm0ftM9-ORB-with-100-EMA/
- TradingView `Opening Range Breakout (ORB)`
  https://www.tradingview.com/script/AMsB94Rs-Opening-Range-Breakout-ORB/
- TradingView `Opening Range Breakout + VWAP + Volume [ORB Strategy]`
  https://www.tradingview.com/script/hapKLoXr-Opening-Range-Breakout-VWAP-Volume-ORB-Strategy/
- TradingView Pine Script docs：Inputs
  https://www.tradingview.com/pine-script-docs/concepts/inputs/

### 外部研究重點

- `Opening Range Breakout` 直接把 EMA 趨勢方向、價格是否站上 EMA、以及 **EMA 是否位於 OR high 之上** 當成 breakout 成立條件。這代表在不少 ORB 腳本裡，EMA trend 並不是次要微調，而是接近主方向確認。
- `ORB with 100 EMA` 更進一步把「100EMA 落在 opening range 盒子內時不給訊號」列為核心限制，顯示 EMA 家族條件常常同時承擔：
  - direction confirmation
  - structure gate
- 相較之下，`Opening Range Breakout (ORB)` 與 `Opening Range Breakout + VWAP + Volume [ORB Strategy]` 雖然也會提供 VWAP slope / VWAP alignment / volume 等可選 filter，但它們更像是 breakout 成立後再做的順風確認或品質微調。
- 官方 Inputs 文件則支持另一個工程結論：toggle state、規則描述、群組顯示應分離，但**沒有要求所有 optional filter 都必須共享同一個 tier 欄位**。

### 研究結論

- `EMA trend` 與 `VWAP slope` 在「都屬趨勢方向 refinement」這件事上確實接近，但它們在外部腳本中的地位並不完全對等。
- 對目前 SignalForge 較合理的判斷是：
  1. `VWAP slope` 繼續保留 `secondary_refinement` 沒問題；
  2. `EMA trend` **暫時不應直接補成同一個 `secondary_refinement` contract**；
  3. 若未來要讓 `EMA trend` 也有顯式角色，應走更完整的 `role/family` 設計，例如把它歸到 `trend_confirmation`，而不是先用平面 tier 硬對齊。

### 理由

- 若現在直接新增例如 `orb_ema_trend_tier=secondary_refinement`，會把一個原本可能更接近主方向確認的條件，硬壓成和 `VWAP slope` 同級的小 filter。
- 這不只會誤導 artifact 解讀，也會讓 `strategy_spec` 的平面欄位繼續膨脹。
- 因此目前比較好的工程邊界是：
  - 承認 `VWAP slope` 是已落地的單點特例；
  - 暫時不要為了表面對稱而擴 `EMA trend` 欄位；
  - 等未來真的要把多個 ORB filter 做角色分層，再一起設計 `role/family`。

### 下一步

1. 下一輪若進入執行輪，不建議直接補 `orb_ema_trend_tier`。
2. 若要先消化一個小債，較合理的是做 reporting readability 修補，而不是再擴 schema。
3. 若未來要重啟這題，應先定義：
   - 哪些屬 `trend_confirmation`
   - 哪些屬 `structure_gate`
   - 哪些屬 `baseline_choice`
   再決定是否需要正式的 `role/family` contract。

## 2026-05-21 執行輪：Phase markdown 補明 ORB attribution 只是一層 compact summary

這輪不改 ORB 策略語意，也不擴 artifact schema；只做一個 reporting readability 修補：當 phase markdown 顯示 `## ORB Filter Attribution` 時，額外補一行解讀，明確說明這個區塊只負責 **accepted / blocked / hold** 的 compact summary，而 `state / tier / rule` 仍以 entry-edge 的 `strategy_spec` 為主。

### 修改內容

- `src\signal_forge\reporting\_legacy.py`
  - 抽出 `_build_phase_orb_filter_attribution_lines(...)`
  - 在 phase markdown 的 ORB attribution 區塊新增：
    - `Interpretation: this phase report keeps ORB attribution as a compact blocked/accepted summary; state, tier, and rule metadata remain in entry-edge strategy_spec artifacts.`
- `tests\test_reporting.py`
  - 補對應 assertion，鎖住 phase markdown 這行可讀性 contract。

### 為什麼做這個修補

- 先前 review 已指出：entry-edge artifact 看得到完整 `strategy_spec`，phase markdown 則只有 attribution counts。
- 若不明講，使用者容易把 phase report 誤讀成「已包含完整 ORB filter metadata」，進而期待在 phase markdown 直接看到 `tier / rule / enabled-disabled state`。
- 這次改動只補說明，不擴 schema，也不讓 phase report 去複製 entry-edge 的完整 metadata surface。

### 驗證

- `python tools\phase_readiness_score.py` -> `110`
- `python -m unittest discover -s tests` -> `130 tests OK`
- `git diff --check` -> clean

### 決策

- keep
- 這次改動把 phase / entry-edge 的 reporting 邊界講清楚，但不把 ORB surface 進一步扁平化到 phase markdown。

### 下一步

1. 若後續還要補 ORB reporting readability，優先考慮更小的 phase 解讀提示，而不是再擴平面 schema。
2. `EMA trend` 是否需要對稱 contract，仍留在研究題，不在這輪一併處理。

## 2026-05-21 分析輪：`EMA trend` 與 `EMA inside-range` 同屬 EMA family，但資訊價值明顯不同

這輪把分析配額從 `VWAP slope wording` 移開，直接用同一份 `MSFT 5m demo` 比較三組 ORB 變體：

1. `EMA trend only`
2. `EMA inside-range only`
3. `EMA trend + EMA inside-range`

目標不是再爭論 wording，而是回答一個更實際的問題：**`EMA trend` 是否真的值得被視為和 `EMA inside-range` 同層、甚至進一步擴成對稱 contract。**

### 比較設定

- 資料來源：`data\processed\ALPHAVANTAGE_MSFT_5M_demo.csv`
- 新產物：
  - `reports\generated\msft-orb-ema-family-comparison-20260521.md`
  - `reports\generated\msft-orb-ema-family-comparison-20260521.json`

### 結果摘要

- `EMA trend only`
  - Decision：`FAIL`
  - PF：`0.264`
  - Trades：`14`
  - Win rate：`50.00%`
  - Avg net PnL：`-26.20`
  - Max DD：`-4.626%`
  - blocked：`1483`
  - accepted：`14`
  - hold：`1143`
  - 主要 blocked reasons：
    - `below_or_high(1403)`
    - `breakout_volume_blocked(73)`
    - `breakout_below_ema(7)`

- `EMA inside-range only`
  - Decision：`PASS`
  - PF：`4.452`
  - Trades：`13`
  - Win rate：`38.46%`
  - Avg net PnL：`16.27`
  - Max DD：`-0.290%`
  - blocked：`1754`
  - accepted：`13`
  - hold：`873`
  - 主要 blocked reasons：
    - `below_or_high(1480)`
    - `breakout_volume_blocked(148)`
    - `ema_inside_opening_range(126)`

- `EMA trend + EMA inside-range`
  - Decision：`PASS`
  - PF：`1.494`
  - Trades：`13`
  - Win rate：`15.38%`
  - Avg net PnL：`6.08`
  - Max DD：`-1.165%`
  - blocked：`1626`
  - accepted：`13`
  - hold：`1001`
  - 主要 blocked reasons：
    - `below_or_high(1480)`
    - `ema_inside_opening_range(69)`
    - `breakout_volume_blocked(62)`
    - `breakout_below_ema(15)`

### 分析結論

- `EMA inside-range` 仍是這份樣本上最強的 ORB 結構 gate。
- `EMA trend` 單獨使用時不只沒有帶來主線價值，反而仍是明確 `FAIL`。
- 更重要的是，把 `EMA trend` 疊到 `EMA inside-range` 上後，**PF 從 `4.452` 掉到 `1.494`**，最大回撤也從 `-0.290%` 變成 `-1.165%`；這代表它在這份資料上不是單純的弱增量，而是會破壞 `EMA inside-range` 已經篩出的強突破集合。
- 因此目前較合理的工程判斷是：
  1. 不要為了表面對稱而擴 `EMA trend` contract。
  2. `EMA inside-range` 繼續保留為 ORB 的高優先級結構 gate。
  3. 後續若還要投入分析輪，應轉向新的 filter family 或更廣樣本，而不是繼續在 `EMA trend` 的 contract 對稱性上消耗配額。

### 下一步

1. `EMA trend` 暫時不應補成和 `VWAP slope` 對稱的 tier/role surface。
2. 若要再做 ORB 比較，優先考慮新的 filter family 或第二份 intraday 樣本，而不是繼續疊加 `EMA trend`。

## 2026-05-21 Code Review：`EMA trend` 現階段更適合降級為 compare-only filter，而不是繼續佔用 ORB contract 配額

這輪是 review-only，不改 ORB 策略語意。重點是把上一輪 `EMA family` 比較結果轉成工程上的收斂結論，避免後續又回頭擴 `EMA trend` 的 artifact / schema surface。

### Finding 1：`EMA trend` 已經有足夠證據證明它目前不值得補對稱 contract

- 嚴重度：中
- 受影響檔案：
  - `src\signal_forge\cli\strategy_options.py`
  - `tests\test_cli.py`
- 證據：
  - `EMA trend only`：PF `0.264`，`FAIL`
  - `EMA inside-range only`：PF `4.452`，`PASS`
  - `EMA trend + EMA inside-range`：PF `1.494`，仍比 `EMA inside-range only` 差很多
- 判讀：
  - 這已經不是「還缺一點證據」的狀態，而是足以支持目前**不要再擴 `orb_ema_trend_*` surface**。
- 建議：
  - 先把 `EMA trend` 視為 compare-only filter。
  - 若未來沒有第二份或更多 intraday 樣本推翻這個結論，不應再投入執行輪去補 tier/role 對稱欄位。

### Finding 2：`strategy_name` 仍會把 `ema10` 編進變體名稱，但這不等於它值得升級成主線 contract

- 嚴重度：低
- 受影響檔案：
  - `src\signal_forge\strategies\orb_volume_vwap.py`
  - `src\signal_forge\cli\strategy_options.py`
- 現況：
  - ORB 變體名稱會在啟用 `EMA trend` 時直接帶出 `ema10`。
- 風險：
  - 人類讀 artifact 時，容易把「名稱上存在」誤解成「方法論上與 `EMA inside-range` 同等重要」。
- 建議：
  - 短期內先不改 naming，避免再擴 schema 或命名契約。
  - 但後續文件與 review 應持續明講：名稱帶出 `ema10` 只是變體識別，不代表它已升級成主線結構條件。

### Finding 3：當前分析輪配額應從 `EMA trend` 移開，轉向新 family 或更廣樣本

- 嚴重度：中
- 受影響檔案：
  - `docs\04-實驗記錄\Autoresearch 實驗記錄.md`
  - `docs\策略筆記\ORB + Volume + VWAP.md`
- 現況：
  - `VWAP slope`、`EMA trend`、`EMA inside-range` 的相對排序已在同一份 `MSFT 5m demo` 上被反覆交叉檢查。
- 風險：
  - 若繼續把分析輪花在同一個 family，只會增加文案與報表密度，不會帶來新的決策資訊。
- 建議：
  - 下一個分析輪若還做 ORB，比較值得投入的是：
    1. 新的 filter family；
    2. 第二份 intraday 樣本；
    3. 不同 market-clock / session 邊界對 ORB 的影響。

### Review 結論

- 目前 `EMA trend` 的最合理定位是：**保留實作、保留 compare 能力，但降級為 compare-only filter**。
- 這不代表要刪掉它，而是代表：
  1. 不再優先擴它的 contract；
  2. 不再優先花分析輪反覆驗證同一題；
  3. 把後續 schema 與測試維護成本留給更有新增資訊的題目。

### 下一步

1. 若下一輪進入研究輪，優先挑新的 ORB filter family 或第二份 intraday 樣本，不要再圍繞 `EMA trend` 做 contract 討論。
2. 若下一輪進入執行輪，也不建議先動 `EMA trend` surface；較合理的是讓執行輪配額回到 reporting / validator 或其他更有新增資訊的 artifact 題目。

## 2026-05-21 研究輪：`前日高低點 / gap context` 是合理的新 family，但現階段不應直接進入 ORB 執行輪

這輪不改程式，只回答一個研究排序問題：在 `EMA trend` 已降級為 compare-only filter 之後，下一個值得研究的 ORB family 是什麼。結論是：**`前日高低點 / gap context` 是合理的新 family，但它比目前 ORB 主線更依賴 previous-day / higher-timeframe 資料邊界，因此現階段應先列為研究主題，不直接進入執行輪。**

### 來源

- TradingView `GeeksDoByte 15m & 30m ORB + Prev Day High/Low`
  https://www.tradingview.com/script/U8dn81NE-GeeksDoByte-15m-30m-ORB-Prev-Day-High-Low/
- TradingView `Opening Range & Prior Day High/Low [Gorb]`
  https://www.tradingview.com/script/xNKGE5KR-Opening-Range-Prior-Day-High-Low-Gorb/
- TradingView `ORB Gap Strategy`
  https://www.tradingview.com/script/qbOn74Yb-ORB-Gap-Strategy/
- TradingView Pine Script docs：`Repainting`
  https://www.tradingview.com/pine-script-docs/concepts/repainting/
- TradingView Pine Script docs：`Other timeframes and data`
  https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/

### 外部研究重點

- 多個公開 ORB 腳本會把 `previous day high / low` 視為和 OR high / low 並列的重要日內結構位階，用來觀察 breakout 是否剛好撞上前日阻力，或是否完成更高級別的突破。
- `ORB Gap Strategy` 也把 gap context 拉進 ORB，做法不是單看當日 opening range，而是把 overnight / 開盤缺口一起當成突破強度的背景條件。
- 但這一類腳本幾乎都依賴 **前一日資料** 或 **higher-timeframe request**。TradingView 官方文件明確提醒：`request.security()` 與 higher-timeframe 資料如果處理不當，會有 historical / realtime 不一致與 repainting 風險。

### 對 SignalForge 的含義

- 這個 family 有研究價值，因為它不是單純再堆一個 intraday 小 filter，而是把 ORB 放回更完整的日內結構脈絡。
- 但它和目前 SignalForge ORB 主線的差別在於：
  1. 需要明確定義 `previous day` 是 regular session 還是 full session；
  2. 需要決定前日高低點、前收、gap 是不是都屬同一個 family；
  3. 需要把 higher-timeframe / previous-day 資料邊界寫進 artifact 與 validator，而不是只在策略內部多加幾個欄位。
- 換句話說，這不是一個適合夜間 automation 直接做成小型執行輪的題目；它比較像下一個獨立研究 family。

### 研究結論

- `前日高低點 / gap context` 值得納入下一階段 ORB 研究候選。
- 但現在更合理的做法是：
  1. 先把它記成 **new filter family / structural context topic**；
  2. 等有第二份 intraday 樣本或更完整的 previous-day 資料假設時，再決定是否值得落地成可選策略條件；
  3. 在那之前，不要把它和 `VWAP slope`、`EMA trend`、`body strength` 這類同日內部 refinement 混成同一類欄位。

### 下一步

1. 下一個 ORB 研究題若要有新增資訊，優先考慮 `previous day high/low`、`gap direction/fill`、`overnight range` 這類新 family，而不是回頭擴 `EMA trend` contract。
2. 若未來真的要實作，應先補：
   - previous-day 邊界定義；
   - artifact / validator 對 higher-timeframe context 的說明；
   - 至少第二份 intraday 樣本。

## 2026-05-21 執行輪：phase markdown 明講前日 / higher-timeframe context 目前不在 ORB contract 內

這輪不改 ORB 策略語意，也不擴 artifact schema；只做一個 reporting readability 修補：在 phase markdown 的 `ORB Filter Attribution` 區塊，把先前研究出的邊界直接寫成人類可讀解讀，避免使用者把目前 ORB 主線和 `previous day high/low`、gap、overnight range 這類新 family 混讀。

### 修改內容

- `src\signal_forge\reporting\_legacy.py`
  - 更新 `_build_phase_orb_filter_attribution_lines(...)` 的 interpretation 行：
    - 保留原本「這裡只是 compact blocked/accepted summary」
    - 額外明講：`previous-day / higher-timeframe context is outside the current ORB contract until that family is defined explicitly`
- `tests\test_reporting.py`
  - 同步更新 exact-text assertion，鎖住 phase markdown 這行新的 contract。

### 為什麼做這個修補

- 上一輪研究已收斂：`前日高低點 / gap context` 是合理的新 family，但目前不該直接混進 ORB 主線。
- 若 phase markdown 不把這個邊界說清楚，後續回看報表時，容易誤以為 phase report 已經隱含 previous-day / higher-timeframe 結構判斷。
- 這輪只補說明，不新增任何 strategy spec 欄位，也不把 phase markdown 擴成第二套完整 schema。

### 驗證

- `python tools\phase_readiness_score.py` -> `110`
- `python -m unittest discover -s tests` -> `131 tests OK`
- `git diff --check` -> clean

### 決策

- keep
- 這次改動把 ORB 目前 contract 和下一個研究 family 的邊界寫進人類可讀報表，但不提前把 previous-day family 變成正式策略欄位。

### 下一步

1. 下一輪若進入分析輪，不需要再為這個 wording 單獨重跑 runtime 比較；較合理的是把分析配額用在新的 filter family 或第二份 intraday 樣本。
2. 若未來真的要落地 previous-day family，應先補資料邊界與 validator，再決定是否新增 artifact 欄位。

## 2026-05-21 分析輪：phase markdown 加入 previous-day 邊界提示後，只影響可讀性，不改變 ORB runtime 指標

這輪不新增策略條件，也不再開新一組 ORB filter 比較。目標只有一個：確認上一輪在 phase markdown 補進 `previous-day / higher-timeframe context is outside the current ORB contract` 之後，是否真的只改變報表解讀，不改變 runtime 行為。

### 比較設定

- 資料來源：`data\processed\ALPHAVANTAGE_MSFT_5M_demo.csv`
- 比較對象：`EMA inside-range only`
- 新執行輸出：以暫存目錄重跑
  - `phase`
  - `entry-edge`
- 參照基線：
  - `reports/generated/msft-orb-ema-family-20260521-ema-box-phase.md`
  - `reports/generated/msft-orb-ema-family-comparison-20260521.json`

### 結果

- phase markdown interpretation 行已從：
  - `state, tier, and rule metadata remain in entry-edge strategy_spec artifacts.`
- 更新為：
  - `state, tier, and rule metadata remain in entry-edge strategy_spec artifacts, and previous-day / higher-timeframe context is outside the current ORB contract until that family is defined explicitly.`
- 但 `EMA inside-range only` 的核心指標維持不變：
  - PF：`4.452`
  - Trades：`13`
  - Win rate：`38.46%`
  - Avg net PnL：`16.27`
  - Max DD：`-0.29%`
  - blocked：`1754`
  - accepted：`13`
  - hold：`873`
  - blocked reasons：`below_or_high(1480), breakout_volume_blocked(148), ema_inside_opening_range(126)`

### 分析結論

- 這次 phase markdown 的 previous-day 邊界提示，和先前的 `orb_vwap_slope_rule` wording cleanup 一樣，屬於 **reporting readability 修補**，不是策略或 artifact schema 變更。
- 它的價值在於：後續回看 phase report 時，不會再把目前 ORB 主線和 `previous day high/low`、gap、overnight range 這類新 family 混讀。
- 因為 runtime 指標完全不變，後續不需要再為這個 wording 題重複消耗分析輪次。

### 下一步

1. 分析輪配額應轉回新的 filter family、第二份 intraday 樣本，或 previous-day family 真正落地前需要的資料邊界題。
2. 若未來再碰 previous-day family，應優先驗證資料與 validator contract，而不是先擴 phase markdown 或 strategy spec 欄位。

## 2026-05-21 Code Review：previous-day family 若要落地，現在還缺資料邊界與 contract 層

這輪是 review-only，不改 ORB 策略語意。重點是把前幾輪已收斂出的 previous-day / higher-timeframe family 風險，轉成明確的工程待辦，避免之後直接在 ORB 主線上零散加欄位。

### Finding 1：previous-day family 目前只存在於研究筆記與 phase prose，還不是 validator / schema contract

- 嚴重度：中
- 受影響檔案：
  - `src\signal_forge\reporting\_legacy.py`
  - `src\signal_forge\cli\strategy_options.py`
- 現況：
  - phase markdown 已明講 previous-day / higher-timeframe context 不在目前 ORB contract 內。
  - 但這個邊界目前仍主要靠人類可讀文字維持，還沒有對應 validator 或正式 schema。
- 風險：
  - 若後續有人直接把 `previous day high/low`、gap 或 overnight range 接進策略內部，artifact reader 可能誤以為既有 `strategy_spec` 已足以描述資料邊界。
- 建議：
  - 在任何 previous-day family 真正落地前，先定義明確 contract：
    1. `previous day` 是 regular session 還是 full session；
    2. gap 與前收是否屬同一個 family；
    3. 需要哪些欄位才能讓 validator 判斷資料邊界一致。

### Finding 2：phase / entry-edge 的 ORB metadata 仍刻意不對稱，若引入 previous-day family 必須先決定是否維持這個設計

- 嚴重度：中
- 受影響檔案：
  - `src\signal_forge\reporting\_legacy.py`
  - `tests\test_reporting.py`
- 現況：
  - entry-edge artifact 保留完整 `strategy_spec`。
  - phase markdown 只保留 compact blocked / accepted summary 與 interpretation。
- 風險：
  - 若未來 previous-day family 真正進入 ORB，phase report 可能又被期待承載更多資料邊界資訊。
- 建議：
  - 在做 previous-day family 前，先決定 phase report 是否維持 summary-only。
  - 若要補充，也應只加最小的 data-boundary summary，不要複製 entry-edge 的完整 metadata surface。

### Finding 3：平面 `strategy_spec` 不適合直接吸收一整組 previous-day / gap family 欄位

- 嚴重度：中
- 受影響檔案：
  - `src\signal_forge\cli\strategy_options.py`
  - `tests\test_cli.py`
- 現況：
  - 目前 ORB 已有大量平面欄位，例如 session、VWAP slope、EMA、range size、body strength 等。
- 風險：
  - 若再直接新增 `orb_previous_day_*`、`orb_gap_*`、`orb_overnight_*` 這種平面 key，schema 會更難讀，也更難維護 exact-text regression。
- 建議：
  - previous-day family 若真的要落地，應先定義 `role/family`，而不是直接堆更多平面 key。
  - 現階段先維持研究題定位，不在夜間 automation 內自行擴 schema。

### Review 結論

- 目前 previous-day / gap context 已有足夠研究價值，但還沒有足夠的資料邊界與 contract 準備度，不能直接進入 ORB 主線執行輪。
- 下一步若真的要推進，優先順序應是：
  1. 第二份 intraday 樣本或更完整 previous-day 假設；
  2. 資料邊界定義；
  3. validator / artifact contract；
  4. 最後才是策略欄位與報表 surface。

### 下一步

1. 研究輪優先轉向 previous-day family 的資料邊界定義，而不是直接討論新 CLI 參數。
2. 執行輪若還要做 ORB，先留給 reporting / validator 題或其他更成熟的 filter family，不要提前把 previous-day family 推進主線。

## 2026-05-21 研究輪：previous-day family 的最低風險第一刀，應先選 prior-day close / gap bias，不是直接上 PDH/PDL + premarket

這輪不改程式，只在 `previous-day / higher-timeframe` family 裡再往前收斂一步：**如果未來真的要替 ORB 落第一個前日脈絡條件，最合理的第一刀不是 `PDH/PDL + premarket` 全家桶，而是先做 `prior-day close / gap bias`。**

### 來源

- TradingView `Opening Range Breakout (ORB)`
  https://www.tradingview.com/script/AMsB94Rs-Opening-Range-Breakout-ORB/
- TradingView `Previous Day, Pre Market and ORB Levels`
  https://www.tradingview.com/script/p8veK3iB-Previous-Day-Pre-Market-and-ORB-Levels/
- TradingView Pine Script docs：`Sessions`
  https://www.tradingview.com/pine-script-docs/concepts/sessions/
- TradingView Pine Script docs：`Extended and regular sessions`
  https://www.tradingview.com/pine-script-docs/v4/essential/extended-and-regular-sessions/

### 外部研究重點

- `Opening Range Breakout (ORB)` 這類策略已經示範一種較窄的 previous-day family 寫法：只用 `prior day's close` 來表達 gap fill bias，要求 long breakout 只能發生在價格仍位於前日收盤下方時。
- `Previous Day, Pre Market and ORB Levels` 則是一個更完整的 family：同時引入 `PDH/PDL`、`PDC`、premarket high/low、5m / 15m ORB，並明講這些資料是靠 `request.security` 與明確的 session logic 取回。
- TradingView 官方 `Sessions` 文件也指出，`regular` / `extended` 並不是所有商品都共用同一個語意，甚至不同市場會有不同的 named session。
- 舊版但仍有參考價值的 `Extended and regular sessions` 文件則更直接點出：若要取 extended session 或其他 session 類型資料，必須透過 session-aware ticker / `security` 邏輯，不是單純多一條線就好。

### 研究結論

- 若要在目前 SignalForge ORB contract 上落第一個 previous-day family 條件，`prior-day close / gap bias` 的工程風險明顯低於 `PDH/PDL + premarket`：
  1. 它只需要一個前日 scalar（前收），不需要同時管理前高、前低、premarket 高低與其跨 session reset。
  2. 它比較像現有 ORB optional filter 的延伸，而不是整組新的結構圖層。
  3. 它比較容易先寫成 artifact / validator / reporting contract，再決定要不要往更完整的 previous-day structure family 擴。
- 相對地，若直接上 `PDH/PDL + premarket`，會一次打開：
  - previous-day regular vs full-session 邊界；
  - premarket 是否納入；
  - `request.security` / session-specific ticker 的資料對齊；
  - 多條前日線在 artifact 與 phase report 要怎麼表示。

### 對 SignalForge 的含義

- 這不代表 `prior-day close / gap bias` 應立即進入執行輪；它仍是研究結論，不是產品決策。
- 但若後續真的要替 ORB 試一個前日脈絡 filter，它比 `PDH/PDL + premarket` 更適合當第一個可驗證切片。
- 因此 previous-day family 現在的較合理排序應是：
  1. `prior-day close / gap bias`
  2. `PDH/PDL`
  3. `premarket / overnight range`

### 下一步

1. 若下一輪還研究 previous-day family，優先定義 `prior-day close` 的 session 邊界，而不是直接設計 `PDH/PDL` 欄位。
2. 若未來進入執行輪，應先確認第二份 intraday 樣本與前收來源定義，再決定是否值得落第一個 gap-bias filter。

## 2026-05-21 執行輪：先把 previous-day family 仍在 ORB contract 外這件事，補成窄範圍 regression

這輪不改 ORB 策略語意，也不新增任何 `previous-day / gap / overnight` 欄位；只做一個窄範圍的 contract test，把目前 ORB surface 的邊界鎖住。

### 本輪修改

- 在 `tests/test_cli.py` 新增 `test_strategy_spec_from_args_keeps_previous_day_family_outside_orb_contract(...)`。
- 直接驗證目前 `strategy_spec_from_args(...)` 產出的 ORB spec：
  - 仍明確宣告 `orb_session_scope=regular-session research contract only`
  - 仍明確宣告 `orb_extended_hours_policy=extended-hours bars are outside the current ORB research contract until session/data boundaries are defined explicitly`
  - 不會偷偷長出 `orb_previous_day_*`、`orb_gap_*`、`orb_overnight_*` 這類新 family key

### 為什麼先做這一刀

- 目前 previous-day family 只有研究結論，還沒有資料邊界、validator 與 artifact contract。
- 若未來有人直接在 ORB `strategy_spec` 上加前收 / gap / overnight 欄位，這個測試會先爆掉，迫使實作者先面對 contract decision，而不是讓 surface 默默膨脹。
- 這比現在就急著落第一個 previous-day filter 更符合目前 repo 的夜間 automation 邊界。

### 下一步

1. 若還要推進 previous-day family，先定義 `prior-day close` 的資料來源與 session 邊界。
2. 在那之前，ORB contract 仍維持 same-session only，不把 previous-day family 提前納入正式 surface。

## 2026-05-21 分析輪：拿掉第一個沒有 in-sample prior close 的 session 後，ORB 主線仍維持 pass

這輪不改策略，也不落 previous-day family；只用既有 `MSFT 5m demo` 做一個資料切片比較，回答目前最實際的問題：**如果把第一個沒有 in-sample prior close 可參照的 session 拿掉，現在的 ORB 主線會不會大幅漂移。**

### 比較設定

- Full sample：`data/processed/ALPHAVANTAGE_MSFT_5M_demo.csv`
- Day2+ sample：`reports/generated/msft_5m_demo_day2plus.csv`
- 策略：`orb-volume-vwap --orb-reject-ema-inside-range`
- 產出報表：
  - `reports/generated/msft-orb-dayboundary-sample-sensitivity-20260521.md`
  - `reports/generated/msft-orb-dayboundary-sample-sensitivity-20260521.json`

### 結果

| Slice | Bars | PF | Trades | Win rate | Avg net PnL | Max DD | Blocked | Accepted | Hold |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Full sample | 4224 | 4.452 | 13 | 38.46% | 16.27 | -0.290% | 1754 | 13 | 873 |
| Day2+ only | 4032 | 6.423 | 12 | 41.67% | 19.23 | -0.203% | 1718 | 12 | 790 |

- Full sample blocked reasons：`below_or_high(1480), breakout_volume_blocked(148), ema_inside_opening_range(126)`
- Day2+ blocked reasons：`below_or_high(1477), breakout_volume_blocked(127), ema_inside_opening_range(114)`

### 分析結論

- 拿掉第一個 session 後，ORB 主線 **沒有翻成 fail**，反而在這份樣本上略為改善：
  - PF：`4.452 -> 6.423`
  - Trades：`13 -> 12`
  - Win rate：`38.46% -> 41.67%`
  - Avg net PnL：`16.27 -> 19.23`
  - Max DD：`-0.290% -> -0.203%`
- 這代表目前唯一的 5m 樣本，還不足以支持「應該立刻把 prior-day family 落進 ORB contract」這種結論。
- 它支持的只是較窄的一點：**在沒有明確 prior-close 資料邊界前，先把 previous-day family 留在研究題是合理的。**

### 下一步

1. 若還要推進 previous-day family，優先補第二份 intraday 樣本。
2. 在樣本仍只有這一份之前，不要把 `prior-day close / gap bias` 提前寫成 ORB 的正式 strategy spec surface。

## 2026-05-21 Code Review：prior-day family 若要落地，現在最缺的不是 filter，而是資料與 contract 分層

這輪是 review-only，不改 ORB 策略語意。重點是把前幾輪對 `prior-day close / gap bias` 的研究結論，整理成真正可執行的工程待辦，避免之後直接把前日欄位塞進 ORB surface。

### Finding 1：目前只有「不要落地」的負面 contract，還沒有「若要落地應先定義什麼」的正面 contract

- 嚴重度：中
- 受影響檔案：
  - `tests/test_cli.py`
  - `src\signal_forge\cli\strategy_options.py`
- 現況：
  - 現在已經有 regression 鎖住 ORB 不會長出 `orb_previous_day_*`、`orb_gap_*`、`orb_overnight_*`。
  - 但 repo 內還沒有對應的「前收資料從哪來、怎麼切 regular/full session、何時可以算有效 prior close」正面定義。
- 風險：
  - 後續實作者可能知道「不能亂加欄位」，卻仍不知道第一個 prior-day contract 應該長什麼樣。
- 建議：
  - 若真的要推進，先寫一份最小 data-boundary spec，而不是直接加 CLI 參數。

### Finding 2：目前用 day2+ 切片做 sample-sensitivity 檢查是合理的，但它仍只是單樣本內部切片，不是第二份樣本

- 嚴重度：中
- 受影響檔案：
  - `reports/generated/msft_5m_demo_day2plus.csv`
  - `reports/generated/msft-orb-dayboundary-sample-sensitivity-20260521.*`
- 現況：
  - 把第一個沒有 in-sample prior close 的 session 拿掉後，主線 ORB 仍維持 `PASS`，而且 PF 還變高。
- 風險：
  - 這個結果足以支持「不要急著落 prior-day family」，但不足以支持任何更積極的 prior-day filter 決策。
- 建議：
  - 下一步若還要推進 previous-day family，應優先補真正獨立的第二份 intraday 樣本，而不是再對這份 MSFT demo 做更多切片。

### Finding 3：phase / entry-edge reporting 對 prior-day family 的責任邊界還沒先定義，容易在實作時邊做邊決定

- 嚴重度：中
- 受影響檔案：
  - `src\signal_forge\reporting\_legacy.py`
  - `tests\test_reporting.py`
- 現況：
  - phase markdown 現在已明講 previous-day / higher-timeframe context 在目前 ORB contract 外。
  - 但若未來真的落 prior-day family，還沒有決定 phase 報表是否只保留 summary，或要不要顯示 prior-close boundary metadata。
- 風險：
  - 實作者可能直接把前日欄位塞進 phase markdown，讓 phase / entry-edge 的 surface 再次失衡。
- 建議：
  - 在正式落地前，先決定 prior-day family 只進 `strategy_spec`，還是 phase report 也要有最小邊界說明；不要到實作當下才即興決定。

### Review 結論

- 目前 `prior-day close / gap bias` 仍是合理的第一個 previous-day family 候選。
- 但真正缺的不是策略條件本身，而是：
  1. 前收資料來源定義；
  2. session 邊界定義；
  3. reporting / validator contract 分層。
- 在這三件事補齊前，較合理的工程決策仍是：**保持 previous-day family 在 ORB contract 外，只保留研究結論與 guardrail。**

### 下一步

1. 研究輪若再碰 previous-day family，先寫 `prior-day close` 的資料邊界草案。
2. 執行輪不要先加新欄位；若要做，也應先從 validator 或 contract note 開始，而不是從策略邏輯開始。

## 2026-05-21 研究：`prior-day close` 第一版資料邊界草案

這輪只做研究，不改 ORB 策略語意。目標是把 `prior-day close / gap bias` 若要成為第一個 previous-day family 候選時，**最小可落地的資料邊界**先寫清楚，避免後續直接把 `orb_previous_day_*` 欄位塞進現有 ORB surface。

### 外部依據

- TradingView `Sessions` 文件：session string 與 named session 是不同層級；若腳本要對 regular / extended hours 有穩定定義，必須先決定 session 邊界，而不是只靠 chart 預設。
- TradingView `Other timeframes and data` 與 `Repainting` 文件：任何 higher-timeframe / previous-session 值若透過 `request.security()` 取得，都要先處理 confirmed value 與 lookahead/repaint 風險。
- TradingView `Opening Range Bias + Prev Day Close`：公開 ORB 腳本確實會把 `prev day close` 當成單一水平線或 gap-bias 參照，而不是一次綁入整組 PDH/PDL/premarket。
- TradingView `ORB Gap Strategy`：gap filter 通常是「先有 session open 與 prior reference，再決定當天只允許某個方向」，顯示 `prior close` 很適合作為 previous-day family 的第一刀。

### 第一版最小資料邊界

1. **第一個前日欄位只允許是一個 scalar：`prior_day_close_regular_session`。**
   - 不同時引入 `PDH`、`PDL`、premarket high/low、overnight range。
   - 目的不是一次把 previous-day family 做滿，而是先驗證「單一前收參照」到底有沒有研究價值。

2. **`prior_day_close_regular_session` 的定義必須是「前一個已完成 regular session 的最後確認 close」。**
   - 不是當天 premarket 最後價。
   - 不是 extended-hours close。
   - 不是即時 developing higher-timeframe bar。

3. **session 邊界必須沿用 ORB 已顯式化的 market-clock 設定。**
   - `prior close` 必須和 `orb_session_start_*`、`orb_session_end_*`、`orb_session_timezone` 屬於同一套 regular-session 定義。
   - 若未來市場切換，不應只改 prior-close 計算，而不改 ORB 自己的 session 邊界。

4. **若資料集第一個 session 沒有可用前收，必須明確標成 unavailable，而不是補值。**
   - 不做 forward fill。
   - 不偷用當日第一根或資料集第一列 close 當 prior close。
   - 在沒有 prior close 的 session 上，gap-bias 類條件應直接視為未啟用或不可判定。

5. **第一版 previous-day family 不應先要求 Pine 風格的 HTF 即時計算。**
   - 對 SignalForge 來說，較低風險的做法是先在資料層或 artifact 層把 `prior_day_close_regular_session` 視為已確認欄位。
   - 若未來真的需要 Pine/TradingView 對齊，才再引入「confirmed HTF value + offset」那一層語意。

### 工程含意

- 這份草案支持的不是「現在就把 gap bias 寫進 ORB」，而是：**如果要落第一個 previous-day family，第一刀應該只是一個 confirmed scalar contract。**
- 它同時否定兩個過早方向：
  1. 直接把 `PDH/PDL + premarket` 一整組欄位塞進 `strategy_spec`。
  2. 在沒有定義 prior-close 資料來源前，就先加 `orb_gap_*` 或 `orb_previous_day_*` CLI 參數。

### 下一步

1. 若還要推進 previous-day family，先補第二份獨立 intraday 樣本。
2. 在樣本與資料邊界都清楚前，不要讓 `prior_day_close_regular_session` 長成正式 CLI surface。

## 2026-05-21 執行輪：把 ORB same-session boundary 從測試敘述推進到 strategy spec validator

這輪不改 ORB 策略語意，也不新增 `previous-day / gap / overnight` 欄位；只做一個更靠近程式本體的 contract 收斂：把「ORB 目前仍是 same-session only」從外層 regression 敘述，推進成 `strategy_options.py` 自己的 validator。

### 本輪修改

- `src\signal_forge\cli\strategy_options.py`
  - 新增 ORB same-session contract 常數：
    - `ORB_SESSION_SCOPE_CONTRACT`
    - `ORB_EXTENDED_HOURS_POLICY_CONTRACT`
    - `ORB_FORBIDDEN_PREVIOUS_DAY_PREFIXES`
  - 新增 `_validate_orb_same_session_contract(spec)`：
    - 檢查 `orb_session_scope`
    - 檢查 `orb_extended_hours_policy`
    - 拒絕任何 `orb_previous_day_*`、`orb_gap_*`、`orb_overnight_*` surface
  - `strategy_spec_from_args(...)` 在 ORB 路徑會主動呼叫這個 validator，而不是只把邊界留給外層測試。
- `tests\test_cli.py`
  - 新增 direct unit test，直接驗證 validator 會拒絕人為混入的 `orb_previous_day_close` 欄位。

### 工程含意

- 先前 repo 已經有「不要讓 previous-day family 提前長進 ORB contract」的 regression。
- 這輪的價值是把那條 guardrail 往內收：
  - 以前：只有 CLI / artifact regression 會抓到 drift
  - 現在：`strategy_spec` 建構點本身就會拒絕 drift
- 這讓後續若有人在 `strategy_spec_from_args(...)` 旁邊直接偷加 `orb_previous_day_*` 類欄位，會先在本地 unit test 與 validator 層失敗，不必等到 phase / entry-edge artifact 才發現。

### 下一步

1. 若還要推進 `prior-day close` family，下一輪應優先定義「正面 contract」與資料來源，而不是再補更多禁止性欄位。
2. 在那之前，ORB same-session boundary 已同時有：
   - phase prose
   - CLI regression
   - `strategy_spec_from_args(...)` direct test
   - 以及本輪新增的內建 validator

## 2026-05-21 分析輪：確認 repo 目前沒有第二份 ORB-capable intraday 樣本

這輪不再對同一份 `MSFT 5m demo` 做更多 wording 驗證或細碎切片，而是直接回答一個更基礎的研究問題：**repo 目前是否已經有第二份可用來驗證 ORB / previous-day family 的獨立 intraday 樣本？**

### 樣本盤點結果

- `data\processed\ALPHAVANTAGE_MSFT_5M_demo.csv`
  - 目前唯一明確符合 ORB 研究需求的 processed intraday 樣本。
- `data\processed\TWSE_2330_1D.csv`
  - 只有日線，不是 intraday；無法拿來驗 opening range、same-session VWAP、fresh breakout、hold bars 或 prior-close intraday bias。
- `data\sample\phase1_demo_ohlcv.csv`
  - 屬於 Phase / fixture 性質的小型示範資料，不應拿來當第二份獨立 ORB 研究樣本。

### 分析結論

1. **目前 repo 只有一份真正可拿來驗 ORB 的 intraday processed 樣本：`ALPHAVANTAGE_MSFT_5M_demo.csv`。**
2. 因此，現階段還不能把 `prior-day close / gap bias` 當成「已有跨樣本證據支持、可以自然落地」的下一刀。
3. 這也解釋了為什麼先前把第一個沒有 in-sample prior close 的 session 移除後，雖然 PF 從 `4.452` 升到 `6.423`，但仍不足以支持 previous-day family 直接進入 ORB contract：那只是**同一份樣本內的敏感度分析**，不是第二份獨立驗證。

### 工程含意

- 下一步若要推進 previous-day family，應優先補：
  1. 第二份真正獨立的 intraday 樣本。
  2. `prior_day_close_regular_session` 的資料來源與 validator contract。
- 在那之前，repo 現在已有充分 guardrail 支持「**不要提前把 `orb_previous_day_*` / `orb_gap_*` / `orb_overnight_*` 長進 ORB surface**」：
  - phase markdown 邊界說明
  - CLI regression
  - `strategy_spec_from_args(...)` direct unit test
  - same-session validator

### 下一步

1. 若要繼續 previous-day family，先定義第二份 intraday 樣本的最低資料需求與來源。
2. 在沒有第二份樣本前，不要直接新增 `prior-day close / gap bias` filter、CLI 參數或 artifact schema。

## 2026-05-21 Code Review：prior-day close 若要真正落地，現在還缺的三個正面 contract

這輪是 review-only，不改 ORB 策略語意。重點是把前幾輪對 previous-day family 的研究與 guardrail，再整理成更可執行的工程待辦。結論是：**目前 repo 已經很清楚地知道「什麼不能做」，但還沒有把「第一個可以做的 prior-day close contract 應長什麼樣」寫成程式或測試層的正面定義。**

### Finding 1：目前只有 negative guardrail，還沒有 `prior_day_close_regular_session` 的正面 validator contract

- 嚴重度：中
- 受影響檔案：
  - `src\signal_forge\cli\strategy_options.py`
  - `tests\test_cli.py`
- 現況：
  - `_validate_orb_same_session_contract(...)` 已能拒絕 `orb_previous_day_*`、`orb_gap_*`、`orb_overnight_*` 混入 ORB surface。
  - 但 repo 仍沒有對應的正面 contract，例如：
    - `prior_day_close_regular_session` 必須來自哪個 session 定義；
    - 它何時可以視為 available；
    - 它在 artifact 中應以什麼命名與格式出現。
- 風險：
  - 未來若真的要落第一個 previous-day family，實作者仍可能邊寫邊決定欄位名稱與來源，導致 contract 漂移。
- 建議：
  - 在新增任何 `orb_previous_day_*` surface 前，先寫一份最小 validator / schema 草案，哪怕一開始只是一個 `dict contract` 或 dedicated validation helper 也可以。

### Finding 2：`first session unavailable` 目前只有研究文字，還沒有對應測試

- 嚴重度：中
- 受影響檔案：
  - `docs\04-實驗記錄\Autoresearch 實驗記錄.md`
  - `docs\策略筆記\ORB + Volume + VWAP.md`
  - `tests\test_cli.py` 或未來的 previous-day family tests
- 現況：
  - 研究筆記已明確寫出：若資料集第一個 session 沒有 prior close，必須標成 unavailable，不得補值。
  - 但這個規則目前仍只存在於文件，不存在任何程式或測試層 contract。
- 風險：
  - 一旦 previous-day family 真正開始實作，最容易被默默做掉的就是 `forward fill`、偷用當日第一根 close、或將第一個 session 直接視為 gap=0。
- 建議：
  - 下一步若真的進入執行輪，優先補一個極小的 unavailable 行為測試，比直接加 filter 更重要。

### Finding 3：phase / entry-edge reporting 對 previous-day family 的責任仍需先定義

- 嚴重度：中
- 受影響檔案：
  - `src\signal_forge\reporting\_legacy.py`
  - `tests\test_reporting.py`
- 現況：
  - phase markdown 已明講 previous-day / higher-timeframe context 目前在 ORB contract 外。
  - entry-edge artifact 則已承擔 `strategy_spec` metadata 主責。
- 風險：
  - future previous-day family 若真的進入 ORB，phase 報表很可能又被期待顯示 prior-close 邊界、availability、或 gap-bias 狀態；若沒有先定義責任，很容易再次讓 phase / entry-edge surface 邊做邊長。
- 建議：
  - 在落第一個 previous-day scalar 前，先明確決定：
    1. prior-day metadata 是否只進 `strategy_spec`；
    2. phase report 是否只保留一句 compact boundary summary；
    3. 哪些資訊絕不進 phase markdown。

### Review 結論

- 目前 ORB 對 previous-day family 的「拒絕式 contract」已經足夠穩。
- 下一步真正缺的不是新 filter，而是：
  1. `prior_day_close_regular_session` 的正面資料 contract；
  2. 第一個 session unavailable 的測試；
  3. phase / entry-edge reporting 的責任分層。

### 下一步

1. 研究輪若再碰 previous-day family，優先把正面 contract 草案寫得更像 validator / schema，而不只是 prose。
2. 執行輪若真的要動 previous-day family，先補 unavailable regression，不要先寫 gap-bias filter。

## 2026-05-21 研究輪：`prior_day_close_regular_session` 的最小正面 contract 草案

這輪不改 ORB 策略語意，只把前幾輪一直提到的「正面 contract」再往前推一步：**如果未來真的要讓 previous-day family 有第一個可落地的 scalar，它的最小 schema 應該長什麼樣。**

### 外部依據

- TradingView `Sessions`
  https://www.tradingview.com/pine-script-docs/v5/concepts/sessions/
- TradingView `Other timeframes and data`
  https://www.tradingview.com/pine-script-docs/v5/concepts/other-timeframes-and-data/
- TradingView `Opening Range Bias + Prev Day Close`
  https://www.tradingview.com/script/EtcLGkoo-Opening-Range-Bias-Prev-Day-Close/
- TradingView `Previous Day's Close Indicator (Regular Hours)`
  https://www.tradingview.com/script/Pokd5BKi-Previous-Day-s-Close-Indicator-Regular-Hours/
- TradingView `Opening Range Breakout (ORB)`
  https://www.tradingview.com/script/AMsB94Rs-Opening-Range-Breakout-ORB/

### 研究結論

公開腳本與官方文件支持一個更窄、更可驗證的第一刀：**先把 previous-day family 縮成單一 scalar `prior_day_close_regular_session`，而不是直接展開成一組 `PDH/PDL/gap/overnight` surface。**

其中最重要的不是欄位名稱，而是它背後要同時鎖住三件事：

1. 它來自 **前一個已完成的 regular session**。
2. 它是 **confirmed close**，不是 developing HTF bar。
3. 若資料集第一個 session 沒有 prior close，狀態必須是 **unavailable**，而不是補值。

### 最小正面 contract 草案

若未來要讓這個 family 進入 validator / schema 層，第一版應至少有以下概念：

- `prior_day_close_regular_session`
  - 定義：前一個已完成 regular session 的最後確認 close。
- `prior_day_close_source_session = regular_session`
  - 明講它不是 full-session、premarket、postmarket 或 overnight。
- `prior_day_close_timezone = orb_session_timezone`
  - 明講它和 ORB 現有的 market-clock contract 綁在一起，不允許獨立漂移。
- `prior_day_close_availability = available | unavailable_first_session`
  - 明講第一個沒有 prior close 的 session 是 unavailable，不做 implicit fallback。
- `prior_day_close_fill_policy = no_forward_fill`
  - 明講不得偷補前值。

### 為什麼這樣比直接做 gap bias 更合理

- 這份 contract 是資料層 / artifact 層的最小切片，還不是策略行為。
- 它能先把最容易漂移的地方固定下來：
  - 來源是 regular session 還是 full session；
  - 時區跟誰綁；
  - 第一個 session 如何處理；
  - 是否允許補值。
- 一旦這四件事沒先鎖住，後面的 `gap bias` filter 其實只是把模糊資料假設包成策略參數。

### 下一步

1. 若進入執行輪，優先補 `unavailable_first_session` regression 或 dedicated validator helper。
2. 在這個最小資料 contract 沒有變成測試前，不要直接新增 `orb_previous_day_close` 或 `orb_gap_bias` CLI surface。

## 2026-05-21 執行輪：補 `prior_day_close_regular_session` 的 first-session unavailable validator contract

這輪不改 ORB 策略語意，也不把 previous-day family 接進目前的 ORB `strategy_spec` surface；只先把上一輪研究整理出的最小正面 contract，縮成一個可測試的 helper 邊界。

### 這輪實作

- 在 `strategy_options.py` 新增 `_validate_orb_prior_day_close_contract(...)`。
- 這個 helper 只驗證研究已經收斂出的最小欄位：
  - `prior_day_close_regular_session`
  - `prior_day_close_source_session = regular_session`
  - `prior_day_close_timezone = orb_session_timezone`
  - `prior_day_close_availability = available | unavailable_first_session`
  - `prior_day_close_fill_policy = no_forward_fill`
- 若 `prior_day_close_availability = unavailable_first_session`，則 `prior_day_close_regular_session` 必須明確寫成 `unavailable`，不能再偷放數值。

### 為什麼先做 helper，不直接接進 ORB surface

- 目前 repo 還沒有第二份 ORB-capable intraday 樣本。
- previous-day family 也還沒有 phase / entry-edge 的正面 metadata 分工。
- 因此這輪的合理邊界是：先把「未來要遵守什麼資料 contract」變成 validator 與測試，而不是把 `orb_previous_day_*` 長成正式 schema。

### 驗證

- 新增 direct unit tests：
  - 接受 `available`
  - 接受 `unavailable_first_session`
  - 拒絕 `forward_fill`
  - 拒絕 `unavailable_first_session` 但仍塞數值

### 下一步

1. 若後續還要推 previous-day family，先補第二份獨立 intraday 樣本。
2. 在 phase / entry-edge reporting 分工沒有先定義前，不要讓這個 helper 直接外溢成 ORB artifact surface。

## 2026-05-21 分析輪：確認 prior-day close validator helper 對 ORB 主線是 runtime-neutral

這輪不再開新 filter，也不再對同一份樣本做更多 previous-day 切片；只做一個更重要的確認：**上一輪補進 repo 的 `prior_day_close_regular_session` validator helper，是否影響目前 ORB 主線 runtime 行為。**

### 比較對象

- Baseline：
  - `reports/generated/msft-orb-dayboundary-full-entry.json`
  - `reports/generated/msft-orb-dayboundary-full-phase_trace_summary.json`
- Current：
  - `reports/generated/msft-orb-priorday-contractcheck-20260521-ema-box-entry.json`
  - `reports/generated/msft-orb-priorday-contractcheck-20260521-ema-box-phase_trace_summary.json`
- Strategy：
  - `orb-volume-vwap --orb-reject-ema-inside-range`
- Data：
  - `data/processed/ALPHAVANTAGE_MSFT_5M_demo.csv`

### 分析結果

- PF：`4.452 -> 4.452`
- Trades：`13 -> 13`
- Win rate：`38.46% -> 38.46%`
- Avg net PnL：`16.27 -> 16.27`
- Max DD：`-0.290% -> -0.290%`
- blocked：`1754 -> 1754`
- accepted：`13 -> 13`
- hold：`873 -> 873`
- blocked reasons 也完全一致：
  - `below_or_high(1480)`
  - `breakout_volume_blocked(148)`
  - `ema_inside_opening_range(126)`

### Artifact boundary check

- `orb_session_scope` 仍是 `regular-session research contract only`
- `orb_extended_hours_policy` 仍是既有 same-session boundary 說明
- current `strategy_spec` 仍然沒有任何：
  - `orb_previous_day_*`
  - `orb_gap_*`
  - `orb_overnight_*`

### 結論

這代表上一輪新增的 `prior_day_close_regular_session` helper 目前仍是 **contract-only change**：

- 它沒有改到 ORB trade selection。
- 它沒有改到 blocked / accepted / hold attribution。
- 它也沒有把 previous-day family 偷帶進目前 same-session artifact surface。

這是現階段最合理的結果。repo 現在多了一個正面 validator helper，但 previous-day family 仍未正式進入 ORB runtime contract。

### 下一步

1. 若還要推進 previous-day family，分析配額應優先轉向第二份獨立 intraday 樣本。
2. 在沒有第二份樣本與 reporting 分工前，不要再為這個 helper 擴 schema 或加 gap-bias filter。

## 2026-05-21 執行輪：正式收編 `TWSE_2330_5M` 為第二份 ORB-capable intraday 樣本

這輪不改 ORB 策略語意，也不新增 previous-day / gap filter；只處理一個更基礎的 repo 邊界問題：**`TWSE_2330_5M.*` 其實已經被台積電延伸研究、ORB 策略筆記與 `reports/generated/tsmc-*` 報表實際使用，因此不應再被視為懸空工作樹，而應正式承認它是 repo 內第二份 ORB-capable intraday 樣本。**

### 這輪收編的檔案

- `data/processed/TWSE_2330_5M.csv`
- `data/processed/TWSE_2330_5M_manifest.json`
- `data/raw/TWSE_2330_5M_yahoo_raw.json`
- `docs/04-實驗記錄/台積電四策略延伸研究.md`

### 樣本身份結論

1. `TWSE_2330_5M.csv` 符合目前 ORB intraday research contract：
   - CSV contract 為 `timestamp,open,high,low,close,volume`
   - bar 具時間資訊與時區偏移，例如 `2026-02-23T09:00:00+08:00`
   - sample manifest 已明寫：
     - `source = Yahoo Finance chart API`
     - `interval = 5m`
     - `timezone = Asia/Taipei`
     - `row_count = 3141`
     - `first_timestamp = 2026-02-23T09:00:00+08:00`
     - `last_timestamp = 2026-05-21T13:30:00+08:00`
2. 它不是 fixture，也不是純筆記附件；repo 已存在對應實驗輸出：
   - `reports/generated/tsmc-orb-5m-20260521.json`
   - `reports/generated/tsmc-orb-5m-20260521.md`
   - `reports/generated/tsmc-orb-5m-20260521_hold_comparison.json`
   - `reports/generated/tsmc-orb-5m-20260521_hold_comparison.md`
3. 因此，先前「repo 目前只有一份 ORB-capable intraday 樣本」的結論，應視為在這批未提交檔案尚未被正式收編前成立；**從這輪開始，repo 應以 `ALPHAVANTAGE_MSFT_5M_demo.csv` 與 `TWSE_2330_5M.csv` 作為兩份已存在的 ORB intraday 樣本。**

### 對 previous-day family 的含義

- 這個收編動作**不等於** `prior-day close / gap bias` 已可直接落進 ORB contract。
- 它只解除了一個較底層的阻塞：之後若要比較 previous-day family，至少不再被「repo 沒有第二份 intraday 樣本」這個說法卡住。
- 真正還缺的仍然是：
  1. `prior_day_close_regular_session` 的正面資料來源 contract；
  2. `unavailable_first_session` 的 artifact / regression 行為；
  3. phase / entry-edge reporting 對 previous-day metadata 的責任分層。

### 下一步

1. 之後若要再進 previous-day family，不要重複盤點「有沒有第二份 intraday 樣本」；直接進入正面資料 contract 與 reporting boundary 設計。
2. 若 `TWSE_2330_5M` 後續要被用作 canonical 台股 ORB 樣本，應維持目前 `Asia/Taipei 09:00-13:30` regular-session metadata，不要再把它混回美股預設 market-clock。

## 2026-05-21 分析輪：比較 `EMA inside-range` 主線在 MSFT 與 TSMC 兩份 intraday 樣本上的跨樣本穩定性

這輪直接比較目前 ORB 主線：

- Strategy：
  - `orb-volume-vwap --orb-reject-ema-inside-range`
- Sample A：
  - `data/processed/ALPHAVANTAGE_MSFT_5M_demo.csv`
- Sample B：
  - `data/processed/TWSE_2330_5M.csv`

### 產出 artifact

- `reports/generated/msft-orb-ema-box-holdcmp-20260521_hold_comparison.json`
- `reports/generated/tsmc-orb-ema-box-holdcmp-20260521_hold_comparison.json`
- `reports/generated/tsmc-orb-ema-box-phase-20260521_trace_summary.json`
- `reports/generated/orb-ema-box-crosssample-20260521.md`
- `reports/generated/orb-ema-box-crosssample-20260521.json`

### MSFT 5m 結果

- hold 1：
  - decision：`pass`
  - PF：`4.452`
  - Trades：`13`
  - Win rate：`38.46%`
  - Avg net PnL：`16.27`
  - Max DD：`-0.290%`
- hold 3 / 5 / 10 全部 `fail`
- phase trace summary：
  - accepted：`13`
  - hold：`873`
  - blocked：`1754`
  - blocked reasons：
    - `below_or_high(1480)`
    - `breakout_volume_blocked(148)`
    - `ema_inside_opening_range(126)`

### TSMC 2330 5m 結果

- hold 1：
  - decision：`fail`
  - PF：`0.083`
  - Trades：`20`
  - Win rate：`5.00%`
  - Avg net PnL：`-10.20`
  - Max DD：`-2.039%`
- hold 3：
  - PF：`0.236`
- hold 5：
  - PF：`0.248`
- hold 10：
  - PF：`0.927`
  - Trades：`19`
  - unclosed：`1`
- phase trace summary：
  - accepted：`20`
  - hold：`396`
  - blocked：`2017`
  - blocked reasons：
    - `below_or_high(1855)`
    - `ema_inside_opening_range(86)`
    - `breakout_volume_blocked(69)`
    - `volume_warmup(7)`

### 交叉判讀

1. `EMA inside-range` 目前不是跨樣本穩定的主線條件。
   - `MSFT 5m demo` 的 hold 1 是明確 `PASS`。
   - `TWSE_2330_5M` 的 hold 1 / 3 / 5 / 10 全部 `FAIL`。
2. 2330 的失敗不是因為 `EMA inside-range` 太嚴。
   - MSFT 被 `ema_inside_opening_range` 擋掉 `126` 次。
   - TSMC 只被擋掉 `86` 次。
   - 也就是說，問題比較像是放行後的突破品質本身較差。
3. 2330 也不是「沒有訊號」。
   - accepted 反而比 MSFT 多：`20 > 13`
   - 但持有期間的報酬品質明顯更差。

### 重要邊界

這輪也暴露出更重要的實驗邊界：`TWSE_2330_5M` 是 `Asia/Taipei 09:00-13:30` regular session，但這次比較仍沿用了目前 ORB 主線既有的 market-clock defaults。這代表：

- 這個比較足以證明「現有 ORB 主線在第二份樣本上不具跨樣本穩定性」。
- 但它不足以證明「2330 本質上不適合 `EMA inside-range`」。
- 若要對台股做更公平的下一輪比較，應先把 `orb_session_timezone`、`session start/end` 明確切到 `Asia/Taipei 09:00-13:30`，再比較是否仍然失敗。

### 結論

- `EMA inside-range` 在目前 repo 的兩份 intraday 樣本上，不具普適穩定性。
- 目前沒有理由把它升格成 market-agnostic 主線 invariant。
- 也沒有理由在這個時間點就把注意力轉去 `prior-day close / gap bias`；更迫切的下一步，是先做 market-clock 對齊後的跨樣本重跑。

### 下一步

1. 若要再用 `TWSE_2330_5M` 做 ORB 比較，先把 `orb_session_timezone`、`session start/end` 對齊 `Asia/Taipei 09:00-13:30`。
2. 在 market-clock 沒對齊前，不要用這份失敗結果直接推導新的 previous-day family filter。
3. `prior_day_close_regular_session` 仍維持 contract-only 狀態；先不要把它擴成 gap-bias runtime filter。

## 2026-05-21 Review 輪：整理 TWSE 2330 market-clock 對齊前的剩餘 contract 缺口

這輪是 review-only，不改 ORB 策略語意；只把 `TWSE_2330_5M` 若要進入下一輪正式比較前，還缺哪些 contract 與測試寫清楚。

### Findings

1. **目前只有「可配置」的 market-clock，還沒有「樣本與 market-clock 必須對齊」的正面 validator。**
   - `tests/test_strategy_factory.py` 與 `tests/test_cli.py` 已經證明 ORB 可以吃 `Asia/Taipei 09:00-13:30`。
   - 但目前系統還沒有任何 guard 會在 `TWSE_2330_5M` 這類台股樣本被拿去跑 `America/New_York 09:30-16:00` defaults 時直接提醒或拒絕。
   - 也就是說，repo 現在有 capability，但還沒有 enforcement。

2. **`TWSE_2330_5M` 已正式收編成第二份 ORB-capable intraday 樣本，但 sample identity 與 market-clock identity 仍是分離的。**
   - 樣本來源、interval、timezone 已寫在 manifest 與研究筆記。
   - 但執行點還沒有一個簡單 contract 可以表達：「這份樣本的 canonical ORB regular session 應該是 `Asia/Taipei 09:00-13:30`」。
   - 因此目前最容易發生的誤讀，不是資料缺失，而是研究者忘了帶對 market-clock 參數。

3. **cross-sample 結論已經足夠，下一步不該再花輪次重複證明 `EMA inside-range` 在 2330 上失敗。**
   - 我們已經知道它在現有 defaults 下跨樣本不穩定。
   - 現在真正缺的是「對齊後是否仍然不穩定」。
   - 所以下一輪若是執行或分析，應直接把焦點放在 `Asia/Taipei 09:00-13:30` 對齊後的 rerun，而不是再做更多 wording、helper-neutrality 或同 defaults 切片。

### 結論

- 目前最關鍵的技術債不是 filter family，而是 **sample-aware market-clock contract 還沒被系統化**。
- 在這個缺口補起來前，不應把 `TWSE_2330_5M` 的失敗結果拿去推導新的 ORB filter 或 previous-day family。

### 下一步

1. 若進入執行輪，優先做「sample-aware market-clock 提示或 validator」，而不是加新 filter。
2. 若進入分析輪，直接重跑 `TWSE_2330_5M` 的 `Asia/Taipei 09:00-13:30` 版本，並和目前 defaults 結果做 A/B 對照。

## 2026-05-21 研究輪：公開 ORB 腳本對多市場 session / timezone 的常見排序

這輪不找新的 entry filter，而是回頭確認一個更底層的研究排序：**當同一套 ORB 要搬到不同市場時，公開腳本通常先處理什麼？**

### 研究來源

- TradingView 官方 `Sessions`
- TradingView 官方 `Other timeframes and data`
- TradingView 官方 `Repainting`
- TradingView 公開腳本：
  - `SessionVWAP + ORB`
  - `ORB Multi Preset`

### 核心觀察

1. **公開 ORB 腳本通常先把 session/timezone 做成一級設定，再談 breakout filter。**
   - `SessionVWAP + ORB` 直接把 Sydney / Tokyo / London / New York / US RTH 拆成不同 session，並明講支援完整 timezone flexibility。
   - `ORB Multi Preset` 更直接：它不是先問哪條 EMA 或哪個 volume filter，而是先替不同 underlying 各自定義 `Pre-ORB`、`ORB`、time 與 timezone。
   - 這和目前 `TWSE_2330_5M` 暴露出的問題一致：2330 的第一個缺口不是 filter family，而是 market-clock contract 還沒被系統化。

2. **TradingView 官方 session 模型也支持把 session 與 timezone 當成顯式邊界，而不是暗含在資料裡。**
   - `time(timeframe, session, timezone)` 就是這種設計。
   - 官方也明講 exchange-defined regular/extended session 與 user-defined session string 是兩回事，這代表 ORB 若要跨市場，不能只靠「這份 CSV 看起來像台股」來推斷邊界。

3. **一旦 previous-day / higher-timeframe family 需要 `request.security()`，複雜度與 repaint 風險會立刻上升。**
   - 官方文件明確提醒：`request.security()` 在 historical / realtime 行為上可能不同，若沒有 offset 與 `lookahead` 管理，會 repaint。
   - 因此，在 market-clock contract 還沒先對齊前，直接把 `prior-day close / gap bias / PDH/PDL` 推進 ORB 主線，工程風險高於收益。

### 結論

- 公開腳本與官方文件的共同訊號很一致：**跨市場 ORB 的第一步應該是 session/timezone/market-clock 對齊，而不是先堆 filter。**
- 這進一步支持目前 repo 的排序：
  1. 先把 `TWSE_2330_5M` 的 canonical `Asia/Taipei 09:00-13:30` contract 系統化；
  2. 再做 market-clock 對齊後的 cross-sample rerun；
  3. 只有在這一步仍顯示不足時，才值得把注意力轉去 previous-day family。

### 下一步

1. 若進入執行輪，優先做 sample-aware market-clock prompt / validator，而不是做新的 ORB filter。
2. 若進入分析輪，優先跑 `TWSE_2330_5M` 的 `Asia/Taipei 09:00-13:30` 對齊版 A/B 比較。

## 2026-05-21 執行輪：替已知台股樣本補 sample-aware market-clock alignment metadata

這輪不改 ORB 策略語意，也不直接阻擋執行；只做一個聚焦改動：對已知的 `TWSE_2330_5M.csv`，在 ORB artifact 裡直接寫出 canonical market-clock expectation，並標示這次 CLI 設定是 `aligned` 還是 `mismatch`。

### 這輪修改

- `src/signal_forge/cli/strategy_options.py`
  - 新增 `ORB_KNOWN_SAMPLE_MARKET_CLOCKS`
  - 新增 `_orb_known_sample_market_clock_metadata(...)`
  - 在 `strategy_spec_from_args(...)` 補進：
    - `orb_known_sample_market_clock_name`
    - `orb_known_sample_market_clock_expected_timezone`
    - `orb_known_sample_market_clock_expected_session_start`
    - `orb_known_sample_market_clock_expected_session_end`
    - `orb_known_sample_market_clock_alignment`
- `tests/test_cli.py`
  - 新增 direct unit test，直接驗證 `TWSE_2330_5M.csv` 在：
    - 既有 defaults 下會標成 `mismatch`
    - `Asia/Taipei 09:00-13:30` 對齊後會標成 `aligned`

### 為什麼先做 metadata，不直接做 hard reject

- 目前 repo 已經有用美股 defaults 跑出台股比較的歷史 artifact，這些結果雖然不夠公平，但仍有研究價值，因為它們證明了「現有主線不具跨樣本穩定性」。
- 這一輪若直接改成 hard reject，會把既有比較路徑整個切斷，反而讓 audit trail 變難讀。
- 先把 `aligned / mismatch` 寫進 artifact，比較符合目前 autoresearch 的可追溯性原則。

### 結論

- repo 現在不只知道 `TWSE_2330_5M` 應該用 `Asia/Taipei 09:00-13:30`，還會在 artifact 層明示這次 run 是否真的對齊。
- 這讓下一輪的台股 A/B 比較可以直接站在 deterministic metadata 上做，而不用再靠外部筆記補判讀。

### 下一步

1. 若進入分析輪，直接比較 `TWSE_2330_5M` 的 `mismatch` 與 `aligned` 版本。
2. 若後續發現研究流程仍經常誤用 defaults，再考慮把這個 metadata 升級成更強的 validator。

## 2026-05-21 分析輪：比較 `TWSE_2330_5M` 的 market-clock mismatch vs aligned 結果

這輪不開新 filter，也不動 previous-day family；只做一個更有判斷力的 A/B：同樣的 ORB 主線、同樣的台積電 5m 樣本，只比較 market-clock 是不是對齊。

### 比較對象

- Strategy：
  - `orb-volume-vwap --orb-reject-ema-inside-range`
- Sample：
  - `data/processed/TWSE_2330_5M.csv`
- Version A（mismatch）：
  - 沿用既有 defaults
- Version B（aligned）：
  - `orb_session_start = 09:00`
  - `orb_session_end = 13:30`
  - `orb_session_timezone = Asia/Taipei`

### 產出 artifact

- `reports/generated/tsmc-orb-ema-box-holdcmp-20260521_hold_comparison.json`
- `reports/generated/tsmc-orb-ema-box-phase-20260521_trace_summary.json`
- `reports/generated/tsmc-orb-ema-box-aligned-holdcmp-20260521_hold_comparison.json`
- `reports/generated/tsmc-orb-ema-box-aligned-phase-20260521_trace_summary.json`
- `reports/generated/tsmc-orb-ema-box-market-clock-ab-20260521.md`
- `reports/generated/tsmc-orb-ema-box-market-clock-ab-20260521.json`

### Hold comparison

#### mismatch

- hold 1：PF `0.083` / Trades `20` / Win rate `5.00%` / Avg net PnL `-10.20` / Max DD `-2.039%`
- hold 3：PF `0.236`
- hold 5：PF `0.248`
- hold 10：PF `0.927`

#### aligned

- hold 1：PF `0.513` / Trades `21` / Win rate `23.81%` / Avg net PnL `-7.47` / Max DD `-2.880%`
- hold 3：PF `0.538`
- hold 5：PF `0.685`
- hold 10：PF `0.309`

### Trace summary 對照

#### mismatch

- accepted：`20`
- hold：`396`
- blocked：`2017`
- blocked reasons：
  - `below_or_high(1855)`
  - `ema_inside_opening_range(86)`
  - `breakout_volume_blocked(69)`
  - `volume_warmup(7)`

#### aligned

- accepted：`21`
- hold：`500`
- blocked：`2266`
- blocked reasons：
  - `below_or_high(2087)`
  - `ema_inside_opening_range(86)`
  - `breakout_volume_blocked(80)`
  - `volume_warmup(13)`

### 關鍵判讀

1. **market-clock 對齊是有實質影響的。**
   - hold 1 的 PF 從 `0.083 -> 0.513`
   - hold 3 的 PF 從 `0.236 -> 0.538`
   - hold 5 的 PF 從 `0.248 -> 0.685`
   - 這代表先前 2330 的失敗，確實有一部分來自 session/timezone mismatch。

2. **但 market-clock 對齊後，策略仍然沒有翻成 pass。**
   - aligned 版本的所有 hold 設定仍是 `FAIL`
   - 所以 2330 的弱表現不能完全歸咎於 market-clock 錯位；台股樣本本身對這條 ORB 主線的相容性仍然偏弱。

3. **對齊後，訊號分布變得更像「同一個市場真正的 regular session」了。**
   - session group count 從 `708` 降到 `354`
   - hold count 從 `396` 升到 `500`
   - 這說明對齊後，更多 bar 被放進了真正應該分析的 regular session 區段，而不是被錯誤時鐘切碎。

4. **`EMA inside-range` 仍然不是 2330 的主要失敗來源。**
   - `ema_inside_opening_range` 在 mismatch / aligned 都是 `86`
   - 也就是說，這條 gate 本身沒有因 market-clock 對齊而成為主因；真正變化最大的是 OR 與 session slicing 本身。

### 結論

- `TWSE_2330_5M` 的 market-clock alignment 是必要修正，不是可有可無的 metadata。
- 但 alignment 只能把結果從「明顯失真」拉回「較合理但仍偏弱」，還不足以把這條 ORB 主線翻成有效。
- 因此下一步不該直接跳去 previous-day family；更合理的是承認：
  1. market-clock mismatch 確實扭曲了 2330 結果；
  2. 即使修正後，這條主線在台股樣本上仍不夠強。

### 下一步

1. 若要再做台股 ORB 比較，今後應以 `aligned` 版作為 canonical 基線，不再沿用 mismatch defaults。
2. 在這個基線上，再決定下一步是比較其他 ORB refinement，還是把台股樣本暫時視為「現有主線不適配」。
3. 目前仍不建議直接把注意力轉去 previous-day / gap bias；先把 same-session 主線在第二份樣本上的表現邊界定清楚。

## 2026-05-21 Review 輪：台股 ORB canonical baseline 改成 aligned 版之後的剩餘工程債

這輪是 review-only，不改策略語意；只整理在 `TWSE_2330_5M` 已明確改用 aligned `Asia/Taipei 09:00-13:30` 作為 canonical baseline 後，還有哪些 guard 與 contract 沒跟上。

### Findings

1. **目前 artifact 已能標示 `aligned / mismatch`，但分析流程尚未要求後續台股比較必須以 aligned 版為主。**
   - 現在的 metadata 足以幫助人讀 artifact。
   - 但如果後續有人再沿用 defaults 跑 `TWSE_2330_5M`，系統仍不會阻止它被誤當成主線比較結果。
   - 也就是說，repo 現在有「描述性 guard」，但還沒有「流程性 guard」。

2. **`TWSE_2330_5M` 的 canonical baseline 已在研究結論裡收斂，但還沒有一個更靠近 CLI / reporting 的固定提示。**
   - 目前這件事主要寫在 `Autoresearch 實驗記錄` 與策略筆記。
   - 若未來 artifact 要更自我說明，可能還需要一個更短、固定的 baseline note，避免台股報表只能靠長文脈絡判讀。

3. **這輪 A/B 已足夠回答 market-clock 問題，下一步不該再重複做同題驗證。**
   - 我們現在已經知道：
     - mismatch 會扭曲結果；
     - aligned 是必要修正；
     - 修正後仍然偏弱。
   - 所以再做第三次同型 A/B 的價值很低。
   - 更合理的是把後續分析配額轉去：
     - 其他 ORB refinement 在 aligned 台股 baseline 上的表現；
     - 或直接承認台股樣本對這條主線不適配。

### 結論

- `TWSE_2330_5M` 的 ORB 比較現在已經有夠清楚的 canonical baseline：`Asia/Taipei 09:00-13:30 aligned`。
- 目前剩餘的工程債不是「再多一個比較」，而是如何避免後續流程又把 `mismatch` 版拿回來當主結論。

### 下一步

1. 若進入執行輪，優先考慮補一個更靠近 reporting / CLI 的台股 baseline 提示，而不是做新 filter。
2. 若進入研究或分析輪，直接站在 aligned 版上比較下一個 refinement，不要再重複 market-clock A/B。

## 2026-05-21 研究輪：確認 public ORB 常把 active preset / market-clock 顯式化

這輪不研究新 filter，也不往 previous-day family 前進；只確認一件更靠前的工程排序：**public ORB 腳本在跨市場場景下，通常會把 active preset、session 與 timezone 直接顯示給使用者，而不是只把它們藏在 inputs 裡。**

### 研究依據

1. `ORB Multi Preset`
   - 腳本直接以多個 underlying preset 為主體，並把各自的 `Pre-ORB`、`ORB` 時段與 timezone 當成功能說明的一部分。
   - 重點不是 breakout filter，而是先把「這個市場用哪個時鐘」說清楚。

2. `RPFXBYDAN - ORB (Opening Range Breakout)`
   - 明講有 market presets、timezone-aware display、以及右上角 info panel。
   - info panel 直接顯示 active market、market timezone、local timezone 與 resolved session windows，避免使用者自己做時差換算。

3. TradingView 官方 `Sessions` / `Time`
   - 官方文件把 `session` 與 `timezone` 當成 Pine 的一級概念，而不是單純視覺設定。
   - 這支持我們目前把 `TWSE_2330_5M` 的 canonical baseline 寫成 `Asia/Taipei 09:00-13:30 aligned`，也支持下一步把這件事更靠近 artifact / reporting 表達。

### 結論

- 對目前 SignalForge 的 ORB 來說，下一個較低風險、也最符合公開實務的改動，不是再加 filter，而是補一個更靠近 **CLI / reporting 的 active baseline 提示**。
- 既然 `TWSE_2330_5M` 已經有 sample-aware market-clock metadata，下一步更合理的是讓人一眼就看出：
  - 這次 run 的 sample 是台股；
  - canonical baseline 是 `Asia/Taipei 09:00-13:30`；
  - 目前結果是否 aligned。
- 這種提示屬於 artifact 可讀性補強，不是策略語意變更，也不需要把 previous-day family 提前拉進主線。

### 下一步

1. 若進入執行輪，優先補一個更靠近 CLI / reporting 的 `active baseline note`，而不是擴新 filter。
2. 若進入分析輪，直接站在 `TWSE_2330_5M aligned` baseline 上比較下一個 refinement，不要再做同題 market-clock A/B。

## 2026-05-21 執行輪：將台股 canonical baseline 提示推進 ORB artifact

這輪不改 ORB 策略語意，只把前一輪研究收斂出的 `active baseline` 提示正式寫進 `strategy_spec`。對已知的 `TWSE_2330_5M.csv`，artifact 現在除了原本的 `aligned / mismatch` metadata 之外，還會固定輸出一行 `orb_known_sample_market_clock_baseline_note`，直接說明這份樣本的 canonical ORB baseline 是 `Asia/Taipei 09:00-13:30`，以及本次 run 是否對齊。

### 修改內容

- `src/signal_forge/cli/strategy_options.py`
  - 擴充 `_orb_known_sample_market_clock_metadata(...)`
  - 新增 `orb_known_sample_market_clock_baseline_note`
- `tests/test_cli.py`
  - 補 direct unit test，分別鎖住：
    - defaults 下的 `mismatch` baseline note
    - `Asia/Taipei 09:00-13:30` 對齊後的 `aligned` baseline note

### 結論

- 這輪把台股 canonical baseline 從「研究結論」再往前推到「artifact 直接可讀」。
- 它不改 ORB breakout、volume、VWAP、EMA inside-range 的 trade selection，只改善跨樣本報表的第一眼可判讀性。

### 下一步

1. 若進入分析輪，直接比較 `TWSE_2330_5M` 在 aligned baseline 上的下一個 refinement，不要再重複驗證 market-clock 本身。
2. 若之後還需要更強的 guard，再考慮把這個 baseline 提示升級成流程性 validator，而不是單純 metadata。

## 2026-05-21 分析輪：TWSE aligned baseline 上的 VWAP slope 沒有新增資訊

這輪直接站在台股 canonical baseline `Asia/Taipei 09:00-13:30 aligned` 上，比較：

1. `orb-volume-vwap --orb-reject-ema-inside-range`
2. `orb-volume-vwap --orb-reject-ema-inside-range --orb-vwap-slope-confirmation`

資料集固定為 `TWSE_2330_5M.csv`，因此這輪不再討論 market-clock 本身，而是只回答：**在台股 aligned baseline 上，`VWAP slope` 這個 secondary refinement 有沒有新增辨識力。**

### 比較結果

- 兩組 `hold 1 / 3 / 5 / 10` 的結果完全相同：
  - hold 1：PF `0.513`、Trades `21`、Win rate `23.81%`、Avg net PnL `-7.47`、Max DD `-2.88%`
  - hold 3：PF `0.538`、Trades `21`、Win rate `47.62%`、Avg net PnL `-11.04`、Max DD `-3.52%`
  - hold 5：PF `0.685`、Trades `21`、Win rate `38.10%`、Avg net PnL `-9.07`、Max DD `-4.84%`
  - hold 10：PF `0.309`、Trades `20`、Win rate `30.00%`、Avg net PnL `-35.61`、Max DD `-8.20%`
- `phase` hold 1 artifact 也完全一致：
  - accepted `21`
  - blocked `2266`
  - hold `500`
  - overlap `0`
  - ignored short `0`
  - blocked reasons：`below_or_high(2087)`、`ema_inside_opening_range(86)`、`breakout_volume_blocked(80)`、`volume_warmup(13)`

### 結論

- 對 `TWSE_2330_5M aligned` 這份樣本而言，`VWAP slope` **沒有新增資訊**。
- 這不是「改善很小」，而是 artifact 與回測指標都完全不變；也就是說，在這份樣本上它目前等價於零增量 refinement。
- 因此後續若要繼續用台股 baseline 比較 ORB refinement，優先順序不應再放在 `VWAP slope`，而應：
  1. 直接承認它在台股 aligned baseline 上暫時沒有研究價值；
  2. 或把分析配額轉給其他 refinement / market-specific 假設。

### 產出報表

- `reports/generated/twse-orb-aligned-emabox_hold_comparison.json`
- `reports/generated/twse-orb-aligned-emabox-vslope_hold_comparison.json`
- `reports/generated/twse-orb-aligned-emabox-phase.md`
- `reports/generated/twse-orb-aligned-emabox-vslope-phase.md`

## 2026-05-21 Code Review：台股 aligned baseline 與 zero-increment refinement 後續工程債

這輪是 review-only，不改 ORB trade logic。重點不是再驗一次 `VWAP slope`，而是把 `TWSE_2330_5M aligned baseline` 與 `VWAP slope zero-increment` 之後，還剩哪些真正值得處理的工程債寫清楚。

### Findings

1. **目前只有描述性 baseline guard，還沒有流程性 guard。**
   - `strategy_spec` 已經會標出：
     - `orb_known_sample_market_clock_alignment`
     - `orb_known_sample_market_clock_baseline_note`
   - 但系統目前不會阻止後續分析再次把 `mismatch` 版拿來當台股主結論。
   - 也就是說，baseline 已經「可見」，但還沒有「被流程偏好」。

2. **`VWAP slope` 在台股 aligned baseline 上已是零增量，但這件事仍只存在於研究結論，不在 artifact contract 裡。**
   - 目前我們已經知道：
     - `TWSE_2330_5M aligned`
     - `EMA inside-range`
     - `EMA inside-range + VWAP slope`
     三者比較下，`VWAP slope` 沒有改變 PF、trade count、blocked reasons 或 hold counts。
   - 但 artifact 還沒有一個更短的 machine-readable 提示，能直接說明「這個 refinement 在這個 sample 上目前屬 compare-only / zero-increment」。
   - 是否要把這種 sample-specific 結論寫進 schema，仍屬產品判斷；現階段先不要硬做。

3. **下一步不該再花在 `VWAP slope` 或第三次 market-clock A/B。**
   - 目前已經有足夠證據說明：
     - `TWSE_2330_5M` 必須用 `Asia/Taipei 09:00-13:30 aligned` 當 canonical baseline；
     - 在這個 baseline 上，`VWAP slope` 沒有新增資訊。
   - 因此後續再跑同題，只會增加 docs 噪音，不會增加研究價值。

### 結論

- 台股 ORB 主線目前應固定站在 `aligned baseline` 上看問題。
- `VWAP slope` 在台股 aligned baseline 上，暫時可視為 **compare-only / zero-increment refinement**。
- 下一個值得進入執行輪或分析輪的主題，不應再是 `VWAP slope`；更合理的是：
  1. baseline flow guard；
  2. 其他台股 market-specific refinement；
  3. 或明確承認現有 ORB 主線對台股不夠適配。

### 下一步

1. 若進入執行輪，優先補一個更靠近 CLI / reporting 的 **aligned baseline flow hint**，而不是再加 filter。
2. 若進入研究或分析輪，直接把配額轉去其他台股假設；不要再對 `VWAP slope` 或 market-clock 做同題重跑。

## 2026-05-21 研究輪：public ORB 較偏好 active preset 提示，而不是 hard reject

這輪不研究新 filter，也不回頭重跑 `TWSE_2330_5M` market-clock A/B；只確認一件工程排序問題：**若已知樣本存在 canonical market-clock，下一步應該做 hard validator，還是先做更明顯的 active baseline / flow hint。**

### 外部依據

1. `RAWPIPSFXBYDAN - ORB (Opening Range Breakout)`
   - 腳本直接把 **Market** 當成主設定，並讓這個設定同時驅動 session timezone 與 default windows。
   - 它還提供右上角 **info panel**，直接顯示 active market、market timezone、local timezone 與 resolved windows。
   - 這種設計重點是「把 active preset 說清楚」，而不是在使用者沒對齊時直接阻止運行。

2. `15-Min Opening Range Indicator & Breakout Targets (ORB)- Willy`
   - 腳本同樣把多市場 / 多 session 場景的第一步放在 **local timezone adjustment** 與 **custom start hour/minute**。
   - 這說明 public ORB 通常先解決「你現在看的是哪個市場時鐘」，再談 breakout refinement。

3. TradingView 官方 `Sessions`
   - 官方文件把 session 判定與 `session.isfirstbar_regular` 這種 regular-session 概念當成一級語意。
   - 這支持我們把台股 `09:00-13:30` 視為 canonical baseline。

4. TradingView 官方 `Repainting` / `Other timeframes and data`
   - 官方明確提醒，當腳本開始依賴跨 timeframe / intrabar request 時，repaint 與 realtime / historical 不一致風險會上升。
   - 這也代表目前更低風險的下一步，仍應優先是 **same-session artifact 提示**，而不是再往更重的 previous-day / higher-timeframe family 推進。

### 結論

- 以公開 ORB 腳本的做法來看，SignalForge 下一步若要強化 `TWSE_2330_5M aligned baseline`，較合理的是：
  1. 先做更靠近 CLI / reporting 的 **active baseline flow hint**；
  2. 而不是立刻升級成 hard reject。
- 原因很直接：
  - 我們仍需要保留 `mismatch` run 作為審計與比較證據；
  - 但也不該讓後續讀 artifact 的人忽略 canonical baseline。

### 下一步

1. 若進入執行輪，應優先補一個 **更顯眼但不阻斷流程** 的 aligned baseline 提示。
2. 若未來台股 ORB artifact 仍反覆被誤讀，再考慮把這個提示升級成更強的 validator 或 warning contract。

## 2026-05-21 執行輪：entry-edge markdown 補上 Known Sample Baseline 提示區塊

這輪不改 ORB trade logic，也不把 `mismatch` 升級成 hard reject；只做一個更靠近報表閱讀面的 contract 補強：**當 `strategy_spec` 帶有已知樣本的 market-clock metadata 時，entry-edge 單次報表與 hold comparison 報表都會在 `Strategy Spec (Distilled)` 之前先輸出 `## Known Sample Baseline` 區塊。**

### 本輪修改

1. `src/signal_forge/reporting/_legacy.py`
   - 新增 `_build_known_sample_baseline_lines(...)`
   - 在 `_markdown_report(...)` 與 `_entry_edge_comparison_markdown(...)` 內插入共用 baseline 提示
   - 提示內容固定優先顯示：
     - `orb_known_sample_market_clock_baseline_note`
     - `Current alignment`
     - `Expected market clock`
     - `Interpretation`

2. `tests/test_reporting.py`
   - 新增單次 entry-edge 報表的 known-sample baseline regression
   - 新增 hold comparison 報表的 known-sample baseline regression
   - 既有 exact-text stable contract 測試保持不變，因為 baseline 區塊只在 metadata 存在時才出現

### 驗證結論

- 這次改動只提升 artifact 可讀性，不改變策略語意或回測結果。
- `test_reporting.py` 全部通過，表示：
  - 一般樣本不會被強制插入新區塊
  - `TWSE_2330_5M` 這類已知樣本則能在報表前段直接看見 canonical baseline 提示

### 結論

- 台股 baseline 提示現在不只存在於 `strategy_spec` 的平面 key，也會提升成 entry-edge markdown 的顯式區塊。
- 這讓後續閱讀 `TWSE_2330_5M` 報表時，不必先往下翻到所有 spec key 才知道本次 run 是否對齊 canonical `Asia/Taipei 09:00-13:30`。

### 下一步

1. 若進入分析輪，直接站在 `TWSE_2330_5M aligned` baseline 上比較下一個台股 refinement。
2. 若進入 review 輪，優先檢查是否還需要更強的 flow hint；不要再重跑同題 market-clock 或 `VWAP slope` 驗證。

## 2026-05-21 分析輪：TWSE aligned baseline 上比較 OR average volume baseline

這輪不再回頭驗證 `VWAP slope` 或 market-clock，而是直接站在台股 canonical baseline `Asia/Taipei 09:00-13:30 aligned` 上，比較：

1. `orb-volume-vwap --orb-reject-ema-inside-range`
2. `orb-volume-vwap --orb-reject-ema-inside-range --orb-use-opening-range-volume-baseline`

目標是回答：**`OR average volume baseline` 在台股樣本上，到底是新的有資訊 refinement，還是只是另一個零增量 gate。**

### 比較對象

- Sample：`data/processed/TWSE_2330_5M.csv`
- Baseline：`Asia/Taipei 09:00-13:30 aligned`
- Hold comparison：
  - `reports/generated/twse-orb-aligned-emabox_hold_comparison.json`
  - `reports/generated/twse-orb-aligned-emabox-orvol_hold_comparison.json`
- Phase trace：
  - `reports/generated/twse-orb-aligned-emabox-phase_trace_summary.json`
  - `reports/generated/twse-orb-aligned-emabox-orvol-phase_trace_summary.json`
- 比較報表：
  - `reports/generated/twse-orb-aligned-emabox-orvol-comparison-20260521.md`
  - `reports/generated/twse-orb-aligned-emabox-orvol-comparison-20260521.json`

### Hold comparison

#### EMA inside-range

- hold 1：PF `0.513` / Trades `21` / Avg net PnL `-7.47` / Max DD `-2.88%`
- hold 3：PF `0.538`
- hold 5：PF `0.685`
- hold 10：PF `0.309`

#### EMA inside-range + OR average volume baseline

- hold 1：PF `0.948` / Trades `12` / Avg net PnL `-0.60` / Max DD `-1.16%`
- hold 3：PF `0.369`
- hold 5：PF `0.406`
- hold 10：PF `0.268`

### Phase trace summary 對照

#### EMA inside-range

- accepted：`21`
- blocked：`2266`
- hold：`500`
- blocked reasons：
  - `below_or_high(2087)`
  - `ema_inside_opening_range(86)`
  - `breakout_volume_blocked(80)`
  - `volume_warmup(13)`

#### EMA inside-range + OR average volume baseline

- accepted：`12`
- blocked：`2475`
- hold：`300`
- blocked reasons：
  - `below_or_high(2156)`
  - `breakout_volume_blocked(231)`
  - `ema_inside_opening_range(86)`
  - `breakout_ema_reference_unavailable(2)`

### 關鍵判讀

1. **`OR average volume baseline` 不是零增量 refinement。**
   - 它明顯改變了 trade count、PF 與 blocked reason 分布。
   - 和先前 `VWAP slope` 在台股 aligned baseline 上完全零增量的情況不同。

2. **它明顯改善了最短持有期，但沒有跨 hold 穩定。**
   - hold 1 PF：`0.513 -> 0.948`
   - hold 1 Avg net PnL：`-7.47 -> -0.60`
   - hold 1 Max DD：`-2.88% -> -1.16%`
   - 但 hold 3 / 5 / 10 的 PF 都更差。

3. **它主要是 trade-compression refinement，不是新的結構 gate。**
   - `ema_inside_opening_range` 維持 `86` 不變。
   - 真正大幅上升的是 `breakout_volume_blocked`：`80 -> 231`
   - accepted trades 也從 `21 -> 12`
   - 這表示它主要是在更嚴格地壓縮突破樣本，而不是重新定義 OR 結構。

### 結論

- 在 `TWSE_2330_5M aligned` 上，`OR average volume baseline` 比 `VWAP slope` 更值得研究，因為它確實帶來了新的行為差異。
- 但它目前只對 hold 1 的品質有明顯幫助，還不足以成為跨 hold 穩定的主線改善。
- 因此較合理的定位是：**台股市場特化的 trade-compression refinement 候選**，而不是已經足以把 ORB 主線翻成 `PASS` 的關鍵條件。

### 下一步

1. 若進入 review 輪，應正式整理這個 refinement 的定位：它比 `VWAP slope` 有資訊，但更像短持有期品質優化，不是普適主線。
2. 若進入後續分析輪，新的台股 refinement 應拿來對照它的 tradeoff：`hold 1 quality up` vs `multi-hold robustness down`。

## 2026-05-21 Code Review：台股 OR average volume baseline 後續工程債

### Review 範圍

- 依據上一輪 `TWSE_2330_5M aligned` baseline 比較：
  - `orb-volume-vwap --orb-reject-ema-inside-range`
  - `orb-volume-vwap --orb-reject-ema-inside-range --orb-use-opening-range-volume-baseline`
- 不改策略語意，只整理目前已經回答完的結論應如何落在工程邊界上。

### Findings

1. **`OR average volume baseline` 已有明確非零增量證據，但仍停留在研究結論層。**
   - 它不是像 `VWAP slope` 那樣的零增量 refinement。
   - 目前已知 tradeoff 很清楚：`hold 1 quality up`，但 `hold 3/5/10 robustness down`。
   - 這個定位已經寫進研究紀錄與策略筆記，但還沒有任何 machine-readable artifact contract 去表達它是「台股短持有期品質優化候選」，不是主線改善。

2. **目前只有描述性 baseline / refinement guard，沒有流程性 guard。**
   - `TWSE_2330_5M` 現在已有 aligned baseline note，也已知 `VWAP slope` 是 zero-increment。
   - 但系統仍不會阻止後續分析把 `mismatch` 版或不適當的 refinement 當成台股主結論。
   - 這代表現階段真正穩定的是研究判斷，不是流程約束。

3. **台股後續 refinement 評估標準應該固定化。**
   - 這輪比較後，較合理的 benchmark 已經不是「能不能比 MSFT 好」，而是：
     - 是否優於 `TWSE_2330_5M aligned` baseline
     - 是否優於 `OR average volume baseline` 這個已知的 trade-compression 候選
     - 是否只是用更少交易數換取短 hold 改善
   - 若不先固定這個 benchmark，後面每個台股 refinement 都會重新解釋一次 tradeoff，維護成本偏高。

### 結論

- `OR average volume baseline` 在台股 aligned baseline 上，應暫定為 **market-specific trade-compression refinement candidate**。
- 它目前值得保留在研究比較集合裡，但還不值得升成台股 ORB 主線改善。
- 下一步若要做小修補，應優先補 closer-to-reporting 的 flow hint 或 benchmark note，而不是再回頭做第三次 volume-baseline / market-clock 類驗證。

### 下一步

1. 若進入執行輪，可考慮在 entry-edge / comparison 報表補一個更明確的 benchmark hint，說明台股後續 refinement 應對照 `aligned baseline` 與 `OR average volume baseline`。
2. 若進入研究輪，應轉向新的台股 market-specific refinement，而不是再圍繞 `VWAP slope` 或 market-clock 做重複驗證。

## 2026-05-21 研究：台股下一個較值得測的 refinement 先看 OR retest / re-break confirmation

### 研究問題

在 `TWSE_2330_5M aligned` baseline 上，現在已知：

- `VWAP slope` 是零增量 refinement。
- `OR average volume baseline` 有資訊，但比較像 trade-compression refinement，且只改善 hold 1。

因此本輪研究改問另一題：**下一個更值得測的台股 market-specific refinement，是不是應該先看同 session 的 OR retest / re-break confirmation，而不是直接跳去 previous-day family？**

### 外部參考

- TradingView `Opening Range Retest`：把 OR retest 視為獨立策略，重點是「突破後回測 opening range」再進場，而不是第一次穿越就觸發。它也明講這種邏輯比較適合 regular market open 活躍的 equity open。
- TradingView `Opening Range with Breakouts & Targets`：直接提供 `Confirm Retest`，要求完整 retest 後再 re-break 才發信號，並且特別加入 `session.ismarket` guard，避免 premarket 汙染 OR levels。
- TradingView 官方 `Sessions`：session / regular / subsession 邊界本來就是一級 contract，代表這類 refinement 可以先維持在同 session 內處理，不必一開始就引入 previous-day / HTF 資料。
- TradingView 官方 `Repainting` 與 `Other timeframes and data`：一旦把 refinement 做成 `request.security()` 型 higher-timeframe / previous-day 邏輯，就要額外處理 confirmed-value 與 repaint 風險。

### 研究結論

1. **對目前台股主線來說，OR retest / re-break confirmation 比 previous-day family 更值得先測。**
   - 它直接對準 `TWSE_2330_5M aligned` 現在暴露出的問題：首次突破後 follow-through 弱。
   - 它和 `OR average volume baseline` 一樣，都屬於 trade-compression 類，但更偏向價格結構確認，而不是純量能壓縮。

2. **它的工程風險低於 previous-day family。**
   - 若只用同 session 的 ORH / ORL、已確認 close、以及 breakout 後回測再突破條件，就不必先引入 `prior_day_close_regular_session`、`request.security()` 或 premarket 定義。
   - 這表示它更適合 SignalForge 現在的 deterministic artifact 與 validator 邊界。

3. **它仍然不是無條件推薦，而是下一個較合理的比較候選。**
   - retest confirmation 很可能也會壓縮交易數，和 `OR average volume baseline` 一樣有 tradeoff。
   - 但至少從公開 ORB 腳本來看，這條 refinement 是常見且結構上合理的 follow-through 修補方式。

### 下一步

1. 若進入執行輪，優先把 `OR retest / re-break confirmation` 定義成同 session、confirmed-bar-only 的研究假設，不要先引入 previous-day / higher-timeframe data。
2. 若進入後續分析輪，應直接拿它對照 `TWSE_2330_5M aligned baseline` 與 `OR average volume baseline`，看它是否只是另一種 trade compression，或真的改善 follow-through 品質。

## 2026-05-21 執行：把 OR retest refinement 先收斂成 same-session / confirmed-bar-only contract

### 本輪修改

- `strategy_spec_from_args(...)` 現在會固定輸出 OR retest 的 machine-readable contract：
  - `orb_retest_scope=same_session_only`
  - `orb_retest_signal_basis=confirmed_bar_close_only`
  - `orb_retest_level_reference=opening_range_high_reclaim`
  - `orb_retest_data_family=no_previous_day_or_higher_timeframe_context`
- 新增 `_validate_orb_retest_contract(...)`，直接拒絕 scope、signal basis 或 data family drift。
- 補 direct unit tests，讓 retest hypothesis 在還沒真正變成交易邏輯前，先有 deterministic artifact boundary。

### 為什麼先做這一刀

- 這輪的目標不是直接宣稱 OR retest 一定有 edge，而是先把研究假設鎖在一個低風險、可驗證的工程邊界內。
- 如此一來，後續若真的進入比較輪，至少可以確定我們測的是：
  - 同 session 的 ORH reclaim
  - 收盤確認後才算有效
  - 不混 previous-day / HTF data

### 結論

- OR retest 現在已經從「研究想法」升級成 **可測的 artifact / validator contract**。
- 但它仍不是正式策略績效結論；下一輪若要比較，應站在 `TWSE_2330_5M aligned baseline` 上，直接拿它對照 `aligned baseline` 與 `OR average volume baseline`。

## 2026-05-21 分析：台股 aligned baseline 上的 OR retest / re-break confirmation

這輪直接把 `OR retest / re-break confirmation` 放到 `TWSE_2330_5M` 的 `Asia/Taipei 09:00-13:30 aligned` baseline 上，比較三組：

1. `ORB + EMA inside-range`
2. `ORB + EMA inside-range + OR average volume baseline`
3. `ORB + EMA inside-range + OR retest / re-break confirmation`

### 報表

- `reports/generated/twse-orb-aligned-emabox_hold_comparison.json`
- `reports/generated/twse-orb-aligned-emabox-orvol_hold_comparison.json`
- `reports/generated/twse-orb-aligned-emabox-retest_hold_comparison.json`
- `reports/generated/twse-orb-aligned-emabox-phase_trace_summary.json`
- `reports/generated/twse-orb-aligned-emabox-orvol-phase_trace_summary.json`
- `reports/generated/twse-orb-aligned-emabox-retest-phase_trace_summary.json`
- `reports/generated/twse-orb-aligned-emabox-retest-comparison-20260521.md`
- `reports/generated/twse-orb-aligned-emabox-retest-comparison-20260521.json`

### 結果摘要

#### OR retest / re-break confirmation

- hold 1：PF `0.282` / Trades `10` / Avg net PnL `-10.02` / Max DD `-1.36%`
- hold 3：PF `0.542` / Trades `9` / Avg net PnL `-7.89` / Max DD `-1.31%`
- hold 5：PF `0.198`
- hold 10：PF `0.151`

### Phase trace summary 對照

#### OR retest / re-break confirmation

- accepted：`10`
- blocked：`2652`
- hold：`125`
- blocked reasons：
  - `below_or_high(2236)`
  - `breakout_volume_blocked(240)`
  - `ema_inside_opening_range(102)`
  - `retest_not_touched(29)`
  - `waiting_for_retest_confirmation(29)`
  - `volume_warmup(13)`
  - `breakout_below_vwap(3)`

### 關鍵判讀

1. **OR retest 不是零增量 refinement。**
   - 它明顯新增了 retest-specific blocked states，也把 trades 從 baseline 的 `21` 壓到 `10`。
   - 所以它不像 `VWAP slope`，不是零資訊條件。

2. **它只在 hold 3 勉強貼近 baseline，整體仍偏弱。**
   - hold 1 PF：`0.513 -> 0.282`，更差。
   - hold 3 PF：`0.538 -> 0.542`，只有很小的持平改善，但 trades `21 -> 9`。
   - hold 5 PF：`0.685 -> 0.198`，更差。
   - hold 10 PF：`0.309 -> 0.151`，更差。

3. **它目前也弱於 OR average volume baseline。**
   - hold 1：`0.948 > 0.282`
   - hold 3：雖然 retest 的 PF `0.542` 高於 OR volume baseline 的 `0.369`，但 retest 仍未達 pass，且交易數更少。
   - hold 5 / 10：retest 顯著更差。

### 結論

- 在 `TWSE_2330_5M aligned` baseline 上，`OR retest / re-break confirmation` 比 `VWAP slope` 更有資訊，但目前整體仍弱於 `OR average volume baseline`。
- 它較合理的定位是：**台股過度壓縮型的 compare-only structure refinement 候選**。
- 因此下一步不應把它升成主線改善，而應把後續台股 refinement 的比較基準固定在：
  - `aligned baseline`
  - `OR average volume baseline`

## 2026-05-21 Code Review：台股 OR retest 與 OR average volume baseline 的優先級收斂

### Review 範圍

- `TWSE_2330_5M aligned baseline`
- `ORB + EMA inside-range`
- `ORB + EMA inside-range + OR average volume baseline`
- `ORB + EMA inside-range + OR retest / re-break confirmation`

### Findings

1. **`OR retest` 已證明不是零增量條件，但目前只應停在 compare-only。**
   - 它新增了 `retest_not_touched`、`waiting_for_retest_confirmation` 這類結構性 blocked reason，代表確實有新資訊。
   - 但整體結果仍弱於 `OR average volume baseline`，也沒有把台股主線翻成 `PASS`。

2. **台股目前已出現更清楚的 refinement priority。**
   - `VWAP slope`：zero-increment，已經不值得繼續消耗輪次。
   - `OR retest`：non-zero-increment，但目前過度壓縮，只適合 compare-only。
   - `OR average volume baseline`：雖然仍未 pass，但至少在 hold 1 上有明確品質改善，因此比 retest 更值得保留為下一層 benchmark。

3. **後續台股 refinement 的 benchmark 已經應該固定。**
   - 新 refinement 不應再只對照 `aligned baseline`。
   - 還應同時對照 `OR average volume baseline`，因為它是目前已知最有資訊、但 tradeoff 也最清楚的台股 market-specific 候選。

### 結論

- `OR retest / re-break confirmation` 目前較合理的定位是：**台股過度壓縮型的 compare-only structure refinement 候選**。
- `OR average volume baseline` 則應暫時保留為台股 refinement benchmark，而不是直接當成主線改善。
- 因此下一步若要做小修補，較合理的是在 comparison / reporting 補 benchmark hint，而不是再回頭對 retest 本身做新的 artifact surface 擴張。

### 下一步

1. 若進入執行輪，可考慮在台股 comparison 報表補一個更明確的 benchmark hint，說明新 refinement 應同時對照 `aligned baseline` 與 `OR average volume baseline`。
2. 若進入研究輪，應轉向新的台股 market-specific refinement，而不是再把 `OR retest` 升格成主線候選。

## 2026-05-21 研究：公開 ORB 腳本通常把 retest 放在較保守的 entry style，而不是 baseline 主線

### 研究問題

在 `TWSE_2330_5M aligned` 上，我們已知：

- `OR retest / re-break confirmation` 不是零增量，但整體弱於 `OR average volume baseline`。
- `OR average volume baseline` 雖未翻成 pass，但至少是目前更有資訊的台股 benchmark。

本輪研究想確認：**公開 ORB 腳本通常如何定位 retest？它更像 baseline 主線，還是較保守的 entry style / confirmation mode？**

### 外部參考

- TradingView `RPFXBYDAN - ORB`：把 breakout trigger modes 與 optional retest filter 一起放在可切換的 signal mode，而不是把 retest 當唯一主線。
- TradingView `NeuraEdge ORB - Opening Range Breakout Indicator`：明確把 `Retest Mode` 描述成「先突破、再回踩觸碰 range level 後才進場」的較保守模式。
- 多篇公開 ORB 腳本與討論都把 retest 放在 classic breakout / pullback / retest setup 的同層切換關係，而不是先驗預設。
- TradingView 官方 `Sessions` 仍支持先把 session / market-clock 定義成一級 contract，再談 entry style 的嚴格度差異。

### 研究結論

1. **公開 ORB 腳本更常把 retest 視為較保守的 entry style，而不是 baseline 主線。**
   - 這代表目前 SignalForge 在台股上把 retest 放在 compare-only / confirmation 候選，方向是合理的。

2. **這也支持我們目前的台股排序。**
   - `aligned baseline`：主比較基準。
   - `OR average volume baseline`：目前更有資訊的台股 trade-compression benchmark。
   - `OR retest`：較保守的結構確認 style，暫不應升成主線改善。

3. **因此下一步若要補工程提示，比較合理的是 benchmark / mode hint，而不是再把 retest 往主線 schema 推。**
   - 對台股報表來說，更需要的是讓人看懂「這是 baseline、benchmark、還是 compare-only entry style」，而不是再增加一層 retest surface。

### 下一步

1. 若進入執行輪，可優先補 comparison / reporting 的 benchmark hint，把台股 refinement 分成 baseline、benchmark、compare-only style。
2. 若進入後續研究輪，新的台股 refinement 應優先對照 `aligned baseline` 與 `OR average volume baseline`，不要再把 retest 當主線優先候選。

## 2026-05-21 執行：在 entry-edge markdown 補台股 refinement benchmark hint

### 本輪修改

- 在 entry-edge 單次報表與 hold comparison markdown 中，沿用既有 `TWSE_2330_5M` known-sample market-clock metadata，再補一層 `TWSE Refinement Benchmark` 區塊。
- 這個區塊不新增策略語意，只用既有 `strategy_spec` 推導：
  - `TWSE_2330_5M aligned baseline` 是主比較基準
  - `OR average volume baseline` 是目前台股 refinement benchmark
  - `OR retest / re-break confirmation` 仍是 compare-only entry style 候選

### 為什麼先做這個

- 目前 repo 已經有：
  - canonical baseline note
  - aligned / mismatch metadata
  - `OR average volume baseline` 與 `OR retest` 的研究排序
- 缺的是更靠近 artifact 的提示，讓後續閱讀單次報表或 hold comparison 時，不用回頭翻長篇研究筆記才知道台股 refinement 應該怎麼解讀。

### 驗證

- readiness score：`110`
- unit tests：`139 tests OK`
- `git diff --check`：clean

### 結論

- 這輪是 **reporting contract 補強**，不是策略邏輯更新。
- 後續新的台股 refinement，應直接對照：
  - `TWSE_2330_5M aligned baseline`
  - `OR average volume baseline`
- 不應再把 `OR retest` 或 `VWAP slope` 當成同優先級主線候選。

## 2026-05-21 分析：台股 aligned baseline 上的 OR full bar above range

這輪直接把另一個同 session、confirmed-bar-only 的結構 refinement 放到 `TWSE_2330_5M` 的 `Asia/Taipei 09:00-13:30 aligned` baseline 上，比較三組：

1. `ORB + EMA inside-range`
2. `ORB + EMA inside-range + OR average volume baseline`
3. `ORB + EMA inside-range + full bar above range`

### 報表

- `reports/generated/twse-orb-aligned-emabox_hold_comparison.json`
- `reports/generated/twse-orb-aligned-emabox-orvol_hold_comparison.json`
- `reports/generated/twse-orb-aligned-emabox-fullbar_hold_comparison.json`
- `reports/generated/twse-orb-aligned-emabox-phase_trace_summary.json`
- `reports/generated/twse-orb-aligned-emabox-orvol-phase_trace_summary.json`
- `reports/generated/twse-orb-aligned-emabox-fullbar-phase_trace_summary.json`
- `reports/generated/twse-orb-aligned-emabox-fullbar-comparison-20260521.md`
- `reports/generated/twse-orb-aligned-emabox-fullbar-comparison-20260521.json`

### 結果摘要

#### OR full bar above range

- hold 1：PF `1.672` / Trades `15` / Avg net PnL `5.14` / Max DD `-0.74%`
- hold 3：PF `0.511`
- hold 5：PF `0.788`
- hold 10：PF `0.778`

### Phase trace summary 對照

#### OR full bar above range

- accepted：`15`
- blocked：`2510`
- hold：`262`
- blocked reasons：
  - `below_or_high(2228)`
  - `breakout_bar_reentered_range(131)`
  - `breakout_volume_blocked(91)`
  - `ema_inside_opening_range(44)`
  - `volume_warmup(13)`
  - `breakout_below_vwap(3)`

### 關鍵判讀

1. **`full bar above range` 不是零增量 refinement。**
   - 它引入了 `breakout_bar_reentered_range(131)` 這個新的結構性 blocked reason。
   - accepted trades 也從 baseline 的 `21` 壓到 `15`。

2. **它是目前第一個把台股 hold 1 直接翻成 `PASS` 的 refinement。**
   - hold 1 PF：`0.513 -> 1.672`
   - hold 1 Avg net PnL：`-7.47 -> 5.14`
   - hold 1 Max DD：`-2.88% -> -0.74%`

3. **它比 `OR average volume baseline` 更像結構改善，而不是單純 trade compression。**
   - `breakout_volume_blocked` 只小幅從 `80 -> 91`
   - `ema_inside_opening_range` 反而從 `86 -> 44`
   - 代表它主要是在過濾「突破 K 棒又回踩回區間內」的弱 follow-through，而不是只靠量能把交易數壓掉

4. **它對較長 hold 也比目前 benchmark 更有韌性。**
   - hold 5 PF：`0.685 -> 0.788`
   - hold 10 PF：`0.309 -> 0.778`
   - 雖然還沒翻成 pass，但明顯優於 `OR average volume baseline`

### 結論

- 在 `TWSE_2330_5M aligned` baseline 上，`full bar above range` 是目前測到最強的台股 ORB refinement 候選。
- 它不只改善 hold 1，還讓 hold 5 / 10 的品質明顯優於 baseline 與 `OR average volume baseline`。
- 這輪先把它定性成：**目前最強、但尚未完成跨 hold 穩定化的台股結構 refinement 候選**。
- 是否要讓它正式取代 `OR average volume baseline` 成為後續台股 benchmark，留到下一輪 review 再收斂。

### 下一步

1. 若進入 review 輪，優先決定 `full bar above range` 是否應升成新的台股 refinement benchmark。
2. 若進入後續分析輪，新的台股 refinement 應同時對照：
   - `aligned baseline`
   - `full bar above range`
   - `OR average volume baseline`

## 2026-05-21 分析：台股 aligned baseline 上 full bar 與 OR average volume baseline 的疊加效果

### 比較問題

前一輪已經知道：

- `full bar above range` 是目前最強的台股結構 refinement 候選
- `OR average volume baseline` 是次層的 trade-compression benchmark

這輪要回答的是更直接的組合問題：

- 若把兩者疊加在 `TWSE_2330_5M` 的 `Asia/Taipei 09:00-13:30 aligned` baseline 上，
- 這是互補，還是只會把 `full bar above range` 的優勢再壓掉？

### 比較對象

同一份資料：

- `data/processed/TWSE_2330_5M.csv`

同一個台股 canonical market clock：

- `Asia/Taipei 09:00-13:30`

比較三組既有 benchmark / 候選：

1. `ORB + EMA inside-range`
2. `ORB + EMA inside-range + full bar above range`
3. `ORB + EMA inside-range + full bar above range + OR average volume baseline`

### 主要結果

#### 1. 疊加後不是退化，而是目前最強的台股 ORB 組合

`full bar above range + OR average volume baseline` 的結果如下：

- hold 1：PF `6.525`、Trades `8`、Avg net PnL `13.88`、Max DD `-0.12%`、`PASS`
- hold 3：PF `2.259`、Trades `8`、Avg net PnL `39.15`、Max DD `-2.25%`、`PASS`
- hold 5：PF `1.374`、Trades `8`、Avg net PnL `21.06`、Max DD `-2.25%`、`PASS`
- hold 10：PF `1.099`、Trades `8`、Avg net PnL `6.73`、Max DD `-2.94%`、`FAIL`

和既有兩組 benchmark 比：

- baseline hold 1 PF：`0.513`
- `full bar above range` hold 1 PF：`1.672`
- `full bar + OR volume baseline` hold 1 PF：`6.525`

這表示 OR volume baseline 在 full-bar 結構確認之後，不是把 edge 再壓掉，而是把台股短持有期與中短持有期一起明顯拉高。

#### 2. 這不只是 trade compression，因為改善已經跨到 hold 3 / 5

若它只是更嚴格地砍掉交易數，通常會看到：

- hold 1 改善
- 但 hold 3 / 5 仍維持弱勢或直接惡化

這次不是這個形狀：

- hold 1：`PASS`
- hold 3：`PASS`
- hold 5：`PASS`
- hold 10：雖然仍 `FAIL`，但 PF 也已經從 baseline 的 `0.309` 拉到 `1.099`

因此這一組比較像：

- `full bar above range` 先處理假突破與 re-entry 結構問題
- `OR average volume baseline` 再把剩下的低品質量能突破壓掉

兩者在台股樣本上呈現的是**結構確認 + 量能確認的互補**，不是單純重複過濾。

#### 3. phase blocked reasons 也支持「互補」而不是「重複」

phase hold 1 的主要 blocked reasons：

- `below_or_high(2251)`
- `breakout_volume_blocked(228)`
- `breakout_bar_reentered_range(141)`
- `ema_inside_opening_range(44)`

和單獨 `full bar above range` 比較：

- `breakout_bar_reentered_range`：`131 -> 141`
- `breakout_volume_blocked`：`91 -> 228`
- `ema_inside_opening_range`：維持低檔 `44`

這代表：

- full-bar 仍主要負責結構確認
- OR volume baseline 則明確加重了量能壓縮
- 兩個 blocked family 並沒有互相取代，而是一起保留下來

### 研究結論

1. **`full bar above range + OR average volume baseline` 是目前台股 aligned baseline 上最強的已測組合。**
   - 它不只優於 baseline，也優於單獨的 `full bar above range` 與單獨的 `OR average volume baseline`。

2. **`OR average volume baseline` 不應再只被視為 full-bar 之下的弱 benchmark。**
   - 單獨看時，它是次層 trade-compression benchmark。
   - 但和 `full bar above range` 疊加時，它又回到有實質增量的互補 refinement。

3. **台股 ORB 的目前排序要再精煉成「baseline / primary refinement / stacked refinement」三層。**
   - `aligned baseline`
   - `full bar above range`
   - `full bar above range + OR average volume baseline`
   - `OR average volume baseline`
   - `OR retest`

### 下一步

1. 下一輪若進入 review，應先判斷：`full bar + OR volume baseline` 是否值得升成台股新的主 benchmark。
2. 下一輪若進入執行或分析，新的台股 refinement 應至少同時對照：
   - `aligned baseline`
   - `full bar above range`
   - `full bar above range + OR average volume baseline`

## 2026-05-21 Code Review：台股 stacked refinement benchmark 與 reporting hint 對齊檢查

### Review 範圍

- `TWSE_2330_5M aligned baseline`
- `ORB + EMA inside-range`
- `ORB + EMA inside-range + full bar above range`
- `ORB + EMA inside-range + full bar above range + OR average volume baseline`
- `TWSE Refinement Benchmark` reporting hint
- `reports/generated/twse-orb-aligned-emabox-fullbar-orvol-comparison-20260521.*`

### Findings

1. **目前台股 benchmark hint 已落後於最新比較結果。**
   - 目前 hint 仍把 `full bar above range` 放在 primary structural benchmark，`OR average volume baseline` 放在 secondary trade-compression benchmark。
   - 但最新比較已經顯示：`full bar + OR average volume baseline` 才是目前最強的台股已測組合，且 hold `1 / 3 / 5` 全部 `PASS`。
   - 受影響檔案：
     - `src/signal_forge/reporting/_legacy.py`
     - `tests/test_reporting.py`
     - `docs/策略筆記/ORB + Volume + VWAP.md`
   - 建議修法：把台股 benchmark 解讀從二層改成三層：
     1. `aligned baseline`
     2. `full bar above range`
     3. `full bar above range + OR average volume baseline`

2. **目前 reporting surface 還沒有 machine-readable 的 stacked refinement 位階。**
   - 報表可以靠 prose hint 解讀出「stacked version 最強」，但 `strategy_spec` 內沒有對應的 benchmark tier / mode 語意。
   - 這不是 bug，但它表示目前 benchmark 順序仍主要靠文案維持，一旦 comparison hint 沒更新，就容易和 canonical 結論脫節。
   - 受影響檔案：
     - `src/signal_forge/reporting/_legacy.py`
     - `reports/generated/*twse*`
   - 建議修法：下一輪若做執行，只先補 reporting / comparison hint；不要在沒有產品判斷前擴新 schema。

3. **`OR average volume baseline` 的角色需要再細分。**
   - 單獨使用時，它是次層 trade-compression benchmark。
   - 和 `full bar above range` 疊加時，它又變成有明顯增量的互補 refinement。
   - 這表示它不能再用單一標籤概括；至少在台股目前研究脈絡裡，要明確區分：
     - standalone benchmark
     - stacked complementary refinement
   - 建議修法：review 後續的 comparison hint 時，明確把 standalone 與 stacked 版本拆開描述。

### 結論

- 這輪 review 的主要結論是：**台股 ORB 的 reporting / comparison hint 已經需要從「單一主 benchmark」升級成「stacked benchmark 優先」的解讀順序。**
- 但這仍屬於 reporting contract 調整，不該在 review 輪順手改策略語意。
- 目前較合理的台股排序是：
  1. `aligned baseline`
  2. `full bar above range`
  3. `full bar above range + OR average volume baseline`
  4. `OR average volume baseline`
  5. `OR retest`

### 下一步

1. 若進入執行輪，優先更新 `TWSE Refinement Benchmark` hint，讓 stacked refinement 成為新的主 benchmark 提示。
2. 若進入研究或分析輪，新的台股 refinement 應至少同時對照：
   - `aligned baseline`
   - `full bar above range`
   - `full bar above range + OR average volume baseline`

## 2026-05-21 研究：公開 ORB 腳本如何呈現 stacked filter 組合

### 研究問題

台股這條線目前已經出現一個新的情況：

- `full bar above range` 單獨使用時，已是高優先級 structural benchmark
- `full bar above range + OR average volume baseline` 疊加後，又成為目前最強的已測組合

這輪要回答的問題不是「哪個回測數字比較好」，而是更接近報表設計：

- 公開 ORB 腳本通常怎麼呈現這種 **多個 confirmation filter 疊加** 的狀態？
- 它們是只保留一個主 benchmark 名稱，
- 還是會直接把目前啟用的 filter 組合視為一個 active profile / max-filter mode？

### 外部依據

1. TradingView `ORB Breakout Strategy with VWAP and Volume Filters`
   - 明確寫出這些 filters 是「designed to work together as a unified entry system」。
   - inputs 也把 filter 視為可 individually enabled / disabled 的組合，而不是只保留單一主條件。

2. TradingView `ORB Breakout`
   - 直接把 breakout signal 定義成多條件同時成立：
     - body closes above OR high
     - volume ≥ OR average volume
     - price above VWAP
     - within signal window
   - 這類寫法本質上就是把結構、量能、VWAP 視為一個 active entry profile。

3. TradingView `Opening Range Breakout + VWAP + Volume [ORB Strategy]`
   - 直接列出 `FILTER COMBINATIONS`：
     - ORB only
     - ORB + VWAP
     - ORB + Volume
     - ORB + VWAP + Volume
   - 並明示 `ORB + VWAP + Volume` 是 `maximum filter (recommended)`。
   - 同時提供 dashboard 顯示 filter status 與 session state。

4. TradingView 官方 `Repainting`
   - 再次支持：若要把 confirmation profile 做成可研究、可重跑的組合，應優先建立在 confirmed-bar-only 的邊界上，而不是偷混未確認資料或 higher-timeframe context。

### 研究結論

1. **公開 ORB 腳本更常把 stacked filters 視為 active confirmation profile，而不是只保留一個單點 benchmark 名稱。**
   - 也就是說，使用者看到的不是「volume 是主 benchmark、full bar 是次要條件」，
   - 而是「目前啟用了哪幾個 filters」。

2. **這和台股目前的本地結果一致。**
   - `full bar above range` 已經有獨立資訊量；
   - `OR average volume baseline` 疊在它上面時，又產生新的增量；
   - 因此 reporting 更合理的做法，不是只替換掉舊 benchmark，而是把 `full bar + OR volume baseline` 明確視為一個新的 active refinement profile。

3. **對 SignalForge 的較合理下一步，不是再擴 schema，而是先讓 hint 文案升級成「benchmark + stacked profile」雙層解讀。**
   - `aligned baseline`
   - `full bar above range`：primary structural benchmark
   - `full bar above range + OR average volume baseline`：current strongest stacked profile
   - `OR average volume baseline`：standalone trade-compression benchmark
   - `OR retest`：compare-only style

### 下一步

1. 若進入執行輪，優先更新 `TWSE Refinement Benchmark` 或相關 reporting hint，讓 stacked profile 被明確標成目前最強的 active Taiwan refinement 組合。
2. 若進入分析輪，新的台股 refinement 應至少同時對照：
   - `aligned baseline`
   - `full bar above range`
   - `full bar above range + OR average volume baseline`

## 2026-05-21 分析：台股 aligned baseline 上 breakout body strength 是否能補到 stacked profile 的新資訊

### 比較問題

前一輪已經收斂出：`full bar above range + OR average volume baseline` 是目前最強的台股 ORB 已測組合。這輪要回答的問題是：

- 若再疊一層 `breakout body strength`，也就是要求 breakout candle body / full range 至少達到 `0.60`，
- 它到底是在補新的結構資訊，
- 還是只是把目前最強的 stacked profile 壓得更少、更慢？

### 比較對象

同一份資料：

- `data/processed/TWSE_2330_5M.csv`

同一個 canonical market clock：

- `Asia/Taipei 09:00-13:30`

比較三組：

1. `ORB + EMA inside-range`
2. `ORB + EMA inside-range + full bar above range + OR average volume baseline`
3. `ORB + EMA inside-range + full bar above range + OR average volume baseline + breakout body strength 0.60`

### 主要結果

#### 1. body strength 0.60 不是零增量 refinement

- hold 1 PF：`6.525 -> 8.426`
- trades：`8 -> 4`
- avg net PnL：`13.88 -> 14.95`
- max DD：`-0.12% -> -0.08%`

這表示它不是完全冗餘。它確實新增了自己的結構 gate，並把最短持有期的突破品質再往上拉。

#### 2. 但它把目前最強的 stacked profile 壓得太狠

相對於 `full bar + OR average volume baseline`：

- hold 3 PF：`2.259 -> 0.584`
- hold 5 PF：`1.374 -> 0.081`
- hold 10 PF：`1.099 -> 0.176`

也就是說，它只改善 hold 1，卻把 hold 3 / 5 / 10 全部拉回明顯 `FAIL`。這不是我們目前想要的台股 benchmark 形狀。

#### 3. 新增的主要 blocked family 是 body 結構，不是量能重複過濾

phase hold 1 blocked reasons：

- `full bar + OR volume baseline`
  - `below_or_high(2251)`
  - `breakout_volume_blocked(228)`
  - `breakout_bar_reentered_range(141)`
- `+ body strength 0.60`
  - `below_or_high(2251)`
  - `breakout_body_too_small(201)`
  - `breakout_bar_reentered_range(141)`
  - `breakout_volume_blocked(81)`

這表示新的門檻主要是在擋掉「突破 body 不夠紮實」的 K 棒，而不是單純重複既有的 volume baseline。

### 結論

1. `breakout body strength 0.60` 是 **non-zero-increment** refinement。
2. 但它目前更像 **over-compressive structure refinement**，而不是新的主 benchmark。
3. 所以台股 ORB 的排序目前應維持：
   1. `aligned baseline`
   2. `full bar above range`
   3. `full bar above range + OR average volume baseline`
   4. `OR average volume baseline`
   5. `OR retest`
   6. `breakout body strength 0.60`（compare-only）

### 下一步

1. 後續若測新的台股 refinement，仍應固定同時對照：
   - `aligned baseline`
   - `full bar above range`
   - `full bar above range + OR average volume baseline`
2. `breakout body strength 0.60` 暫時不升成主 benchmark，只保留 compare-only 位置。

## 2026-05-21 Code Review：台股 full bar above range 與現有 benchmark 的優先級收斂

### Review 範圍

- `TWSE_2330_5M aligned baseline`
- `ORB + EMA inside-range`
- `ORB + EMA inside-range + full bar above range`
- `ORB + EMA inside-range + OR average volume baseline`
- 最近幾輪新增的 benchmark / baseline hint 與 comparison 報表

### Findings

1. **`full bar above range` 已經超過「只是另一個 compare-only 候選」的門檻。**
   - 它不只在 hold 1 翻成 `PASS`，還讓 hold 5 / 10 明顯優於目前 baseline 與 `OR average volume baseline`。
   - 這代表它的角色已經不該再和 `OR retest` 放在同一個層級討論。

2. **目前 repo 的台股 benchmark 提示仍偏描述性，還沒有把新優先級寫進 machine-readable contract。**
   - `TWSE Refinement Benchmark` 區塊目前仍把 `OR average volume baseline` 當成主要 benchmark。
   - 但最新比較已顯示，若後續還沿用舊 hint，會低估 `full bar above range` 的研究優先級。

3. **`OR average volume baseline` 的角色需要降級成次層 benchmark，而不是主 benchmark。**
   - 它仍有資訊價值，因為 hold 1 的品質改善與 trade-compression tradeoff 很清楚。
   - 但在 `full bar above range` 已出現後，它更適合當成「量能壓縮型對照組」，而不是台股主 benchmark。

4. **`OR retest` 的定位現在更清楚了。**
   - `VWAP slope`：zero-increment
   - `OR retest`：non-zero-increment，但仍是 compare-only style
   - `OR average volume baseline`：次層 trade-compression benchmark
   - `full bar above range`：目前最強的台股結構 refinement 候選

### 結論

- 這輪 review 的主要結論是：**`full bar above range` 應該升成新的台股 refinement benchmark 候選第一順位**。
- 但因為這牽涉 benchmark hint / reporting 文案與後續比較流程，這輪先只記錄，不在 review 輪順手改 artifact contract。
- 下一輪若進入執行，最合理的是更新 comparison / reporting hint，讓台股 refinement 的解讀順序變成：
  1. `aligned baseline`
  2. `full bar above range`
  3. `OR average volume baseline`
  4. `OR retest`

### 下一步

1. 若進入執行輪，優先更新台股 benchmark hint，把 `full bar above range` 提升成主要 benchmark。
2. 若進入研究或分析輪，新的台股 refinement 應直接同時對照：
   - `aligned baseline`
   - `full bar above range`
   - `OR average volume baseline`

## 2026-05-21 執行：把台股 refinement benchmark hint 升級為 full bar above range 優先

### 本輪修改

- `TWSE Refinement Benchmark` 區塊現在改以 `full bar above range` 為台股 ORB 的 **primary structural benchmark**。
- `OR average volume baseline` 從原本的主 benchmark，降成 **secondary trade-compression benchmark**。
- `OR retest` 則維持 **compare-only entry style**，不再和 benchmark 同層解讀。
- 這輪同時補了一個新的 exact-text regression，直接鎖住 `full bar above range` 路徑的 benchmark hint。

### 為什麼要改

- 前一輪 review 已經收斂出：`full bar above range` 不只讓 hold 1 直接翻成 `PASS`，也比 `OR average volume baseline` 更像結構改善，而不是單純壓縮交易數。
- 若報表仍沿用舊的 benchmark hint，後續台股 refinement 會繼續把 `OR average volume baseline` 誤讀成第一優先 benchmark，和最新比較結果不一致。

### 結論

- 這輪是 **comparison / reporting contract 對齊最新研究結論**，不改策略 trade logic。
- 台股 ORB 的報表解讀順序現在應固定為：
  1. `aligned baseline`
  2. `full bar above range`
  3. `OR average volume baseline`
  4. `OR retest`

### 下一步

1. 若進入分析輪，新的台股 refinement 應直接同時對照：
   - `aligned baseline`
   - `full bar above range`
   - `OR average volume baseline`
2. 若進入 review 輪，應檢查這個 benchmark hint 是否已經足夠穩定，不必再擴 machine-readable schema。

## 2026-05-21 執行：把台股 refinement hint 升級成 benchmark + stacked profile

### 本輪修改

- `TWSE Refinement Benchmark` 區塊不再只停在單一 benchmark 排序，而是明確拆成兩層：
  - `full bar above range`：standalone primary structural benchmark
  - `full bar above range + OR average volume baseline`：目前最強的 stacked profile
- 若本次 run 已同時啟用 `full bar above range` 與 `OR average volume baseline`，報表會直接提示這是目前最強的台股已測組合，並要求先對照 `aligned baseline`，再對照單獨的 `full bar above range`。
- 這輪只改 reporting contract 與 exact-text regression，不改策略 trade logic。

### 為什麼要改

- 前一輪研究已經收斂出：公開 ORB 腳本在多個 confirmation filter 疊加時，更常把它們呈現成 **active confirmation profile**，而不是只保留一個單點 benchmark 名稱。
- 本地結果也已經證明：
  - `full bar above range` 是高優先級 structural benchmark
  - `full bar above range + OR average volume baseline` 又進一步成為目前最強的台股已測組合
- 如果 hint 仍只保留單層 benchmark，後續讀報表的人會看不出 stacked profile 已經有獨立的解讀地位。

### 結論

- 台股 ORB 的 comparison / reporting hint 現在應固定用以下順序理解：
  1. `aligned baseline`
  2. `full bar above range`
  3. `full bar above range + OR average volume baseline`
  4. `OR average volume baseline`
  5. `OR retest`
- 這是 **報表解讀順序** 的升級，不是 machine-readable schema 擴張，也不是策略語意變更。

### 下一步

1. 若進入分析輪，新的台股 refinement 應至少同時對照：
   - `aligned baseline`
   - `full bar above range`
   - `full bar above range + OR average volume baseline`
2. 若進入 review 輪，應檢查這個雙層 hint 是否已足夠穩定，暫時不必再擴成更重的 schema。

## 2026-05-21 研究：公開 ORB 腳本如何定位 full bar / close-confirmation breakout

### 研究問題

在 `TWSE_2330_5M aligned` 上，`full bar above range` 已經是目前最強的台股 ORB refinement 候選。這輪要回答的不是它在本地回測有沒有 edge，而是另一個更根本的定位問題：

- 公開 ORB 腳本通常把這種 **full bar / close-confirmation breakout** 放在哪個層級？
- 它比較像：
  - 和 volume baseline 同類的附加 filter
  - 還是更接近 breakout qualification / confirmation mode？

### 外部依據

- TradingView `[CT] ORB Suite` 明確把 breakout qualification 做成可切換規則，包含 `body cross`、`close cross`、以及 `close above or below the range boundary`，重點是用更嚴格的 breakout confirmation 取代單純 touch logic。
- TradingView `ORB 15min: Break & Confirm` 則要求：先有 breakout，再由另一根 K 棒 **收在 breakout candle 高點上方** 才算確認，並且可再疊加 VWAP / EMA。
- TradingView 官方 `Repainting` 文件明講：若要避免 repaint，就必須接受 **只用 confirmed values** 的延遲成本。
- TradingView 官方 `Sessions` 文件也支持把 session / timezone 當成顯式 contract，讓 breakout qualification 建立在先定義好的 market-clock 上，而不是先跳去 higher-timeframe 或 previous-day data。

### 研究結論

1. **公開 ORB 腳本通常把 full bar / close-confirmation 視為 breakout qualification 或 confirmation mode。**
   - 它的核心工作是提高 breakout 本身的成立門檻。
   - 它不是單純以 volume 壓縮交易數的替代方案。

2. **這和目前台股樣本的表現是對齊的。**
   - `full bar above range` 新增的關鍵 blocked reason 是 `breakout_bar_reentered_range`，表示它主要在處理「突破 K 棒又掉回 OR 盒子內」的弱 follow-through。
   - 這種行為邏輯比 `OR average volume baseline` 更接近結構確認，而不是量能 compression。

3. **因此它現在升成台股 benchmark 第一順位，是有外部邏輯支撐的。**
   - `OR average volume baseline` 仍有資訊價值，但較像次層 trade-compression benchmark。
   - `OR retest` 則更像保守的 compare-only entry style。

### 對目前主線的影響

- 台股 ORB 的較合理排序目前可固定為：
  1. `aligned baseline`
  2. `full bar above range`
  3. `OR average volume baseline`
  4. `OR retest`
- 下一步若要補工程提示，應優先補 **benchmark / mode hint**，幫使用者看懂 `full bar above range` 是高優先級 breakout qualification，而不是再回頭重跑 volume / retest 類舊題。

### 下一步

1. 若進入執行輪，可考慮把台股 comparison / reporting hint 改成以 `full bar above range` 為主要 benchmark。
2. 若進入後續分析輪，新的台股 refinement 應同時對照：
   - `aligned baseline`
   - `full bar above range`
   - `OR average volume baseline`

## 2026-05-21 Review：台股 body strength 與 stacked profile 的位階收斂

### Findings

1. **Severity: medium — `breakout body strength 0.60` 不應升成台股主 benchmark。**
   - 在 `TWSE_2330_5M aligned` 上，它雖然把 hold 1 PF 從 `6.525` 拉到 `8.426`，但 trades 也從 `8` 壓到 `4`。
   - 更重要的是，它會把較長持有期明顯拉壞：hold 3 `2.259 -> 0.584`、hold 5 `1.374 -> 0.081`、hold 10 `1.099 -> 0.176`。
   - **受影響檔案：** `docs/04-實驗記錄/Autoresearch 實驗記錄.md`、`docs/策略筆記/ORB + Volume + VWAP.md`
   - **建議修法：** 維持它的 compare-only structure refinement 定位，不要把它推進 comparison hint 的主 benchmark 階層。

2. **Severity: medium — 台股後續比較基準應固定為三層，而不是只對照單一 baseline。**
   - 目前最穩定的比較骨架已經不是單純 `aligned baseline -> full bar above range`，而是：
     1. `aligned baseline`
     2. `full bar above range`
     3. `full bar above range + OR average volume baseline`
   - 若後續新 refinement 沒有同時對照這三層，結論很容易誤把「單獨有效」和「只在疊加 profile 裡有效」混在一起。
   - **受影響檔案：** `src/signal_forge/reporting/_legacy.py`、`tests/test_reporting.py`
   - **建議修法：** 後續比較與提示都固定以這三層作為台股 canonical anchors，暫時不再擴更重的 machine-readable schema。

3. **Severity: low — 目前的雙層 reporting hint 已足夠，但需要持續和 canonical 結論同步。**
   - 現有 `benchmark + stacked profile` 提示已經能表達：
     - `full bar above range` 是 primary structural benchmark
     - `full bar above range + OR average volume baseline` 是目前最強 stacked profile
   - 真正的風險不是 hint 太弱，而是後續若 benchmark 排序再變，hint 可能再度落後於研究結論。
   - **受影響檔案：** `src/signal_forge/reporting/_legacy.py`、`tests/test_reporting.py`、`docs/04-實驗記錄/Autoresearch 實驗記錄.md`
   - **建議修法：** 下一個 review 輪優先檢查 hint 與 canonical 排序是否一致，而不是再為 `body strength` 重跑同型 A/B。

### 結論

- `breakout body strength 0.60` 目前可明確定性為 **compare-only structure refinement**。
- `full bar above range + OR average volume baseline` 則仍是目前最強的台股已測 stacked profile。
- 因此後續新的台股 refinement，應固定同時對照：
  1. `aligned baseline`
  2. `full bar above range`
  3. `full bar above range + OR average volume baseline`

### 下一步

1. 若進入執行輪，優先檢查 reporting / comparison hint 是否已完整反映這三層基準。
2. 若進入分析輪，新的台股 refinement 不再和 `breakout body strength 0.60` 爭 benchmark 位階，而是直接對照上述三層 canonical anchors。

## 2026-05-21 研究：台股下一個較值得測的 refinement 應先看 signal window / one-and-done

### 研究問題

在 `TWSE_2330_5M aligned` 上，`full bar above range + OR average volume baseline` 已經成為目前最強的已測 stacked profile。這時如果還要找下一個台股 market-specific refinement，較合理的優先順序是什麼？

### 外部依據

- 多個公開 ORB 腳本都把 **signal window / only first breakout / one trade per session** 放在和 breakout qualification 並列的一級設定，而不是額外的高階資料家族：
  - `Opening Range Breakout (ORB)`：明確有 **time window** 與 OR 大小 filter。
  - `Session Opening Range Breakout (ORBO)`：明確有 **time filters**，只在某些時段內允許 breakout。
  - `ORB (Opening Range Breakout)`：有 **one-signal-per-side-per-day guard** 與 optional retest filter。
  - `ORB Opening Range Breakout LliterH`：明確有 **signal window**，限制在 OR 結束後的一段時間內才接受 breakout。
  - `ORB SESSIONS`：有 **max trades/session**、cooldown 與 `bars inside ORB` 類似 re-arm 條件。

### 研究結論

1. **台股下一個較值得測的 refinement，不是先跳去 previous-day family，而是先看 signal window / one-and-done。**
   - 這個方向仍在 same-session 範圍內。
   - 不需要引入 `request.security()`、prior-day scalar、premarket 定義或 higher-timeframe context。

2. **這個候選和目前台股樣本的問題更貼近。**
   - 現在最強的台股 stacked profile 已經能把 hold `1 / 3 / 5` 翻成 `PASS`，但它仍可能保留過晚 breakout 或同 session 後段的弱 follow-through。
   - signal window / one-and-done 比較像在處理「何時不該再追」的 session 內風險，而不是再對單根 breakout bar 疊更重的結構門檻。

3. **repaint / lookahead 風險相對低。**
   - 若規則只依賴 OR 結束後的已確認 bar、session clock 與既有 same-session rails，則主要是 deterministic session gating。
   - 目前看不到一定要引入 `request.security`、intrabar 或 higher-timeframe lookahead 的必要。

### 對目前主線的影響

- 台股後續新的 refinement，較合理的比較順序現在是：
  1. `aligned baseline`
  2. `full bar above range`
  3. `full bar above range + OR average volume baseline`
  4. `signal window / one-and-done` 候選
- `breakout body strength 0.60` 與 `OR retest` 仍維持 compare-only，不往前提。

### 下一步

1. 若進入執行輪，優先把 `signal window / one-and-done` 先收斂成 same-session、confirmed-bar-only 的研究 contract。
2. 若進入分析輪，新的台股比較應直接對照：
   - `aligned baseline`
   - `full bar above range`
   - `full bar above range + OR average volume baseline`
   - `signal window / one-and-done` 候選

## 2026-05-21 分析：台股 aligned baseline 上的 signal window 60 分鐘 cutoff

### 比較對象

這輪固定比較 `TWSE_2330_5M` 的 `Asia/Taipei 09:00-13:30 aligned` baseline 上兩組：

1. `ORB + EMA inside-range + full bar above range + OR average volume baseline`
2. 同一組再加 `signal window 60`

### 主要結果

- `signal window 60` 不是小幅 trade-compression，而是 **直接把目前最強 stacked profile 壓成零交易**：
  - hold 1 PF：`6.525 -> undefined`
  - hold 3 PF：`2.259 -> undefined`
  - hold 5 PF：`1.374 -> undefined`
  - hold 10 PF：`1.099 -> undefined`
  - trades：`8 -> 0`

### phase attribution

- 原本最強的 stacked profile：
  - accepted `8`
  - blocked `2668`
  - hold `111`
  - top blocked reasons：`below_or_high(2251)`、`breakout_volume_blocked(228)`、`breakout_bar_reentered_range(141)`

- 加上 `signal window 60` 後：
  - accepted `0`
  - blocked `2287`
  - hold `0`
  - 新增主要 reason：`outside_signal_window(500)`

### 解讀

1. **目前不是 signal window family 沒價值，而是 60 分鐘 cutoff 太早。**
   - 現在最強的台股 stacked profile 在不加 cutoff 時有 `8` 筆交易。
   - 加上 `signal window 60` 之後，所有可成交 breakout 都被 `outside_signal_window` 擋掉，代表 cutoff 把有效 breakout 一起清掉了。

2. **這條線暫時不該升成下一個主 benchmark。**
   - 它和 `full bar above range`、`OR average volume baseline` 不同，這輪沒有展現出「更乾淨但仍保留可交易樣本」的增量，而是直接把樣本數壓到零。

3. **後續若繼續研究，應把「signal window」和「one-and-done」拆開。**
   - `signal window 60` 現在已可先定性為過度壓縮。
   - 但 `one-and-done` 仍可能是另一種不同的 session 內風險控制，不應因為這輪 60 分鐘 cutoff 失敗就一起否決。

### 結論

- `signal window 60` 在 `TWSE_2330_5M aligned` 上屬於 **over-compressive session refinement**。
- 它目前弱於：
  1. `aligned baseline`
  2. `full bar above range`
  3. `full bar above range + OR average volume baseline`

### 下一步

1. 若再研究 session 類 refinement，優先把 `one-and-done` 和 `signal window` 分開，不要再直接沿用 60 分鐘 cutoff。
2. 若要重測 signal window，應把 cutoff 視為獨立參數假設，而不是直接假設它能和目前最強 stacked profile 共存。

## 2026-05-21 執行：把台股 signal window 候選收斂成 machine-readable contract

### 本輪修改

- ORB `strategy_spec` 現在固定輸出：
  - `orb_signal_window_scope=same_session_only`
  - `orb_signal_window_signal_basis=confirmed_bar_close_only`
  - `orb_signal_window_cutoff_reference=session_start_elapsed_minutes`
  - `orb_signal_window_position_effect=entry_cutoff_only_no_force_flatten`
- 新增 `_validate_orb_signal_window_contract(...)`，直接拒絕：
  - scope drift
  - signal basis drift
  - cutoff reference drift
  - 把 signal window 誤升成 force-flatten 規則
- 補 direct unit tests，讓 signal window contract 的失敗更靠近 `strategy_spec` 建構點，而不是只靠 CLI 端到端 summary 才發現 drift。

### 為什麼先做這一刀

- `signal window / one-and-done` 已被研究收斂成較值得測的台股下一個候選，但目前還不適合直接進回測語意修改。
- 先把它鎖成 deterministic contract，比較能避免後續在沒有明確產品判斷時，偷偷混入：
  - intrabar probe
  - cross-session window
  - after-cutoff force flatten

### 結論

- 這輪只是把 **台股 session refinement 候選** 先收斂成可測試、可追溯的 metadata contract。
- 它不代表已經接受 `signal window / one-and-done` 的交易語意，也不代表已經優於 `full bar above range + OR average volume baseline`。

### 下一步

1. 若進入分析輪，再用 `TWSE_2330_5M aligned` 比較 signal window 候選和目前三層 canonical anchors。
2. 若進入 review 輪，優先檢查這個 contract 是否已足夠穩定，不需要再把它擴成更重的 schema。

## 2026-05-21 Review：台股 signal window 60 的位階與 session refinement 拆分

### Findings

1. **Severity: medium — `signal window 60` 應固定為 over-compressive session refinement，而不是下一個主 benchmark。**
   - 它不是零增量條件，因為確實新增了 `outside_signal_window(500)` 這個新的 session blocked family。
   - 但它對目前最強 stacked profile 的作用不是「保留較少但更好的交易」，而是直接把 `8` 筆交易壓成 `0`。
   - **受影響檔案：** `docs/04-實驗記錄/Autoresearch 實驗記錄.md`、`docs/策略筆記/ORB + Volume + VWAP.md`
   - **建議修法：** 後續不要再把 `signal window 60` 和 `full bar above range` / `full bar + OR average volume baseline` 放在同一級 benchmark 候選裡。

2. **Severity: medium — session 類 refinement 現在需要拆成兩條線，而不是繼續混成同一題。**
   - 目前至少要拆開：
     - `signal window`：研究 cutoff 對有效 breakout 的殺傷程度
     - `one-and-done`：研究同 session 只取第一筆 breakout 是否能保留品質
   - 若不拆開，後續很容易把 `signal window 60` 的失敗，錯誤投射成整個 session family 都沒有價值。
   - **受影響檔案：** `docs/04-實驗記錄/Autoresearch 實驗記錄.md`、後續比較報表
   - **建議修法：** 下一輪若回到研究或執行，優先定義 `one-and-done` 的 same-session、confirmed-bar-only contract；不要沿用 60 分鐘 cutoff 直接代表整個 session family。

3. **Severity: low — 目前 reporting hint 不需要立刻再擴，但比較敘事要固定避開 `signal window 60`。**
   - 現有台股 benchmark / stacked profile hint 的主責任是解釋：
     - `aligned baseline`
     - `full bar above range`
     - `full bar above range + OR average volume baseline`
   - `signal window 60` 目前還不值得升成報表中的正式 benchmark 層。
   - **受影響檔案：** `src/signal_forge/reporting/_legacy.py`、`tests/test_reporting.py`
   - **建議修法：** 暫時不要再為 `signal window 60` 擴 hint；先等 `one-and-done` 有比較結果後，再決定 session family 是否需要獨立提示層。

### 結論

- `signal window 60` 現在可明確定性為 **over-compressive session refinement**。
- 台股後續若還要研究 session family，應先分流成：
  1. `signal window`
  2. `one-and-done`
- 在新的證據出來前，台股 canonical comparison anchors 仍維持：
  1. `aligned baseline`
  2. `full bar above range`
  3. `full bar above range + OR average volume baseline`

### 下一步

1. 若進入研究輪，優先整理 `one-and-done` 的外部模式與最小 contract。
2. 若進入執行輪，優先把 `one-and-done` 收斂成 machine-readable contract，而不是再調整 `signal window 60` 數值。

## 2026-05-21 研究：台股 session family 裡 `one-and-done` 比 `signal window` 更值得先走下一步

### 研究問題

在 `signal window 60` 已被定性為 over-compressive 之後，台股 session family 若還要繼續往前走，下一個較合理的候選應該是什麼？

### 外部依據

- TradingView `Opening-Range Breakout` 明確提供 **One Trade Per Day** toggle。
- TradingView `ORB Breakout` 明確標示 **once per day per direction**。
- TradingView `ORB Breakout Strategy` 也把 **maximum one trade per day** 當成系統級控制。
- TradingView `ORB Strategy [LuciTech]` 明確說 **only the first confirmed breakout per day is traded**，而且若超過某個時間仍沒 breakout，當天就不交易。
- TradingView `RPFXBYDAN - ORB` 明確提供 **one-signal-per-side-per-day guard**。
- TradingView `ORB SESSIONS` 則更進一步把它放進 **max trades/session / re-arm / cooldown** 這一類 session control family 裡。

### 研究結論

1. **在台股 session family 裡，`one-and-done` 比 `signal window` 更值得先走下一步。**
   - 它比較像「先接受一個有效 breakout，然後阻止同 session 後續追價」。
   - 這和 `signal window 60` 直接把整段後續時間切掉不同。

2. **這條線仍然符合目前 SignalForge 的安全邊界。**
   - 它可以維持在 same-session、confirmed-bar-only。
   - 不需要引入 previous-day、higher-timeframe 或 intrabar 探針。

3. **它比較像 session control，而不是新的 breakout qualification。**
   - `full bar above range` 仍是結構確認。
   - `OR average volume baseline` 仍是 volume compression / stacked profile 元件。
   - `one-and-done` 則更像「成交機會數量管理」，目的是減少後續重複 breakout 嘗試。

### 對目前主線的影響

- 台股 session family 現在較合理的分流是：
  - `signal window`：目前已知 `60` 分鐘版本過度壓縮
  - `one-and-done`：下一個較值得正式收斂 contract 的候選

- 在新的數據出來前，台股 canonical comparison anchors 仍維持：
  1. `aligned baseline`
  2. `full bar above range`
  3. `full bar above range + OR average volume baseline`

### 下一步

1. 若進入執行輪，優先把 `one-and-done` 收斂成 same-session、confirmed-bar-only 的 machine-readable contract。
2. 若進入分析輪，`one-and-done` 應直接對照：
   - `aligned baseline`
   - `full bar above range`
   - `full bar above range + OR average volume baseline`

## 2026-05-21 執行：把台股 `one-and-done` 候選收斂成 machine-readable contract

### 本輪修改

- ORB `strategy_spec` 現在固定輸出：
  - `orb_one_and_done_mode=research_candidate_only`
  - `orb_one_and_done_scope=same_session_only`
  - `orb_one_and_done_signal_basis=confirmed_bar_close_only`
  - `orb_one_and_done_position_effect=first_entry_only_no_force_flatten`
  - `orb_one_and_done_reset_rule=reset_on_next_session_start`
  - `orb_one_and_done_data_family=no_previous_day_or_higher_timeframe_context`
- 新增 `_validate_orb_one_and_done_contract(...)`，直接拒絕：
  - cross-session cooldown drift
  - intrabar drift
  - force-flatten drift
  - previous-day / higher-timeframe data family drift
- 補 direct unit tests，讓 `one-and-done` 的研究邊界可以在 `strategy_spec` 建構點被鎖住，而不是等到後續真的接進回測語意後才發現 drift。

### 為什麼先做這一刀

- 目前台股 session family 已經明確分成：
  - `signal window`：已知 `60` 分鐘版本過度壓縮
  - `one-and-done`：下一個更值得正式比較的候選
- 在還沒決定 `one-and-done` 具體交易語意之前，先把它的 contract 鎖成 deterministic metadata，能避免後續把：
  - same-session entry count control
  - cross-session cooldown
  - after-cutoff force flatten

  這幾種完全不同的 session control 混在一起。

### 結論

- 這輪只是把 `one-and-done` 候選正式收斂成 **same-session、confirmed-bar-only、entry-count-control** 的 machine-readable contract。
- 它不代表 `one-and-done` 已經被接受為新的交易語意，也不代表它已經優於：
  1. `aligned baseline`
  2. `full bar above range`
  3. `full bar above range + OR average volume baseline`

### 下一步

1. 若進入分析輪，直接用 `TWSE_2330_5M aligned` 比較 `one-and-done` 與上述三層 canonical anchors。
2. 若進入 review 輪，優先檢查這個 contract 是否已足夠穩定，不必急著再擴成更重的 schema。

## 2026-05-21 分析：`one-and-done` contract 對目前台股最強 stacked profile 的 runtime 中性驗證

### 比較對象

這輪還不能直接比較真正的 `one-and-done` 交易語意，因為目前 repo 只新增了 machine-readable contract，尚未把它接進 ORB breakout 的實際 entry control。

因此這輪分析固定回答另一個更立即的問題：

- 在 `TWSE_2330_5M` 的 `Asia/Taipei 09:00-13:30 aligned` baseline 上，
- 目前最強的台股 stacked profile

  `ORB + EMA inside-range + full bar above range + OR average volume baseline`

  在加入 `one-and-done` contract metadata 後，runtime 是否保持完全不變。

### 主要結果

- hold comparison 指標全部維持不變：
  - hold 1：PF `6.525`、Trades `8`、Win rate `37.5%`、Avg net PnL `13.88`
  - hold 3：PF `2.259`、Trades `8`、Win rate `50.0%`、Avg net PnL `39.15`
  - hold 5：PF `1.374`、Trades `8`、Win rate `50.0%`、Avg net PnL `21.06`
  - hold 10：PF `1.099`、Trades `8`、Win rate `37.5%`、Avg net PnL `6.73`

- phase hold 1 attribution 也維持原狀：
  - accepted `8`
  - blocked `2668`
  - hold `111`
  - top blocked reasons：
    - `below_or_high(2251)`
    - `breakout_volume_blocked(228)`
    - `breakout_bar_reentered_range(141)`
    - `ema_inside_opening_range(44)`

- 新增的只有 `strategy_spec` metadata：
  - `orb_one_and_done_mode`
  - `orb_one_and_done_scope`
  - `orb_one_and_done_signal_basis`
  - `orb_one_and_done_position_effect`
  - `orb_one_and_done_reset_rule`
  - `orb_one_and_done_data_family`

### 解讀

1. **這輪證明 `one-and-done` 目前仍只是 contract，不是已生效的交易語意。**
   - 它不會影響目前台股最強 stacked profile 的 PF、交易數、blocked reasons 或 hold counts。

2. **這個中性驗證是必要的。**
   - 先確認 contract-only 變更沒有碰壞現有 baseline，後續才有資格在下一個執行輪把 `one-and-done` 真正接進 entry control。

3. **因此下一輪若要做真正的 `one-and-done` 比較，必須清楚承認那會是策略語意改動。**
   - 不能把這輪的中性結果誤讀成 `one-and-done` 已經證明有效或無效。

### 本地分析報表

- `reports/generated/twse-orb-aligned-oneanddone-contract-neutral-20260521_hold_comparison.json`
- `reports/generated/twse-orb-aligned-oneanddone-contract-neutral-20260521_hold_comparison.md`
- `reports/generated/twse-orb-aligned-oneanddone-contract-neutral-20260521-phase.json`
- `reports/generated/twse-orb-aligned-oneanddone-contract-neutral-20260521-phase.md`

### 下一步

1. 若進入 review 輪，應把 `one-and-done` 先定性成 **contract-ready but semantics-not-enabled**。
2. 若之後真的要分析 `one-and-done`，需要先做一個執行輪，把它正式接進 ORB 的 entry-count-control 語意，再和三層 canonical anchors 比較。

## 2026-05-21 Review：台股 `one-and-done` 應固定定性為 contract-ready but semantics-not-enabled

### Findings

1. **中等嚴重度 - `one-and-done` 現在不應被提升成新的台股 benchmark。**
   - 目前 repo 已經有 `one-and-done` 的 machine-readable contract 與 validator tests。
   - 但最新分析同時證明，這些欄位目前只會增加 metadata，不會改變 `TWSE_2330_5M aligned` 上最強 stacked profile 的 runtime。
   - 因此目前能成立的最強結論只有：它已經 **contract-ready**，但仍 **semantics-not-enabled**。

2. **中等嚴重度 - session family 必須明確區分 contract readiness 與實際交易語意。**
   - 如果不先切開這兩件事，後續很容易把：
     - `signal window 60` 的 over-compression，
     - `one-and-done` 的 contract-only 狀態，
     - 以及真正啟用 entry-count-control 之後的交易結果

     混成同一類 session refinement 討論。
   - 這會直接污染台股 refinement 的位階判讀。

3. **低嚴重度 - 目前 reporting hint 已足夠，不需要為 `one-and-done` 額外新增 machine-readable ranking。**
   - 現有台股 comparison hints 已經能固定三層 canonical anchors：
     1. `aligned baseline`
     2. `full bar above range`
     3. `full bar above range + OR average volume baseline`
   - 在 `one-and-done` 還沒真正接進 breakout entry-count-control 前，沒有必要再為它長出新的 benchmark schema。

### 結論

- `one-and-done` 現在最合理的正式定性是 **contract-ready but semantics-not-enabled**。
- 在新的策略語意實作與回測證據出來前，台股 canonical comparison anchors 維持不變：
  1. `aligned baseline`
  2. `full bar above range`
  3. `full bar above range + OR average volume baseline`
- 因此這條線下一步若要繼續，不應再做 metadata / wording 類驗證，而應直接進入真正的 entry-count-control 語意實作。

### 下一步

1. 若進入執行輪，優先把 `one-and-done` 真正接進 ORB breakout 的 entry-count-control。
2. 啟用後的第一輪分析，固定同時對照：
   - `aligned baseline`
   - `full bar above range`
   - `full bar above range + OR average volume baseline`
3. 在那之前，不要把 `one-and-done` 提升成新的台股 benchmark，也不要把 contract-only 中性結果誤讀成策略有效性證據。

## 2026-05-21 研究：公開 ORB 的 `one-and-done` 更常是 direction-scoped guard，不一定是整個 session 只准一筆

### 外部參照

- TradingView `Opening Range Breakout (ORB)` 提到「only 1 trade of the first break and close of the ORB」。
- TradingView `ORB Breakout` 提到「fires once per day per direction, independently」。
- TradingView `ORB Strategy [LuciTech]` 提到「Only the first confirmed breakout per day is traded — one long signal and one short signal maximum per ORB session」。
- TradingView `RPFXBYDAN - ORB (Opening Range Breakout)` 也明講它有 `one-signal-per-side-per-day guard`。

### 主要研究結論

1. 公開 ORB 的 `one-and-done` 常見的其實不是單一版本，而是至少兩種語意：
   - **per-side / per-direction guard**
   - **entire-session one-trade guard**

2. 這代表目前 SignalForge 把 `one-and-done` 先收斂成 `entry-count-control` 是對的，但還不夠精確。
   - 下一步真正要落策略語意前，應先決定：
     - 是 `first long breakout only`
     - 還是 `session 內只要成交一次就全部關閉後續 entry`

3. 以目前台股主線 `TWSE_2330_5M aligned` 而言，**較低風險的第一刀應先從 per-direction / long-only guard 開始**。
   - 原因是目前研究主線本來就是 long-only ORB entry edge。
   - 如果直接做整個 session one-trade guard，會把尚未研究的 short-side 與反向 breakout 行為一起混進來。

### 為什麼這個差異重要

- `per-direction guard` 比較像：
  - 第一個有效 long breakout 成立後，不再接受同 session 的第二個 long breakout
- `entire-session guard` 比較像：
  - 只要 session 內已經成交一筆，就不再接受任何新 entry

這兩者都叫 `one-and-done`，但它們對交易數、後續 blocked reasons 與台股 session 結構的影響完全不同。若不先切清楚，後續分析很容易把 guard 範圍誤當成策略有效性。

### repaint / lookahead / MTF 風險判斷

- 這個 family 目前仍可以維持在：
  - same-session
  - confirmed-bar-only
  - 不使用 `request.security()`
  - 不依賴 previous-day / higher-timeframe context

- 因此它的主要風險不是 repaint，而是 **session control 語意是否定義清楚**。

### 下一步

1. 若進入執行輪，應先把 `one-and-done` contract 再收斂成：
   - `per_direction`
   - 或 `entire_session`

   其中一種，不要兩種一起做。
2. 對目前台股主線，建議優先從 **long-only / per-direction first-entry guard** 開始。
3. 在 guard 範圍沒先定清楚前，不要直接把 `one-and-done` 接進 runtime 再拿結果做大結論。

## 2026-05-21 執行：把 `one-and-done` contract 精化成 long-only / per-direction first-entry guard

### 這輪修改

這輪沒有啟用新的交易語意，只把 `one-and-done` 的 machine-readable contract 從較模糊的 `entry-count-control` 候選，再往前收斂一層：

- 新增 `orb_one_and_done_guard_scope = long_only_per_direction_first_entry`
- validator 現在會直接拒絕：
  - `entire_session_one_trade`
  - 其他未定義的 guard scope drift

### 為什麼先做這件事

前一輪研究已經確認，公開 ORB 的 `one-and-done` 常見至少有兩種不同 guard：

1. `per-direction / per-side`
2. `entire-session one-trade`

如果不先把 contract 鎖進其中一種，後續即使真的把 `one-and-done` 接進 runtime，分析結果也會同時混入：

- long-only first-entry 限制
- 整個 session 全關閉後續 entry

兩種完全不同的 session control 語意。

### 目前正式定義

在現在的台股 ORB 主線上，`one-and-done` 的 contract 應解讀成：

- 只處理 long-only 主線
- 只在同一個 session 內生效
- 只接受 confirmed-bar close breakout
- 第一個有效 long breakout 成立後，不再接受同 session 的第二個 long breakout
- 不強制平倉
- 下一個 session 才 reset

### 結論

- `one-and-done` 現在仍是 **contract-ready but semantics-not-enabled**。
- 但相較前一輪，這個 contract 已不再只是抽象的 `entry-count-control`，而是更明確地固定成：

  `long_only_per_direction_first_entry`

- 這讓後續若真的要做語意實作，目標已經更清楚，不必再同時處理 `entire_session one-trade` 版本。

### 下一步

1. 若進入分析輪，這輪不需要額外重跑 runtime；因為目前仍是 contract-only 變更。
2. 若進入 review 輪，應檢查：
   - reporting / strategy note 是否仍把 `one-and-done` 寫得太模糊
   - 是否還有地方把它描述成 generic one-trade-per-day
3. 若之後真的要進策略語意實作，應直接把這個 guard scope 接進 long breakout 的 entry-count-control，而不是先回頭討論 `entire_session` 版本。

## 2026-05-21 分析：精化後的 `one-and-done guard scope` 仍是 contract-only

### 比較對象

這輪比較的不是新的交易規則，而是上一輪把 `one-and-done` contract 從 generic entry-count-control 再收斂成：

- `long_only_per_direction_first_entry`

之後，是否會意外改到目前最強台股 stacked profile 的 runtime。

比較主線維持：

- `TWSE_2330_5M`
- `Asia/Taipei 09:00-13:30 aligned`
- `ORB + EMA inside-range + full bar above range + OR average volume baseline`

### 結果

結果完全不變，表示這輪仍然只是 **contract 精化**，不是新的交易控制：

- hold 1：PF `6.525`、Trades `8`
- hold 3：PF `2.259`、Trades `8`
- hold 5：PF `1.374`、Trades `8`
- hold 10：PF `1.099`、Trades `8`

phase hold 1 attribution 也維持原狀：

- accepted `8`
- blocked `2668`
- hold `111`
- top blocked reasons：
  - `below_or_high(2251)`
  - `breakout_volume_blocked(228)`
  - `breakout_bar_reentered_range(141)`
  - `ema_inside_opening_range(44)`

### 解讀

1. `one-and-done` 現在仍是 **contract-ready but semantics-not-enabled**。
2. 這輪的價值在於減少 guard scope 的語意模糊，不在於提供新的策略績效證據。
3. 因此不能把這輪的中性結果誤讀成：
   - `one-and-done` 已經有效
   - 或 `one-and-done` 已經不值得做

它只證明：目前 repo 內新增的是更清楚的 contract metadata，而不是 entry-count-control runtime。

### 下一步

1. 若之後真的要比較 `one-and-done`，應先進執行輪，把它正式接進 long breakout 的 entry-count-control 語意。
2. 在那之前，台股 canonical comparison anchors 仍維持：
   - `aligned baseline`
   - `full bar above range`
   - `full bar above range + OR average volume baseline`
3. review 與 reporting 不應把 contract-only 中性結果寫成策略有效性證據。

## 2026-05-21 Review：`one-and-done` 近期 contract / reporting / 筆記邊界

### Findings

1. **Severity: medium — `one-and-done` metadata 已接近可啟用狀態，但 runtime state 仍只靠語意描述，不靠明確欄位。**
   - 目前 `strategy_spec` 已經固定輸出：
     - `orb_one_and_done_mode`
     - `orb_one_and_done_scope`
     - `orb_one_and_done_guard_scope`
     - `orb_one_and_done_position_effect`
   - 這讓 contract 已經相當完整，但 downstream 若只看 key 名稱，很容易把它誤讀成「已經生效的交易控制」，而不是「尚未接進 runtime 的 research contract」。
   - **受影響檔案：** `src/signal_forge/cli/strategy_options.py`、`tests/test_cli.py`
   - **建議修法：** 等真正進入語意實作輪時，不要直接偷換這批 metadata 的解讀；要嘛維持 `research_candidate_only` 並另外補 runtime-enabled 狀態，要嘛新增一個明確的 execution-state 欄位，避免 contract-only 與 semantics-enabled 被混用。

2. **Severity: medium — 台股 reporting hint 目前已能說清 benchmark 與 stacked profile，但還沒有 session-family 的落點。**
   - 這不是 bug，因為 `one-and-done` 現在本來就不該升成 benchmark。
   - 但它意味著：等未來真的啟用 `one-and-done` entry-count-control 時，現有 exact-text regression 不會主動提醒這條 session family 應該被讀成 compare-only、還是新的 active profile。
   - **受影響檔案：** `src/signal_forge/reporting/_legacy.py`、`tests/test_reporting.py`
   - **建議修法：** 現在先不要擴 hint；等 `one-and-done` 真正接進 runtime，再補一個窄範圍 exact-text regression，避免現在為 contract-only 候選長出過早的 reporting schema。

3. **Severity: medium — `ORB + Volume + VWAP` 策略筆記已混入大量實驗時序，和 repo 明訂的筆記分工不一致。**
   - `AGENTS.md` 已明確要求策略筆記只保留術語、假設、進出場條件、主要參數、圖解、風險與下一步；`策略狀態`、`目前結果`、`變更紀錄` 應放在實驗紀錄或回測報告。
   - 但目前 `docs/策略筆記/ORB + Volume + VWAP.md` 已累積大量 benchmark 排序、輪次結論與 session-family 時序，和 `Autoresearch 實驗記錄` 形成重複記錄來源。
   - **受影響檔案：** `docs/策略筆記/ORB + Volume + VWAP.md`
   - **建議修法：** 下一個適合的文件輪，應把策略筆記收斂回「策略定義與風險」，把輪次比較、benchmark 排序、contract-ready / compare-only 這些時序性內容留在 `Autoresearch 實驗記錄`。

### 結論

- `one-and-done` 現在仍應固定定性為 **contract-ready but semantics-not-enabled**。
- 在真正接進 entry-count-control 前，不應為它提前長出 benchmark 等級的 reporting schema。
- 目前較明顯的文件債，不在程式，而在 `ORB + Volume + VWAP` 策略筆記已逐漸承擔實驗紀錄職責，和既定分工開始重疊。

### 下一步

1. 若進入執行輪，優先做真正的 `one-and-done` entry-count-control 語意，不再停留在 metadata。
2. 若進入文件輪，優先把 `ORB + Volume + VWAP` 策略筆記去時序化，讓它回到策略筆記框架。
3. 在那之前，台股 canonical comparison anchors 維持：
   - `aligned baseline`
   - `full bar above range`
   - `full bar above range + OR average volume baseline`

## 2026-05-21 研究：`one-and-done` 較合理的計數基準應是 confirmed / traded breakout，不是第一次觸碰

### 外部參照

- TradingView `ORB Breakout`：`Fires once per day per direction, independently.` 並把 breakout 定義在 close / VWAP / volume / signal window 全部成立之後。
  https://www.tradingview.com/script/KWfBq6HU-ORB-Breakout/
- TradingView `ORB Strategy [LuciTech]`：`Only the first confirmed breakout per day is traded`，明確把計數點放在 **confirmed breakout**。
  https://www.tradingview.com/script/10yYqaY7-ORB-Strategy-LuciTech/
- TradingView `RPFXBYDAN - ORB`：在 optional retest filter 存在時，仍描述成 `one-signal-per-side-per-day guard`，而 retest 模式下 `the first break only arms the signal`。
  https://www.tradingview.com/script/23PYvshx-RPFXBYDAN-ORB-Opening-Range-Breakout/

### 主要研究結論

1. 公開 ORB 的 `one-and-done`，較常限制的是 **真正成立的 signal / trade**，不是第一個 raw touch。
2. 若策略存在 retest / re-break flow，第一個突破很多時候只是 `arm` 狀態；真正被計入 one-and-done 的，通常是後面的 confirmed signal。
3. 因此對目前 SignalForge 的 long-only / per-direction first-entry guard，較低風險的第一個語意版本應是：
   - 先讓 breakout 完成目前所有 entry qualification
   - 只有 **accepted long entry** 才消耗當前 session 的 one-and-done quota
   - 不是第一個碰到 OR high、第一個突破嘗試、或第一個 retest arm 就直接鎖死同 session

### 對 SignalForge 的含義

- 這個結論會直接影響未來 `one-and-done` 真正接進 runtime 的位置。
- 較合理的接法不是在 breakout state machine 最前面就提前封鎖，而是：
  1. 先完成目前既有的 ORB qualification
  2. 在 signal 被接受、準備產生 long entry 的那一刻
  3. 才把 `same-session long quota` 從可用翻成不可用

### 為什麼這樣比較穩

- 能避免把失敗的 breakout 嘗試也算進 quota。
- 和目前 `full bar above range`、`OR average volume baseline` 這些已存在的 qualification 邏輯比較一致。
- 若未來 `retest confirmation` 重新回到台股主線，也不需要重做一套新的 one-and-done 解讀。

### 下一步

1. 若進入執行輪，應先做 **accepted-entry-based** 的 one-and-done 語意，而不是 first-touch-based 版本。
2. 真正的第一輪比較，仍固定對照：
   - `aligned baseline`
   - `full bar above range`
   - `full bar above range + OR average volume baseline`
3. 在那之前，不要把 `one-and-done` 寫成「第一碰就鎖死」；那和目前公開 ORB 常見模式並不一致。

## 2026-05-21 Review：`one-and-done` accepted-entry-based 前的 execution-state 與文件分工風險

### Findings

1. **Severity: medium — `one-and-done` 若下一輪真的接進 accepted-entry-based runtime，現在還缺 execution-state 層的明確區分。**
   - 目前 repo 已有完整的 contract metadata，例如：
     - `orb_one_and_done_mode=research_candidate_only`
     - `orb_one_and_done_guard_scope=long_only_per_direction_first_entry`
     - `orb_one_and_done_position_effect=first_entry_only_no_force_flatten`
   - 但這些欄位都還是在描述「研究候選的邊界」，不是在描述「本次 run 是否真的啟用了 accepted-entry quota」。
   - **受影響檔案：** `src/signal_forge/cli/strategy_options.py`、未來的 ORB runtime / trace summary
   - **建議修法：** 若下一輪真的要啟用 accepted-entry-based one-and-done，應另外補一層 execution-state 或 trace attribution，不要直接把現有 contract metadata 偷換成已啟用語意。

2. **Severity: medium — accepted-entry-based 版本若直接上線，之後很難只靠現有 phase summary 判斷 quota 是在哪一筆 accepted long 被消耗。**
   - 現在 ORB phase / trace 已能看 `accepted_entry_count`、blocked reasons、hold counts，但還不能明確回答：
     - 哪一筆 accepted long 是當 session 的 first accepted entry
     - 後續被 one-and-done 擋掉的 breakout 是因為 quota exhausted，而不是原本的 structure / volume gate
   - 這不是現在要順手實作的大改，但它是下一輪啟用 runtime 前最需要先想清楚的 artifact 邊界。
   - **受影響檔案：** `src/signal_forge/reporting/_orb_attribution.py`、未來的 `*_trace_summary.json`
   - **建議修法：** 等真正進入語意實作輪時，把 `one_and_done_quota_consumed` 類的 attribution 視為同一輪的一部分；不要先啟用 runtime，再讓報表處於不可判讀狀態。

3. **Severity: medium — `ORB + Volume + VWAP` 策略筆記持續混入 benchmark 排序與輪次時序，已超出策略筆記應承擔的範圍。**
   - repo 的 `AGENTS.md` 已明確要求：策略筆記應聚焦在術語、假設、進出場條件、主要參數、風險與下一步；輪次結論、benchmark 排序、contract-ready / compare-only 這類內容應留在 `Autoresearch 實驗記錄`。
   - 目前 `docs/策略筆記/ORB + Volume + VWAP.md` 仍保留大量時序性實驗結論，和這份實驗紀錄有重疊風險。
   - **受影響檔案：** `docs/策略筆記/ORB + Volume + VWAP.md`
   - **建議修法：** 下一個適合的文件輪，應把策略筆記去時序化，讓它回到策略定義文件；實驗排序與 benchmark 演進則集中留在 `Autoresearch 實驗記錄`。

### 結論

- `one-and-done` 目前仍應固定定性為 **contract-ready but semantics-not-enabled**。
- 真正的 accepted-entry-based 版本若要上線，不能只有 runtime guard，還要一起補 execution-state / attribution 邊界。
- 目前更急迫的債不在策略邏輯本身，而在：未來 runtime 啟用後的可判讀性，以及策略筆記與實驗紀錄之間的文件分工。

### 下一步

1. 若進入執行輪，應把 accepted-entry-based `one-and-done` runtime 與 execution-state attribution 視為同一個改動包，而不是只做前者。
2. 若先進文件輪，應把 `ORB + Volume + VWAP` 策略筆記去時序化，讓 benchmark 排序與輪次結論回到 `Autoresearch 實驗記錄`。
3. 在新的語意證據出來前，台股 canonical comparison anchors 維持：
   - `aligned baseline`
   - `full bar above range`
   - `full bar above range + OR average volume baseline`

## 2026-05-23 研究：多檔台股批次回測避免單一標的偏誤

這輪依使用者要求，把策略回測從單一 `2330` 擴大成七檔 TWSE 大型股同時 sweep。新的研究工具是 `tools\multi_stock_entry_edge_sweep.py`，同一個命令會對多個 CSV、三個日線策略與多個固定持有期做 entry-edge 評估，並用跨股票總 gross profit / gross loss 計算 aggregate PF。

### 本輪股票池

- `2330`：沿用既有台積電日線資料，sweep 時用 common window 過濾。
- `2317`、`2454`、`2308`、`2303`、`2412`、`2882`：本輪用 TWSE `STOCK_DAY` 補齊 `2020-01-01` 到 `2026-05-20` 日線資料。

TWSE 下載路徑也同步修正：`rwd/zh/afterTrading/STOCK_DAY` 在本環境回 `HTTP 307` HTML，已改用可直接回 JSON 的 `exchangeReport/STOCK_DAY`，並在 `tests/test_data_fetch.py` 加上路徑 regression。

### 主要結果

| Strategy | Hold | 通過股票 | Aggregate PF | Trades | Avg win rate | Worst max drawdown |
|---|---:|---:|---:|---:|---:|---:|
| `confluence-score` | `10` | `7/7` | `2.299` | `349` | `58.98%` | `-27.56%` |
| `sma-crossover` | `10` | `5/7` | `1.818` | `45` | `48.78%` | `-10.45%` |
| `sma-crossover` | `5` | `3/7` | `1.689` | `45` | `58.44%` | `-9.25%` |

結論：目前最符合 `PF >= 1.5` 且較不偏單一股票的候選，是 `confluence-score` 搭配 `hold=10`。逐檔 PF 都高於 `1.5`，aggregate PF 為 `2.299`。

### 保留疑慮

- 這仍是 entry-edge 固定持有期，不是完整投資組合或真實下單系統。
- `confluence-score hold=10` 的 signal overlap 很高，表示完整策略還必須先定義「重疊訊號如何處理」。
- `sma-crossover hold=10` 雖然 aggregate PF 達標，但只有 `5/7` 檔通過，而且交易數較少，因此不是本輪首選。

### 下一步

1. 將 `Confluence Score + hold=10` 視為 Phase 2 候選。
2. 下一輪若要繼續優化，不先堆更多濾網，而是處理 overlap 語意與持倉規則。
3. 所有後續策略優化都應先跑多股票 sweep，再判斷是否真的改善。

## 2026-05-23 研究：`Confluence Score + signal cooldown` 降低重疊訊號

這輪延續多股票基準，沒有再新增股票池或換資料區間，而是針對前一輪最大的保留疑慮：`Confluence Score + hold=10` 的 signal overlap 過高。做法是新增通用 `SignalCooldownStrategy` wrapper，接受一筆 long entry 後，在指定 bar 數內封鎖新的 long entry；既有持倉延續不會被強制平倉。

### 本輪假設

- 若 overlap 主要來自同一段趨勢中反覆觸發高分訊號，進場冷卻應能降低重複 entry。
- 冷卻規則應只處理新的 long entry，不改寫 score，也不把已接受的 long 持倉強制變成 flat。
- 評估仍使用七檔 TWSE common window：`2020-01-01` 到 `2026-05-20`。

### 驗證命令

```powershell
python tools\multi_stock_entry_edge_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --strategy confluence-score `
  --hold-bars-list 10 `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --pass-profit-factor 1.5 `
  --signal-cooldown-bars 10 `
  --summary-json reports\generated\twse-multistock-confluence-cooldown10-20260523.json `
  --summary-md reports\generated\twse-multistock-confluence-cooldown10-20260523.md
```

### 結果

| Strategy | Hold | Cooldown | 通過股票 | Aggregate PF | Trades | Avg win rate | Avg end equity | Worst max drawdown | Total overlap |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `confluence-score` | `10` | `10` | `7/7` | `2.324` | `439` | `58.44%` | `29138.43` | `-33.05%` | `0` |
| `confluence-score` baseline | `10` | disabled | `7/7` | `2.299` | `349` | `58.98%` | `22467.51` | `-27.56%` | `300` |

逐檔 PF：

| Symbol | PF | Trades | Win rate | Avg net PnL | Max drawdown | Overlap |
|---|---:|---:|---:|---:|---:|---:|
| `2303` | `2.043` | `66` | `59.09%` | `551.36` | `-33.05%` | `0` |
| `2308` | `2.950` | `58` | `55.17%` | `329.88` | `-23.15%` | `0` |
| `2317` | `2.257` | `56` | `53.57%` | `253.76` | `-26.56%` | `0` |
| `2330` | `2.628` | `68` | `60.29%` | `367.62` | `-15.62%` | `0` |
| `2412` | `3.037` | `63` | `65.08%` | `75.22` | `-4.47%` | `0` |
| `2454` | `2.523` | `61` | `60.66%` | `460.29` | `-24.07%` | `0` |
| `2882` | `1.709` | `67` | `55.22%` | `95.83` | `-13.12%` | `0` |

### Keep / Discard 判斷

- **Keep**：`signal_cooldown_bars=10` 讓 total overlap 從 `300` 降到 `0`，aggregate PF 從 `2.299` 微升到 `2.324`，七檔仍全數通過 `PF > 1.5`。
- **Tradeoff**：worst max drawdown 從 `-27.56%` 惡化到 `-33.05%`，因此它是目前較好的持倉語意候選，不是最終風控版本。
- **不採用**：單純把 `threshold` 調高到 `4` 或 `5` 並沒有改善穩健性；`threshold=3, hold=10` 仍是較平衡基準。

### 下一步

1. 把 `Confluence Score + hold=10 + signal_cooldown_bars=10` 視為目前多股票 PF 目標的主候選。
2. 下一輪不要再只追 PF，應補風控維度：例如冷卻後的 drawdown 來源、停損/停利或部位縮放。
3. 若要新增策略，必須與這個 candidate 在同一個七檔 common window 上比較。

## 2026-05-24 研究與執行：benchmark drawdown 納入多股票 sweep

這輪接續「希望策略朝穩定營利方向疊代」的長期目標。依 [[../02-規劃/策略回測與優化評估準則|策略回測與優化評估準則]]，不能只看 PF 與總報酬；本輪先把目前主候選和 buy-and-hold 的報酬 / 回撤 tradeoff 攤開，再做一個聚焦工具改動。

### 外部研究參考

- Moskowitz、Ooi、Pedersen 的 Time Series Momentum 研究指出，跨市場資產存在 1 到 12 個月的報酬延續，且時間序列動能在極端市場表現有研究價值。
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2089463
- Moreira、Muir 的 Volatility Managed Portfolios 指出，高波動時降低風險曝險可提升 Sharpe；這支持後續不要只追進場分數，而要補波動 / 回撤控制。
  https://econpapers.repec.org/paper/nbrnberwo/22208.htm
- Antonacci 的 Dual Momentum 研究指出，absolute momentum 對降低波動與 drawdown 特別重要；這支持下一輪可以測「絕對動能 / 長期趨勢持有」類策略，但必須用同一批股票與 benchmark 檢查。
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2042750

### 本輪 baseline

使用七檔 TWSE common window、`confluence-score + hold=10 + signal_cooldown_bars=10`：

| 指標 | 結果 | 解讀 |
|---|---:|---|
| Aggregate PF | `2.324` | 交易 edge 仍達標 |
| 通過股票 | `7/7` | 多股票 PF gate 通過 |
| Trades | `439` | 樣本數足夠初步解讀 |
| Avg return | `191.38%` | 策略本身有正報酬 |
| Avg CAGR | `17.10%` | 不是單純靠一兩筆交易撐起 |
| Avg Sharpe / Sortino / Calmar | `0.979` / `2.214` / `0.935` | 風險調整表現有研究價值，但 Calmar 未達強候選 |
| Worst MDD | `-33.05%` | 仍是主要風險缺口 |
| Avg B&H return | `452.73%` | 強趨勢樣本中，被動持有報酬極高 |
| Worst B&H MDD | `-54.37%` | 策略明顯降低回撤，但犧牲大量 upside |
| Avg excess return | `-261.35%` | 不可宣稱已優於 benchmark |

逐檔來看，策略在七檔中都比 buy-and-hold 有較低最大回撤；但只有 `2412` 的 total return 也高於 buy-and-hold。因此目前候選應被解讀為「風險降低型候選」，不是「總報酬勝出型候選」。

### 長持有期測試

同樣使用 `confluence-score` 與 cooldown：

| 設定 | 通過股票 | Aggregate PF | Avg return | Worst MDD | Avg excess return | 判斷 |
|---|---:|---:|---:|---:|---:|---|
| `hold=80, cooldown=10` | `6/7` | `4.106` | `308.56%` | `-42.70%` | `-144.17%` | compare-only：更接近 benchmark，但 overlap 回來且回撤惡化 |
| `hold=80, cooldown=80` | `5/7` | `3.744` | `358.84%` | `-50.92%` | `-93.89%` | discard：相對報酬改善，但通過數下降、回撤接近 B&H |
| `hold=120, cooldown=10` | `7/7` | `3.515` | `185.50%` | `-39.51%` | `-267.23%` | compare-only：PF 漂亮但交易數下降、相對報酬未改善 |

結論：延長 hold 能改善對 benchmark 的落後幅度，但會把回撤拉高，且容易重新出現 overlap。這不能直接升級為主候選。

### 本輪程式改動

- `tools\multi_stock_entry_edge_sweep.py` 的 `SweepRow` 新增 `benchmark_max_drawdown`。
- `SweepAggregate` 新增 `worst_benchmark_max_drawdown`。
- Markdown 輸出在 aggregate 與 per-stock 表格顯示 B&H max drawdown。

這個改動不改策略語意，只讓每輪策略比較能同時回答：

- 策略是否賺錢；
- 是否輸給 buy-and-hold；
- 若輸給 buy-and-hold，是否至少用較低 MDD 換來更高可存活性。

### Keep / Discard 判斷

- **Keep**：benchmark drawdown 欄位。它直接補上策略評估準則中的風險與 benchmark-relative 檢查，讓後續優化不會把負 excess return 誤讀成失敗，也不會把低回撤 tradeoff 看漏。
- **Compare-only**：`hold=80, cooldown=10`。它改善 avg excess return，但有 overlap 與較大回撤，不能升級。
- **Discard**：`hold=80, cooldown=80` 作為主候選。它 avg excess return 最接近 B&H，但 worst MDD 到 `-50.92%`，且只有 `5/7` 股票通過 PF gate。

### 下一步

1. 下一輪優先測絕對動能 / 長期趨勢持有類候選，目標不是再把 PF 往上堆，而是同時改善 `Avg excess return` 與 `Worst MDD`。
2. 若做策略語意改動，應明確區分 entry-edge 固定 hold 與 Phase 2 target-state 持有；目前固定 hold 已顯示會犧牲強趨勢 upside。
3. 繼續補 `cost stress` 與 walk-forward / OOS，避免長 hold 或動能濾網只是在 2020-2026 台股強趨勢樣本上貼合。

## 2026-05-24 研究與執行：Absolute Momentum 長期趨勢候選

這輪依 [[../02-規劃/策略回測與優化評估準則|策略回測與優化評估準則]]，測試「絕對動能 / 長期趨勢持有」候選。研究假設來自 Time Series Momentum 與 Dual Momentum 類文獻：若回看期報酬為正，且價格仍位於長期趨勢均線上方，策略可能保留趨勢 upside，同時避開長期下跌段。

### 本輪程式改動

- 新增 `src\signal_forge\strategies\absolute_momentum.py`。
- 新增 registry key：`absolute-momentum`。
- Phase 1 factory 固定建構 long-only 版本，並拒絕 `allow_short=True`。
- CLI 既有 `--fast-window` / `--slow-window` 分別對應 `momentum_window` / `trend_window`。
- `tools\multi_stock_entry_edge_sweep.py` 的預設日線策略清單加入 `absolute-momentum`，讓後續多股票 sweep 會自動納入比較。
- 新增策略筆記：[[../策略筆記/Absolute Momentum|Absolute Momentum]]。

### Entry-edge sweep

命令：

```powershell
python tools\multi_stock_entry_edge_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --strategy absolute-momentum `
  --hold-bars-list 10,20,40,80 `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --pass-profit-factor 1.5 `
  --summary-json reports\generated\twse-absolute-momentum-entry-edge-20260524.json `
  --summary-md reports\generated\twse-absolute-momentum-entry-edge-20260524.md
```

結果：

| Strategy | Hold | 通過股票 | Aggregate PF | Trades | Avg return | Worst MDD | Avg excess return | 判斷 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `absolute-momentum` | `10` | `6/7` | `2.247` | `118` | `28.34%` | `-23.65%` | `-424.39%` | discard as main：MDD 低但報酬太低 |
| `absolute-momentum` | `20` | `6/7` | `2.762` | `93` | `48.15%` | `-35.34%` | `-404.58%` | discard as main：低於目前候選 |
| `absolute-momentum` | `40` | `7/7` | `3.284` | `74` | `72.62%` | `-29.00%` | `-380.11%` | compare-only：PF 與 MDD 可讀，但 upside 犧牲過大 |
| `absolute-momentum` | `80` | `5/7` | `3.842` | `54` | `108.47%` | `-40.48%` | `-344.26%` | discard as main：通過數下降且 MDD 惡化 |

相對目前基準 `confluence-score + hold=10 + signal_cooldown_bars=10`：

| 指標 | Confluence cooldown baseline | Absolute Momentum 較可讀設定 |
|---|---:|---:|
| Avg return | `191.38%` | `72.62%` at hold `40` |
| Worst MDD | `-33.05%` | `-29.00%` at hold `40` |
| Avg excess return | `-261.35%` | `-380.11%` at hold `40` |

解讀：`absolute-momentum + hold=40` 的 worst MDD 較低，但平均報酬與相對 buy-and-hold 落後幅度明顯更差；不能升級為主候選。

### Target-state sanity check

因為 Absolute Momentum 本質上是 target-state 趨勢持有，不一定適合只用固定 hold entry-edge 解讀，所以另外用既有 `Backtester` 做 close-to-close target exposure sanity check。

預設 `momentum_window=126` / `trend_window=200` 結果：

| 指標 | 結果 |
|---|---:|
| Avg return | `225.78%` |
| Worst MDD | `-50.74%` |
| Avg B&H return | `452.95%` |
| Avg excess return | `-227.17%` |

解讀：完整持倉可改善平均報酬與平均 excess，但 worst MDD 接近 buy-and-hold，沒有達成「同時改善 Avg excess return 與 Worst MDD」的本輪目標。

小型參數網格 `momentum_window in 63,126,189,252`、`trend_window in 100,150,200,250` 也沒有找到 worst MDD 優於 `-40%` 且 excess 明顯改善的設定。這表示單純調整動能 / SMA 視窗不是下一個高品質方向。

### Keep / Discard 判斷

- **Keep**：程式層的 `absolute-momentum` 策略與 regression tests。它提供一個文獻支持、deterministic、long-only 的趨勢持有比較錨點，未來多股票 sweep 可持續追蹤。
- **Compare-only**：`absolute-momentum + hold=40`。它在 entry-edge 下七檔都通過 PF gate，且 worst MDD 比 Confluence cooldown baseline 低，但平均報酬與 avg excess return 太差。
- **Discard as main candidate**：預設 `126/200` 作為目前主策略。完整持倉雖改善 avg excess return，但 worst MDD 惡化到 `-50.74%`，不符合穩定營利方向。

### 下一步

1. 不再優先擴大 Absolute Momentum 參數搜尋；避免把樣本內強趨勢貼合成漂亮回測。
2. 下一輪優先補正式 Phase 2 target-state 報表，讓完整持倉策略能直接輸出 benchmark-relative return、MDD、Sortino、Calmar 與 cost stress。
3. 若繼續研究動能類策略，應加入波動縮放或 drawdown control，而不是只調整回看期與均線期數。

## 2026-05-24 研究與執行：Target-state 多股票正式報表

這輪補上正式 Phase 2 target-state 報表工具，避免再用臨時 script 解讀完整持倉策略。新工具是 `tools\multi_stock_target_state_sweep.py`，用既有 `Backtester` 執行 close-to-close target exposure 回測，並在同一份報表中輸出策略績效、buy-and-hold benchmark、excess return、Sharpe、Sortino、Calmar、turnover、time in market 與 1x / 2x / 3x cost stress。

### 本輪程式改動

- 新增 `tools\multi_stock_target_state_sweep.py`。
- 新增 `TargetStateRow` / `TargetStateAggregate`，固定逐檔與 aggregate JSON schema。
- 支援多股票、多策略、多成本倍率：
  - `--strategy` 可重複指定；未指定時使用日線策略清單。
  - `--cost-multipliers-list 1,2,3` 會等比例放大 commission / slippage / transaction tax。
  - `--signal-cooldown-bars` 可沿用 entry-edge wrapper，但 target-state 解讀必須特別小心。
- `tests\test_multi_stock_sweep_tool.py` 新增 parser 與 aggregate regression，鎖住成本倍率解析、benchmark-relative counts 與 drawdown counts。

### Target-state 報表命令

Confluence 無 cooldown：

```powershell
python tools\multi_stock_target_state_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --strategy confluence-score `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-multipliers-list 1,2,3 `
  --summary-json reports\generated\twse-target-state-confluence-coststress-20260524.json `
  --summary-md reports\generated\twse-target-state-confluence-coststress-20260524.md
```

Confluence cooldown：

```powershell
python tools\multi_stock_target_state_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --strategy confluence-score `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-multipliers-list 1,2,3 `
  --signal-cooldown-bars 10 `
  --summary-json reports\generated\twse-target-state-confluence-cooldown10-coststress-20260524.json `
  --summary-md reports\generated\twse-target-state-confluence-cooldown10-coststress-20260524.md
```

Absolute Momentum：

```powershell
python tools\multi_stock_target_state_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --strategy absolute-momentum `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-multipliers-list 1,2,3 `
  --summary-json reports\generated\twse-target-state-absolute-momentum-coststress-20260524.json `
  --summary-md reports\generated\twse-target-state-absolute-momentum-coststress-20260524.md
```

### Aggregate 結果

| Candidate | Cost | Positive | Beat B&H | Lower MDD | Avg return | Avg excess | Worst MDD | Avg Sharpe | Avg Sortino | Avg Calmar | Trades | Avg time in market | 判斷 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `absolute-momentum` | `1x` | `6/7` | `1/7` | `6/7` | `225.78%` | `-226.95%` | `-50.74%` | `0.727` | `1.160` | `0.653` | `350` | `54.05%` | compare-only：報酬 / turnover 最好，但 MDD 太接近 B&H |
| `absolute-momentum` | `3x` | `6/7` | `1/7` | `6/7` | `219.77%` | `-232.52%` | `-51.33%` | `0.709` | `1.133` | `0.631` | `350` | `54.05%` | compare-only：成本壓力後仍穩，但 MDD 未解 |
| `confluence-score` | `1x` | `6/7` | `0/7` | `6/7` | `176.57%` | `-276.16%` | `-51.40%` | `0.636` | `1.084` | `0.422` | `1299` | `39.39%` | discard as target-state main：交易切換太多，且沒有 beat B&H |
| `confluence-score` | `3x` | `6/7` | `0/7` | `6/7` | `157.93%` | `-294.36%` | `-52.63%` | `0.559` | `0.966` | `0.355` | `1299` | `39.39%` | discard as target-state main：成本壓力下更弱 |
| `confluence-score + cooldown10` | `1x` | `6/7` | `0/7` | `6/7` | `108.16%` | `-344.57%` | `-49.24%` | `0.586` | `0.951` | `0.342` | `879` | `30.21%` | discard as target-state main：cooldown 降低曝險但犧牲更多 upside |
| `confluence-score + cooldown10` | `3x` | `6/7` | `0/7` | `5/7` | `98.03%` | `-354.25%` | `-50.91%` | `0.529` | `0.863` | `0.297` | `879` | `30.21%` | discard as target-state main：成本後仍未改善核心問題 |

### 解讀

1. **Absolute Momentum 是目前 target-state 較好的 compare-only 錨點**：平均報酬、平均 excess、交易數與成本壓力都比 Confluence target-state 乾淨，但 worst MDD 仍在 `-50%` 左右，不能說已經朝穩定營利完成。
2. **Confluence cooldown 是 entry-edge 工具，不是自然的完整持倉規則**：在 target-state 回測中，`SignalCooldownStrategy` 會把 cooldown 期間的新 long entry 改成 flat；這可降低 entry overlap，但用完整持倉解讀時會造成額外曝險切換，所以不能把 entry-edge 的 keep 結論直接搬到 Phase 2。
3. **1x / 2x / 3x 成本壓力沒有摧毀平均正報酬，但也沒有解決 benchmark-relative 問題**：三個候選在 3x 成本下平均仍為正，但 `Beat B&H` 最多只有 Absolute Momentum 的 `1/7`。
4. **下一步不該再只調參**：目前缺的是 drawdown control / volatility scaling / allocation rule，而不是更細的 moving window 搜尋。

### Keep / Discard 判斷

- **Keep**：`multi_stock_target_state_sweep.py`。它補上 Phase 2 必要報表，讓完整持倉策略能直接看 benchmark-relative、cost stress 與 risk-adjusted metrics。
- **Compare-only**：`absolute-momentum` target-state。它是目前較好的完整持倉比較錨點，但 MDD 太高。
- **Discard as target-state main**：`confluence-score` 與 `confluence-score + cooldown10`。它們在 entry-edge 有研究價值，但完整持倉報酬 / MDD / turnover tradeoff 不適合直接升級。

### 下一步

1. 優先研究 volatility scaling 或 drawdown control，目標是把 Absolute Momentum 的 `Worst MDD` 從約 `-50%` 降到明顯低於 buy-and-hold，同時不要把 avg excess return 打回 Confluence cooldown 水準。
2. 替 target-state 報表加入 drawdown attribution，定位 worst MDD 主要來自 `2454` 還是其他標的與期間。
3. 做 walk-forward / OOS split，確認 Absolute Momentum 的 target-state edge 是否集中在 2020-2026 強趨勢樣本。

## 2026-05-24 研究與執行：Absolute Momentum volatility target 風控 overlay

這輪接續前一輪 target-state 結論：`absolute-momentum` 是目前較好的完整持倉 compare-only 錨點，但 1x 成本 worst MDD 約 `-50.74%`，接近 buy-and-hold，不符合穩定營利方向。這輪不改動進場邏輯，而是實作一個只降曝險、不加槓桿的 `VolatilityTargetStrategy` wrapper，測試高波動時縮小 target exposure 是否能降低回撤，同時避免 avg excess return 被打回 Confluence cooldown target-state 水準。

### 外部研究參考

- Moreira、Muir 的 Volatility Managed Portfolios 研究指出，許多因子的預期報酬不會隨波動同步上升，因此高波動時降低曝險可能提升 Sharpe。
  https://www.nber.org/papers/w22208
- Harvey、Hoyle、Korgaonkar、Rattray、Sargaison、Van Hemert 的 volatility targeting 報告指出，volatility targeting 對 equity 與 credit 類資產最有效，主要效果包含降低左尾風險與 drawdown。
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3175538

### 本輪程式改動

- 新增 `src\signal_forge\strategies\volatility_target.py`。
- `VolatilityTargetStrategy` 包裝既有策略，流程是：
  1. 底層策略先輸出原始 `Signal`。
  2. 若 `target_position == 0`，保留空手。
  3. 若樣本不足以估 realized volatility，保持空手，reason 為 `vol_target_warmup`。
  4. 若樣本足夠，使用最近 close-to-close returns 計算年化 realized volatility。
  5. `scale = min(max_scale, target_annual_volatility / realized_annual_volatility)`。
  6. 輸出 `target_position * scale`；預設 `max_scale=1.0`，所以不加槓桿。
- `build_phase1_strategy(...)` 新增可選 volatility target 參數，讓 target-state 工具可用同一個 factory 建立 wrapper。
- `tools\multi_stock_target_state_sweep.py` 新增：
  - `--volatility-target`
  - `--volatility-lookback-bars`
  - `--target-annual-volatility`
  - `--volatility-min-observations`
  - `--volatility-max-scale`
- 新增 `tests\test_volatility_target.py`，並補 strategy factory / target-state parser regression。

### Target-state 報表命令

```powershell
python tools\multi_stock_target_state_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --strategy absolute-momentum `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-multipliers-list 1,3 `
  --volatility-target `
  --volatility-lookback-bars 20 `
  --target-annual-volatility 0.40 `
  --volatility-min-observations 20 `
  --summary-json reports\generated\twse-target-state-absolute-momentum-voltarget040-coststress-20260524.json `
  --summary-md reports\generated\twse-target-state-absolute-momentum-voltarget040-coststress-20260524.md
```

### Aggregate 結果

| Candidate | Cost | Positive | Beat B&H | Lower MDD | Avg return | Avg excess | Worst MDD | Avg Sharpe | Avg Sortino | Avg Calmar | Trades | Avg time in market | 判斷 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `absolute-momentum` 原始 target-state | `1x` | `6/7` | `1/7` | `6/7` | `225.78%` | `-226.95%` | `-50.74%` | `0.727` | `1.160` | `0.653` | `350` | `54.05%` | compare-only：報酬最好，但回撤太大 |
| `vol-target 0.25` | `1x` | `6/7` | `1/7` | `6/7` | `132.44%` | `-320.29%` | `-35.14%` | `0.704` | `1.113` | `0.555` | `3445` | `45.00%` | compare-only：回撤改善最大，但 upside 犧牲太多 |
| `vol-target 0.30` | `1x` | `6/7` | `1/7` | `6/7` | `153.69%` | `-299.04%` | `-39.69%` | `0.704` | `1.112` | `0.576` | `2707` | `48.27%` | compare-only：仍偏保守 |
| `vol-target 0.35` | `1x` | `6/7` | `1/7` | `6/7` | `169.42%` | `-283.31%` | `-43.95%` | `0.705` | `1.115` | `0.591` | `2049` | `50.47%` | compare-only：風險/報酬較平衡 |
| `vol-target 0.40` | `1x` | `6/7` | `1/7` | `6/7` | `180.83%` | `-271.90%` | `-47.45%` | `0.706` | `1.116` | `0.598` | `1558` | `51.86%` | compare-only：保留最多 upside，回撤仍有改善 |
| `vol-target 0.40` | `3x` | `6/7` | `1/7` | `6/7` | `175.16%` | `-277.13%` | `-48.05%` | `0.686` | `1.086` | `0.572` | `1558` | `51.86%` | compare-only：成本壓力後仍未失效，但未勝原始風險調整 |

### 解讀

1. **Volatility target 有降低 drawdown 的效果**：`0.25` 把 worst MDD 壓到 `-35.14%`，`0.40` 仍可降到 `-47.45%`，都低於原始 target-state 的 `-50.74%`。
2. **但它不是主候選**：Sharpe / Sortino / Calmar 沒有明顯勝過原始 Absolute Momentum，且 `Beat B&H` 仍只有 `1/7`。
3. **比較合理的追蹤區間是 `0.35` 到 `0.40`**：它們比 Confluence cooldown target-state 的 avg excess 約 `-344.57%` 好，也比原始 Absolute Momentum 回撤低，但還需要 drawdown attribution 與 OOS。
4. **交易數大幅增加**：vol target 會因 fractional exposure 每日調整而增加 trade count。成本壓力後仍保持正報酬，但下一輪若要深化，應研究 rebalance threshold 或再平衡頻率，而不是只調 target vol。

### Keep / Discard 判斷

- **Keep**：`VolatilityTargetStrategy` wrapper 與 target-state CLI 參數。它把 drawdown control 變成可重現、可成本壓力檢查的研究假設。
- **Compare-only**：`absolute-momentum + vol-target`。目前有降低 worst MDD 的效果，但沒有足夠證據升級成主候選。
- **Discard as main candidate**：把 `target_annual_volatility=0.25` 當主策略。它回撤改善最大，但平均報酬與 avg excess 犧牲太多。

### 下一步

1. 補 target-state drawdown attribution，定位 vol target 的 worst MDD 仍來自哪檔股票與期間。
2. 補 walk-forward / OOS split，確認 `0.35` 到 `0.40` 不是 2020-2026 樣本內折衷。
3. 若繼續優化 vol target，先測 rebalance threshold / weekly rebalance，降低 fractional exposure 每日微調造成的交易數。

## 2026-05-24 研究與執行：Target-state drawdown attribution

這輪接續 volatility target 結論，先補 target-state 報表中的 drawdown attribution。目的不是優化參數，而是回答：Absolute Momentum 與 volatility target 的 worst MDD 到底來自哪檔股票、哪段期間，以及當時策略是否仍維持過高曝險。

### 本輪程式改動

- `tools\multi_stock_target_state_sweep.py` 新增 `DrawdownAttribution`，由 `BacktestResult.equity_curve` 找出最大回撤的 peak、trough 與 recovery。
- `TargetStateRow` 新增：
  - `max_drawdown_start_timestamp`
  - `max_drawdown_trough_timestamp`
  - `max_drawdown_recovery_timestamp`
  - `max_drawdown_duration_bars`
  - `max_drawdown_recovery_bars`
  - `max_drawdown_trough_position`
  - `max_drawdown_average_abs_position`
- `TargetStateAggregate` 新增 worst drawdown symbol 與對應 attribution 欄位。
- Markdown 報表新增 `Drawdown Attribution` 與 `Per Stock Drawdown` 兩段，讓下一輪策略修改可以先定位問題來源。
- `tests\test_multi_stock_sweep_tool.py` 新增 regression test，鎖住 peak / trough / recovery / exposure 計算。

### Target-state attribution 結果

| Candidate | Cost | Worst symbol | Worst MDD | Peak | Trough | Recovery | Duration bars | Recovery bars | Trough position | Avg abs position | 判斷 |
|---|---:|---|---:|---|---|---|---:|---:|---:|---:|---|
| `absolute-momentum` | `1x` | `2454` | `-50.74%` | `2024-06-20` | `2025-12-24` | `2026-05-04` | `370` | `80` | `1.000` | `0.574` | compare-only：回撤來源明確，但仍接近 B&H |
| `absolute-momentum` | `3x` | `2454` | `-51.33%` | `2024-06-20` | `2025-12-24` | `2026-05-04` | `370` | `80` | `1.000` | `0.574` | compare-only：成本放大後回撤更深 |
| `absolute-momentum + vol-target 0.40` | `1x` | `2454` | `-47.45%` | `2024-06-20` | `2025-12-24` | `2026-05-05` | `370` | `81` | `1.000` | `0.515` | compare-only：平均曝險下降，但 trough 仍滿倉 |
| `absolute-momentum + vol-target 0.40` | `3x` | `2454` | `-48.05%` | `2024-06-20` | `2025-12-24` | `2026-05-05` | `370` | `81` | `1.000` | `0.515` | compare-only：成本壓力後仍非主候選 |

### 解讀

1. **worst MDD 不是多檔平均問題，而是集中在 `2454` 的長回撤**：原始與 vol-target 版本的 peak / trough 都是 `2024-06-20` 到 `2025-12-24`。
2. **Volatility target 有幫助，但不是足夠的保護機制**：`target_annual_volatility=0.40` 把 1x worst MDD 從 `-50.74%` 降到 `-47.45%`，但 peak-to-trough 平均曝險只從 `0.574` 降到 `0.515`，trough position 仍是 `1.000`。
3. **問題不是再把 target vol 微調漂亮**：若 worst trough 當天仍滿倉，下一步應測 drawdown-state / per-symbol risk-off 或再平衡門檻，而不是只改 `target_annual_volatility`。
4. **`2412` 是另一個要注意的弱點**：報表顯示 `2412` 在 `2022-04-26` 到 `2026-04-08` 的最大回撤尚未完全恢復，且策略本身總報酬為負，後續若做股票池或 regime 過濾，也要把它列為失敗案例。

### Keep / Discard 判斷

- **Keep**：drawdown attribution 報表欄位與 tests。它補上策略評估準則要求的「先定位回撤來源」。
- **Compare-only**：`absolute-momentum + vol-target 0.40`。它比原始版本降低 worst MDD，但沒有解決 `2454` trough 滿倉問題。
- **Discard as immediate main candidate**：繼續單純調 target vol。這輪證據顯示問題是 drawdown 狀態辨識與單檔風險控制，不只是目標波動率高低。

### 下一步

1. 優先做 `absolute-momentum` 的 drawdown-state / per-symbol risk-off 最小版本，例如當單檔 equity 從高點回撤超過門檻時暫時降曝險，並用同一套七檔、1x / 3x 成本壓力比較。
2. 若不先改策略，先補 walk-forward / OOS split，確認 `2454` 的 2024-2025 回撤不是樣本內特例。
3. 若繼續 volatility target，先測 rebalance threshold / weekly rebalance，目標是降低交易數，而不是期待它單獨解決最大回撤。

## 2026-05-24 研究與執行：Absolute Momentum drawdown risk-off overlay

這輪接續 target-state drawdown attribution 結論：`absolute-momentum` 與 `vol-target 0.40` 的 worst MDD 都集中在 `2454` 的 `2024-06-20` 到 `2025-12-24`，且 trough 當天仍是滿倉 `1.000`。因此本輪不再調動能窗或目標波動，而是新增一個可驗證的 `DrawdownRiskOffStrategy` wrapper，用策略層 proxy equity 測試單檔回撤狀態下先降曝險是否有效。

### 本輪程式改動

- 新增 `src\signal_forge\strategies\drawdown_risk_off.py`。
- `DrawdownRiskOffStrategy` 包裝既有策略，流程是：
  1. 底層策略先輸出逐 bar `Signal`。
  2. wrapper 用與 `Backtester` 對齊的 close-to-close target exposure 語意維護 proxy equity。
  3. proxy equity 從本地 high-water mark 回撤超過 `drawdown_threshold` 時，後續 `risk_off_bars` 內將非零 target 改成 `0.0`，reason 為 `drawdown_risk_off`。
  4. risk-off 結束後以當下 proxy equity 重設本地 high-water mark，避免 flat 期間因舊高點造成永久空手。
- `build_phase1_strategy(...)` 新增：
  - `drawdown_risk_off`
  - `drawdown_risk_off_threshold`
  - `drawdown_risk_off_bars`
- `tools\multi_stock_target_state_sweep.py` 新增：
  - `--drawdown-risk-off`
  - `--drawdown-risk-off-threshold`
  - `--drawdown-risk-off-bars`
- 新增 `tests\test_drawdown_risk_off.py`，並補 strategy factory / target-state parser regression。

### Target-state 報表命令

單獨 drawdown risk-off：

```powershell
python tools\multi_stock_target_state_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --strategy absolute-momentum `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-multipliers-list 1,3 `
  --drawdown-risk-off `
  --drawdown-risk-off-threshold 0.25 `
  --drawdown-risk-off-bars 120 `
  --summary-json reports\generated\twse-target-state-absolute-momentum-ddriskoff25b120-20260524.json `
  --summary-md reports\generated\twse-target-state-absolute-momentum-ddriskoff25b120-20260524.md
```

疊加 volatility target：

```powershell
python tools\multi_stock_target_state_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --strategy absolute-momentum `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-multipliers-list 1,3 `
  --volatility-target `
  --volatility-lookback-bars 20 `
  --target-annual-volatility 0.40 `
  --volatility-min-observations 20 `
  --volatility-max-scale 1.0 `
  --drawdown-risk-off `
  --drawdown-risk-off-threshold 0.25 `
  --drawdown-risk-off-bars 120 `
  --summary-json reports\generated\twse-target-state-absolute-momentum-voltarget040-ddriskoff25b120-20260524.json `
  --summary-md reports\generated\twse-target-state-absolute-momentum-voltarget040-ddriskoff25b120-20260524.md
```

### Aggregate 結果

| Candidate | Cost | Positive | Beat B&H | Lower MDD | Avg return | Avg excess | Worst MDD | Avg Sharpe | Avg Sortino | Avg Calmar | Trades | Avg time in market | 判斷 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `absolute-momentum` 原始 target-state | `1x` | `6/7` | `1/7` | `6/7` | `225.78%` | `-226.95%` | `-50.74%` | `0.727` | `1.160` | `0.653` | `350` | `54.05%` | compare-only：報酬最好，但回撤太大 |
| `vol-target 0.40` | `1x` | `6/7` | `1/7` | `6/7` | `180.83%` | `-271.90%` | `-47.45%` | `0.706` | `1.116` | `0.598` | `1558` | `51.86%` | compare-only：回撤降低但風險調整未勝原始 |
| `dd-risk-off 20%/60` | `1x` | `5/7` | `1/7` | `5/7` | `142.47%` | `-310.26%` | `-59.40%` | `0.535` | `0.852` | `0.386` | `313` | `46.48%` | discard：worst MDD 惡化且 2454 trough 仍滿倉 |
| `dd-risk-off 25%/120` | `1x` | `6/7` | `1/7` | `6/7` | `207.18%` | `-245.55%` | `-46.95%` | `0.682` | `1.093` | `0.599` | `301` | `47.20%` | compare-only：比 raw 降回撤，但 Sharpe / Calmar 下降 |
| `vol-target 0.40 + dd-risk-off 25%/120` | `1x` | `6/7` | `1/7` | `6/7` | `188.37%` | `-264.36%` | `-44.93%` | `0.738` | `1.176` | `0.620` | `1416` | `48.25%` | compare-only：本輪較佳風控組合，但仍未解 benchmark-relative |
| `vol-target 0.40 + dd-risk-off 25%/120` | `3x` | `6/7` | `1/7` | `6/7` | `183.14%` | `-269.15%` | `-45.16%` | `0.719` | `1.148` | `0.595` | `1416` | `48.25%` | compare-only：成本壓力後仍未失效，但不能升級 |

### 解讀

1. **單純 `20%/60 bars` 是錯的方向**：它把 worst MDD 從原始 `-50.74%` 惡化到 `-59.40%`，而且 positive count 降到 `5/7`，所以 discard。
2. **`25%/120 bars` 有降低 MDD，但不是主候選**：1x worst MDD 降到 `-46.95%`，平均報酬仍有 `207.18%`，但 Sharpe / Calmar 低於原始 target-state。
3. **疊加 `vol-target 0.40` 後，本輪風控 tradeoff 較好**：1x worst MDD 降到 `-44.93%`，平均 Sharpe `0.738` 略高於原始 target-state `0.727`，但 avg return 低於原始，且仍只有 `1/7` beat B&H。
4. **trough position 問題仍未完全解**：`vol-target 0.40 + dd-risk-off 25%/120` 的 worst drawdown 仍來自 `2454`，peak `2024-06-20`、trough `2025-12-24`，trough position 仍是 `1.000`，只是 peak-to-trough 平均曝險降到 `0.248`。

### Keep / Discard 判斷

- **Keep**：`DrawdownRiskOffStrategy` wrapper 與 target-state CLI 參數。它把 drawdown-state 風控變成可重現、可測試、可成本壓力檢查的研究假設。
- **Discard**：`dd-risk-off 20%/60 bars`。它明確惡化 worst MDD。
- **Compare-only**：`dd-risk-off 25%/120` 與 `vol-target 0.40 + dd-risk-off 25%/120`。它們有降低回撤的價值，但 benchmark-relative 與 trough 滿倉問題仍未解。

### 下一步

1. 不再只擴大 drawdown threshold / risk-off bars grid；下一輪若做風控，應測 re-entry 條件或 weekly rebalance。
2. 補 walk-forward / OOS split，確認 `25%/120` 的 tradeoff 不是 2020-2026 樣本內折衷。
3. 針對 `2412` 與 `2454` 建立失敗案例檢查：一個是負報酬弱標的，一個是長回撤集中標的。

## 2026-05-24 研究與執行：Target-state walk-forward / OOS 分段驗證

這輪接續策略評估準則中的 anti-overfitting 要求，不新增交易邏輯，而是讓 `multi_stock_target_state_sweep.py` 能對同一批策略 / 成本 / wrapper 做 walk-forward / OOS 分段。目的不是把參數調得更漂亮，而是確認前面看到的 drawdown-control tradeoff 是否能離開 full-window 樣本仍站得住。

### 本輪程式改動

- `tools\multi_stock_target_state_sweep.py` 新增：
  - `WalkForwardWindow`
  - `WalkForwardWindowResult`
  - `WalkForwardRetentionRow`
  - `parse_walk_forward_windows(...)`
  - `run_walk_forward_sweep(...)`
  - `build_walk_forward_retention(...)`
  - `format_walk_forward_markdown(...)`
- CLI 新增 `--walk-forward-windows`，格式為 `label:start:end,label:start:end`。
- JSON 摘要在既有 `rows` / `aggregates` 外，額外輸出：
  - `walk_forward_windows`
  - `walk_forward_results`
  - `walk_forward_retention`
- Markdown 摘要新增：
  - `Walk-forward Windows`
  - `Walk-forward Retention`
- `tests\test_multi_stock_sweep_tool.py` 新增 parser、retention 公式與 CLI regression。

### Target-state OOS 報表命令

原始 Absolute Momentum：

```powershell
python tools\multi_stock_target_state_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --strategy absolute-momentum `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-multipliers-list 1,3 `
  --walk-forward-windows "is:2020-01-01:2023-12-31,oos:2024-01-01:2026-05-20" `
  --summary-json reports\generated\twse-target-state-absolute-momentum-oos-20260524.json `
  --summary-md reports\generated\twse-target-state-absolute-momentum-oos-20260524.md
```

疊加 `vol-target 0.40 + dd-risk-off 25%/120`：

```powershell
python tools\multi_stock_target_state_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --strategy absolute-momentum `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-multipliers-list 1,3 `
  --volatility-target `
  --volatility-lookback-bars 20 `
  --target-annual-volatility 0.40 `
  --volatility-min-observations 20 `
  --volatility-max-scale 1.0 `
  --drawdown-risk-off `
  --drawdown-risk-off-threshold 0.25 `
  --drawdown-risk-off-bars 120 `
  --walk-forward-windows "is:2020-01-01:2023-12-31,oos:2024-01-01:2026-05-20" `
  --summary-json reports\generated\twse-target-state-absolute-momentum-voltarget040-ddriskoff25b120-oos-20260524.json `
  --summary-md reports\generated\twse-target-state-absolute-momentum-voltarget040-ddriskoff25b120-oos-20260524.md
```

Confluence cooldown target-state 對照：

```powershell
python tools\multi_stock_target_state_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --strategy confluence-score `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-multipliers-list 1,3 `
  --signal-cooldown-bars 10 `
  --walk-forward-windows "is:2020-01-01:2023-12-31,oos:2024-01-01:2026-05-20" `
  --summary-json reports\generated\twse-target-state-confluence-cooldown10-oos-20260524.json `
  --summary-md reports\generated\twse-target-state-confluence-cooldown10-oos-20260524.md
```

### OOS 結果摘要

| Candidate | Cost | IS positive | IS beat B&H | IS avg return | IS avg excess | IS worst MDD | OOS positive | OOS beat B&H | OOS avg return | OOS avg excess | OOS worst MDD | 判斷 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `absolute-momentum` | `1x` | `6/7` | `2/7` | `36.76%` | `-43.54%` | `-40.50%` | `5/7` | `1/7` | `84.58%` | `-105.25%` | `-36.32%` | compare-only：OOS 報酬保留，但 active return 仍負 |
| `absolute-momentum` | `3x` | `6/7` | `2/7` | `35.49%` | `-44.67%` | `-41.17%` | `5/7` | `1/7` | `83.31%` | `-106.29%` | `-36.93%` | compare-only：成本壓力後仍未崩，但 benchmark-relative 不合格 |
| `vol-target 0.40 + dd-risk-off 25%/120` | `1x` | `6/7` | `2/7` | `41.12%` | `-39.18%` | `-27.81%` | `5/7` | `0/7` | `62.17%` | `-127.67%` | `-27.20%` | compare-only：MDD 較穩，但 OOS 完全沒 beat B&H |
| `vol-target 0.40 + dd-risk-off 25%/120` | `3x` | `6/7` | `2/7` | `39.83%` | `-40.32%` | `-28.21%` | `5/7` | `0/7` | `61.05%` | `-128.55%` | `-27.54%` | compare-only：成本後仍穩，但 active return 更弱 |
| `confluence-score + cooldown10` | `1x` | `7/7` | `2/7` | `37.71%` | `-42.59%` | `-38.11%` | `5/7` | `0/7` | `45.93%` | `-143.90%` | `-26.09%` | discard as target-state main：OOS active return 最弱 |
| `confluence-score + cooldown10` | `3x` | `7/7` | `0/7` | `33.70%` | `-46.46%` | `-39.18%` | `5/7` | `0/7` | `43.26%` | `-146.34%` | `-26.74%` | discard as target-state main：成本壓力後仍沒有 benchmark edge |

### 解讀

1. **樣本外總報酬沒有崩潰，但 benchmark-relative 全部不合格**：三個候選 OOS 都保持平均正報酬，但 `Beat B&H` 最好只有原始 Absolute Momentum 的 `1/7`；兩個風控 / cooldown 版本都是 `0/7`。
2. **風控 overlay 的價值是降低回撤，不是提升 active return**：`vol-target 0.40 + dd-risk-off 25%/120` 把 OOS worst MDD 壓到約 `-27%`，比原始 Absolute Momentum 的約 `-36%` 好，但 avg return 也從 `84.58%` 降到 `62.17%`，avg excess 從 `-105.25%` 惡化到 `-127.67%`。
3. **Confluence cooldown 仍不適合 target-state 主線**：OOS worst MDD 約 `-26.09%` 看似較穩，但 OOS avg excess 約 `-143.90%`，且 `0/7` beat buy-and-hold。
4. **OOS retention 不能只看 return retention**：三個候選 OOS return retention 都超過 `100%`，但這是因為 OOS benchmark 更強；真正的問題是 active return 全部為負，因此不能升級。

### Keep / Discard 判斷

- **Keep**：walk-forward / OOS 報表功能與 tests。它補上策略評估準則的 anti-overfitting gate，讓之後找新策略或調參必須通過同一個樣本外檢查。
- **Compare-only**：原始 `absolute-momentum` 與 `vol-target 0.40 + dd-risk-off 25%/120`。前者 OOS 報酬較強但回撤較深；後者 OOS 回撤較低但完全輸給 B&H。
- **Discard as target-state main**：`confluence-score + cooldown10`。它在 target-state/OOS 下沒有 benchmark edge，只能保留為 Phase 1 entry-edge 研究線索。

### 下一步

1. 不再把「降低 worst MDD」當成唯一優化方向；下一輪必須同時看 OOS active return。
2. 若繼續 Absolute Momentum，優先做 re-entry / weekly rebalance / stock-pool 或 regime filter，目標是改善 `Beat B&H`，不是只壓低 MDD。
3. 若上網找新策略，第一版就要用這個 OOS split 和 1x/3x cost stress 檢查，不接受只有 full-window equity curve 的策略。

## 2026-05-24 Relative Momentum stock-pool filter

### 假設

前一輪 OOS 顯示 Absolute Momentum 系列「平均報酬為正，但 benchmark-relative 不合格」。本輪參考 momentum 文獻中的兩條線索：

- time-series / absolute momentum：用標的自己的過去報酬判斷是否有趨勢。
- cross-sectional / relative momentum：在同一股票池內偏好近期相對強的標的。

因此本輪假設是：先保留 Absolute Momentum 的 `126/200` long/flat 判斷，再加一層多股票相對動能白名單，只允許同日 lookback return 排名前 N 且自身 return 大於 0 的股票保留非零 target。

### 本輪程式改動

- `tools\multi_stock_target_state_sweep.py` 新增：
  - `build_relative_momentum_allowlist(...)`
  - `RelativeMomentumFilteredStrategy`
- CLI 新增：
  - `--relative-momentum-filter`
  - `--relative-momentum-lookback-bars`
  - `--relative-momentum-top-n`
  - `--relative-momentum-min-return`
- `tests\test_multi_stock_sweep_tool.py` 新增：
  - parser regression
  - allowlist top-N ranking regression
  - wrapper flatten regression

### Target-state OOS 報表命令

正式留存的 top-3 報表：

```powershell
python tools\multi_stock_target_state_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --strategy absolute-momentum `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-multipliers-list 1,3 `
  --relative-momentum-filter `
  --relative-momentum-lookback-bars 126 `
  --relative-momentum-top-n 3 `
  --relative-momentum-min-return 0.0 `
  --walk-forward-windows "is:2020-01-01:2023-12-31,oos:2024-01-01:2026-05-20" `
  --summary-json reports\generated\twse-target-state-absolute-momentum-relmom-top3-oos-20260524.json `
  --summary-md reports\generated\twse-target-state-absolute-momentum-relmom-top3-oos-20260524.md
```

### OOS 結果摘要

| Candidate | Cost | OOS positive | OOS beat B&H | OOS avg return | OOS avg excess | OOS worst MDD | 判斷 |
|---|---:|---:|---:|---:|---:|---:|---|
| `absolute-momentum + rel-mom top3` | `1x` | `6/7` | `0/7` | `65.21%` | `-124.63%` | `-32.95%` | discard as improvement：降曝險但沒有 benchmark edge |
| `absolute-momentum + rel-mom top3` | `3x` | `6/7` | `0/7` | `64.08%` | `-125.52%` | `-33.33%` | discard as improvement：成本壓力後仍沒有 beat B&H |

額外掃描 `lookback=63/126/252`、`topN=1/2/3/4/5/7`：

| Lookback | Top N | Cost | OOS Avg return | OOS Avg excess | Beat B&H | Worst MDD | 解讀 |
|---:|---:|---:|---:|---:|---:|---:|---|
| `126` | `7` | `1x` | `84.58%` | `-105.25%` | `1/7` | `-36.32%` | 最佳 active return，但等同幾乎不篩選 |
| `252` | `7` | `1x` | `81.35%` | `-108.48%` | `1/7` | `-32.88%` | 回撤略好，active return 較差 |
| `63` | `7` | `1x` | `76.09%` | `-113.75%` | `1/7` | `-30.87%` | 仍是寬鬆篩選，沒有改善勝率 |
| `126` | `3` | `1x` | `65.21%` | `-124.63%` | `0/7` | `-32.95%` | 嚴格 top-N 後報酬下降 |
| `252` | `1` | `1x` | `50.66%` | `-139.18%` | `0/7` | `-17.21%` | 回撤最低之一，但犧牲太多 upside |

### Keep / Discard 判斷

- **Keep as tool**：相對動能白名單是 deterministic、test-covered、預設關閉的研究能力，可保留供後續 portfolio allocation 或其他策略使用。
- **Discard as Absolute Momentum improvement**：top-N 股票池篩選沒有改善 OOS `Beat B&H` 或 avg excess，不能當成穩定營利方向。
- **下一步**：不要再只靠股票池 top-N 降曝險；若繼續 Absolute Momentum，應改測 re-entry、weekly rebalance 或市場 regime，且仍用同一 OOS split 和 1x/3x cost stress 驗證。

## 2026-05-24 Portfolio-level Relative Momentum Rotation

### 假設

上一輪把 relative momentum 當成逐檔 target-state filter，結果不佳。但這個評估方式有一個方法問題：相對動能本來是 portfolio allocation 問題，不應該把每檔股票各自拿去和自己的 buy-and-hold 比。這輪改成 portfolio-level rotation：

- 同一批七檔 TWSE 股票視為一個股票池。
- 每個 rebalance date 用 lookback return 排名。
- 只持有近期報酬大於 `0` 的 top-N 股票，等權配置。
- Benchmark 改成同一股票池的 equal-weight buy-and-hold portfolio。

### 來源

- Goyal and Jegadeesh, Cross-Sectional and Time-Series Tests of Return Predictability: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2610288
- Antonacci, Absolute Momentum: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2244633
- Jegadeesh and Titman, Returns to Buying Winners and Selling Losers: https://www.jstor.org/stable/2328882
- Kim, Tse and Wald, Time Series Momentum and Volatility Scaling: https://www.sciencedirect.com/science/article/abs/pii/S1386418116301379

### 本輪程式改動

- 新增 `tools\portfolio_rotation_sweep.py`：
  - 多 CSV 載入與共同 timestamp 對齊。
  - `daily` / `weekly` / `monthly` rebalance。
  - lookback return top-N 等權配置。
  - equal-weight buy-and-hold portfolio benchmark。
  - 1x / 3x cost stress。
  - `--walk-forward-windows` 分段驗證。
  - JSON / Markdown 摘要輸出。
- 新增 `tests\test_portfolio_rotation_sweep_tool.py`：
  - CLI parser regression。
  - close table common timestamp 對齊 regression。
  - top momentum 選股 regression。
  - benchmark 初始入場成本 regression。
  - portfolio retention regression。
- 新增策略筆記：[[../策略筆記/Portfolio Relative Momentum Rotation|Portfolio Relative Momentum Rotation]]。

### 正式候選命令

```powershell
python tools\portfolio_rotation_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-multipliers-list 1,3 `
  --rebalance-frequency monthly `
  --lookback-bars 21 `
  --top-n 3 `
  --min-return 0.0 `
  --walk-forward-windows "is:2020-01-01:2023-12-31,oos:2024-01-01:2026-05-20" `
  --summary-json reports\generated\twse-portfolio-rotation-monthly-lb21-top3-oos-20260524.json `
  --summary-md reports\generated\twse-portfolio-rotation-monthly-lb21-top3-oos-20260524.md
```

三段 rolling split：

```powershell
python tools\portfolio_rotation_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-multipliers-list 1,3 `
  --rebalance-frequency monthly `
  --lookback-bars 21 `
  --top-n 3 `
  --min-return 0.0 `
  --walk-forward-windows "early:2020-01-01:2021-12-31,mid:2022-01-01:2023-12-31,oos:2024-01-01:2026-05-20" `
  --summary-json reports\generated\twse-portfolio-rotation-monthly-lb21-top3-rolling-20260524.json `
  --summary-md reports\generated\twse-portfolio-rotation-monthly-lb21-top3-rolling-20260524.md
```

### 結果摘要

| Window | Cost | Return | Equal-weight B&H | Excess | MDD | Benchmark MDD | Sharpe | 判斷 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Full `2020-2026` | `1x` | `968.64%` | `404.03%` | `564.61%` | `-30.81%` | `-28.11%` | `1.711` | promising candidate |
| Full `2020-2026` | `3x` | `936.91%` | `403.83%` | `533.09%` | `-31.25%` | `-28.11%` | `1.691` | 成本壓力後仍保留 |
| IS `2020-2023` | `1x` | `93.14%` | `83.28%` | `9.86%` | `-30.81%` | `-28.11%` | `0.942` | IS edge 小但為正 |
| OOS `2024-2026` | `1x` | `485.79%` | `177.11%` | `308.68%` | `-21.11%` | `-25.16%` | `2.783` | OOS 強，但需防過擬合 |
| OOS `2024-2026` | `3x` | `479.73%` | `177.00%` | `302.73%` | `-21.15%` | `-25.16%` | `2.768` | 3x 成本後仍強 |

三段 rolling split：

| Window | Cost | Return | Equal-weight B&H | Excess | MDD | Benchmark MDD | Sharpe | 判斷 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `2020-2021` | `1x` | `104.58%` | `90.91%` | `13.67%` | `-16.30%` | `-23.11%` | `1.623` | 正 active return |
| `2022-2023` | `1x` | `0.45%` | `-1.77%` | `2.21%` | `-24.71%` | `-27.59%` | `0.107` | 弱市場中勉強勝出，但 edge 很薄 |
| `2024-2026` | `1x` | `485.79%` | `177.11%` | `308.68%` | `-21.11%` | `-25.16%` | `2.783` | 強勢市場中顯著勝出 |

### 解讀

1. **這是第一個 portfolio-level active return 明顯為正的候選**：和 equal-weight B&H portfolio 比，full-window 與 OOS 都為正，3x 成本壓力後仍保留。
2. **真正改善來自評估層級修正**：相對動能不適合逐檔和單檔 B&H 比；portfolio rotation 的 benchmark 必須是同股票池的 equal-weight portfolio。
3. **中段 2022-2023 是弱點**：`1x` excess 只有 `+2.21%`，Sharpe 只有 `0.107`，代表策略在盤整或弱市場中沒有明顯 edge，只是略勝 benchmark。
4. **OOS 很強但不能直接宣稱穩定營利**：本輪小範圍掃描後選出 `monthly + 21 bars + top3`，仍有參數選擇偏誤風險；需要更多 rolling split、更多股票池與 active risk 指標。

### Keep / Discard 判斷

- **Keep**：`tools\portfolio_rotation_sweep.py` 與 tests。它補上 portfolio-level 評估能力，避免相對動能被逐檔 B&H 指標錯判。
- **Promising candidate**：`monthly + 21 bars + top3 + min_return 0.0`。它通過 full-window、OOS、3x 成本與三段 rolling split 的初步 gate。
- **Not complete / not stable-profit proof**：股票池太小、參數是掃描後挑出；雖然已補 Information Ratio / tracking error / active drawdown，但中段 rolling split 的 IR 太低，仍不能標為穩定營利完成。

### 下一步

1. 增加 rolling windows，例如每兩年訓練、一年測試，避免只看三段粗切。
2. 擴大 TWSE 股票池或加入 sector / market regime，確認結果不是少數大型半導體股驅動。
3. 若繼續調 portfolio rotation 參數，必須同時看 Information Ratio、tracking error 與 active max drawdown，不只看 total return。
4. 保留 live dry-run only，不做 broker / API key / 真實下單。

## 2026-05-24 Portfolio rotation active-risk 指標

### 假設

前一輪 portfolio rotation 的總報酬與 OOS excess 很強，但仍缺 benchmark-relative risk 指標。這輪不再掃新參數，而是補上三個檢查：

- `annualized_active_return`：策略逐期報酬減 benchmark 逐期報酬後的年化算術平均。
- `tracking_error`：active return 的年化標準差，也就是主動風險。
- `information_ratio`：annualized active return / tracking error。
- `active_max_drawdown`：用 normalized relative equity 計算相對 benchmark 的高點回落。

### 來源

- CFA Institute, Sharpe Ratio and Information Ratio: https://rpc.cfainstitute.org/-/media/documents/code/gips/sharpe-ratio-and-the-information-ratio.pdf
- CFA Institute, Analysis of Active Portfolio Management: https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2025/analysis-active-portfolio-management
- Bailey and Lopez de Prado, The Deflated Sharpe Ratio: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551

### 本輪程式改動

- `tools\portfolio_rotation_sweep.py` 的 `PortfolioRotationResult` 新增：
  - `annualized_active_return`
  - `tracking_error`
  - `information_ratio`
  - `active_max_drawdown`
- equal-weight benchmark 權益曲線改由共用 helper 建立，避免 benchmark summary 與 active-risk 計算使用不同基準。
- Markdown / JSON / walk-forward retention 會輸出 IR、tracking error 與 active MDD。
- `tests\test_portfolio_rotation_sweep_tool.py` 補上 active-risk regression。

### 驗證命令

```powershell
python tools\portfolio_rotation_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-multipliers-list 1,3 `
  --rebalance-frequency monthly `
  --lookback-bars 21 `
  --top-n 3 `
  --min-return 0.0 `
  --walk-forward-windows "early:2020-01-01:2021-12-31,mid:2022-01-01:2023-12-31,oos:2024-01-01:2026-05-20" `
  --summary-json reports\generated\twse-portfolio-rotation-monthly-lb21-top3-active-risk-20260524.json `
  --summary-md reports\generated\twse-portfolio-rotation-monthly-lb21-top3-active-risk-20260524.md
```

### Active-risk 結果摘要

| Window | Cost | Annual active | Tracking error | IR | Active MDD | 解讀 |
|---|---:|---:|---:|---:|---:|---|
| Full `2020-2026` | `1x` | `14.43%` | `16.81%` | `0.858` | `-21.73%` | full-window 主動風險報酬達強候選水準 |
| Full `2020-2026` | `3x` | `13.90%` | `16.82%` | `0.826` | `-22.76%` | 成本壓力後仍保留 |
| `2020-2021` | `1x` | `4.48%` | `15.94%` | `0.281` | `-16.97%` | 早期 window 有正 active return，但 IR 只算有意義、未達強 |
| `2022-2023` | `1x` | `0.95%` | `17.05%` | `0.056` | `-18.34%` | 弱點：幾乎沒有 risk-adjusted active edge |
| `2024-2026` | `1x` | `37.82%` | `17.80%` | `2.124` | `-16.04%` | OOS 非常強，但也代表結果高度集中於近年 |

### 解讀

1. **IR 補上後，結論更保守**：full-window IR `0.858` 很強，但不是每個 rolling window 都強；`2022-2023` IR 只有 `0.056`，幾乎沒有主動風險報酬。
2. **OOS 強度集中在 2024-2026**：OOS IR `2.124` 很漂亮，但也提示參數可能特別吃近年強勢行情或股票池結構，不能直接視為穩定營利。
3. **Active MDD 沒有失控**：full-window active MDD 約 `-21.73%`，OOS active MDD 約 `-16.04%`，代表相對 benchmark 的回撤可讀，但仍需更廣股票池確認。

### Keep / Discard 判斷

- **Keep**：active-risk 指標與報表欄位。它們直接對應策略評估準則的 benchmark-relative gate。
- **Promising candidate but not complete**：`monthly + 21 bars + top3` 仍是目前最強 portfolio-level 候選，但穩定性尚未被證明。
- **下一步**：先做更多 rolling windows 或擴大股票池；不要只靠 OOS `2024-2026` 的高 IR 判定策略穩定。

## 2026-05-24 Portfolio rotation rolling windows

### 假設

前一輪 active-risk 指標顯示 `2022-2023` 中段 IR 幾乎為零，但它仍只是手寫的三段切分。這輪不調策略參數，而是把 rolling window 產生器做進 `portfolio_rotation_sweep.py`，讓同一候選可以固定用 24 個月視窗、12 個月步進檢查穩定性。

### 本輪程式改動

- `tools\portfolio_rotation_sweep.py` 新增 `build_rolling_windows(...)`。
- CLI 新增：
  - `--rolling-window-months`
  - `--rolling-step-months`
  - `--rolling-min-months`
- `--walk-forward-windows` 與 `--rolling-window-months` 互斥，避免同一份報表混入兩套 window 語意。
- `tests\test_portfolio_rotation_sweep_tool.py` 新增 parser 與 rolling final partial window regression。

### 驗證命令

```powershell
python tools\portfolio_rotation_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-multipliers-list 1,3 `
  --rebalance-frequency monthly `
  --lookback-bars 21 `
  --top-n 3 `
  --min-return 0.0 `
  --rolling-window-months 24 `
  --rolling-step-months 12 `
  --rolling-min-months 12 `
  --summary-json reports\generated\twse-portfolio-rotation-monthly-lb21-top3-rolling24m-20260524.json `
  --summary-md reports\generated\twse-portfolio-rotation-monthly-lb21-top3-rolling24m-20260524.md
```

### 24 個月 rolling 結果摘要

| Window | Range | Cost | Return | Benchmark return | Excess | IR | Active MDD | 判斷 |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `roll01` | `2020-2021` | `1x` | `104.58%` | `90.91%` | `13.67%` | `0.281` | `-16.97%` | 正，但 IR 不高 |
| `roll02` | `2021-2022` | `1x` | `-18.74%` | `5.88%` | `-24.62%` | `-0.881` | `-23.27%` | 失敗 window |
| `roll03` | `2022-2023` | `1x` | `0.45%` | `-1.77%` | `2.21%` | `0.056` | `-18.34%` | 幾乎沒有 edge |
| `roll04` | `2023-2024` | `1x` | `96.83%` | `68.20%` | `28.63%` | `0.759` | `-14.88%` | 強候選水準 |
| `roll05` | `2024-2025` | `1x` | `240.41%` | `81.93%` | `158.48%` | `2.288` | `-10.07%` | 非常強 |
| `roll06` | `2025-2026-05` | `1x` | `226.20%` | `102.48%` | `123.72%` | `2.012` | `-16.04%` | 非常強，但 partial window |

### 解讀

1. **rolling windows 推翻了「穩定」假設**：`roll02` 是明確失敗區間，策略輸給等權 benchmark 且 IR 為負。
2. **強度集中在 2023 之後**：`roll04` 到 `roll06` 都很強，代表策略可能吃到近年大型股動能環境；這不是壞事，但不能當成跨 regime 穩定證明。
3. **中段問題需要策略層改進**：如果要繼續這條線，下一步不是再看 full-window，而是針對 2021-2022 做 market regime filter、風險降檔或擴大股票池。

### Keep / Discard 判斷

- **Keep**：rolling window generator 與 tests。它讓每次 portfolio rotation 調參都能固定檢查多個滑動區間。
- **Downgrade candidate confidence**：`monthly + 21 bars + top3` 仍是目前最強候選之一，但因 `roll02` 失敗，不能稱為穩定營利候選。
- **下一步**：先研究 market regime / risk-off overlay 對 `roll02` 的影響，或擴大股票池；不要只用 2024-2026 做主論據。

## 2026-05-24 Portfolio rotation market regime filter

### 假設

24 個月 rolling windows 顯示 `2021-2022` 是 portfolio rotation 的明確失敗區間。這輪參考 moving-average market timing / trend filter 文獻，測一個最小 market regime overlay：用同一股票池的等權 normalized price index 作為市場 proxy，當 index 低於自身 SMA 時，該次 rebalance 不持股、留現金。

### 來源

- Meb Faber, Relative Strength Strategies for Investing: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1585517
- The real-life performance of market timing with moving average and time-series momentum rules: https://link.springer.com/article/10.1057/jam.2014.25
- Market Timing with Moving Averages: https://www.mdpi.com/2071-1050/10/7/2125

### 本輪程式改動

- `tools\portfolio_rotation_sweep.py` 新增：
  - `--market-regime-filter`
  - `--market-regime-sma-bars`
  - `_equal_weight_price_index(...)`
  - `_market_regime_is_risk_on(...)`
- `PortfolioRotationResult` 新增：
  - `market_regime_filter`
  - `market_regime_sma_bars`
  - `regime_block_count`
- Markdown 報表新增 regime 欄位，walk-forward windows 也會顯示每段被 regime 擋掉的 rebalance 次數。
- `tests\test_portfolio_rotation_sweep_tool.py` 新增 market regime parser / block regression。

### 參數掃描摘要

先用 `market_regime_sma_bars = 42 / 63 / 84 / 126 / 168 / 200 / 252` 做小範圍掃描，固定其餘參數為 `monthly + 21 bars + top3`。

| SMA bars | Full return | Full excess | Full IR | `2021-2022` return | `2021-2022` excess | `2021-2022` IR | Positive excess windows | 解讀 |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `42` | `414.89%` | `10.86%` | `0.019` | `-21.83%` | `-27.71%` | `-0.936` | `3/6` | 太敏感，幾乎消滅 active edge |
| `63` | `604.95%` | `200.92%` | `0.340` | `-11.33%` | `-17.21%` | `-0.570` | `3/6` | 改善 roll02，但整體弱 |
| `84` | `780.38%` | `376.35%` | `0.544` | `-7.71%` | `-13.59%` | `-0.463` | `5/6` | 本輪較合理折衷，但仍輸原始候選 |
| `126` | `610.77%` | `206.74%` | `0.340` | `-2.20%` | `-8.08%` | `-0.319` | `2/6` | 最能降低 roll02 傷害，但犧牲多數 window |
| `168` | `668.25%` | `264.22%` | `0.411` | `-2.02%` | `-7.90%` | `-0.319` | `2/6` | 和 126 類似，仍不夠好 |
| `200` | `701.57%` | `297.54%` | `0.450` | `-0.99%` | `-6.87%` | `-0.290` | `2/6` | roll02 最接近修復，但整體 window 太少過關 |
| `252` | `482.21%` | `78.18%` | `0.149` | `-2.58%` | `-8.46%` | `-0.345` | `2/6` | 太慢，整體 active edge 明顯下降 |

### 正式 compare-only 報表命令

本輪保留 `84` bar SMA 作為折衷版本的正式報表，不代表它升級為主候選。

```powershell
python tools\portfolio_rotation_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-multipliers-list 1,3 `
  --rebalance-frequency monthly `
  --lookback-bars 21 `
  --top-n 3 `
  --min-return 0.0 `
  --market-regime-filter `
  --market-regime-sma-bars 84 `
  --rolling-window-months 24 `
  --rolling-step-months 12 `
  --rolling-min-months 12 `
  --summary-json reports\generated\twse-portfolio-rotation-monthly-lb21-top3-regime84-rolling24m-20260524.json `
  --summary-md reports\generated\twse-portfolio-rotation-monthly-lb21-top3-regime84-rolling24m-20260524.md
```

### `84` bar SMA 結果摘要

| Window | Cost | Return | Benchmark return | Excess | IR | Active MDD | Regime blocks | 判斷 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Full `2020-2026` | `1x` | `780.38%` | `404.03%` | `376.35%` | `0.544` | `-24.82%` | `21` | 比原始候選弱 |
| `2020-2021` | `1x` | `98.29%` | `90.91%` | `7.38%` | `0.150` | `-23.02%` | `5` | 正但很弱 |
| `2021-2022` | `1x` | `-7.71%` | `5.88%` | `-13.59%` | `-0.463` | `-26.76%` | `11` | 改善但仍失敗 |
| `2022-2023` | `1x` | `3.11%` | `-1.77%` | `4.88%` | `0.074` | `-23.49%` | `10` | 幾乎沒有 edge |
| `2023-2024` | `1x` | `72.07%` | `68.20%` | `3.86%` | `0.167` | `-19.30%` | `6` | 大幅低於原始候選 |
| `2024-2025` | `1x` | `97.82%` | `81.93%` | `15.90%` | `0.249` | `-26.96%` | `8` | 大幅低於原始候選 |
| `2025-2026-05` | `1x` | `182.65%` | `102.48%` | `80.17%` | `1.200` | `-22.08%` | `3` | 仍強，但少於原始候選 |

### 解讀

1. **market regime filter 可以降低 `2021-2022` 傷害，但沒有修好**：`roll02` excess 從原始 `-24.62%` 改到 `-13.59%`，但仍是負值。
2. **代價是整體 active edge 明顯下降**：full-window IR 從原始 `0.858` 降到 `0.544`，full excess 從 `564.61%` 降到 `376.35%`。
3. **過濾器主要是降曝險，不是增加穩定 edge**：`84` bar SMA 讓 avg exposure 降到約 `67.37%`；這可降低局部傷害，但也錯過 2024-2025 的強勢輪動。

### Keep / Discard 判斷

- **Keep as compare tool**：market regime filter 是 deterministic、test-covered、預設關閉的可選工具，保留給後續比較。
- **Discard as current improvement**：`market_regime_sma_bars=84` 不能升級主候選，因為它雖改善 `roll02`，但 full-window 與多數強勢 window 明顯變弱。
- **下一步**：不要繼續只調 SMA 長度；若要修 `2021-2022`，應測更具體的 risk-off / re-entry 條件，或擴大股票池確認是否只是七檔大型股結構造成。

## 2026-05-24 Portfolio rotation volatility target

### 假設

前一輪 market regime filter 用市場方向判斷 risk-on / risk-off，但它犧牲太多強勢 window。這輪改測另一種風控假設：**動能策略的 crash risk 可能和波動升高有關，因此在 portfolio rotation 的再平衡日，若新目標投組的近期 realized volatility 高於目標年化波動，就只降曝險、不加槓桿。**

這輪不是新增 broker、不是真實下單，也不是把 volatility target 當成保證獲利的風控；它只是一個 deterministic、test-covered 的比較 overlay。

### 來源

- Pedro Barroso and Pedro Santa-Clara, Momentum has its moments: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2041429
- Alan Moreira and Tyler Muir, Volatility-Managed Portfolios: https://conference.nber.org/confer/2016/LTAMs16/Moreira_Muir.pdf
- Time-series momentum: A Monte Carlo approach: https://www.sciencedirect.com/science/article/abs/pii/S0957417421017172

### 本輪程式改動

- `tools\portfolio_rotation_sweep.py` 新增 portfolio-level volatility target：
  - `--volatility-target`
  - `--volatility-lookback-bars`
  - `--target-annual-volatility`
  - `--volatility-min-observations`
  - `--volatility-max-scale`
- 縮放語意：
  - 只在 rebalance date 對已選出的 target weights 生效。
  - 用該目標投組的歷史 close-to-close returns 估算 realized volatility。
  - `scale = min(max_scale, target_annual_volatility / realized_annual_volatility)`。
  - 預設 `max_scale = 1.0`，所以只會降曝險，不加槓桿。
- `PortfolioRotationResult` 新增：
  - `volatility_target`
  - `volatility_lookback_bars`
  - `target_annual_volatility`
  - `volatility_min_observations`
  - `volatility_max_scale`
  - `volatility_scaled_rebalance_count`
  - `volatility_warmup_count`
  - `average_volatility_scale`
- Markdown 報表新增 volatility target 欄位；rolling windows 也會顯示 `Vol scaled` 與 `Avg vol scale`。
- `tests\test_portfolio_rotation_sweep_tool.py` 新增 parser 與高波動縮放 regression。

### 參數掃描摘要

固定主候選 `monthly + 21 bars + top3`，掃 `volatility_lookback_bars = 21 / 42 / 63` 與 `target_annual_volatility = 12% / 15% / 20% / 25% / 30%`。

| Vol lookback | Target vol | Full return | Full excess | Full IR | Full MDD | Avg exposure | Avg scale | `2021-2022` excess | `2021-2022` IR | Positive excess windows | 解讀 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `21` | `12%` | `169.65%` | `-234.38%` | `-0.832` | `-21.62%` | `50.53%` | `0.545` | `-18.14%` | `-0.737` | `2/6` | 回撤下降，但 full-window active edge 失效 |
| `21` | `20%` | `401.48%` | `-2.55%` | `-0.038` | `-30.51%` | `73.82%` | `0.797` | `-23.70%` | `-0.881` | `2/6` | 接近 benchmark，但沒有主動 edge |
| `21` | `30%` | `642.99%` | `238.97%` | `0.462` | `-30.40%` | `86.43%` | `0.936` | `-23.42%` | `-0.826` | `5/6` | 保留報酬但仍輸原始候選 |
| `42` | `12%` | `185.84%` | `-218.19%` | `-0.771` | `-16.79%` | `49.05%` | `0.540` | `-16.85%` | `-0.693` | `1/6` | 風險最低但 active edge 被消滅 |
| `42` | `20%` | `447.03%` | `43.00%` | `0.065` | `-25.05%` | `72.48%` | `0.799` | `-22.85%` | `-0.890` | `4/6` | 本輪正式 compare-only；沒有修好失敗段 |
| `42` | `30%` | `696.74%` | `292.71%` | `0.535` | `-30.40%` | `85.69%` | `0.946` | `-27.91%` | `-1.000` | `5/6` | full IR 接近 SMA84 regime，但 roll02 更糟 |
| `63` | `20%` | `423.48%` | `19.45%` | `0.009` | `-24.69%` | `71.38%` | `0.787` | `-26.92%` | `-1.054` | `3/6` | 沒有改善主問題 |
| `63` | `30%` | `679.52%` | `275.49%` | `0.515` | `-30.40%` | `85.19%` | `0.941` | `-32.22%` | `-1.182` | `5/6` | full-window 尚可但失敗 window 惡化 |

### 正式 compare-only 報表命令

本輪保留 `lookback=42`、`target_annual_volatility=20%` 作為正式報表，原因是它沒有過度極端降曝險，且能展示此 overlay 的真實 tradeoff。

```powershell
python tools\portfolio_rotation_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-multipliers-list 1,3 `
  --rebalance-frequency monthly `
  --lookback-bars 21 `
  --top-n 3 `
  --min-return 0.0 `
  --volatility-target `
  --volatility-lookback-bars 42 `
  --target-annual-volatility 0.20 `
  --rolling-window-months 24 `
  --rolling-step-months 12 `
  --rolling-min-months 12 `
  --summary-json reports\generated\twse-portfolio-rotation-monthly-lb21-top3-voltarget20-lb42-rolling24m-20260524.json `
  --summary-md reports\generated\twse-portfolio-rotation-monthly-lb21-top3-voltarget20-lb42-rolling24m-20260524.md
```

### `target vol 20% / lookback 42` 結果摘要

| Window | Cost | Return | Benchmark return | Excess | IR | MDD | Active MDD | Avg exposure | Avg scale | 判斷 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Full `2020-2026` | `1x` | `447.03%` | `404.03%` | `43.00%` | `0.065` | `-25.05%` | `-30.80%` | `72.48%` | `0.799` | 主動 edge 幾乎消失 |
| `2020-2021` | `1x` | `94.23%` | `90.91%` | `3.32%` | `0.028` | `-11.55%` | `-23.80%` | `63.05%` | `0.781` | 低回撤但幾乎無 active edge |
| `2021-2022` | `1x` | `-16.97%` | `5.88%` | `-22.85%` | `-0.890` | `-25.05%` | `-21.59%` | `58.61%` | `0.828` | 沒修好失敗段 |
| `2022-2023` | `1x` | `4.85%` | `-1.77%` | `6.62%` | `0.172` | `-17.22%` | `-16.27%` | `65.53%` | `0.863` | 小幅改善中段 |
| `2023-2024` | `1x` | `77.49%` | `68.20%` | `9.29%` | `0.269` | `-16.39%` | `-14.77%` | `76.87%` | `0.872` | 明顯低於原始候選 |
| `2024-2025` | `1x` | `98.37%` | `81.93%` | `16.44%` | `0.338` | `-16.39%` | `-21.42%` | `66.16%` | `0.761` | 強勢段被削弱 |
| `2025-2026-05` | `1x` | `94.75%` | `102.48%` | `-7.73%` | `-0.242` | `-9.40%` | `-25.11%` | `57.80%` | `0.686` | partial window 反而輸 benchmark |

### 解讀

1. **volatility target 降低曝險，但沒有創造穩定 active edge**：低目標波動能降低 MDD，但 full-window excess 變成負值或接近 0。
2. **`2021-2022` 沒有被修好**：正式版本 `lookback=42 / target=20%` 的 `roll02` excess 是 `-22.85%`，只比原始 `-24.62%` 小幅改善，IR 仍約 `-0.890`。
3. **會錯過強勢 window**：2024-2025 與 2025-2026 的原始版本很強，但 volatility target 將曝險降到約 `66%` / `58%`，使 active edge 大幅下降甚至轉負。
4. **和 market regime filter 組合也沒有升級**：`regime SMA84 + vol target 30% / lookback 42` full IR 約 `0.250`、`roll02` excess 約 `-13.49%`，比單獨 SMA84 的 full IR `0.544` 差，不能視為改善。

### Keep / Discard 判斷

- **Keep as compare tool**：portfolio-level volatility target 是 deterministic、test-covered、預設關閉的風控 overlay，可用來比較不同風險降曝險假設。
- **Discard as current improvement**：本輪掃描沒有任何一組同時改善 full-window IR、`2021-2022` excess、rolling positive windows 與 MDD，因此不能升級主候選。
- **下一步**：不要繼續只調 `target_annual_volatility` 或 lookback；若要修穩定性，下一步更合理的是擴大股票池，或加入更具體的 re-entry / breadth 條件，而不是單純波動縮放。

## 2026-05-24 Portfolio rotation breadth filter

### 假設

前兩輪 market regime filter 與 volatility target 都是在「市場方向」或「波動」上降曝險，但沒有同時改善 full-window IR 與 `2021-2022` 失敗段。這輪改測更貼近 breadth momentum / protective asset allocation 的假設：

> 若同一股票池中只有少數股票維持正動能，portfolio rotation 可能只是追逐單一強勢股，而不是承擔健康的市場寬度；因此在 rebalance date 先檢查正動能股票數，低於門檻就持有現金。

這不是 broker、不是真實下單，也不是績效保證；它只是 deterministic、test-covered、預設關閉的 breadth gate。

### 來源

- Keller and Keuning, Protective Asset Allocation (PAA): https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2759734
- Keller and Keuning, Breadth Momentum and Vigilant Asset Allocation (VAA): https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3002624
- Keller and Keuning, Defensive Asset Allocation (DAA): https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3212862
- Antonacci, Absolute Momentum: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2244633

這些來源的共通點不是照抄 ETF 配置，而是把「relative momentum 選攻擊資產」和「absolute / breadth momentum 做 crash protection」分開。SignalForge 版本因此只蒸餾為本地七檔 TWSE 股票池可驗證的研究假設：計算股票池中 `lookback` 報酬為正的檔數，低於 `breadth_min_positive_count` 時留現金。

### 本輪程式改動

- `tools\portfolio_rotation_sweep.py` 新增 portfolio-level breadth filter：
  - `--breadth-filter`
  - `--breadth-lookback-bars`
  - `--breadth-min-positive-count`
  - `--breadth-positive-threshold`
- `PortfolioRotationResult` 新增：
  - `breadth_filter`
  - `breadth_lookback_bars`
  - `breadth_min_positive_count`
  - `breadth_positive_threshold`
  - `breadth_block_count`
  - `breadth_warmup_count`
  - `average_breadth_positive_count`
- Markdown 報表新增 breadth 欄位；rolling windows 也會顯示 breadth blocks 與 avg breadth。
- `tests\test_portfolio_rotation_sweep_tool.py` 新增 parser 與「正動能檔數不足時轉現金」regression。

### 參數掃描摘要

固定主候選 `monthly + 21 bars + top3`，掃 `breadth_lookback_bars = 21 / 42 / 63 / 84` 與 `breadth_min_positive_count = 1..7`。下表列出代表組合：

| Breadth lookback | Min positive | Full return | Full excess | Full IR | Full MDD | Avg exposure | `2021-2022` excess | `2021-2022` IR | Positive excess windows | 解讀 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| baseline | - | `968.64%` | `564.61%` | `0.858` | `-30.81%` | `91.84%` | `-24.62%` | `-0.881` | `5/6` | 原始候選，失敗段明確 |
| `21` | `2` | `677.10%` | `273.07%` | `0.488` | `-27.47%` | `83.33%` | `-17.66%` | `-0.618` | `5/6` | 改善失敗段但犧牲 full IR |
| `21` | `5` | `561.93%` | `157.90%` | `0.216` | `-16.30%` | `45.50%` | `3.59%` | `0.024` | `4/6` | roll02 轉正但主動 edge 太弱 |
| `42` | `1` | `1081.40%` | `677.37%` | `0.946` | `-30.81%` | `90.30%` | `-28.94%` | `-1.053` | `5/6` | full-window 變強但失敗段惡化 |
| `42` | `2` | `1193.44%` | `789.41%` | `1.017` | `-21.11%` | `84.39%` | `-16.91%` | `-0.598` | `5/6` | 本輪最佳折衷；仍未修好 roll02 |
| `42` | `3` | `847.66%` | `443.64%` | `0.671` | `-21.11%` | `74.75%` | `-10.33%` | `-0.357` | `4/6` | 較保守但 full IR 低於 baseline |
| `84` | `2` | `887.93%` | `483.90%` | `0.750` | `-31.88%` | `87.97%` | `-31.56%` | `-1.111` | `5/6` | full MDD 與失敗段不佳 |

### 正式報表命令

本輪保留 `breadth_lookback_bars=42`、`breadth_min_positive_count=2` 作為正式報表。它是目前第一個同時提高 full-window IR、降低 full-window MDD、改善 `2021-2022` 傷害的 overlay，但 `2021-2022` 仍是負 excess，因此不能視為穩定營利證明。

```powershell
python tools\portfolio_rotation_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-multipliers-list 1,3 `
  --rebalance-frequency monthly `
  --lookback-bars 21 `
  --top-n 3 `
  --min-return 0.0 `
  --breadth-filter `
  --breadth-lookback-bars 42 `
  --breadth-min-positive-count 2 `
  --breadth-positive-threshold 0.0 `
  --rolling-window-months 24 `
  --rolling-step-months 12 `
  --rolling-min-months 12 `
  --summary-json reports\generated\twse-portfolio-rotation-monthly-lb21-top3-breadth42-min2-rolling24m-20260524.json `
  --summary-md reports\generated\twse-portfolio-rotation-monthly-lb21-top3-breadth42-min2-rolling24m-20260524.md
```

### `breadth 42 / min positive 2` 結果摘要

| Window | Cost | Return | Benchmark return | Excess | IR | MDD | Active MDD | Breadth blocks | Avg breadth | Avg exposure | 判斷 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Full `2020-2026` | `1x` | `1193.44%` | `404.03%` | `789.41%` | `1.017` | `-21.11%` | `-18.89%` | `7` | `4.176` | `84.39%` | full-window 明顯優於 baseline |
| Full `2020-2026` | `3x` | `1158.06%` | `403.83%` | `754.23%` | `0.988` | `-21.15%` | `-19.63%` | `7` | `4.176` | `84.39%` | 3x 成本後仍保留 |
| `2020-2021` | `1x` | `113.86%` | `90.91%` | `22.95%` | `0.387` | `-16.30%` | `-17.56%` | `2` | `4.143` | `75.82%` | 比 baseline 的 early window 更好 |
| `2021-2022` | `1x` | `-11.03%` | `5.88%` | `-16.91%` | `-0.598` | `-19.10%` | `-24.17%` | `5` | `2.941` | `55.53%` | 改善但仍失敗 |
| `2022-2023` | `1x` | `21.75%` | `-1.77%` | `23.51%` | `0.686` | `-11.92%` | `-13.94%` | `5` | `3.471` | `60.05%` | 明顯改善原本弱中段 |
| `2023-2024` | `1x` | `86.62%` | `68.20%` | `18.42%` | `0.514` | `-21.11%` | `-15.19%` | `1` | `4.450` | `83.98%` | 仍正，但低於原始強勢段 |
| `2024-2025` | `1x` | `157.23%` | `81.93%` | `75.30%` | `1.330` | `-21.11%` | `-19.58%` | `0` | `4.632` | `87.36%` | 強勢段仍保留 |
| `2025-2026-05` | `1x` | `228.51%` | `102.48%` | `126.03%` | `1.754` | `-13.23%` | `-16.88%` | `0` | `4.615` | `82.47%` | partial window 仍強 |

### 解讀

1. **breadth gate 是目前最有用的風控 overlay**：相較 market regime SMA84 與 volatility target，它是第一個讓 full-window IR 高於 baseline、MDD 低於 baseline，同時改善中段 rolling windows 的版本。
2. **但它仍沒有解決 `2021-2022`**：`roll02` excess 從 `-24.62%` 改到 `-16.91%`，MDD 從 `-30.40%` 改到 `-19.10%`，但 IR 仍是 `-0.598`，不能稱為穩定。
3. **強勢段報酬被削弱但未消失**：2024-2025 excess 從原始 `158.48%` 降到 `75.30%`，代表這個 gate 有明顯機會成本；好處是 MDD 與 2022-2023 穩定性改善。
4. **breadth gate 比單純調曝險更像策略假設**：它不是一律縮小權重，而是在市場寬度不足時轉現金，較符合「相對動能需要足夠廣度支撐」的研究假設。

### Keep / Discard 判斷

- **Keep**：breadth filter 功能、CLI、JSON/Markdown 欄位與 tests。它是 deterministic、預設關閉、可重複驗證的 portfolio rotation overlay。
- **Promote to current best compare candidate**：`monthly + 21 bars + top3 + breadth lookback 42 / min positive 2` 是目前 portfolio rotation 的最佳折衷候選。
- **Not stable-profit proof**：因 `2021-2022` 仍輸 benchmark，且七檔股票池仍太小，不能宣稱已穩定營利。
- **下一步**：先做更大股票池與 1x / 2x / 3x cost stress 的固定報表，再測 re-entry 或 canary universe；不要只繼續微調 breadth threshold。

## 2026-05-24 TWSE14 股票池擴大驗證

### 假設

上一輪 breadth filter 在七檔股票池上得到最佳折衷，但「七檔大型股」仍太小，可能只是半導體與金融權重的樣本結構。這輪不新增交易策略，而是把 portfolio rotation 候選拿到更大的 TWSE 股票池檢查：

1. 先擴大資料池，加入塑化、電子代工、航運、金融與封測控股。
2. 修正資料下載 helper 對 TWSE 端點 `HTTP 308` 的處理，避免批次下載因 User-Agent / redirect 失敗。
3. 固定 `monthly + 21 bars + top3`，重新比較 baseline 與 `breadth lookback 42` 的不同 `min positive count`。
4. 對最佳折衷候選產生 1x / 2x / 3x 成本壓力與 24 個月 rolling windows。

### 本輪資料改動

原有股票池：

```text
2303, 2308, 2317, 2330, 2412, 2454, 2882
```

新增股票：

| Symbol | 粗略類別 | Rows | Source |
|---|---|---:|---|
| `1301` | 塑化 | `1526` | TWSE STOCK_DAY |
| `1303` | 塑化 | `1547` | TWSE STOCK_DAY |
| `2382` | 電子代工 | `1547` | TWSE STOCK_DAY |
| `2603` | 航運 | `1540` | TWSE STOCK_DAY |
| `2881` | 金融 | `1547` | TWSE STOCK_DAY |
| `2891` | 金融 | `1547` | TWSE STOCK_DAY |
| `3711` | 封測控股 | `1547` | TWSE STOCK_DAY |

> [!warning]
> 這些 TWSE 日線仍是未還原權息資料。它們足以做 deterministic research / relative comparison，但不能當成可交易績效保證。

### 資料下載工具修正

- `src\signal_forge\data\fetch.py` 的 `_fetch_url_text(...)` 現在每次 request 會帶 `User-Agent: SignalForge/1.0 research data fetcher`。
- 若資料來源回 `HTTP 308`，會依 `Location` 追蹤最多 5 次；缺少 Location 或轉址過多會拋出明確 `ValueError`。
- `tests\test_data_fetch.py` 新增 fake HTTP 308 regression，鎖住 request URL、redirect URL 與 User-Agent。

這個修正是資料可靠性改動，不碰 broker、不讀 credential、不改 live dry-run 邊界。

### 14 檔 scan 摘要

固定：

```text
rebalance = monthly
lookback_bars = 21
top_n = 3
min_return = 0.0
breadth_lookback_bars = 42
```

| Setting | Full return | Full excess | Full IR | Full MDD | Avg exposure | `2021-2022` excess | `2021-2022` IR | `2022-2023` excess | Positive excess windows | 解讀 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| baseline | `1178.12%` | `841.94%` | `1.035` | `-44.29%` | `96.15%` | `14.12%` | `0.395` | `26.34%` | `6/6` | 擴大股票池後 baseline 也轉強，但 MDD 太深 |
| `breadth42/min2` | `1401.28%` | `1065.10%` | `1.136` | `-44.29%` | `94.58%` | `-5.07%` | `0.032` | `34.66%` | `5/6` | full IR 改善但 roll02 變弱，不採用 |
| `breadth42/min3` | `1974.85%` | `1638.67%` | `1.417` | `-23.01%` | `88.51%` | `40.48%` | `0.799` | `89.46%` | `6/6` | 本輪最佳折衷 |
| `breadth42/min4` | `1648.91%` | `1312.73%` | `1.283` | `-21.93%` | `84.08%` | `16.09%` | `0.389` | `53.70%` | `6/6` | MDD 略低但 IR / excess 較弱 |
| `breadth42/min8` | `1648.04%` | `1311.86%` | `1.165` | `-18.18%` | `57.17%` | `42.83%` | `0.833` | `37.44%` | `6/6` | 風險較低但曝險太低，機會成本高 |
| `breadth42/min10` | `514.89%` | `178.71%` | `0.295` | `-18.18%` | `42.40%` | `36.46%` | `0.712` | `19.53%` | `3/6` | 過度保守，active edge 消失 |

### 正式報表命令

```powershell
python tools\portfolio_rotation_sweep.py `
  --csv data\processed\TWSE_1301_1D.csv `
  --csv data\processed\TWSE_1303_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2382_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2603_1D.csv `
  --csv data\processed\TWSE_2881_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --csv data\processed\TWSE_2891_1D.csv `
  --csv data\processed\TWSE_3711_1D.csv `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-multipliers-list 1,2,3 `
  --rebalance-frequency monthly `
  --lookback-bars 21 `
  --top-n 3 `
  --min-return 0.0 `
  --breadth-filter `
  --breadth-lookback-bars 42 `
  --breadth-min-positive-count 3 `
  --breadth-positive-threshold 0.0 `
  --rolling-window-months 24 `
  --rolling-step-months 12 `
  --rolling-min-months 12 `
  --summary-json reports\generated\twse14-portfolio-rotation-monthly-lb21-top3-breadth42-min3-rolling24m-20260524.json `
  --summary-md reports\generated\twse14-portfolio-rotation-monthly-lb21-top3-breadth42-min3-rolling24m-20260524.md
```

### `TWSE14 breadth42/min3` 結果摘要

| Scope | Cost | Return | Benchmark return | Excess | IR | MDD | Active MDD | Breadth blocks | Avg exposure | 判斷 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Full `2020-2026` | `1x` | `1974.85%` | `336.18%` | `1638.67%` | `1.417` | `-23.01%` | `-26.79%` | `5` | `88.51%` | 最佳折衷 |
| Full `2020-2026` | `2x` | `1940.15%` | `336.09%` | `1604.05%` | `1.403` | `-23.24%` | `-26.87%` | `5` | `88.51%` | 成本壓力後仍強 |
| Full `2020-2026` | `3x` | `1906.02%` | `336.01%` | `1570.01%` | `1.389` | `-23.48%` | `-26.95%` | `5` | `88.51%` | 3x 成本後仍強 |
| `2020-2021` | `1x` | `335.65%` | `91.24%` | `244.41%` | `1.900` | `-18.37%` | `-19.81%` | `1` | `84.43%` | 強 |
| `2021-2022` | `1x` | `64.77%` | `24.29%` | `40.48%` | `0.799` | `-23.01%` | `-21.25%` | `4` | `65.60%` | 原失敗段被修復到正 excess |
| `2022-2023` | `1x` | `98.27%` | `8.80%` | `89.46%` | `2.041` | `-9.25%` | `-7.79%` | `4` | `64.76%` | 強 |
| `2023-2024` | `1x` | `113.54%` | `51.20%` | `62.34%` | `1.237` | `-19.91%` | `-15.09%` | `0` | `87.76%` | 強 |
| `2024-2025` | `1x` | `82.58%` | `53.98%` | `28.60%` | `0.662` | `-19.91%` | `-20.70%` | `0` | `86.73%` | 正但較弱 |
| `2025-2026-05` | `1x` | `110.14%` | `79.78%` | `30.36%` | `0.564` | `-16.41%` | `-26.79%` | `0` | `82.47%` | partial window 正但 active MDD 偏深 |

### 解讀

1. **擴大股票池後，breadth gate 的證據明顯變強**：`breadth42/min3` 在 full-window、1x/2x/3x 成本、6 個 rolling windows 都保持正 excess。
2. **原本 `2021-2022` 問題被修復到正 active return**：七檔股票池的 `breadth42/min2` 仍輸 benchmark；14 檔後 `breadth42/min3` 在 `2021-2022` excess 約 `40.48%`、IR 約 `0.799`。
3. **風險仍不可忽略**：full-window MDD 約 `-23.01%`，active MDD 約 `-26.79%`；`2025-2026` partial window 雖為正 excess，但 active MDD 偏深。
4. **不能直接視為穩定營利完成**：資料未還原權息、股票池仍只有 14 檔、`min3` 是本輪掃描後挑出，仍有參數選擇偏誤；也尚未檢查交易容量、流動性、現金利息、真實稅費與不可成交情境。

### Keep / Discard 判斷

- **Keep**：新增 TWSE 資料與 fetcher User-Agent / HTTP 308 regression。這是讓更大股票池回測可重複的必要基礎。
- **Promote current best compare candidate**：`TWSE14 monthly + 21 bars + top3 + breadth42/min3`。它比七檔版本更接近穩健候選，但仍不是穩定營利證明。
- **Next**：下一輪優先補 `portfolio_rotation_sweep.py` 的 per-symbol / per-window selection attribution，確認報酬是否集中在 `2603` 或少數高波動股票；再考慮 adjusted price 或更大股票池。

## 2026-05-24 Portfolio rotation 選股歸因

### 目的

上一輪 `TWSE14 breadth42/min3` 雖然在 full-window、1x/2x/3x 成本與 6 個 rolling windows 都維持正 excess，但仍有一個重大疑問：這個結果是否其實只靠 `2603`、`2308` 或少數高波動股票貢獻。

本輪不改策略邏輯、不調參數，只補 deterministic attribution artifact，讓每個 full-window 與 rolling window 都能回答：

- 哪些股票實際被持有最多。
- 哪些股票的 `weight * close-to-close return` 貢獻最高。
- 單檔股票對總絕對貢獻的占比是否過高。
- 每個 rolling window 的主要貢獻股票是否一直是同一檔。

### 程式改動

- `tools\portfolio_rotation_sweep.py`
  - 新增 `PortfolioSymbolAttribution`。
  - `PortfolioRotationResult` 新增 `symbol_attribution` 欄位。
  - 回測過程會累積：
    - `selected_bar_count`
    - `selected_bar_share`
    - `rebalance_selected_count`
    - `rebalance_selected_share`
    - `average_weight`
    - `average_selected_weight`
    - `return_contribution`
    - `absolute_contribution_share`
  - Markdown 新增 `Top Symbol Attribution` 與 `Walk-forward Top Symbol Attribution`。
- `tests\test_portfolio_rotation_sweep_tool.py`
  - 鎖住 attribution 的持倉天數與報酬貢獻計算。
  - 鎖住 Markdown attribution 區段。

### 正式報表命令

```powershell
python tools\portfolio_rotation_sweep.py `
  --csv data\processed\TWSE_1301_1D.csv `
  --csv data\processed\TWSE_1303_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2382_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2603_1D.csv `
  --csv data\processed\TWSE_2881_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --csv data\processed\TWSE_2891_1D.csv `
  --csv data\processed\TWSE_3711_1D.csv `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-multipliers-list 1,2,3 `
  --rebalance-frequency monthly `
  --lookback-bars 21 `
  --top-n 3 `
  --min-return 0.0 `
  --breadth-filter `
  --breadth-lookback-bars 42 `
  --breadth-min-positive-count 3 `
  --breadth-positive-threshold 0.0 `
  --rolling-window-months 24 `
  --rolling-step-months 12 `
  --rolling-min-months 12 `
  --summary-json reports\generated\twse14-portfolio-rotation-monthly-lb21-top3-breadth42-min3-rolling24m-attribution-20260524.json `
  --summary-md reports\generated\twse14-portfolio-rotation-monthly-lb21-top3-breadth42-min3-rolling24m-attribution-20260524.md
```

### Full-window attribution

`1x`、`2x`、`3x` 成本倍率的選股結果相同，成本只影響權益曲線，不改選股排序。Full-window top 5：

| Rank | Symbol | Return contribution | Abs contribution share | Selected bars | Selected bar share | Rebalance selected | Rebalance share | 解讀 |
|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1 | `2603` | `81.88%` | `23.77%` | `457` | `32.64%` | `22` | `32.35%` | 最大貢獻，但未超過 25% |
| 2 | `2308` | `62.61%` | `18.17%` | `397` | `28.36%` | `20` | `29.41%` | 重要貢獻 |
| 3 | `2454` | `45.14%` | `13.10%` | `416` | `29.71%` | `21` | `30.88%` | 重要貢獻 |
| 4 | `2382` | `38.75%` | `11.25%` | `299` | `21.36%` | `15` | `22.06%` | 重要貢獻 |
| 5 | `3711` | `26.33%` | `7.64%` | `330` | `23.57%` | `18` | `26.47%` | 次要貢獻 |

Full-window 看起來不是單一股票壟斷，top 1 `2603` 絕對貢獻占比約 `23.77%`；但 top 5 合計約 `73.93%`，仍代表候選主要依賴少數高動能股票群。

### Rolling window attribution

| Window | Top symbol | Top abs contribution share | Top contribution | 解讀 |
|---|---|---:|---:|---|
| `roll01` `2020-2021` | `2603` | `44.86%` | `76.24%` | 高度依賴航運行情 |
| `roll02` `2021-2022` | `2603` | `68.75%` | `60.26%` | 原本問題段雖轉正 excess，但幾乎靠 `2603` 撐住 |
| `roll03` `2022-2023` | `2382` | `42.35%` | `33.41%` | 主要貢獻切到電子代工 |
| `roll04` `2023-2024` | `2382` | `37.09%` | `31.07%` | 貢獻仍偏集中但不是單一極端 |
| `roll05` `2024-2025` | `2308` | `36.63%` | `31.59%` | 主要貢獻切到電源/工控 |
| `roll06` `2025-2026-05` | `2308` | `48.75%` | `52.26%` | partial window 有單檔集中風險 |

### 解讀

1. **Full-window 沒有單檔完全壟斷**：最大貢獻 `2603` 約 `23.77%`，這比「單一股票撐完整體績效」好。
2. **但 rolling windows 仍高度集中**：`roll02` 的 `2603` 占 `68.75%`，`roll06` 的 `2308` 占 `48.75%`。這表示「6/6 positive excess」不能直接解讀為分散穩定，因為某些分段仍由單檔行情主導。
3. **`roll02` 被修復但證據品質還不夠**：`2021-2022` excess 已轉正，但 attribution 顯示主要來自 `2603`，這是參數候選的弱點。
4. **下一步不應再微調 breadth threshold**：應先加入 concentration guard / max single-symbol attribution gate，或用更大股票池與 adjusted price 檢查這種集中度是否自然下降。

### Keep / Discard 判斷

- **Keep**：per-symbol / per-window attribution artifact 與 tests。這直接補上策略評估準則要求的「不要只靠少數大贏家」檢查。
- **Keep as current best compare candidate**：`TWSE14 monthly + 21 bars + top3 + breadth42/min3` 仍是目前最強候選。
- **Not stable-profit proof**：rolling attribution 顯示部分 window 對單檔依賴過高；資料仍未還原權息，股票池仍小，尚未驗證流動性與容量。
- **Next**：優先做 concentration guard，例如報表先標示 `max_symbol_abs_contribution_share`、`top3_abs_contribution_share`，再測是否能用更大股票池、sector cap 或 top-N / rebalance 約束降低分段集中度，而不是只追求更高 return / IR。

## 2026-05-24 Portfolio rotation concentration guard 指標

### 目的

上一輪已經能看到逐股 attribution，但判讀仍要人工從表格中抓最大值。本輪不改策略交易語意，只把集中度變成 `PortfolioRotationResult` 的一級欄位，讓 full-window 與 rolling windows 都能直接檢查：

- `max_symbol_abs_contribution_symbol`
- `max_symbol_abs_contribution_share`
- `top3_symbol_abs_contribution_share`

這三個欄位用來回答「目前候選是否靠一檔或前三檔股票撐住」，是策略升級前必須看的 guard 指標。

### 程式改動

- `tools\portfolio_rotation_sweep.py`
  - `PortfolioRotationResult` 新增 `max_symbol_abs_contribution_symbol`、`max_symbol_abs_contribution_share`、`top3_symbol_abs_contribution_share`。
  - 新增 `_symbol_concentration_metrics(...)`，由 `symbol_attribution` 推導集中度。
  - `Portfolio Result` 與 `Walk-forward Windows` Markdown 表格直接輸出最大貢獻股票、最大貢獻占比與 top-3 貢獻占比。
- `tests\test_portfolio_rotation_sweep_tool.py`
  - 鎖住 concentration 欄位與 Markdown 表頭。

### TWSE14 concentration 結果

固定候選仍是：

```text
TWSE14 monthly + 21 bars + top3 + breadth42/min3
```

Full-window：

| Scope | Max symbol | Max contribution share | Top-3 contribution share | 判斷 |
|---|---|---:|---:|---|
| `2020-2026` | `2603` | `23.77%` | `55.04%` | full-window 沒有單檔壟斷，但 top-3 已過半 |

Rolling windows：

| Window | Max symbol | Max contribution share | Top-3 contribution share | 判斷 |
|---|---|---:|---:|---|
| `roll01` `2020-2021` | `2603` | `44.86%` | `73.33%` | 高度集中 |
| `roll02` `2021-2022` | `2603` | `68.75%` | `82.56%` | 最嚴重集中；原本問題段主要靠航運行情修復 |
| `roll03` `2022-2023` | `2382` | `42.35%` | `72.39%` | 高度集中 |
| `roll04` `2023-2024` | `2382` | `37.09%` | `70.58%` | 偏集中 |
| `roll05` `2024-2025` | `2308` | `36.63%` | `60.80%` | 中度集中 |
| `roll06` `2025-2026-05` | `2308` | `48.75%` | `69.86%` | partial window 偏集中 |

### 解讀

1. **Full-window 集中度可接受但不低**：單檔最大 `23.77%` 還不到單一壟斷，但 top-3 `55.04%` 代表報酬主要來自少數強勢股。
2. **Rolling window 才是主要問題**：`roll02` 的 max share `68.75%`、top-3 `82.56%`，代表最關鍵修復段其實高度依賴 `2603`。
3. **候選仍不應升級為穩定營利**：即使 IR、MDD、rolling excess 變好，concentration guard 顯示分段穩健性不足。
4. **下一輪方向**：測試 concentration-aware 約束，例如提高 `top_n`、限制單一股票連續入選、加入 sector cap，或先擴大股票池看 top-3 share 是否自然下降。

### Keep / Discard 判斷

- **Keep**：concentration guard 指標與 tests。這讓策略評估準則中的「不要只靠少數大贏家」變成可直接讀取的報表欄位。
- **Compare-only**：`TWSE14 breadth42/min3` 仍是目前最強候選，但 concentration risk 未解。
- **Next**：先用同一批資料測 `top_n=4/5` 或更大股票池，要求 rolling `max_symbol_abs_contribution_share` 與 `top3_symbol_abs_contribution_share` 降低，同時不得犧牲太多 IR / active drawdown。

## 2026-05-24 Portfolio rotation top-N concentration-aware 比較

### 目的

上一輪 concentration guard 顯示 `TWSE14 breadth42/min3 top3` 的 full-window 指標很強，但 rolling window 仍高度集中，尤其 `roll02` 幾乎靠 `2603` 撐住。本輪不新增策略語意、不改 breadth threshold，只測同一組資料與同一個 breadth gate 下的 `top_n=3/4/5`。

核心假設：

> 若提高持股檔數能降低 concentration，同時保留足夠 IR、正 rolling excess 與較好的 active drawdown，則較高 `top_n` 可能比純追求最高總報酬更接近穩健候選。

### 固定條件

```text
universe = TWSE14
rebalance = monthly
lookback_bars = 21
min_return = 0.0
breadth_filter = on
breadth_lookback_bars = 42
breadth_min_positive_count = 3
cost_multipliers = 1,2,3
rolling_windows = 24m window / 12m step / 12m min
```

報表檔案：

- `reports/generated/twse14-portfolio-rotation-monthly-lb21-top3-breadth42-min3-concentration-compare-20260524.json`
- `reports/generated/twse14-portfolio-rotation-monthly-lb21-top4-breadth42-min3-concentration-compare-20260524.json`
- `reports/generated/twse14-portfolio-rotation-monthly-lb21-top5-breadth42-min3-concentration-compare-20260524.json`

### Full-window 與 rolling 摘要

以下皆看 `1x` 成本倍率；`2x/3x` 成本仍維持同方向，未改變結論。

| Top N | Full return | Full excess | Full IR | Full MDD | Full active MDD | Full max share | Full top-3 share | Min rolling excess | Min rolling IR | Worst rolling active MDD | Max rolling max share | Max rolling top-3 share | 判斷 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `3` | `1974.85%` | `1638.67%` | `1.417` | `-23.01%` | `-26.79%` | `23.77%` | `55.04%` | `28.60%` | `0.564` | `-26.79%` | `68.75%` | `82.56%` | 最高報酬，但 active drawdown 與 rolling concentration 較重 |
| `4` | `1546.66%` | `1210.48%` | `1.401` | `-18.61%` | `-20.21%` | `22.48%` | `48.32%` | `28.52%` | `0.724` | `-20.21%` | `67.39%` | `81.68%` | 最佳風險調整折衷 |
| `5` | `1239.02%` | `902.84%` | `1.292` | `-19.17%` | `-19.81%` | `19.37%` | `47.60%` | `15.93%` | `0.484` | `-19.81%` | `62.47%` | `77.33%` | 集中度再降，但 edge 與最弱 rolling window 明顯變差 |

### 解讀

1. **`top_n=4` 是目前較好的穩健折衷**：相對 `top_n=3`，full IR 幾乎只從 `1.417` 降到 `1.401`，但 MDD 從 `-23.01%` 改到 `-18.61%`，active MDD 從 `-26.79%` 改到 `-20.21%`。
2. **`top_n=4` 降低 full-window concentration**：full top-3 絕對貢獻占比從 `55.04%` 降到 `48.32%`，比較不依賴少數大贏家。
3. **rolling concentration 仍未解**：`top_n=4` 的 max rolling top-3 share 仍有 `81.68%`，只比 `top_n=3` 的 `82.56%` 小幅改善；`roll02` 仍主要依賴 `2603`。
4. **`top_n=5` 不宜升級**：雖然 concentration 下降，但 full excess、IR、min rolling excess 與 min rolling IR 都明顯變弱，像是過度分散而不是更穩健。
5. **不能宣稱穩定營利**：top-N 約束改善了風險調整，但資料仍未還原權息、股票池仍小、rolling concentration 仍高，且未檢查流動性、容量與真實成交限制。

### Keep / Discard 判斷

- **Promote current risk-adjusted compare candidate**：`TWSE14 monthly + 21 bars + top4 + breadth42/min3`。它犧牲部分總報酬，換到更低 MDD / active MDD、接近不變的 IR、較低 full-window top-3 concentration。
- **Keep as high-return benchmark**：`top3 + breadth42/min3` 仍保留為最高報酬比較錨點，但不再是「穩健性」優先的首選。
- **Compare-only / do not promote**：`top5 + breadth42/min3`。它降低 concentration，但 edge 衰退太多，不符合「不要只為了降低集中度而犧牲 active return」的方向。
- **Next**：不要再只測更大的 `top_n`；下一步應測 sector / group cap、限制單檔連續入選、或擴大股票池，目標是處理 rolling concentration，而不是只降低 full-window concentration。

## 2026-05-24 Portfolio rotation 單檔連續入選上限比較

### 目的

上一輪 `top_n=4` 降低了 full-window drawdown 與 full-window top-3 concentration，但 rolling concentration 仍未解。本輪不改 breadth gate、不新增資料，只新增一個可關閉的 concentration-aware 約束：

> 若某檔股票已連續入選達 `max_consecutive_selections_per_symbol`，下一次 rebalance 暫時排除它一次，迫使策略不要無限制追同一檔股票。

### 程式改動

- `tools/portfolio_rotation_sweep.py`
  - `run_portfolio_rotation(...)`、`run_portfolio_rotation_sweep(...)`、`run_walk_forward_rotation(...)` 新增 `max_consecutive_selections_per_symbol`，預設 `None`，不改既有行為。
  - CLI 新增 `--max-consecutive-selections-per-symbol`。
  - `PortfolioRotationResult` 新增 `max_consecutive_selections_per_symbol` 與 `consecutive_selection_block_count`。
  - Markdown full-window 與 walk-forward tables 新增 `Consec cap` / `Consec blocks`。
- `tests/test_portfolio_rotation_sweep_tool.py`
  - 新增 parser regression。
  - 新增兩檔股票測試，確認連續入選達上限後，強勢股會暫停一次，替代股票可入選。

### 固定條件

```text
universe = TWSE14
rebalance = monthly
lookback_bars = 21
top_n = 4
min_return = 0.0
breadth_filter = on
breadth_lookback_bars = 42
breadth_min_positive_count = 3
cost_multipliers = 1,2,3
rolling_windows = 24m window / 12m step / 12m min
```

報表檔案：

- `reports/generated/twse14-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec3-rolling24m-20260524.json`
- `reports/generated/twse14-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec4-rolling24m-20260524.json`
- `reports/generated/twse14-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-rolling24m-20260524.json`
- `reports/generated/twse14-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec6-rolling24m-20260524.json`

### Full-window 與 rolling 摘要

以下皆看 `1x` 成本倍率；無上限列使用前一輪 `top4 + breadth42/min3` 報表作基準。

| Max consecutive | Full return | Full excess | Full IR | Full MDD | Full active MDD | Full top-3 share | Full blocks | Min rolling excess | Min rolling IR | Max rolling top-3 share | Rolling blocks | 判斷 |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `none` | `1546.66%` | `1210.48%` | `1.401` | `-18.61%` | `-20.21%` | `48.32%` | `0` | `28.52%` | `0.724` | `81.68%` | `0` | 原 top4 風險調整折衷 |
| `3` | `1221.90%` | `885.72%` | `1.190` | `-19.18%` | `-20.42%` | `45.60%` | `10` | `11.89%` | `0.360` | `83.05%` | `14` | 過度干預，edge 明顯受損 |
| `4` | `1761.80%` | `1425.62%` | `1.536` | `-18.61%` | `-20.21%` | `50.80%` | `3` | `31.98%` | `0.719` | `82.82%` | `6` | IR 高，但 full top-3 與 rolling top-3 concentration 變差 |
| `5` | `1738.80%` | `1402.62%` | `1.515` | `-18.61%` | `-20.21%` | `46.31%` | `2` | `37.22%` | `0.814` | `82.62%` | `4` | 最新 compare candidate；改善 IR 與最弱 rolling，但未解 concentration |
| `6` | `1585.81%` | `1249.63%` | `1.424` | `-18.61%` | `-20.21%` | `47.98%` | `1` | `28.52%` | `0.724` | `81.68%` | `1` | 幾乎不傷害策略，但也幾乎不約束 concentration |

### 解讀

1. **`max consecutive 3` 太硬**：full IR 掉到 `1.190`，min rolling IR 掉到 `0.360`，且 rolling top-3 concentration 沒有下降，應 discard。
2. **`max consecutive 4` 追到更高 IR，但 concentration 反而變差**：full top-3 share 升到 `50.80%`，max rolling top-3 share 升到 `82.82%`，不適合作為 concentration 修復結論。
3. **`max consecutive 5` 是最新 compare candidate**：full IR `1.515`、min rolling IR `0.814`，MDD 與 active MDD 維持在 `-18.61%` / `-20.21%`，且 full top-3 share 比原 top4 低。
4. **但連續入選限制沒有解 rolling concentration**：`max consecutive 5` 的 max rolling top-3 share 仍約 `82.62%`，比原 top4 的 `81.68%` 還高一點。它改善的是部分 window 的 return / IR，不是 concentration 問題本身。
5. **不能宣稱穩定營利**：結果仍受未還原權息、TWSE14 小股票池、少數強勢股行情與未檢查流動性/容量限制影響。

### Keep / Discard 判斷

- **Keep code**：單檔連續入選上限、block count 與 Markdown 報表欄位。它是 deterministic、預設關閉、test-covered 的策略約束。
- **Promote compare candidate**：`TWSE14 monthly + 21 bars + top4 + breadth42/min3 + max consecutive 5`。它是目前 IR / rolling IR 較強的比較候選，但不是穩定營利證明。
- **Discard as primary fix**：`max consecutive 3` 與 `4` 不適合作為 concentration 修復；前者傷害 edge，後者讓 concentration 變差。
- **Next**：改測 sector / group cap、更大股票池或 canary universe。若下一輪仍要留在同一批 TWSE14，應把目標明確放在降低 rolling max share / rolling top-3 share，而不是只提高 full-window IR。

## 2026-05-24 Portfolio rotation sector/group cap 比較

### 目的

單檔連續入選上限改善了部分 IR，但沒有解 rolling concentration。本輪改測 sector / group cap，原因是 momentum 文獻中有一條 industry momentum 線索：Moskowitz and Grinblatt 的 *Do Industries Explain Momentum?* 指出產業成分可解釋相當多個股 momentum；近年綜述也把 industry momentum 視為 momentum 共移動的重要方向。因此這輪不直接換新策略，而是把同一個 portfolio rotation 轉成可檢查「同組股票是否過度集中」的研究假設。

研究假設：

> 若 rolling concentration 來自同產業股票一起主導，則限制每個 sector / group 的入選檔數，應可降低 rolling `max_symbol_abs_contribution_share` 或 `top3_symbol_abs_contribution_share`，且不能大幅犧牲 IR、active drawdown 與 min rolling excess。

### 程式改動

- `tools/portfolio_rotation_sweep.py`
  - CLI 新增 `--symbol-group SYMBOL:GROUP`，可重複指定股票到自訂群組。
  - CLI 新增 `--max-selections-per-group`，限制每次 rebalance 同組最多入選檔數。
  - `PortfolioRotationResult` 新增 `symbol_groups`、`max_selections_per_group`、`group_selection_block_count`。
  - Full-window 與 walk-forward Markdown 新增 `Group cap` / `Group blocks` 欄位。
- `tests/test_portfolio_rotation_sweep_tool.py`
  - 新增 symbol group parser conflict regression。
  - 新增三檔股票情境，確認同組上限會阻擋第二檔 semiconductor，讓不同組股票補上。

### 固定條件

```text
universe = TWSE14
rebalance = monthly
lookback_bars = 21
top_n = 4
min_return = 0.0
breadth_filter = on
breadth_lookback_bars = 42
breadth_min_positive_count = 3
cost_multipliers = 1,2,3
rolling_windows = 24m window / 12m step / 12m min
```

本輪手動群組：

```text
petrochemical = 1301, 1303
semiconductor = 2303, 2330, 2454, 3711
electronics = 2308, 2317, 2382
telecom = 2412
shipping = 2603
financial = 2881, 2882, 2891
```

報表檔案：

- `reports/generated/twse14-portfolio-rotation-monthly-lb21-top4-breadth42-min3-groupcap1-rolling24m-20260524.json`
- `reports/generated/twse14-portfolio-rotation-monthly-lb21-top4-breadth42-min3-groupcap2-rolling24m-20260524.json`
- `reports/generated/twse14-portfolio-rotation-monthly-lb21-top4-breadth42-min3-groupcap2-maxconsec5-rolling24m-20260524.json`

### Full-window 與 rolling 摘要

以下皆看 `1x` 成本倍率；`none` 與 `maxconsec5` 為前輪基準。

| Case | Group cap | Consec cap | Full return | Full excess | Full IR | Full MDD | Active MDD | Full top-3 share | Group blocks | Consec blocks | Min rolling excess | Min rolling IR | Max rolling max share | Max rolling top-3 share | Rolling group blocks | 判斷 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `none` | `none` | `none` | `1546.66%` | `1210.48%` | `1.401` | `-18.61%` | `-20.21%` | `48.32%` | `0` | `0` | `28.52%` | `0.724` | `67.39%` | `81.68%` | `0` | 原 top4 風險調整折衷 |
| `maxconsec5` | `none` | `5` | `1738.80%` | `1402.62%` | `1.515` | `-18.61%` | `-20.21%` | `46.31%` | `0` | `2` | `37.22%` | `0.814` | `65.37%` | `82.62%` | `0` | 目前最佳 compare candidate，但 concentration 未解 |
| `groupcap1` | `1` | `none` | `1090.65%` | `754.47%` | `1.096` | `-21.73%` | `-26.04%` | `49.02%` | `49` | `0` | `14.82%` | `0.433` | `66.08%` | `83.77%` | `75` | 過度限制，discard |
| `groupcap2` | `2` | `none` | `1620.42%` | `1284.24%` | `1.449` | `-18.48%` | `-19.81%` | `51.29%` | `15` | `0` | `29.69%` | `0.610` | `67.39%` | `81.68%` | `22` | full 指標可看，但 rolling IR 變弱、concentration 不降 |
| `groupcap2 + maxconsec5` | `2` | `5` | `1582.66%` | `1246.48%` | `1.430` | `-18.48%` | `-20.20%` | `51.23%` | `15` | `2` | `27.37%` | `0.565` | `65.37%` | `82.62%` | `22` | 比 maxconsec5 弱，不升級 |

### 解讀

1. **group cap 不是 TWSE14 目前問題的主解法**：`groupcap2` 的 max rolling top-3 share 仍是 `81.68%`，`groupcap2 + maxconsec5` 仍是 `82.62%`，沒有把 concentration 問題往下壓。
2. **`groupcap1` 太硬**：full IR 降到 `1.096`、active MDD 惡化到 `-26.04%`，且 max rolling top-3 share 變成 `83.77%`，應 discard。
3. **`groupcap2` 只改善部分 full-window 風險**：MDD / active MDD 略優於原 top4，但 min rolling IR 從 `0.724` 掉到 `0.610`，不符合穩健性優先。
4. **與 `maxconsec5` 疊加反而變弱**：full IR 從 `1.515` 降到 `1.430`，min rolling IR 從 `0.814` 降到 `0.565`，不應取代目前 compare candidate。
5. **結論仍不是穩定營利**：rolling concentration 主要不是單純 sector group 過量可解，可能需要更大股票池、canary universe、adjusted price、或流動性/容量條件重新定義可交易股票池。

### Keep / Discard 判斷

- **Keep code**：group cap、group block count 與 Markdown/JSON 欄位。它讓 sector-aware 或自訂群組限制可以被 deterministic 測試與後續更大股票池重用。
- **Do not promote**：`groupcap1`、`groupcap2`、`groupcap2 + maxconsec5` 都不升級為主候選。
- **Keep current compare candidate**：`top4 + breadth42/min3 + max consecutive 5` 仍是目前 IR / min rolling IR 較佳的候選，但 concentration 未解。
- **Next**：優先測更大股票池或 canary universe；若繼續做 group-aware 方法，應同時輸出 group-level attribution，確認報酬是否從單檔集中轉成 group 集中。

### 來源

- Moskowitz and Grinblatt, *Do Industries Explain Momentum?*, Journal of Finance, 1999, DOI: https://doi.org/10.1111/0022-1082.00146
- *Momentum: what do we know 30 years after Jegadeesh and Titman’s seminal paper?*, Financial Markets and Portfolio Management, 2022: https://link.springer.com/article/10.1007/s11408-022-00417-8

## 2026-05-24 Portfolio rotation TWSE23 擴大股票池比較

### 目的

前幾輪已確認 `top4 + breadth42/min3 + max consecutive 5` 是目前 TWSE14 中 IR / min rolling IR 較好的 compare candidate，但 rolling contribution 仍高度集中。本輪不再微調 breadth 或 group cap，而是擴大股票池，測試 concentration 是否會因可選標的變多而自然下降。

核心假設：

> 若 concentration 主要來自股票池太小，擴大到更多 TWSE 大型股後，rolling `max_symbol_abs_contribution_share` 與 `top3_symbol_abs_contribution_share` 應下降；但若同時讓 min rolling excess、Information Ratio 或 drawdown 顯著惡化，則只能保留為資料/集中度診斷，不可升級。

### 程式與資料改動

- `src/signal_forge/data/fetch.py`
  - TWSE request header 改為集中產生，除 `User-Agent` 外補上 `Accept: application/json,text/plain,*/*` 與 TWSE historical stock-day `Referer`。
  - 原因是 TWSE 對部分 `STOCK_DAY` request 會回同路徑 HTTP 308；補上瀏覽器式 JSON request header 後，第一批被卡住的股票可正常回傳 JSON。
- `tests/test_data_fetch.py`
  - 擴充 HTTP 308 redirect regression，確認 fetcher 會帶 JSON `Accept` 與 stock-day `Referer`。
- 新增 9 檔資料：`1101`、`1102`、`1216`、`1326`、`2002`、`2207`、`2327`、`2357`、`2379`。
- 本輪股票池從 TWSE14 擴大到 TWSE23：

```text
1101,1102,1216,1301,1303,1326,2002,2207,2303,2308,2317,2327,2330,2357,2379,2382,2412,2454,2603,2881,2882,2891,3711
```

資料限制：

- 原計畫另抓 `2395,2408,2474,3008,3034,3045,3231,4904,4938,5871,5880,6505,6669`，但 TWSE 在多次 request 後再次出現重複 HTTP 308 / 短窗節流現象。
- 這不是策略結果失敗，而是資料擷取邊界；下一次若要擴到 TWSE30+，應放慢批次、加 retry spacing，或改用已調整權息且較穩定的資料源。

### 固定條件

```text
universe = TWSE23
rebalance = monthly
lookback_bars = 21
min_return = 0.0
breadth_filter = on
breadth_lookback_bars = 42
breadth_positive_threshold = 0.0
max_consecutive_selections_per_symbol = 5
cost_multipliers = 1,2,3
rolling_windows = 24m window / 12m step / 12m min
```

報表檔案：

- `reports/generated/twse23-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-rolling24m-20260524.json`
- `reports/generated/twse23-portfolio-rotation-monthly-lb21-top4-breadth42-min5-maxconsec5-rolling24m-20260524.json`
- `reports/generated/twse23-portfolio-rotation-monthly-lb21-top4-breadth42-min8-maxconsec5-rolling24m-20260524.json`
- `reports/generated/twse23-portfolio-rotation-monthly-lb21-top5-breadth42-min5-maxconsec5-rolling24m-20260524.json`
- `reports/generated/twse23-portfolio-rotation-monthly-lb21-top5-breadth42-min8-maxconsec5-rolling24m-20260524.json`
- `reports/generated/twse23-portfolio-rotation-monthly-lb21-top3-breadth42-min5-maxconsec5-rolling24m-20260524.json`
- `reports/generated/twse23-portfolio-rotation-monthly-lb21-top3-breadth42-min8-maxconsec5-rolling24m-20260524.json`

### TWSE14 vs TWSE23 摘要

以下皆看 `1x` 成本倍率。

| Case | Top N | Breadth min | Full return | Full excess | Full IR | Full MDD | Active MDD | Full top-3 share | Min rolling excess | Min rolling IR | Worst rolling active MDD | Max rolling max share | Max rolling top-3 share | 判斷 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `TWSE14 current compare` | `4` | `3` | `1738.80%` | `1402.62%` | `1.515` | `-18.61%` | `-20.21%` | `46.31%` | `37.22%` | `0.814` | `-20.21%` | `65.37%` | `82.62%` | 目前最佳 compare candidate |
| `TWSE23` | `4` | `3` | `649.25%` | `488.35%` | `1.179` | `-36.64%` | `-26.89%` | `46.09%` | `-17.99%` | `-0.291` | `-33.07%` | `39.51%` | `65.32%` | concentration 改善，但穩健性失敗 |
| `TWSE23` | `4` | `5` | `676.97%` | `516.08%` | `1.208` | `-34.40%` | `-24.19%` | `46.51%` | `-14.41%` | `-0.201` | `-30.60%` | `41.11%` | `65.32%` | 略優於 min3，但仍有負 rolling |
| `TWSE23` | `4` | `8` | `484.16%` | `323.27%` | `0.758` | `-23.66%` | `-24.97%` | `45.78%` | `0.60%` | `0.116` | `-24.97%` | `51.50%` | `71.20%` | 唯一正 min rolling excess，但 IR 太弱 |
| `TWSE23` | `5` | `5` | `526.75%` | `365.85%` | `1.108` | `-33.44%` | `-21.14%` | `41.25%` | `-12.98%` | `-0.265` | `-23.36%` | `36.10%` | `56.62%` | concentration 最好，但 edge 不足 |
| `TWSE23` | `5` | `8` | `376.88%` | `215.99%` | `0.610` | `-21.54%` | `-27.34%` | `41.87%` | `-4.04%` | `-0.067` | `-27.34%` | `47.53%` | `65.71%` | 過度防守 |
| `TWSE23` | `3` | `5` | `588.13%` | `427.24%` | `0.931` | `-34.09%` | `-28.81%` | `49.24%` | `-2.32%` | `0.158` | `-31.55%` | `51.20%` | `75.78%` | 不如 top4/top5 |
| `TWSE23` | `3` | `8` | `429.57%` | `268.68%` | `0.614` | `-25.72%` | `-33.10%` | `50.29%` | `-11.14%` | `-0.159` | `-33.10%` | `62.32%` | `78.47%` | 不升級 |

### 解讀

1. **擴大股票池確實降低 rolling concentration**：`TWSE14 top4/min3/maxconsec5` 的 max rolling top-3 share 約 `82.62%`；`TWSE23 top4/min3` 降到 `65.32%`，`TWSE23 top5/min5` 進一步降到 `56.62%`。
2. **但 edge 與回撤明顯惡化**：`TWSE23 top4/min3` full IR 降到 `1.179`，MDD 惡化到 `-36.64%`，且 min rolling excess 為 `-17.99%`、min rolling IR 為 `-0.291`。
3. **`top5/min5` 是 concentration 最乾淨的對照，不是主候選**：max rolling top-3 share 降到 `56.62%`，但 min rolling excess 為 `-12.98%`、min rolling IR 為 `-0.265`，代表分散後沒有保留足夠 active edge。
4. **`top4/min8` 只適合作為風險門檻觀察**：它是唯一 min rolling excess 為正的 TWSE23 設定，但 full IR 只有 `0.758`、min rolling IR 只有 `0.116`，不足以取代目前候選。
5. **結論不是穩定營利證明**：TWSE23 證明「更大股票池能降低 concentration」，但也揭露目前 ranking / breadth gate 在更多標的上不夠穩健。這表示下一輪應改善資料與股票池品質，而不是只把標的數量加大。

### Keep / Discard 判斷

- **Keep code/data**：TWSE header 修正與 9 檔新增日線資料。這讓後續可以繼續擴充可驗證股票池。
- **Keep as diagnostic**：TWSE23 擴大股票池結果保留為 concentration diagnostic；它證明 concentration 可以被股票池規模壓低。
- **Do not promote**：所有 TWSE23 本輪設定都不取代 `TWSE14 top4 + breadth42/min3 + max consecutive 5`。
- **Current compare candidate unchanged**：目前仍以 `TWSE14 top4 + breadth42/min3 + max consecutive 5` 作績效 compare candidate，但它仍不是穩定營利證明。
- **Next**：優先測 adjusted price、較慢批次完成 TWSE30+、流動性/容量條件與 canary universe。若只繼續調 breadth min 或 top-N，會重複已知 tradeoff。

## 2026-05-24 Portfolio rotation liquidity / capacity gate 比較

### 目的

TWSE23 擴大股票池顯示 concentration 可以下降，但 edge 與回撤惡化。這代表下一步不應只增加股票數量，而要定義「可交易股票池品質」。本輪新增可關閉的 liquidity / capacity gate，用平均成交金額排除成交金額不足的股票，檢查它是否能改善可執行性，同時不破壞 `top4 + breadth42/min3 + max consecutive 5` 的 active-risk 表現。

研究假設：

> 若部分不穩定性來自成交金額較弱或容量較差的標的，則在 rebalance 前排除近 N 日平均成交金額不足的股票，應能保留或改善 IR / active drawdown，且不應讓 min rolling excess 或 cost stress 失效。

### 程式改動

- `tools/portfolio_rotation_sweep.py`
  - CLI 新增 `--liquidity-lookback-bars`，預設 `20`。
  - CLI 新增 `--min-average-traded-value`，預設 `None`，未設定時不改既有策略語意。
  - 每次 rebalance 時，用對齊後的 `close * volume` 計算近 N 根平均成交金額；低於門檻的股票不能進入 momentum ranking。
  - `PortfolioRotationResult` 新增 `liquidity_lookback_bars`、`min_average_traded_value`、`liquidity_block_count`、`liquidity_warmup_count`、`average_liquidity_eligible_count`。
  - Markdown full-window 與 walk-forward table 新增 Liquidity 欄位。
- `tests/test_portfolio_rotation_sweep_tool.py`
  - 新增 parser regression。
  - 新增低成交金額強勢股測試，確認 liquidity filter 會排除低成交金額 momentum leader，讓較低動能但成交金額合格的股票補上。

### 固定條件

```text
rebalance = monthly
lookback_bars = 21
top_n = 4
min_return = 0.0
breadth_filter = on
breadth_lookback_bars = 42
breadth_positive_threshold = 0.0
max_consecutive_selections_per_symbol = 5
liquidity_lookback_bars = 20
cost_multipliers = 1,2,3
rolling_windows = 24m window / 12m step / 12m min
```

主要報表檔案：

- `reports/generated/twse14-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-liq500m-rolling24m-20260524.json`
- `reports/generated/twse14-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-liq1000m-rolling24m-20260524.json`
- `reports/generated/twse14-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-liq2000m-rolling24m-20260524.json`
- `reports/generated/twse23-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-liq500m-rolling24m-20260524.json`
- `reports/generated/twse23-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-liq1000m-rolling24m-20260524.json`
- `reports/generated/twse23-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-liq2000m-rolling24m-20260524.json`

### Full-window 與 rolling 摘要

以下皆看 `1x` 成本倍率。

| Case | Liquidity min | Full return | Full excess | Full IR | Full MDD | Active MDD | Liquidity blocks | Avg liquid count | Full top-3 share | Min rolling excess | Min rolling IR | Worst rolling active MDD | Max rolling max share | Max rolling top-3 share | 判斷 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `TWSE14 current` | `none` | `1738.80%` | `1402.62%` | `1.515` | `-18.61%` | `-20.21%` | `0` | `n/a` | `46.31%` | `37.22%` | `0.814` | `-20.21%` | `65.37%` | `82.62%` | 原 compare candidate |
| `TWSE14 liq500m` | `500M` | `1745.89%` | `1409.71%` | `1.521` | `-18.61%` | `-19.81%` | `4` | `13.18` | `46.43%` | `37.22%` | `0.814` | `-19.81%` | `65.37%` | `82.62%` | 最新 execution-aware compare candidate |
| `TWSE14 liq1000m` | `1B` | `2144.77%` | `1808.59%` | `1.615` | `-25.16%` | `-23.40%` | `25` | `10.23` | `48.46%` | `28.90%` | `0.636` | `-22.43%` | `61.13%` | `80.42%` | 報酬高但回撤與 rolling IR 變差 |
| `TWSE14 liq2000m` | `2B` | `1445.01%` | `1108.83%` | `1.076` | `-43.53%` | `-42.00%` | `46` | `6.89` | `49.88%` | `-11.51%` | `-0.041` | `-42.00%` | `57.57%` | `78.56%` | discard |
| `TWSE23 liq500m` | `500M` | `750.26%` | `589.36%` | `1.286` | `-35.35%` | `-29.81%` | `16` | `18.72` | `46.33%` | `-8.54%` | `-0.046` | `-26.80%` | `40.42%` | `63.55%` | diagnostic only |
| `TWSE23 liq1000m` | `1B` | `798.58%` | `637.68%` | `1.256` | `-38.98%` | `-30.81%` | `25` | `13.15` | `47.68%` | `-16.91%` | `-0.230` | `-34.55%` | `39.37%` | `65.11%` | diagnostic only |
| `TWSE23 liq2000m` | `2B` | `1149.40%` | `988.51%` | `1.532` | `-39.81%` | `-30.37%` | `37` | `7.89` | `52.28%` | `-21.67%` | `-0.341` | `-33.73%` | `43.65%` | `79.76%` | 不升級 |

### 成本壓力檢查

`TWSE14 liq500m` 在成本壓力下仍保留方向：

| Cost | Return | Excess | IR | MDD | Total cost |
|---:|---:|---:|---:|---:|---:|
| `1x` | `1745.89%` | `1409.71%` | `1.521` | `-18.61%` | `830.17` |
| `2x` | `1717.32%` | `1381.22%` | `1.505` | `-18.66%` | `1642.92` |
| `3x` | `1689.18%` | `1353.18%` | `1.490` | `-18.71%` | `2438.58` |

### 解讀

1. **`TWSE14 liq500m` 是最合理的 execution-aware 改良**：只觸發 `4` 次 liquidity block，平均合格股票仍有 `13.18` 檔；full IR 從 `1.515` 微升到 `1.521`，active MDD 從 `-20.21%` 改到 `-19.81%`。
2. **`liq500m` 沒有解 rolling concentration**：max rolling top-3 share 仍是 `82.62%`，所以它改善的是可交易性 gate 與小幅風險調整，不是 concentration 主解法。
3. **`liq1000m` 不能被高報酬誤導**：full IR `1.615`、return `2144.77%` 很漂亮，但 MDD 惡化到 `-25.16%`，min rolling IR 降到 `0.636`，不符合穩健性優先。
4. **`liq2000m` 明確 discard**：TWSE14 在 `2B` 門檻下 min rolling excess 轉負、MDD 到 `-43.53%`，代表過度限制讓策略集中到更糟的風險組合。
5. **TWSE23 仍不升級**：liquidity gate 可改善部分 full-window IR，但 min rolling excess / IR 仍為負，且 MDD 仍在 `-35%` 到 `-40%` 附近，不能取代 TWSE14 候選。

### Keep / Discard 判斷

- **Keep code**：liquidity / capacity gate 與報表欄位。它是 deterministic、預設關閉、test-covered，符合策略評估準則的「可執行性與成本」層。
- **Promote execution-aware compare candidate**：`TWSE14 top4 + breadth42/min3 + max consecutive 5 + liquidity 500M/20 bars`。它保留原候選 edge，並加上一層基本成交金額 gate。
- **Do not promote**：`TWSE14 liq1000m` 雖然報酬與 IR 更高，但回撤與 rolling IR tradeoff 較差；只能作高門檻對照。
- **Discard**：`TWSE14 liq2000m`。
- **Diagnostic only**：所有 TWSE23 liquidity 結果。
- **Next**：若繼續處理 concentration，下一步不應再硬拉 liquidity threshold；應改測 adjusted price、canary universe、或 group-level attribution，確認是否能降低 rolling top-3 share 而不犧牲 min rolling excess / IR。

## 2026-05-24 Portfolio rotation group-level attribution 診斷

### 目的

前一輪 liquidity gate 讓 `TWSE14 top4 + breadth42/min3 + max consecutive 5 + liquidity 500M/20 bars` 成為最新 execution-aware compare candidate，但 rolling top-3 symbol contribution 仍約 `82.62%`。本輪不再加新濾網，而是補 group-level attribution，檢查集中度到底是單檔問題，還是產業/群組 regime 問題。

研究假設：

> 若 full-window 或 rolling 的 group contribution share 明顯高於 symbol contribution share，代表策略雖然不是只靠單一股票，但仍高度依賴少數產業群組。下一步應先處理資料品質、股票池與 group regime，而不是單純再加單檔限制。

### 程式改動

- `tools/portfolio_rotation_sweep.py`
  - 新增 `PortfolioGroupAttribution`，把逐股 `weight * close-to-close return` 彙總到自訂 group / sector。
  - `PortfolioRotationResult` 新增 `max_group_abs_contribution_group`、`max_group_abs_contribution_share`、`top3_group_abs_contribution_share` 與 `group_attribution`。
  - Markdown full-window table 新增 Max group / Max group share / Top3 group share。
  - Markdown 新增 `Top Group Attribution` 與 `Walk-forward Top Group Attribution`。
- `tests/test_portfolio_rotation_sweep_tool.py`
  - 新增 group attribution aggregation regression。
  - 擴充 Markdown regression，確認 group attribution 區段與 summary 欄位會輸出。

### 固定條件

```text
universe = TWSE14
rebalance = monthly
lookback_bars = 21
top_n = 4
min_return = 0.0
breadth_filter = on
breadth_lookback_bars = 42
breadth_min_positive_count = 3
max_consecutive_selections_per_symbol = 5
liquidity_lookback_bars = 20
min_average_traded_value = 500M
cost_multipliers = 1,2,3
rolling_windows = 24m window / 12m step / 12m min
```

群組設定：

```text
petrochemical = 1301, 1303
semiconductor = 2303, 2330, 2454, 3711
electronics = 2308, 2317, 2382
telecom = 2412
shipping = 2603
financial = 2881, 2882, 2891
```

報表檔案：

- `reports/generated/twse14-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-liq500m-groups-rolling24m-20260524.json`
- `reports/generated/twse14-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-liq500m-groups-rolling24m-20260524.md`

### Full-window 摘要

以下皆看 `1x` 成本倍率。

| Case | Return | Excess | IR | MDD | Active MDD | Max symbol | Max symbol share | Top3 symbol share | Max group | Max group share | Top3 group share | 判斷 |
|---|---:|---:|---:|---:|---:|---|---:|---:|---|---:|---:|---|
| `TWSE14 liq500m + groups` | `1745.89%` | `1409.71%` | `1.521` | `-18.61%` | `-19.81%` | `2603` | `20.95%` | `46.43%` | `electronics` | `33.90%` | `89.27%` | group concentration 很高 |

Top groups：

| Rank | Group | Members | Return contribution | Abs contribution share | Avg weight |
|---:|---|---|---:|---:|---:|
| 1 | `electronics` | `2308,2317,2382` | `106.07%` | `33.90%` | `21.11%` |
| 2 | `semiconductor` | `2303,2330,2454,3711` | `102.98%` | `32.91%` | `30.33%` |
| 3 | `shipping` | `2603` | `70.26%` | `22.46%` | `10.05%` |

### Rolling 摘要

| Window | Excess | IR | Max symbol | Max symbol share | Top3 symbol share | Max group | Max group share | Top3 group share |
|---|---:|---:|---|---:|---:|---|---:|---:|
| `roll01` | `141.46%` | `1.524` | `2603` | `42.00%` | `68.46%` | `shipping` | `42.93%` | `90.31%` |
| `roll02` | `37.22%` | `0.814` | `2603` | `65.37%` | `82.62%` | `shipping` | `75.64%` | `93.74%` |
| `roll03` | `69.80%` | `1.832` | `2382` | `40.14%` | `74.12%` | `electronics` | `42.83%` | `96.81%` |
| `roll04` | `44.13%` | `1.123` | `2382` | `34.14%` | `61.46%` | `electronics` | `43.16%` | `83.12%` |
| `roll05` | `51.75%` | `1.187` | `2308` | `25.31%` | `60.89%` | `electronics` | `59.22%` | `89.59%` |
| `roll06` | `80.16%` | `1.323` | `2308` | `35.37%` | `60.32%` | `electronics` | `53.05%` | `90.53%` |

### 解讀

1. **不是單純單檔集中問題**：full-window 最大單檔 share 只有 `20.95%`，但 top-3 group share 高達 `89.27%`，代表報酬主要集中在 electronics / semiconductor / shipping 三個群組。
2. **rolling group concentration 更嚴重**：`roll02` 的 shipping group share 達 `75.64%`，`roll03` 的 top-3 group share 達 `96.81%`，即使該 window IR 為正，仍高度依賴少數產業 regime。
3. **group cap 已測但不是解法**：前輪 `groupcap2` 降低不了 rolling top-3 symbol share，且 min rolling IR 變弱。本輪 attribution 顯示下一步應先理解群組 regime / 資料品質，而不是硬上 group cap。
4. **execution-aware compare candidate 不變**：`liq500m` 仍保留為 execution-aware compare candidate，因為 1x/2x/3x 成本壓力與 active MDD 表現仍好；但它不是 concentration 修復，也不是穩定營利證明。

### Keep / Discard 判斷

- **Keep code**：group-level attribution 與 Markdown/JSON 欄位。它是 deterministic、test-covered，能讓後續每個 portfolio rotation 回測都檢查 group concentration。
- **Keep diagnostic**：本輪 `TWSE14 liq500m + groups` 診斷結果保留為 compare-only / diagnostic evidence。
- **Do not promote**：不因 group attribution 而升級策略；這輪只揭露風險來源，沒有降低風險。
- **Next**：優先測 adjusted price、canary universe、較慢批次 TWSE30+、或 group regime / group exposure diagnostic。下一輪若新增策略限制，必須同時看 symbol 與 group concentration，不能只看 full-window IR。

## 2026-05-24 Portfolio rotation group exposure 診斷

### 目的

上一輪 group-level attribution 顯示 `TWSE14 top4 + breadth42/min3 + max consecutive 5 + liquidity 500M/20 bars` 的報酬高度集中在少數群組，但還不能判斷集中度來源是「策略長期把資金壓在同一群組」還是「曝險不算最高的群組在特定 regime 報酬異常強」。本輪補上 group average-weight exposure 欄位，專門回答這個問題。

研究假設：

> 若最大貢獻群組和最大平均曝險群組不同，代表集中度不一定能靠硬性曝險 cap 解決；應優先檢查資料品質、股票池設計、調整後價格與 regime 驗證。

### 程式改動

- `tools/portfolio_rotation_sweep.py`
  - `PortfolioRotationResult` 新增 `max_group_average_weight_group`、`max_group_average_weight` 與 `top3_group_average_weight`。
  - 新增 `_group_exposure_metrics(...)`，用既有 `PortfolioGroupAttribution.average_weight` deterministic 推導最大群組平均曝險與前三群組平均曝險。
  - Markdown full-window 與 walk-forward table 新增 Max exposure group / Max group avg weight / Top3 group avg weight。
- `tests/test_portfolio_rotation_sweep_tool.py`
  - 擴充 group attribution aggregation regression，鎖住 group exposure summary。
  - 擴充 Markdown regression，確認新欄位會輸出。

### 報表檔案

- `reports/generated/twse14-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-liq500m-group-exposure-rolling24m-20260524.json`
- `reports/generated/twse14-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-liq500m-group-exposure-rolling24m-20260524.md`

### Full-window 摘要

以下皆看 `1x` 成本倍率。

| Return | Excess | IR | MDD | Active MDD | Max group | Max group share | Top3 group share | Max exposure group | Max group avg weight | Top3 group avg weight |
|---:|---:|---:|---:|---:|---|---:|---:|---|---:|---:|
| `1745.89%` | `1409.71%` | `1.521` | `-18.61%` | `-19.81%` | `electronics` | `33.90%` | `89.27%` | `semiconductor` | `30.33%` | `65.99%` |

### Rolling group exposure 摘要

| Window | IR | Max group | Max group share | Top3 group share | Max exposure group | Max group avg weight | Top3 group avg weight |
|---|---:|---|---:|---:|---|---:|---:|
| `roll01` | `1.524` | `shipping` | `42.93%` | `90.31%` | `semiconductor` | `31.16%` | `60.88%` |
| `roll02` | `0.814` | `shipping` | `75.64%` | `93.74%` | `financial` | `15.64%` | `40.52%` |
| `roll03` | `1.832` | `electronics` | `42.83%` | `96.81%` | `semiconductor` | `29.17%` | `52.05%` |
| `roll04` | `1.123` | `electronics` | `43.16%` | `83.12%` | `semiconductor` | `29.03%` | `73.52%` |
| `roll05` | `1.187` | `electronics` | `59.22%` | `89.59%` | `electronics` | `28.37%` | `62.07%` |
| `roll06` | `1.323` | `electronics` | `53.05%` | `90.53%` | `electronics` | `28.37%` | `67.81%` |

### 解讀

1. **full-window 最大貢獻群組不是最大曝險群組**：最大貢獻是 `electronics`，但最大平均曝險是 `semiconductor`。這代表 full-window concentration 並不只是策略長期超配 electronics，而是 electronics 在持有期間的 realized return 較強。
2. **`roll02` 是最關鍵警訊**：`shipping` 貢獻 share 高達 `75.64%`，但該 window 最大平均曝險是 `financial`，且 top-3 group avg weight 只有 `40.52%`。這表示 `2603/shipping` 的 regime return 影響遠大於平均曝險，硬上 group exposure cap 未必能解決問題。
3. **後段 window 仍有群組曝險重疊**：`roll05`、`roll06` 的最大貢獻與最大曝險都指向 `electronics`，表示 2024-2026 的強勢期同時存在 exposure concentration 與 return concentration。
4. **策略候選狀態不變**：`liq500m` 仍是 execution-aware compare candidate；group exposure 只補診斷能力，沒有降低 concentration 或證明穩定營利。

### Keep / Discard 判斷

- **Keep code**：group exposure summary 欄位與 Markdown / JSON 輸出。它是 deterministic、test-covered，能讓後續每個 portfolio rotation 回測同時檢查貢獻集中與曝險集中。
- **Keep diagnostic**：本輪結果保留為 compare-only / diagnostic evidence。
- **Do not promote**：不因為新增診斷欄位而升級策略；目前仍有 group regime dependency、未還原權息與小股票池限制。
- **Next**：優先測 adjusted price、較慢批次 TWSE30+、canary universe 或 group regime validation。若要再做限制，應先確認限制能同時改善 `max_group_abs_contribution_share`、`top3_group_abs_contribution_share`、`max_group_average_weight` 與 min rolling IR，而不是只把曝險壓低。

## 2026-05-24 Portfolio rotation dominant group exclusion 診斷

### 目的

上一輪 group exposure 顯示部分 window 的 concentration 來自群組 regime return，而不是單純長期高曝險。本輪不新增策略規則，只做固定 universe ablation：在同一組 portfolio rotation 參數下，分別移除 `shipping`、`electronics`、`semiconductor`，檢查最新 execution-aware compare candidate 是否真的依賴特定 dominant group。

研究假設：

> 若移除任一 dominant group 後 full-window / rolling edge 大幅失效，代表目前策略仍是 group-regime dependent；若某個移除組合仍保留 rolling edge，則該群組不是必要 edge 來源，但也要同步檢查回撤與 concentration 是否惡化。

### 固定條件

```text
base universe = TWSE14
rebalance = monthly
lookback_bars = 21
top_n = 4
min_return = 0.0
breadth_filter = on
breadth_lookback_bars = 42
breadth_min_positive_count = 3
max_consecutive_selections_per_symbol = 5
liquidity_lookback_bars = 20
min_average_traded_value = 500M
cost_multipliers = 1,2,3
rolling_windows = 24m window / 12m step / 12m min
```

報表檔案：

- `reports/generated/twse14-no-shipping-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-liq500m-group-regime-rolling24m-20260524.json`
- `reports/generated/twse14-no-electronics-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-liq500m-group-regime-rolling24m-20260524.json`
- `reports/generated/twse14-no-semiconductor-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-liq500m-group-regime-rolling24m-20260524.json`

### Full-window 與 rolling 摘要

以下皆看 `1x` 成本倍率。

| Case | Full return | Full excess | Full IR | MDD | Active MDD | Min rolling excess | Min rolling IR | Worst rolling active MDD | Max rolling top3 symbol share | Max rolling top3 group share | 判斷 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `baseline` | `1745.89%` | `1409.71%` | `1.521` | `-18.61%` | `-19.81%` | `37.22%` | `0.814` | `-19.81%` | `82.62%` | `96.81%` | 最新 execution-aware compare candidate |
| `no shipping` | `1026.02%` | `761.18%` | `1.255` | `-17.62%` | `-19.99%` | `-4.68%` | `-0.185` | `-19.99%` | `77.15%` | `98.63%` | 移除 shipping 後 rolling edge 失效 |
| `no electronics` | `620.88%` | `331.37%` | `0.650` | `-27.31%` | `-29.03%` | `-10.16%` | `-0.204` | `-29.03%` | `75.48%` | `93.64%` | electronics 是主要 edge 來源 |
| `no semiconductor` | `845.21%` | `613.36%` | `1.210` | `-25.31%` | `-26.64%` | `26.86%` | `0.708` | `-26.64%` | `87.25%` | `98.68%` | edge 尚存但風險與集中度惡化 |

### 成本壓力摘要

| Case | 1x IR | 2x IR | 3x IR | 3x return | 3x excess | 3x MDD |
|---|---:|---:|---:|---:|---:|---:|
| `baseline` | `1.521` | `1.505` | `1.490` | `1689.18%` | `1353.18%` | `-18.71%` |
| `no shipping` | `1.255` | `1.239` | `1.222` | `992.08%` | `727.39%` | `-17.65%` |
| `no electronics` | `0.650` | `0.635` | `0.620` | `599.06%` | `309.71%` | `-27.75%` |
| `no semiconductor` | `1.210` | `1.195` | `1.181` | `820.21%` | `588.49%` | `-25.53%` |

### 解讀

1. **Shipping 是 2021-2022 rolling edge 的關鍵保護來源**：`no shipping` full-window 仍有 `1.255` IR，但 `roll02` excess 轉成 `-4.68%`、IR `-0.185`。這表示直接移除 `2603/shipping` 不是穩健解法。
2. **Electronics 是最核心的 full-window edge 來源**：`no electronics` full IR 只剩 `0.650`，MDD 惡化到 `-27.31%`，min rolling excess 也轉負。這支持上一輪 observation：2024-2026 的強勢高度依賴 electronics。
3. **Semiconductor 不是必要 edge 來源，但提供分散與風險緩衝**：`no semiconductor` 仍有正 min rolling excess `26.86%` 與 min rolling IR `0.708`，但 MDD / active MDD 惡化到 `-25.31%` / `-26.64%`，max rolling top3 symbol share 升到 `87.25%`，max rolling top3 group share 升到 `98.68%`。
4. **群組排除不是升級方向**：三個 ablation 都沒有同時改善 edge、回撤與 concentration。baseline 仍是相對最平衡的 compare candidate，但 group regime dependency 被進一步確認。

### Keep / Discard 判斷

- **Keep diagnostic**：dominant group exclusion 作為 group regime validation evidence 保留。
- **Do not promote**：`no shipping`、`no electronics`、`no semiconductor` 都不升級為主候選。
- **Current compare candidate unchanged**：仍維持 `TWSE14 top4 + breadth42/min3 + max consecutive 5 + liquidity 500M/20 bars` 作 execution-aware compare candidate。
- **Next**：不要靠固定排除群組處理 concentration；下一步優先測 adjusted price、較慢批次 TWSE30+、canary universe 或更高品質股票池。若繼續做 group-aware 策略，應是 regime-aware sizing / validation，而不是硬刪 dominant sector。

## 2026-05-24 Portfolio rotation canary universe 診斷

### 目的

前幾輪已經證明 TWSE14 最新候選在 full-window、成本壓力與 rolling 6 窗口上表現不錯，但仍高度依賴少數股票與群組。這輪不用 TWSE14 內部再調參，而是把同一組 execution-aware candidate 原封不動套到新增的 9 檔股票，做 canary universe validation。

研究假設：

> 如果策略形狀真的具備可泛化 edge，則在未作為主調參錨點的 canary 股票池上，至少不應出現長期負 excess、rolling IR 大幅轉負或 concentration 更嚴重的情況。

### Canary 股票池

```text
cement = 1101, 1102
food = 1216
petrochemical = 1326
steel = 2002
auto = 2207
electronics = 2327, 2357, 2379
```

資料範圍：各檔皆使用 `2020-01-01` 到 `2026-05-20` 的 TWSE 日線資料。

### 固定條件

```text
rebalance = monthly
lookback_bars = 21
top_n = 4
min_return = 0.0
breadth_filter = on
breadth_lookback_bars = 42
breadth_min_positive_count = 3
max_consecutive_selections_per_symbol = 5
liquidity_lookback_bars = 20
min_average_traded_value = 500M
cost_multipliers = 1,2,3
rolling_windows = 24m window / 12m step / 12m min
```

報表檔案：

- `reports/generated/twse-canary9-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-liq500m-rolling24m-20260524.json`
- `reports/generated/twse-canary9-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-liq500m-rolling24m-20260524.md`

### Full-window 與 rolling 摘要

以下皆看 `1x` 成本倍率。

| Case | Full return | Full excess | Full IR | MDD | Active MDD | Liquidity blocks | Avg liquid count | Min rolling excess | Min rolling IR | Worst rolling active MDD | Max rolling top3 symbol share | Max rolling top3 group share |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `TWSE14 baseline` | `1745.89%` | `1409.71%` | `1.521` | `-18.61%` | `-19.81%` | `4` | `13.18` | `37.22%` | `0.814` | `-19.81%` | `82.62%` | `96.81%` |
| `TWSE23 liq500m` | `750.26%` | `589.36%` | `1.286` | `-35.35%` | `-29.81%` | `16` | `18.72` | `-8.54%` | `-0.046` | `-26.80%` | `63.55%` | `n/a` |
| `Canary9` | `14.92%` | `-0.91%` | `-0.002` | `-44.29%` | `-38.22%` | `32` | `5.46` | `-33.45%` | `-1.645` | `-35.02%` | `89.54%` | `98.45%` |

### Canary rolling 明細

| Window | Return | Excess | IR | MDD | Active MDD | Max symbol | Top3 symbol share | Max group | Top3 group share |
|---|---:|---:|---:|---:|---:|---|---:|---|---:|
| `roll01` | `37.72%` | `12.20%` | `0.216` | `-14.55%` | `-18.68%` | `2379` | `81.65%` | `electronics` | `98.00%` |
| `roll02` | `-37.12%` | `-33.45%` | `-1.645` | `-42.92%` | `-35.02%` | `2379` | `89.54%` | `electronics` | `98.45%` |
| `roll03` | `-24.88%` | `-22.16%` | `-1.028` | `-33.31%` | `-31.30%` | `2379` | `86.90%` | `electronics` | `95.14%` |
| `roll04` | `23.73%` | `14.38%` | `0.553` | `-13.37%` | `-16.16%` | `2379` | `68.67%` | `electronics` | `89.81%` |
| `roll05` | `-20.15%` | `-7.65%` | `-0.278` | `-31.79%` | `-23.63%` | `2327` | `86.99%` | `electronics` | `96.85%` |
| `roll06` | `3.47%` | `8.63%` | `0.466` | `-22.23%` | `-23.63%` | `2327` | `84.75%` | `petrochemical` | `91.81%` |

### 成本壓力摘要

| Cost | Return | Excess | IR | MDD |
|---:|---:|---:|---:|---:|
| `1x` | `14.92%` | `-0.91%` | `-0.002` | `-44.29%` |
| `2x` | `13.76%` | `-2.05%` | `-0.013` | `-44.69%` |
| `3x` | `12.61%` | `-3.18%` | `-0.024` | `-45.09%` |

### 解讀

1. **Canary 沒有通過泛化驗證**：full-window excess 為負、IR 幾乎為 `0`，且 MDD 達 `-44.29%`。這和 TWSE14 baseline 的正 excess / 正 IR 明顯不同。
2. **rolling failure 很嚴重**：`roll02` 與 `roll03` 連續兩個 rolling window 都是負 excess / 負 IR；`roll02` IR 為 `-1.645`。
3. **concentration 也沒有改善**：Canary9 的 max rolling top-3 symbol share 達 `89.54%`，max rolling top-3 group share 達 `98.45%`，比 TWSE14 baseline 更集中。
4. **liquidity gate 在 canary 池觸發更頻繁**：`32` 次 liquidity block，平均合格股票只有 `5.46` 檔，表示這個 canary 池容量與可選廣度都不足。

### Keep / Discard 判斷

- **Keep diagnostic**：canary universe validation 作為反證保留；它直接指出 TWSE14 候選尚未跨股票池泛化。
- **Do not promote**：不得把目前 execution-aware compare candidate 升級為穩定營利或主策略。
- **Current compare candidate unchanged**：仍可用 `TWSE14 top4 + breadth42/min3 + max consecutive 5 + liquidity 500M/20 bars` 作 compare candidate，但它更像 TWSE14-specific candidate，而不是已泛化策略。
- **Next**：優先處理資料品質與 universe quality：adjusted price、較慢批次 TWSE30+、更嚴格股票池篩選、canary 分層設計。不要再只微調 breadth / top-N；canary failure 表示問題不是單一門檻可解。

## 2026-05-24 Portfolio rotation adjusted price 診斷

### 目的

前幾輪一直把 TWSE STOCK_DAY 未調整權息列為主要資料邊界。本輪不改策略參數，而是把 Yahoo chart 的 `adjclose / close` 當成調整係數，套回 repo 既有 TWSE OHLCV，成交量仍保留 TWSE 原始成交股數，重新跑同一組 execution-aware compare candidate。

研究假設：

> 如果原本 TWSE14 強績效不是由未調整權息資料放大，則調整價版本至少應保留接近的 Information Ratio、rolling excess 與 drawdown profile；若調整價後 IR 明顯下降或 rolling window 變弱，原本未調整價結果不得當作主證據。

### 資料處理

- Yahoo 只用來提供調整係數：`adjustment_ratio = adjclose / close`。
- 調整後 OHLC：`TWSE open/high/low/close * adjustment_ratio`。
- 成交量：保留 TWSE 原始 `volume`，避免 Yahoo 台股 volume 與 TWSE 成交股數口徑不同而污染 liquidity gate。
- 暫存 CSV：`reports/generated/adjusted-data/TWSEADJ_<symbol>_1D.csv`。

Sanity check：直接使用 Yahoo OHLCV 會讓台股 volume 口徑和 TWSE 不一致，因此不採用 Yahoo volume 版本作主判斷。

### 固定條件

```text
universe = TWSE14
rebalance = monthly
lookback_bars = 21
top_n = 4
min_return = 0.0
breadth_filter = on
breadth_lookback_bars = 42
breadth_min_positive_count = 3
max_consecutive_selections_per_symbol = 5
liquidity_lookback_bars = 20
min_average_traded_value = 500M
cost_multipliers = 1,2,3
rolling_windows = 24m window / 12m step / 12m min
```

報表檔案：

- `reports/generated/twse14-twse-yahoo-ratio-adjusted-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-liq500m-rolling24m-20260524.json`
- `reports/generated/twse14-twse-yahoo-ratio-adjusted-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-liq500m-rolling24m-20260524.md`

### Full-window 與成本壓力

| Cost | Return | Excess | IR | MDD | Active MDD |
|---:|---:|---:|---:|---:|---:|
| `1x` | `1644.65%` | `1160.72%` | `1.156` | `-27.97%` | `-20.62%` |
| `2x` | `1616.61%` | `1132.79%` | `1.140` | `-28.20%` | `-20.79%` |
| `3x` | `1589.02%` | `1105.32%` | `1.125` | `-28.44%` | `-20.98%` |

與未調整價 baseline 對照：

| Case | Return | Excess | IR | MDD | Active MDD | Min rolling excess | Min rolling IR |
|---|---:|---:|---:|---:|---:|---:|---:|
| `TWSE14 raw liq500m` | `1745.89%` | `1409.71%` | `1.521` | `-18.61%` | `-19.81%` | `37.22%` | `0.814` |
| `TWSE14 adjusted-ratio liq500m` | `1644.65%` | `1160.72%` | `1.156` | `-27.97%` | `-20.62%` | `1.54%` | `0.104` |

### Rolling 摘要

| Window | Return | Excess | IR | MDD | Active MDD | Max symbol | Top3 symbol share | Max group | Top3 group share |
|---|---:|---:|---:|---:|---:|---|---:|---|---:|
| `roll01` | `262.86%` | `157.89%` | `1.563` | `-17.65%` | `-19.81%` | `2603` | `65.72%` | `shipping` | `91.03%` |
| `roll02` | `38.76%` | `1.54%` | `0.104` | `-27.10%` | `-20.61%` | `2603` | `76.90%` | `shipping` | `91.39%` |
| `roll03` | `66.75%` | `40.96%` | `1.000` | `-18.41%` | `-14.49%` | `2382` | `68.29%` | `electronics` | `94.77%` |
| `roll04` | `124.18%` | `55.26%` | `1.252` | `-17.04%` | `-13.77%` | `2382` | `59.59%` | `electronics` | `83.06%` |
| `roll05` | `92.27%` | `26.18%` | `0.638` | `-18.61%` | `-18.11%` | `2308` | `54.05%` | `electronics` | `85.83%` |
| `roll06` | `132.63%` | `44.78%` | `0.779` | `-13.79%` | `-20.62%` | `2308` | `63.07%` | `electronics` | `92.51%` |

### 解讀

1. **調整價後 edge 明顯降級**：full-window IR 從 `1.521` 降到 `1.156`，MDD 從 `-18.61%` 惡化到 `-27.97%`。策略沒有完全失效，但未調整價結果明顯過度樂觀。
2. **最弱 rolling window 幾乎失去安全邊際**：`roll02` excess 只剩 `1.54%`、IR 只剩 `0.104`，遠低於未調整價的 `37.22%` / `0.814`。
3. **group concentration 仍未解**：adjusted-ratio 版本 full-window top3 group share 仍約 `91.29%`，rolling top3 group share 最高約 `94.77%`，代表資料調整沒有自然解決群組依賴。
4. **liquidity gate 仍可執行但不構成穩定證據**：`1x/2x/3x` 成本後 IR 仍為正，但 MDD、rolling IR 與群組集中度都不足以升級。

### Keep / Discard 判斷

- **Keep diagnostic**：adjusted-ratio 回測是必要資料品質反證，後續評估 portfolio rotation 必須優先看調整價版本。
- **Do not promote**：不得用未調整價 `IR 1.521` / `MDD -18.61%` 當主策略證據；目前候選仍是 compare-only。
- **Current compare candidate downgraded**：`TWSE14 top4 + breadth42/min3 + max consecutive 5 + liquidity 500M/20 bars` 仍可作工程比較錨點，但策略品質判斷要以 adjusted-ratio 的 `IR 1.156`、`MDD -27.97%`、min rolling IR `0.104` 為主要風險版本。
- **Next**：正式化 adjusted price 資料來源與 manifest、較慢批次完成 TWSE30+、建立更高品質股票池，並在所有後續回測同時報 raw 與 adjusted-ratio 結果。

## 2026-05-24 Adjusted price data tool 正式化

### 目的

上一輪 adjusted price 診斷證明未調整權息資料會讓 portfolio rotation 候選過度樂觀，但當時的 adjusted CSV 還只是暫存研究流程。本輪把資料處理正式化成 test-covered 工具，讓後續策略迭代可以穩定重建 raw / adjusted-ratio 對照資料，而不是每次用臨時腳本。

研究假設：

> 若策略品質判斷要優先看 adjusted-ratio 版本，資料來源、調整方法、成交量口徑與缺漏列數就必須寫入 manifest，否則後續 TWSE30+ 或更高品質股票池驗證無法被重現。

### 程式改動

- 新增 `tools/build_twse_adjusted_ohlcv.py`。
- 新增 `tests/test_build_twse_adjusted_ohlcv_tool.py`。
- 工具會讀取既有 SignalForge TWSE OHLCV CSV。
- Yahoo chart 只提供 `adjclose / close` 調整比例，不使用 Yahoo OHLCV 與 volume。
- 調整後 OHLC：`source open/high/low/close * adjustment_ratio`。
- 成交量：保留 source CSV 的 TWSE `volume`。
- 輸出 adjusted CSV 與 deterministic manifest JSON。
- manifest 固定記錄：
  - `adjusted = true`
  - `adjustment_method = source_ohlcv_scaled_by_yahoo_adjclose_ratio`
  - `adjustment_source = Yahoo chart adjclose/close ratio`
  - `price_source_csv`
  - `volume_source = source CSV volume preserved`
  - `source_row_count`
  - `row_count`
  - `missing_adjustment_count`
  - `skipped_row_count`
  - `timezone = Asia/Taipei`

### 命令範例

```powershell
python tools\build_twse_adjusted_ohlcv.py `
  --symbol 2330 `
  --source-csv data\processed\TWSE_2330_1D.csv `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --output-csv reports\generated\adjusted-data\TWSEADJ_2330_1D.csv `
  --manifest-json reports\generated\adjusted-data\TWSEADJ_2330_1D_manifest.json
```

### 測試覆蓋

- Parser regression：鎖住 symbol、source CSV、日期窗、output CSV 與 manifest 參數。
- Yahoo ratio parsing：鎖住 UTC timestamp 轉 Asia/Taipei 日期，避免調整比例錯位。
- Ratio application：鎖住 OHLC scaling、TWSE volume 保留、缺 ratio skip count。
- Full tool flow：用固定 Yahoo chart fixture，不連網，驗證輸出 CSV 可載入且 manifest deterministic。
- Manifest regression：確認不寫入 current timestamp，避免每次重建資料都產生不可比較 diff。

### Keep / Discard 判斷

- **Keep code**：這是回測可驗證性改動，讓 adjusted-ratio 資料來源從一次性診斷升級成可重跑工具。
- **Do not promote strategy**：本輪沒有改善策略績效，也不代表 portfolio rotation 已穩定營利；它只是把資料品質 gate 補上。
- **Next**：用這個工具批次重建 TWSE14 adjusted CSV 與 manifest，再把 portfolio rotation 報表改成同時引用 raw / adjusted-ratio 結果；之後再慢批次擴到 TWSE30+ 或更高品質股票池。

## 2026-05-24 TWSE14 adjusted batch manifest 與重跑報表

### 目的

上一輪已把單檔 adjusted price 工具正式化，但 TWSE14 portfolio rotation 仍缺一個可重跑、可稽核的批次入口。本輪補上 batch 工具與 regression test，並用同一批 14 檔股票重新產生 adjusted CSV、per-symbol manifest、batch manifest，再重跑 execution-aware compare candidate。

研究假設：

> 若 adjusted-ratio 版本是後續策略品質判斷的主要風險版本，TWSE14 的每檔 adjusted CSV 與 portfolio rotation 報表都必須能從同一個 batch manifest 重建，否則後續 raw / adjusted 對照無法當成穩定 gate。

### 程式改動

- 新增 `tools/build_twse_adjusted_ohlcv_batch.py`。
- 新增 `tests/test_build_twse_adjusted_ohlcv_batch_tool.py`。
- Batch 工具用固定命名規則讀取 `data/processed/TWSE_<symbol>_1D.csv`，輸出：
  - `reports/generated/adjusted-data/TWSEADJ_<symbol>_1D.csv`
  - `reports/generated/adjusted-data/TWSEADJ_<symbol>_1D_manifest.json`
  - `reports/generated/adjusted-data/TWSE14_adjusted_batch_manifest_20260524.json`
- Batch manifest 不寫入 current timestamp，固定記錄 `adjustment_method`、`adjustment_source`、`volume_source`、每檔結果與 total counts。

### 批次命令

```powershell
python tools\build_twse_adjusted_ohlcv_batch.py `
  --symbols-list 1301,1303,2303,2308,2317,2330,2382,2412,2454,2603,2881,2882,2891,3711 `
  --source-dir data\processed `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --output-dir reports\generated\adjusted-data `
  --batch-manifest-json reports\generated\adjusted-data\TWSE14_adjusted_batch_manifest_20260524.json
```

批次結果：

| Field | Value |
|---|---:|
| Symbols | `14` |
| Adjusted rows | `21479` |
| Per-symbol CSVs | `14` |
| Per-symbol manifests | `14` |
| Missing adjustment count | `26` |
| Skipped row count | `2482` |

`skipped_row_count_total` 主要包含來源 CSV 中日期窗外資料列；`missing_adjustment_count_total=26` 需要保留在 manifest 中，後續若擴 TWSE30+ 時必須一起檢查。

### 重跑 portfolio rotation

使用剛建立的 adjusted CSV 重跑同一組 execution-aware compare candidate：

```text
universe = TWSE14 adjusted batch
rebalance = monthly
lookback_bars = 21
top_n = 4
breadth_filter = 42 / min positive 3
max_consecutive_selections_per_symbol = 5
liquidity_lookback_bars = 20
min_average_traded_value = 500M
cost_multipliers = 1,2,3
rolling_windows = 24m window / 12m step / 12m min
```

報表檔案：

- `reports/generated/twse14-batch-adjusted-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-liq500m-rolling24m-20260524.json`
- `reports/generated/twse14-batch-adjusted-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-liq500m-rolling24m-20260524.md`

### Full-window 與成本壓力

| Cost | Return | Excess | IR | MDD | Active MDD | Top3 symbol share | Top3 group share |
|---:|---:|---:|---:|---:|---:|---:|---:|
| `1x` | `1644.65%` | `1160.72%` | `1.156` | `-27.97%` | `-20.62%` | `47.26%` | `91.29%` |
| `2x` | `1616.61%` | `1132.79%` | `1.140` | `-28.20%` | `-20.79%` | `47.26%` | `91.29%` |
| `3x` | `1589.02%` | `1105.32%` | `1.125` | `-28.44%` | `-20.98%` | `47.26%` | `91.29%` |

### Rolling 摘要

| Window | Excess | IR | MDD | Active MDD | Max symbol | Top3 symbol share | Max group | Top3 group share |
|---|---:|---:|---:|---:|---|---:|---|---:|
| `roll01` | `157.89%` | `1.563` | `-17.65%` | `-19.81%` | `2603` | `65.72%` | `shipping` | `91.03%` |
| `roll02` | `1.54%` | `0.104` | `-27.10%` | `-20.61%` | `2603` | `76.90%` | `shipping` | `91.39%` |
| `roll03` | `40.96%` | `1.000` | `-18.41%` | `-14.49%` | `2382` | `68.29%` | `electronics` | `94.77%` |
| `roll04` | `55.26%` | `1.252` | `-17.04%` | `-13.77%` | `2382` | `59.60%` | `electronics` | `83.06%` |
| `roll05` | `26.18%` | `0.638` | `-18.61%` | `-18.11%` | `2308` | `54.05%` | `electronics` | `85.83%` |
| `roll06` | `44.78%` | `0.779` | `-13.79%` | `-20.62%` | `2308` | `63.07%` | `electronics` | `92.51%` |

### Keep / Discard 判斷

- **Keep code**：batch adjusted 工具與 regression tests。它把 TWSE14 adjusted 資料從單檔手動流程提升成可重跑 batch contract。
- **Keep diagnostic**：batch adjusted portfolio report 與前一輪 adjusted 診斷一致，證明結果不是臨時檔案造成的偶然差異。
- **Do not promote strategy**：adjusted-ratio 版本仍只有 `IR 1.156`、`MDD -27.97%`、min rolling IR `0.104`，且 top3 group share 仍約 `91.29%`；這不是穩定營利證明。
- **Current state**：`top4 + breadth42/min3 + max consecutive 5 + liquidity 500M/20 bars` 仍是 execution-aware compare candidate，但策略品質判斷必須以 adjusted batch 報表為主要風險版本。
- **Next**：讓後續 portfolio rotation 報表同時列出 raw / adjusted-ratio 來源與 batch manifest path；再做 TWSE30+ 或更高品質股票池，優先降低 rolling group concentration，而不是只微調 top-N 或 breadth threshold。

## 2026-05-24 raw / adjusted portfolio rotation 比較 artifact

### 目的

上一輪已正式化 TWSE14 adjusted batch manifest，但 raw 與 adjusted portfolio rotation 結果仍需要人工比對。本輪新增 deterministic 比較工具，讓策略評估 gate 可以直接引用同一份 raw summary、adjusted summary 與 batch manifest，避免只看未調整價結果而誤判策略品質。

研究假設：

> 若 adjusted-ratio 版本要作為策略品質主要風險版本，raw / adjusted 對照本身也必須成為可重跑 artifact，而不是筆記中的手動表格。

### 程式改動

- 新增 `tools/compare_portfolio_rotation_reports.py`。
- 新增 `tests/test_compare_portfolio_rotation_reports_tool.py`。
- 工具會讀取兩份 portfolio rotation summary JSON，對齊 full-window cost label 與 rolling window label，輸出 adjusted-minus-raw 的 return、excess、IR、MDD、active MDD、top3 symbol share 與 top3 group share。
- 可選 `--adjusted-batch-manifest-json` 會把 adjusted batch 的 rows、missing adjustment、skipped rows 與調整方法摘要寫進比較 artifact。

### 產生 artifact

```powershell
python tools\compare_portfolio_rotation_reports.py `
  --raw-summary-json reports\generated\twse14-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-liq500m-group-exposure-rolling24m-20260524.json `
  --adjusted-summary-json reports\generated\twse14-batch-adjusted-portfolio-rotation-monthly-lb21-top4-breadth42-min3-maxconsec5-liq500m-rolling24m-20260524.json `
  --adjusted-batch-manifest-json reports\generated\adjusted-data\TWSE14_adjusted_batch_manifest_20260524.json `
  --raw-label raw-twse `
  --adjusted-label adjusted-ratio-batch `
  --rolling-cost-label 1x `
  --output-json reports\generated\twse14-raw-vs-batch-adjusted-portfolio-rotation-lb21-top4-liq500m-compare-20260524.json `
  --output-md reports\generated\twse14-raw-vs-batch-adjusted-portfolio-rotation-lb21-top4-liq500m-compare-20260524.md
```

### 主要結果

| Scope | Raw | Adjusted | Delta |
|---|---:|---:|---:|
| Full 1x return | `1745.89%` | `1644.65%` | `-101.24%` |
| Full 1x excess | `1409.71%` | `1160.72%` | `-248.99%` |
| Full 1x IR | `1.521` | `1.156` | `-0.364` |
| Full 1x MDD | `-18.61%` | `-27.97%` | `-9.36%` |
| Full top3 group share | `89.27%` | `91.29%` | `+2.02%` |
| Weakest rolling IR | `roll02 = 0.814` | `roll02 = 0.104` | `-0.711` |

Adjusted batch manifest 摘要：

| Field | Value |
|---|---:|
| Symbols | `14` |
| Adjusted rows | `21479` |
| Missing adjustment count | `26` |
| Skipped rows | `2482` |

### Keep / Discard 判斷

- **Keep code**：raw / adjusted 比較工具與 regression tests。這是回測可驗證性與策略 gate 改動，不是績效最佳化。
- **Keep artifact**：比較 artifact 直接暴露 adjusted 後 IR、MDD 與 rolling robustness 的降級，後續 portfolio rotation 迭代應先引用這份對照或同等 artifact。
- **Do not promote strategy**：adjusted 後 full IR 仍有 `1.156`，但 MDD 惡化到 `-27.97%`，最弱 rolling IR 只有 `0.104`，top3 group share 仍超過 `91%`；不能視為穩定營利。
- **Current state**：`top4 + breadth42/min3 + max consecutive 5 + liquidity 500M/20 bars` 保留為 execution-aware compare candidate，但策略品質判斷以 adjusted-ratio 與 raw/adjusted comparison gate 為準。
- **Next**：下一步不是再微調 top-N 或 breadth threshold，而是做 TWSE30+、更高品質股票池、group regime validation，或更嚴格的容量/流動性 gate，並要求 adjusted 版本的 min rolling IR、MDD 與 concentration 同時改善。

## 2026-05-24 Portfolio rotation group breadth validation

### 目的

上一輪 group regime validation 顯示 adjusted `top3 / breadth4 / maxconsec5 / liq500M` 在 full + 6 個 rolling windows 全部是 high concentration，且 `7 / 7` 都是 `return_regime_dominated`。本輪再補一層 group breadth validation：不改策略規則，只檢查 dominant contribution group 內部是否有足夠成員一起呈現正動能，或只是單一股票 / 窄廣度撐起貢獻。

研究假設：

> 如果 dominant group 的貢獻來自單成員群組或低正動能廣度，即使 adjusted IR 仍為正，也不能把它升級成穩定營利候選；下一步應改善股票池品質或設計更直接的 contribution concentration gate，而不是繼續微調同一組 top-N / breadth threshold。

### 程式改動

- 新增 `tools/portfolio_rotation_group_breadth_validation.py`。
- 新增 `tests/test_portfolio_rotation_group_breadth_validation_tool.py`。
- 工具讀取 portfolio rotation summary JSON 與同一批 OHLCV CSV，對 full-window 與 rolling windows 計算 dominant group 的：
  - 成員數。
  - rebalance 樣本數。
  - 平均正動能成員比例。
  - 多數成員正動能的 rebalance 比例。
  - 全成員同時正動能的 rebalance 比例。
  - 平均成員 lookback return。
- 輸出 `broad_group_momentum`、`narrow_group_momentum`、`single_member_group` 或 `missing_breadth`，並保留 gate failure reason。

### 產生 artifact

```powershell
python tools\portfolio_rotation_group_breadth_validation.py `
  --summary-json reports\generated\twse14-batch-adjusted-portfolio-rotation-monthly-lb21-top3-breadth42-min4-maxconsec5-liq500m-rolling24m-20260524.json `
  --csv reports\generated\adjusted-data\TWSEADJ_1301_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_1303_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2303_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2308_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2317_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2330_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2382_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2412_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2454_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2603_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2881_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2882_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2891_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_3711_1D.csv `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-label 1x `
  --output-json reports\generated\twse14-batch-adjusted-portfolio-rotation-lb21-top3-breadth4-liq500m-group-breadth-validation-20260524.json `
  --output-md reports\generated\twse14-batch-adjusted-portfolio-rotation-lb21-top3-breadth4-liq500m-group-breadth-validation-20260524.md
```

### 主要結果

| Field | Value |
|---|---:|
| Gate pass | `false` |
| Rows | `7` |
| High concentration windows | `7` |
| Broad group momentum windows | `4` |
| Narrow group momentum windows | `1` |
| Single-member dominant windows | `2` |
| Missing breadth windows | `0` |
| Weakest breadth window | `roll03`，electronics 平均正動能成員比例約 `58.82%` |
| Weakest IR window | `roll02`，IR 約 `0.264` |

Window 重點：

| Window | Dominant group | Breadth type | Members | Avg positive share | Failure reason |
|---|---|---|---:|---:|---|
| `full` | `electronics` | `broad_group_momentum` | `3` | `60.70%` | `top3_group_contribution_concentration` |
| `roll01` | `shipping` | `single_member_group` | `1` | `71.43%` | `top3_group_contribution_concentration`, `single_member_dominant_group` |
| `roll02` | `shipping` | `single_member_group` | `1` | `64.71%` | `top3_group_contribution_concentration`, `single_member_dominant_group` |
| `roll03` | `electronics` | `narrow_group_momentum` | `3` | `58.82%` | `top3_group_contribution_concentration`, `dominant_group_breadth_below_threshold` |
| `roll04` | `electronics` | `broad_group_momentum` | `3` | `70.18%` | `top3_group_contribution_concentration` |
| `roll05` | `electronics` | `broad_group_momentum` | `3` | `70.37%` | `top3_group_contribution_concentration` |
| `roll06` | `electronics` | `broad_group_momentum` | `3` | `69.23%` | `top3_group_contribution_concentration` |

### Keep / Discard 判斷

- **Keep code**：group breadth validation 是回測可驗證性工具，能把 group regime dependency 分解成 broad / narrow / single-member evidence，並有 regression tests。
- **Keep artifact**：這份 artifact 說明 adjusted `top3 / breadth4 / maxconsec5 / liq500M` 的 concentration 問題不是單一型態；`roll01/roll02` 是 `shipping` 單成員 dominant，`roll03` 是 `electronics` 窄廣度，其他 electronics windows 雖有 broad momentum 但仍 top3 group contribution 過高。
- **Do not promote strategy**：即使 `top3 / breadth4` 的 adjusted min rolling IR 從 baseline `0.104` 改到 `0.264`，它仍有 `7 / 7` high concentration、`2 / 7` 單成員 dominant、`1 / 7` 窄廣度，不能視為穩定營利。
- **Current state**：`top3 / breadth4 / maxconsec5 / liq500M` 只保留為 compare anchor；它比 adjusted top4 baseline 的最弱 rolling IR 好，但 concentration gate 仍明確失敗。
- **Next**：下一步優先做更高品質股票池或 TWSE30+，但要同時跑 raw/adjusted、group regime、group breadth 與 concentration gate。若要設計新規則，應直接限制 realized group contribution concentration 或處理單成員群組，而不是再擴同一組 top-N / breadth / max-consecutive grid。

## 2026-05-24 Portfolio rotation promotion gate

### 目的

前幾輪已經把 adjusted summary、raw/adjusted comparison、group regime validation 與 group breadth validation 分別做成 artifact，但升級判斷仍需要人工在多份報告間切換。本輪新增 promotion gate，把這些證據合併成單一 `keep` / `compare-only` 結論，避免後續策略疊代只引用單一漂亮指標。

研究假設：

> 如果一個 portfolio rotation 候選要從 compare-only 升級，必須同時通過 full-window IR、3x cost stress、rolling IR、rolling excess、drawdown、symbol concentration、group concentration、raw/adjusted 降級、group regime 與 group breadth gate；只通過其中一部分不能視為穩定營利證明。

### 程式改動

- 新增 `tools/portfolio_rotation_promotion_gate.py`。
- 新增 `tests/test_portfolio_rotation_promotion_gate_tool.py`。
- 工具讀取：
  - portfolio rotation summary JSON。
  - raw / adjusted comparison JSON。
  - group regime validation JSON。
  - group breadth validation JSON。
- 預設升級門檻：
  - full 1x IR `>= 1.0`。
  - stress 3x IR `>= 0.75`。
  - min rolling IR `>= 0.50`。
  - min rolling excess `>= 0`。
  - full MDD / active MDD 絕對值 `<= 30%`。
  - max rolling top3 symbol share `<= 80%`。
  - max rolling top3 group share `<= 90%`。
  - raw/adjusted IR drop 不得超過 `0.25`。
  - adjusted MDD 惡化不得超過 `5%`。

### 產生 artifact

```powershell
python tools\portfolio_rotation_promotion_gate.py `
  --summary-json reports\generated\twse14-batch-adjusted-portfolio-rotation-monthly-lb21-top3-breadth42-min4-maxconsec5-liq500m-rolling24m-20260524.json `
  --raw-adjusted-comparison-json reports\generated\twse14-raw-vs-batch-adjusted-portfolio-rotation-lb21-top3-breadth4-liq500m-compare-20260524.json `
  --group-regime-validation-json reports\generated\twse14-batch-adjusted-portfolio-rotation-lb21-top3-breadth4-liq500m-group-regime-validation-20260524.json `
  --group-breadth-validation-json reports\generated\twse14-batch-adjusted-portfolio-rotation-lb21-top3-breadth4-liq500m-group-breadth-validation-20260524.json `
  --output-json reports\generated\twse14-batch-adjusted-portfolio-rotation-lb21-top3-breadth4-liq500m-promotion-gate-20260524.json `
  --output-md reports\generated\twse14-batch-adjusted-portfolio-rotation-lb21-top3-breadth4-liq500m-promotion-gate-20260524.md
```

### 主要結果

| Field | Value |
|---|---:|
| Decision | `compare-only` |
| Gate pass | `false` |
| Full 1x IR | `1.141` |
| Full 1x excess | `1406.71%` |
| Full 1x MDD | `-22.67%` |
| Full 1x active MDD | `-26.91%` |
| Stress 3x IR | `1.114` |
| Min rolling IR | `0.264` |
| Min rolling excess | `10.73%` |
| Worst rolling MDD | `-19.91%` |
| Worst rolling active MDD | `-26.91%` |
| Max rolling top3 symbol share | `81.40%` |
| Max rolling top3 group share | `97.38%` |

Failure reasons：

- `rolling_ir_below_threshold`
- `symbol_concentration_above_threshold`
- `group_concentration_above_threshold`
- `group_regime_gate_failed`
- `group_breadth_gate_failed`
- `single_member_dominant_group`
- `narrow_group_momentum`

### Keep / Discard 判斷

- **Keep code**：promotion gate 是回測可驗證性與策略升級判斷工具，能把多份 diagnostic artifact 收斂成單一可重跑結論，並有 regression tests。
- **Keep artifact**：本輪 promotion artifact 直接證明 adjusted `top3 / breadth4 / maxconsec5 / liq500M` 不能升級；它雖然 full-window 與 3x stress IR 仍強，但 rolling IR、rolling concentration、group regime 與 group breadth 都未通過。
- **Do not promote strategy**：目前沒有任何 portfolio rotation candidate 可稱為穩定營利。`top3 / breadth4 / maxconsec5 / liq500M` 仍只是 compare anchor，不是 keep。
- **Next**：下一步若繼續找新策略或調參，必須讓 promotion gate 同時改善 min rolling IR、max rolling top3 symbol/group share、group regime 與 group breadth。優先方向仍是更高品質股票池、TWSE30+ raw/adjusted 共同 gate，或直接限制 realized group contribution concentration / 單成員群組依賴。

## 2026-05-24 Portfolio rotation single-member group gate

### 目的

前一輪 group breadth validation 顯示 adjusted `top3 / breadth4 / maxconsec5 / liq500M` 的 `roll01/roll02` 是 `shipping` 單成員群組 dominant。這一輪把「單成員群組依賴」轉成 portfolio rotation 可選事前 gate，而不是只在事後診斷中標記。

研究假設：

> 如果單成員群組是 concentration 的主要風險，則要求入選股票所屬群組至少有 2 個成員，應該降低 single-member dependency；若 rolling edge 直接失效，就代表硬擋單成員群組不是可升級策略規則。

### 程式改動

- `tools/portfolio_rotation_sweep.py` 新增 `--min-symbols-per-selected-group`，預設 `1`，不改既有策略語意。
- `PortfolioRotationResult` 新增 `min_symbols_per_selected_group` 與 `group_member_block_count`。
- 選股流程會在 ranking 階段排除成員數低於門檻的群組；若設定大於 `1`，必須提供 `--symbol-group`，避免沒有分組時誤把所有股票視為單成員群組。
- Markdown full-window 與 rolling table 新增 `Min group members`、`Group member blocks`。
- `tools/portfolio_rotation_promotion_gate.py` 的 candidate parameters 會保留 `min_symbols_per_selected_group`。
- `tests/test_portfolio_rotation_sweep_tool.py` 新增 parser、單成員群組阻擋與 Markdown 欄位 regression。

### 產生 artifact

```powershell
python tools\portfolio_rotation_sweep.py `
  --csv reports\generated\adjusted-data\TWSEADJ_1301_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_1303_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2303_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2308_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2317_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2330_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2382_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2412_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2454_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2603_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2881_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2882_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_2891_1D.csv `
  --csv reports\generated\adjusted-data\TWSEADJ_3711_1D.csv `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-multipliers-list 1,2,3 `
  --rebalance-frequency monthly `
  --lookback-bars 21 `
  --top-n 3 `
  --breadth-filter `
  --breadth-lookback-bars 42 `
  --breadth-min-positive-count 4 `
  --liquidity-lookback-bars 20 `
  --min-average-traded-value 500000000 `
  --max-consecutive-selections-per-symbol 5 `
  --min-symbols-per-selected-group 2 `
  --symbol-group 1301:plastics `
  --symbol-group 1303:plastics `
  --symbol-group 2303:semiconductor `
  --symbol-group 2308:electronics `
  --symbol-group 2317:electronics `
  --symbol-group 2330:semiconductor `
  --symbol-group 2382:electronics `
  --symbol-group 2412:telecom `
  --symbol-group 2454:semiconductor `
  --symbol-group 2603:shipping `
  --symbol-group 2881:financial `
  --symbol-group 2882:financial `
  --symbol-group 2891:financial `
  --symbol-group 3711:semiconductor `
  --rolling-window-months 24 `
  --rolling-step-months 12 `
  --rolling-min-months 12 `
  --summary-json reports\generated\twse14-batch-adjusted-portfolio-rotation-monthly-lb21-top3-breadth42-min4-maxconsec5-liq500m-mingroup2-rolling24m-20260524.json `
  --summary-md reports\generated\twse14-batch-adjusted-portfolio-rotation-monthly-lb21-top3-breadth42-min4-maxconsec5-liq500m-mingroup2-rolling24m-20260524.md
```

### 主要結果

| Field | Value |
|---|---:|
| Full 1x IR | `0.759` |
| Full 1x excess | `609.71%` |
| Full 1x MDD | `-21.34%` |
| Full 1x active MDD | `-26.91%` |
| Stress 3x IR | `0.729` |
| Min rolling IR | `-0.994` |
| Min rolling excess | `-34.76%` |
| Worst rolling active MDD | `-26.91%` |
| Full top3 symbol share | `53.20%` |
| Full top3 group share | `98.26%` |
| Group member blocks | `51` |

與上一輪 adjusted `top3 / breadth4 / maxconsec5 / liq500M` compare anchor 相比：

| Metric | Previous anchor | Min group members 2 |
|---|---:|---:|
| Full 1x IR | `1.141` | `0.759` |
| Stress 3x IR | `1.114` | `0.729` |
| Min rolling IR | `0.264` | `-0.994` |
| Min rolling excess | `10.73%` | `-34.76%` |
| Max rolling top3 group share | `97.38%` | `100.00%` |

### Keep / Discard 判斷

- **Keep code**：`--min-symbols-per-selected-group` 是 deterministic、test-covered 的事前風控 / ablation 參數，能重跑檢查單成員群組依賴。
- **Discard setting**：`min_symbols_per_selected_group=2` 不能作為目前策略升級方向。它移除 `shipping/2603` 後，`roll02` excess 轉為 `-34.76%`、IR 轉為 `-0.994`，直接讓 rolling edge 失效。
- **Do not promote strategy**：full-window group concentration 仍高，top3 group share 約 `98.26%`；而且 stress 3x IR 只剩 `0.729`，低於 promotion gate 的 `0.75` stress threshold。
- **Current state**：這輪證明「硬擋單成員群組」不是解法；單成員群組風險要靠更高品質股票池、TWSE30+、或更細的 group contribution / re-entry gate 處理。
- **Next**：保留此參數作為 future ablation；下一輪不要把 `min_symbols_per_selected_group=2` 納入主候選，除非新股票池補足 shipping / telecom 等單成員群組後重新驗證。

## 2026-05-24 Portfolio rotation universe audit

### 目的

上一輪證明硬擋單成員群組會讓 adjusted `roll02` 直接失效，因此這輪不再新增選股規則，而是把「股票池品質」本身做成 deterministic audit。目標是在 TWSE30+ 或更高品質股票池實驗前，先確認每檔股票是否有足夠歷史資料、平均成交金額、群組成員數與 adjusted CSV coverage。

研究假設：

> 如果 portfolio rotation 的下一步是更高品質股票池，就必須先把股票池選擇變成可重跑 artifact；否則擴大股票池只是另一種人工挑樣本，仍可能造成 overfitting 或 group concentration 假象。

### 程式改動

- 新增 `tools/portfolio_rotation_universe_audit.py`。
- 新增 `tests/test_portfolio_rotation_universe_audit_tool.py`。
- 工具會讀取多檔 OHLCV CSV，依固定日期窗計算：
  - row count。
  - first / last timestamp。
  - 平均成交金額 `close * volume`。
  - group member count。
  - adjusted CSV 是否存在。
  - 逐股 `eligible` / `diagnostic-only` decision 與 failure reasons。
- Markdown / JSON 會同時輸出 group summary，讓單成員群組與 adjusted coverage 缺口在策略 sweep 前就可見。

### 產生 artifact

一般 TWSE23 universe audit：

```powershell
python tools\portfolio_rotation_universe_audit.py `
  --csv data\processed\TWSE_1101_1D.csv `
  --csv data\processed\TWSE_1102_1D.csv `
  --csv data\processed\TWSE_1216_1D.csv `
  --csv data\processed\TWSE_1301_1D.csv `
  --csv data\processed\TWSE_1303_1D.csv `
  --csv data\processed\TWSE_1326_1D.csv `
  --csv data\processed\TWSE_2002_1D.csv `
  --csv data\processed\TWSE_2207_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2327_1D.csv `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2357_1D.csv `
  --csv data\processed\TWSE_2379_1D.csv `
  --csv data\processed\TWSE_2382_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2603_1D.csv `
  --csv data\processed\TWSE_2881_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --csv data\processed\TWSE_2891_1D.csv `
  --csv data\processed\TWSE_3711_1D.csv `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --min-row-count 1200 `
  --min-average-traded-value 500000000 `
  --min-group-members 2 `
  --adjusted-csv-dir reports\generated\adjusted-data `
  --summary-json reports\generated\twse23-universe-audit-20260524.json `
  --summary-md reports\generated\twse23-universe-audit-20260524.md
```

Require adjusted 版本：

```powershell
python tools\portfolio_rotation_universe_audit.py `
  @csvArgs `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --min-row-count 1200 `
  --min-average-traded-value 500000000 `
  --min-group-members 2 `
  --adjusted-csv-dir reports\generated\adjusted-data `
  --require-adjusted-csv `
  @groupArgs `
  --summary-json reports\generated\twse23-universe-audit-require-adjusted-20260524.json `
  --summary-md reports\generated\twse23-universe-audit-require-adjusted-20260524.md
```

### 主要結果

| Field | TWSE23 audit | Require adjusted |
|---|---:|---:|
| Symbols | `23` | `23` |
| Eligible symbols | `16` | `12` |
| Groups | `10` | `10` |
| Singleton groups | `5` | `5` |
| Adjusted available | `14` | `14` |
| Min row count | `1200` | `1200` |
| Min average traded value | `500M` | `500M` |
| Min group members | `2` | `2` |

Require adjusted 後仍 eligible 的股票：

```text
1301,1303,2303,2308,2317,2330,2382,2454,2881,2882,2891,3711
```

品質通過但目前缺 adjusted CSV 的股票：

```text
1101,2327,2357,2379
```

主要 diagnostic-only 類型：

| 類型 | 股票 |
|---|---|
| liquidity below threshold | `1102,1326,2207` |
| group members below threshold | `1216,2002,2207,2412,2603` |
| adjusted missing but otherwise useful | `1101,2327,2357,2379` |

### Keep / Discard 判斷

- **Keep code**：universe audit 是 deterministic、test-covered 的研究前置 gate，能避免後續擴大股票池時靠人工猜測。
- **Keep artifact**：TWSE23 audit 說明目前 raw 可用股票池雖有 23 檔，但只有 16 檔通過基本品質；若策略品質判斷要求 adjusted CSV，現階段只剩 12 檔可直接進入 adjusted rotation。
- **Do not promote strategy**：這輪沒有改善策略績效，也沒有證明 portfolio rotation 穩定營利；它只讓下一輪股票池擴充的資料邊界更清楚。
- **Current state**：`TWSE23 raw` 仍只適合作 concentration diagnostic；要做真正的 expanded adjusted candidate，至少要補齊 `1101,2327,2357,2379` 的 adjusted CSV 或直接做 TWSE30+ adjusted batch。
- **Next**：優先補齊 eligible 但缺 adjusted 的股票，再重跑 adjusted universe audit、portfolio rotation sweep、raw/adjusted comparison、group regime / breadth validation 與 promotion gate。
