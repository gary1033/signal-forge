---
title: ORB + Volume + VWAP
tags:
  - project/SignalForge
  - trading/strategy
  - trading/intraday
status: research
updated: 2026-05-21
repo_impl: C:\Projects\signal-forge\src\signal_forge\strategies\orb_volume_vwap.py
---

# ORB + Volume + VWAP

## 先懂這些詞

- **ORB（Opening Range Breakout，開盤區間突破）**：先觀察開盤後前幾分鐘的高低點，把它當成市場一開始的主戰區。若之後價格正式突破這個區間，代表當日可能出現方向性表態。
- **Opening range / 開盤區間**：例如前 `30` 分鐘內的最高價與最低價。這份策略會把這段時間當成區間建立期，期間不進場。
- **Breakout / 突破**：不是單純盤中刺穿，而是 bar close 真正收在區間上方，避免只被上影線誤觸發。
- **Session VWAP / 當日 VWAP**：從當日 session 開始一路累積的成交量加權平均價。若價格站在它上方，白話上代表當日平均成交成本偏向有利於多方。
- **Relative volume / 相對量能**：把當前 bar 的成交量跟最近 N 根 bar 的平均量比較。這份策略用它過濾「有突破形狀但沒有跟量」的假突破。
- **OR average volume / 開盤區間平均量能**：只用 opening range 建立期內那些 bar 的成交量做平均，拿來判斷 breakout 當下是否相對於早盤主戰區真正放量。
- **Long-only / 只做多**：策略只產生 `target_position=1.0` 或 `0.0`，不討論放空。
- **Session reset / 換日重置**：前一天若已進場，新的 session 開始時先把狀態歸零，再重新建立新的一天開盤區間。
- **Warmup / 暖機期**：量能平均或 session 區間還沒形成前，策略只會輸出空手。

## 策略假設

這個策略相信：真正值得追的 intraday breakout，不只是價格穿越某條線，還要同時滿足兩件事。

第一，突破發生在開盤區間完成之後，代表市場先把早盤的價格爭奪區間走出來。第二，突破當下要有量能放大，而且價格位於當日 VWAP 上方，才比較像是有參與度、不是單純低量滑價。

換句話說，這不是單看 ORB 的純形態策略，而是把「區間突破、量能確認、VWAP 站上」綁在同一根 bar 上，盡量只保留相對乾淨的 long breakout。

## 進出場條件

- `opening_range_building`：當前 bar 還在開盤區間建立期內，例如 session 開始後前 `30` 分鐘，`target_position=0.0`。
- `session_timestamp_required`：若資料只有日期、沒有 intraday 時間，策略不會硬做 ORB 判斷，直接維持空手。
- `outside_session`：bar 早於設定的 session 起始時間時，不參與判斷。
- `below_or_high`：開盤區間完成後，若 close 仍未收在 OR high 上方，維持空手。
- `breakout_below_vwap`：價格雖然突破 OR high，但若 close 沒有站上 session VWAP，維持空手。
- `breakout_vwap_slope_blocked`：若啟用 VWAP slope confirmation，而且 breakout 當下的 session VWAP 相對前一根同 session bar 沒有上升，則不接受這次突破。它的語意不是「價格是否在 VWAP 上方」，而是「VWAP 本身是否仍在往上走」。
- `breakout_below_ema`：若啟用 EMA trend confirmation，而且 breakout 當下的 close 仍未站上 rolling EMA，則不接受這次突破。它的語意是：即使價格已經越過 OR high，若較慢的 intraday 趨勢基線還沒有被重新站上，就不把這次訊號視為夠乾淨的趨勢突破。
- `breakout_ema_slope_blocked`：若啟用 EMA trend confirmation，而且 rolling EMA 相對前一根同 session bar 沒有上升，則不接受這次突破。這個條件用來明寫策略對「EMA 本身也要往上」的要求。
- `ema_inside_opening_range`：若啟用 EMA inside-range 結構 gate，而且 breakout 發生時 rolling EMA 仍落在 OR 盒子內，就不接受這次突破。它的語意不是「價格有沒有站上 EMA」，而是「趨勢基線本身還卡在早盤主戰區裡，結構上仍然模糊」。
- `breakout_ema_reference_unavailable`：若啟用 EMA inside-range gate，但 breakout 當下還沒有足夠 bar 讓 rolling EMA 完成暖機，則這次 breakout 不進場。這個情況通常代表 EMA window 設太長，已經超過目前可用的 intraday 範圍。
- `breakout_volume_blocked`：價格突破且站上 VWAP，但成交量未達目前啟用的量能 baseline 乘上 `volume_multiplier`，維持空手。預設 baseline 是 rolling volume SMA；若啟用 `OR average volume baseline`，則改成對比 opening range 平均量能。
- `opening_range_too_narrow` / `opening_range_too_wide`：若啟用 range size filter，且開盤區間相對於 session 第一根開盤價的百分比太窄或太寬，即使有突破也不進場。
- `breakout_body_too_small`：若啟用 breakout candle body strength，且突破 K 棒的 `abs(close - open) / (high - low)` 沒有達到最小門檻，維持空手。
- `breakout_not_fresh_from_or`：若啟用 fresh breakout gate，而且前一根 close 已經離開 OR 盒子，代表這根 bar 不是「從區間內部重新發動」的 breakout，維持空手。
- `outside_signal_window`：若啟用 signal window cutoff，而且新的 breakout 發生在允許時間窗之外，則不接受這次新突破；這不是 forced flatten 規則，既有 long 不會因為超時自動歸零。
- `orb_volume_vwap_breakout`：close 突破 OR high、站上 session VWAP、量能達門檻時，`target_position=1.0`。
- `waiting_for_retest_confirmation`：若啟用 retest confirmation，第一次突破後不立刻進場，而是先記錄「已突破，等待回踩確認」。
- `retest_not_touched`：已經突破，但後續 bar 還沒有真正回踩 OR high，維持空手。
- `orb_retest_vwap_breakout`：啟用 retest confirmation 時，只有在突破之後的後續 bar 回踩 OR high，並重新以 close-confirmed 站穩區間上方、同時通過 VWAP 與量能條件，才翻成 long。
- `hold_intraday_breakout`：同一個 session 內，若已經進入 long 狀態，後續 bar 維持 `target_position=1.0`，不重複進場。
- `session_reset`：新 session 開始時，若前一根 bar 還在 long，先輸出 `target_position=0.0`，避免把前一日 intraday breakout 直接帶進下一天。

目前這個實作是 **最小 long-only 版本**：

- 只做向上突破。
- 只接受 close-confirmed breakout。
- 不含停損、停利、retest、FVG、dashboard、alert webhook。
- 不含 short-side 邏輯。

若啟用 retest confirmation，策略流程會改成：

1. 先偵測突破，但不立刻進場。
2. 等之後的 bar 至少有一次回踩 OR high。
3. 回踩後的 bar 重新收在 OR high 上方，且仍符合 VWAP 與量能條件，才真的進場。

這個模式的目的是減少第一時間假突破，但代價是進場會更慢，也可能錯過一路不回踩的強勢走勢。

## 主要參數

- `opening_range_minutes`：預設 `30`，代表 session 開始後前 30 分鐘用來建立 OR high / OR low。
- `session_start_hour` / `session_start_minute`：預設 `09:30`，目前先以美股 regular session 為基準；現在也可以從 CLI 用 `--orb-session-start-hour`、`--orb-session-start-minute` 覆寫。
- 若要把這個策略用在台積電 `2330` 的 regular-session 研究，market-clock metadata 應改成 `Asia/Taipei 09:00-13:30`，而不是沿用美股預設。
- `volume_window`：預設 `20`，用來計算平均量能。
- `volume_multiplier`：預設 `1.5`，代表 breakout bar 的量能至少要是最近平均量的 1.5 倍。
- `require_vwap_confirmation`：預設 `True`，要求 breakout bar close 站上 session VWAP。
- `--orb-vwap-slope-confirmation`：可選的 VWAP slope confirmation。若有設定，除了 `close > VWAP` 之外，還要求 breakout 當下的 session VWAP 相對前一根同 session bar 保持上升，避免在平或下彎的 VWAP 上方追突破。
- artifact 的 `strategy_spec` 現在會把 `orb_vwap_slope_tier` 明寫成 `secondary_refinement`，避免後續把它誤讀成 ORB 主線第一層結構條件。
- `--orb-ema-trend-confirmation`：可選的 EMA trend confirmation。若有設定，breakout 當下除了要維持 `close > OR high`，還要求 `close > rolling EMA`，且該 EMA 相對前一根同 session bar 保持上升，避免只靠短線噴出就追價。
- `--orb-ema-window`：EMA trend confirmation 使用的 rolling EMA 視窗長度。預設 `20`；視窗越大，越偏向「較慢趨勢基線」。
- `--orb-reject-ema-inside-range`：可選的結構 gate。若有設定，當 breakout 發生時只要 rolling EMA 仍落在 `OR low ~ OR high` 之間，就直接拒絕這次訊號。這一條不是再疊一個 generic 均線濾網，而是直接利用 EMA 與 OR 盒子的相對位置判斷 breakout 結構是否夠乾淨。
- `require_retest_confirmation`：預設 `False`。開啟後，突破不立刻進場，要先等回踩 OR high 後再確認一次；CLI 參數是 `--orb-retest-confirmation`。
- `--orb-opening-range-minutes`：CLI 可覆寫 OR 建立期長度，讓同一個 ORB 骨架能研究不同市場或不同開盤節奏。
- artifact 的 `strategy_spec` 現在也會明寫 ORB 目前是 `regular-session research contract only`，避免把這個版本誤讀成已支援 extended-hours。
- `--orb-min-range-pct` / `--orb-max-range-pct`：可選的 OR range size filter。它先用 session 第一根 bar 開盤價當參考，要求 OR 寬度百分比落在指定區間內；這是目前 repo 的最小研究版本，還不是 ATR-normalized 寫法。
- `--orb-min-breakout-pct`：可選的 breakout distance threshold。若有設定，close 不只要收過 OR high，還要至少高出 OR high 一段最小百分比，才算有效突破。
- `--orb-full-bar-above-range`：可選的 breakout candle structure gate。若有設定，breakout candle 的 `low` 也必須站在 OR high 上方，不能只有 close 勉強越線。
- `--orb-min-breakout-body-pct`：可選的 breakout candle body strength。若有設定，breakout candle 的 `body / full candle range` 必須達到最小比例，才接受這次突破。
- `--orb-fresh-breakout-from-or`：可選的 fresh breakout gate。若有設定，只有前一根 close 仍在 OR 盒子內時，當前這根 close 穿出 OR high 才視為新的 breakout。
- `--orb-use-opening-range-volume-baseline`：可選的 OR 專用量能 baseline。若有設定，breakout volume 會拿來對比 opening range 平均量能，而不是一般 rolling volume SMA。
- `--orb-signal-window-minutes`：可選的 signal window cutoff。若有設定，只有 session 開始後某段時間內發生的**新 breakout** 會被接受；它不會強制平掉已經持有的 long，只是停止追更晚才出現的突破。
- `--orb-session-end-hour`、`--orb-session-end-minute`：目前先用來顯式記錄 ORB regular-session 的結束邊界，會寫進 artifact / strategy spec，方便之後定義完整的 market-clock contract；這一步**不會**自動變成 forced flat 規則。
- `--orb-session-timezone`：目前先用來顯式記錄 ORB 研究假設所依賴的 market-clock timezone，避免把時間邊界默默綁死在資料欄位或聊天上下文裡。
- summary artifact 的 `strategy_spec` 現在也會寫出 run-level `orb_observed_range_pct_*` 欄位，讓回看結果時能直接知道這次資料中的 OR 大小範圍。
- 若有啟用 range gate，artifact 也會補上 `orb_observed_range_pct_below_min_sessions`、`orb_observed_range_pct_within_gate_sessions`、`orb_observed_range_pct_above_max_sessions`，直接顯示這次資料有多少 session 被 gate 擋在外面。
- 若有啟用 `--orb-use-opening-range-volume-baseline`，artifact 的 `strategy_spec` 也會明寫目前 breakout volume 是相對於 OR 平均量能，而不是 rolling volume SMA。

## 股價走勢解說圖

![[assets/orb-volume-vwap-trend-explainer.png]]

圖中藍色虛線代表開盤區間上緣、紫色線代表 session VWAP。只有當價格在區間完成後正式突破 OR high，且突破 bar 同時站上 VWAP、伴隨量能放大時，才視為 long entry。此圖為教學示意圖，不是真實市場資料，也不代表績效保證。

## 風險與限制

- ORB 是 intraday 概念；若資料只有日線，這個策略基本上不適用。
- `09:30` session 起點是市場假設，不適合直接硬套到台股、期貨、加密貨幣或 extended-hours。
- 若要支援其他市場，session start / OR 長度 / 是否視 regular session 為唯一有效區間，都應該被明確參數化。
- 同樣的量能門檻對不同市場不一定合理，`1.5x` 只是研究起點。
- 目前進場後是 session 內持有，不是完整的停損停利系統。
- 若啟用 retest confirmation，會犧牲部分第一時間最強的 breakout，換取較高的確認度。
- 只做 long-only，若市場更適合做反向 breakout 或 short，這個版本不會捕捉。
- session VWAP 只從當日開盤累積，不等於 anchored VWAP，也不處理事件錨點。
- 目前沒有明確的 session close exit 規則；若後續要加入，會把策略從 entry refinement 推向完整 intraday 持有系統。
- TradingView 官方 session 文件把 regular / premarket / postmarket 視為不同 session 類型；若未來要研究 extended-hours，不能只在策略內多加一個布林值，還要先定義資料來源與 VWAP / OR 區間是否跨 session 累積。
- 多個 ORB 腳本會把開盤區間大小是否「過小」或「過大」當成濾網；目前版本已加入可選的 OR range size filter，但它是用開盤參考價百分比，而不是 ATR-normalized，後續仍可再升級。
- 現在 artifact 雖然已經會寫出 `orb_observed_range_pct_*`，但這些觀測值還需要先跨資料集比對，否則太早升級到 ATR-normalized，容易把新複雜度加進來，卻還不知道舊定義到底哪裡不夠用。
- 若啟用 breakout distance threshold，門檻設太高會讓強勢但貼近 OR high 的有效突破也被擋掉，所以它比較適合當可選 refinement，而不是預設硬規則。
- 若啟用 full-close-above-range，會犧牲部分帶下影但最後成功走強的突破；它換來的是更乾淨的結構確認，而不是更多訊號數量。
- 若啟用 breakout candle body strength，門檻設太高會把「有突破但帶長影線」的真突破一併擋掉，所以它比較適合當可選 refinement，而不是預設硬規則。
- 公開 ORB 腳本也常要求 breakout candle 本身要夠強，例如 body ratio 達到下限，或整根 candle 都站在 OR high 上方；這兩種都仍屬單時間框架的 entry quality filter。
- 公開 ORB 腳本也常加入「突破必須超出 OR high 一段最小距離」的門檻；這種 breakout distance threshold 仍屬 entry quality filter，後續若要補強，可優先於更重的 session policy。
- 另一類 ORB 腳本會要求 breakout 必須是「從 OR 盒子內部發動」：也就是前一根 close 還在 OR 內，下一根才真正收出 OR 外。這能避免 price 已經在區間外游走時，後續每一根再被誤讀成新的 breakout。
- 還有一類 ORB 腳本不只看「最近 N 根平均量」，而是把 breakout volume 直接對比 **opening range 本身的平均量能**。這種寫法更貼近 ORB 自己的語意，因為它比較的是「突破這一刻」相對於早盤主戰區到底有沒有放量。
- OR average volume baseline 雖然更貼近 ORB 語意，但也更依賴 opening range 建立期本身的資料品質；若 OR 視窗太短、成交量異常集中，baseline 可能比 rolling SMA 更敏感。
- signal window cutoff 若設得太短，會把「開盤後稍晚才成熟、但仍然有效」的突破直接擋掉；若設得太長，則和沒有 cutoff 的差異會很小。
- 很多公開 ORB 腳本會把 `session time / timezone` 做成顯式設定，甚至把 OR 視窗與 trading session 分開定義；目前 SignalForge 雖然已把這層設定寫進 CLI / strategy spec，但還沒有把它進一步變成出場規則或 extended-hours policy。
- VWAP slope confirmation 雖然仍屬低風險的 entry-quality filter，但它會把 VWAP 從「位置條件」升級成「位置 + 方向」條件；若條件過嚴，可能把剛轉正、但 VWAP 還來不及明顯抬升的有效突破一起擋掉。
- EMA trend confirmation 雖然仍屬低風險的單時間框架 refinement，但它會把 ORB 的趨勢對齊從「只看當日 VWAP」擴成「同時看較慢的 intraday EMA」；若 EMA 視窗設太短，它可能只是重複 VWAP / body / fresh breakout 已經擋掉的訊號，若設太長，則可能把剛啟動的有效突破一起擋掉。
- EMA inside-range gate 雖然也屬低風險的單時間框架 refinement，但它會把 ORB 從「突破時價格在哪裡」推進到「突破時趨勢基線相對 OR 盒子在哪裡」；若 EMA window 太短，EMA 很容易快速脫離 OR 盒子，這條 gate 可能幾乎不起作用；若設太長，則可能讓許多本來合理的早盤突破因為 EMA 暖機太慢而被擋下。
- 若啟用 fresh breakout gate，會犧牲部分「先低量站出區間、隔一根才放量」的追價機會；它換來的是更乾淨的 breakout 定義，避免已經站在區間外的價格被重複計算成新訊號。
- 很多公開 ORB 腳本也提供 `close / high-low / wick` 三種 trigger mode，但對目前的 SignalForge 來說，`close` 仍是最合理的研究邊界；若切到 `wick` 或 `high-low`，策略就會更接近 intrabar 判定，而不再只是 close-confirmed breakout。
- 公開 ORB 腳本常同時提供 `signal window cutoff`，例如只允許開盤後前一段時間內的新 breakout。這類條件雖然不是純 entry quality filter，但仍可用同時間框架的 session/time 邊界實作，不需要引入 `request.security()`。

## 下一步

- 先補 intraday 樣本資料需求，確認 repo 要怎麼保存可重現的 ORB 測試資料。
- 若要用台積電 `2330` 正式回測，先準備手動匯入的 intraday CSV，欄位固定為 `timestamp,open,high,low,close,volume`，且 `timestamp` 必須含時間資訊。
- 目前本地 SignalForge 工作區沒有可直接供 ORB 使用的 `2330` intraday CSV；下一步是先把這個阻塞點解除，而不是再拿日線結果硬做比較。
- 比較是否要把 ORB high 突破後的持有狀態改成「持有到 session 結束」還是允許中途掉回 VWAP 就歸零。
- 已加入可選 retest confirmation；下一步改成比較「第一時間突破」與「回踩再確認」兩種版本的 entry-edge 語意差異。
- 若要做 session close exit，應該把 session end time、forced flatten 顯示方式與 reporting contract 一起定義，而不是只在策略內部偷加一條歸零規則。
- 若要讓 ORB 脫離美股預設，下一步應把 session start、opening range minutes 與 timezone 假設寫成更明確的 CLI / strategy spec，而不是繼續藏在策略預設值裡。
- 目前已經把 session 起點與 opening range length 暴露成 CLI 參數；下一步是釐清 session end 與 timezone 是否也要進入 strategy spec。
- extended-hours 暫時應視為資料邊界，不應在沒有對應樣本與產品判斷時直接變成策略模式。
- range size filter 已經有最小版本，且 OR range 已開始寫進 artifact；下一步應先利用 `orb_observed_range_pct_*` 回看不同資料集的分布，再決定是否值得升級成 ATR-normalized gate。
- 若後續發現大多數 session 都落在 gate 內或外，應先調整研究假設或比較不同資料集，再決定 ATR-normalized 是否真的能提供額外資訊。
- 若要再補一個小型 refinement，`min breakout % beyond OR` 比 trading cutoff、session close exit 或 extended-hours 更適合先進入研究候選。
- breakout distance 之後，下一個較低風險的研究候選是 breakout candle strength / full-close-above-range，因為它仍然不需要新的 session 或持有語意。
- breakout candle body ratio 現在已可作為可選條件；下一步更合理的是比較它與 `full-close-above-range` 疊加後，實際擋掉多少弱突破，而不是立刻再擴到 EMA、gap 或 session cutoff。
- `breakout starts from inside OR` 現在已可作為可選條件；下一步更合理的是比較它與 body strength 疊加後，是否只是重複擋掉同一批弱突破。
- `OR average volume baseline` 現在已可作為可選條件；下一步更合理的是比較它和 rolling volume SMA 在不同資料集上，到底擋掉的是同一批弱突破，還是真的補到新的 entry-quality 邏輯。
- `signal window cutoff` 現在已可作為可選條件；下一步更合理的是比較它和 fresh breakout、body strength、OR volume baseline 疊加後，實際擋掉的是同一批晚到突破，還是補到新的 session policy 邏輯。
- `session end/timezone 顯式化` 現在已補進 CLI / strategy spec；下一步更合理的是先比較不同 market-clock 設定下 artifact 的解讀差異，再決定 `session close exit` 是否值得進入可選 policy。
- 若還要再補一個低風險、且仍屬 entry-quality 的 refinement，`VWAP slope confirmation` 比 `session close exit` 更適合先做。它的語意是：不只要求價格站在 VWAP 上方，還要求 VWAP 本身正向傾斜，避免在平或下彎的 VWAP 上方追假突破。
- `VWAP slope confirmation` 現在已可作為可選條件；下一步更合理的是比較它和 body strength、fresh breakout、OR volume baseline 疊加後，是否只是重複擋掉同一批弱突破。
- 若還要再補一個低風險、且仍屬單時間框架趨勢對齊的 refinement，`EMA trend confirmation` 會比 `gap fill bias` 或 `session close exit` 更適合先做。它的語意是：不只要求 VWAP 與價格對齊，還要求較慢的 intraday 趨勢基線也在往上，避免只靠當日 VWAP 的短期抬升就追突破。
- `EMA trend confirmation` 現在已可作為可選條件；下一步更合理的是比較它和 `VWAP slope`、`body strength`、`fresh breakout` 疊加後，到底是補到新的趨勢對齊資訊，還是只是重複擋掉同一批晚到或偏弱的 breakout。
- 若還要再補一個低風險、而且更貼近 ORB 幾何結構的 refinement，`EMA relative to opening range` 會比單純再堆一條 generic SMA 更合理。它的語意不是「再多一條均線」，而是直接問：**EMA 本身相對 OR 盒子在哪裡**，例如只在 `OR high` 位於 EMA 上方時接受 long，或當 EMA 落在 OR 盒子內部時直接不給訊號。
- 這種 `EMA relative to OR` gate 仍然屬單時間框架、close-confirmed 的 entry-quality filter；它不像 gap fill bias 那樣需要把 prior-day close / session 邊界語意拉進來，也不像 `session close exit` 那樣直接進入持有 policy。
- `EMA inside-range` 現在已可作為可選條件；下一步更合理的是比較它和 `EMA trend confirmation`、`VWAP slope`、`fresh breakout` 疊加後，是否真的補到新的結構資訊，而不是只重複擋掉同一批弱突破。
- 依公開 ORB 腳本研究，`EMA inside-range` 比 `VWAP slope` 更接近 ORB 的核心幾何結構。像 `ORB with 100 EMA` 這類腳本會直接把「EMA 落在 OR 盒子內」視為禁訊號條件；相對地，`VWAP slope` 雖然常見，但更像第二層 momentum refinement。
- 因此目前較合理的主線排序是：先把 `EMA inside-range` 視為高優先級結構 gate，再把 `VWAP slope` 視為次要、可選、需要額外樣本證據才值得保留的趨勢微調條件。
- 進一步用 `MSFT 5m demo` 比較 `EMA inside-range` 與 `EMA inside-range + VWAP slope` 後，`VWAP slope` 顯示出**微弱但非零**的增量：PF 從 `4.452` 小幅升到 `4.546`，hold bars 從 `873` 降到 `865`，並新增 `2` 根 `breakout_vwap_slope_blocked`。這代表它不是完全冗餘，但仍不足以升回主線核心條件。
- 因此目前較合理的定位是：`VWAP slope` 保持可選、可比較，但仍屬次要 refinement，而不是 ORB 主線的第一層結構 gate。
- 進一步對照公開腳本後，這個排序更明確：`ORB + Volume + VWAP Breakout` 與 `Opening Range Breakout + VWAP + Volume` 這類腳本的主線通常停在 `price relative to VWAP`，`VWAP slope` 若存在，也多半只是額外 direction filter；因此 SignalForge 沒必要再擴大它的主線 CLI / artifact surface。
- 目前 repo 也已把這個排序正式寫進 artifact：`strategy_spec` 會用 `orb_vwap_slope_tier=secondary_refinement` 明示 `VWAP slope` 的層級。後續回看 JSON / markdown 時，不用再靠實驗紀錄猜它是不是主線條件。
- 進一步用 `MSFT 5m demo` 重跑 disabled / enabled 兩條路徑後，可以確認 `orb_vwap_slope_tier=secondary_refinement` 在 runtime artifact 其實早就同時存在於：
  - `EMA inside-range`（`orb_vwap_slope_confirmation=disabled`）
  - `EMA inside-range + VWAP slope`（`orb_vwap_slope_confirmation=enabled`）
  上一輪補的 disabled/default regression 並沒有改變 artifact 內容，只是把這個 deterministic contract 正式鎖進測試。
- 進一步對照公開 ORB 腳本後，`VWAP slope` 最合理的定位仍是 **direction/trend refinement**，而不是所有 optional filter 的統一模板。`EMA trend` 和它屬同層；但 `OR size`、`OR volume baseline`、`gap fill`、`signal window` 比較像不同 family 的條件，因此後續若要擴 artifact contract，應優先走 `role/family`，不要把全部欄位都標成同一個 `secondary_refinement`。
- 目前 `VWAP slope tier` 也已經有三層保護：artifact disabled/enabled regression、runtime artifact 不變分析，以及 `strategy_spec_from_args(...)` 的直接單元測試。這表示在沒有新策略語意變更之前，夜間自動化不需要再為同一個 `VWAP slope tier` 問題重複跑更多同型比較；更合理的下一步是把注意力轉向 `EMA trend` 是否也需要對稱 contract，或把 disabled 狀態下的 `orb_vwap_slope_rule` 文案調整得更中性。
- 在繼續增加 stop loss、take profit、trailing stop 或 session close exit 前，應先補 ORB filter attribution / rejection summary，讓 artifact 能直接看出各個 filter 擋掉多少候選突破，以及它們是否只是重複擋掉同一批弱訊號。
- `orb_filter_attribution` 現在已寫進 `*_trace_summary.json`；若這批 run 屬於 ORB 語意，artifact 會直接列出 `accepted / hold / session / range / structure / trend / volume / retest / other` 的 group counts，以及真正屬於 filter rejection 的 blocked reasons。
- 因此下一步不該先再堆新 filter，而應進入分析比較：用既有資料與 artifacts 對照不同 ORB filter 組合，確認 `EMA inside-range`、`EMA trend`、`VWAP slope`、`OR volume baseline` 等條件到底補到什麼資訊。
- 目前第一份用 repo 內 `MSFT 5m demo` 做的 attribution 比較顯示：`EMA inside-range` 是唯一把 ORB 從 `FAIL` 拉到 `PASS` 的 refinement，且同時大幅壓低最大回撤；相對地，`VWAP slope` 在這份樣本上沒有新增辨識力，`OR volume baseline` 則過度保守。
- stop / target / session close exit 都是合理候選，但它們屬於 Phase 2 持有與出場 policy；若要實作，應同步設計 execution assumption、fill rule、reason / reporting contract 與 regression tests，而不是把它當成單純 entry filter。
- 若 `session close exit` 之後真的要做，也應該建立新的 reason / reporting contract，明確區分「時間邊界 metadata」與「出場規則」。
- `wick/high-low trigger mode` 仍放後面，避免把策略從 close-confirmed 推向 intrabar 語意。
- `VWAP slope` 目前更適合留在 compare-first / optional refinement 的位置；除非後續第二份 intraday 樣本顯示它能穩定提供獨立資訊，否則不應再把更多主線 surface 配額用在它身上。
- `orb_vwap_slope_rule` 現在已改成靜態規則描述，enabled / disabled 狀態交由 `orb_vwap_slope_confirmation` 單獨表達。這次 wording cleanup 已確認只改善 artifact 可讀性，不改變 ORB runtime 行為或回測指標。
- `EMA trend` 雖然和 `VWAP slope` 同樣屬方向確認類條件，但在不少公開 ORB 腳本裡，EMA 更接近主方向確認或結構 gate，而不只是次要微調；因此目前不建議為了表面對稱，直接把它也標成和 `VWAP slope` 一樣的 `secondary_refinement`。若未來要擴 contract，較合理的是改走 `role/family`，把 `trend confirmation`、`structure gate`、`baseline choice` 分開。
- phase markdown 現在會在 `ORB Filter Attribution` 區塊明講：這裡只是一層 compact blocked/accepted summary；真正的 `state / tier / rule` metadata 仍以 entry-edge artifact 的 `strategy_spec` 為主。這能避免把 phase 報表誤讀成完整 ORB filter schema。
- 進一步用 `MSFT 5m demo` 比較 `EMA trend only`、`EMA inside-range only`、`EMA trend + EMA inside-range` 後，可以更明確地看到：`EMA inside-range` 是這個 EMA family 裡真正有主線價值的條件；`EMA trend` 單獨仍是 `FAIL`，而且疊加在 `EMA inside-range` 上還會把 PF 從 `4.452` 拉低到 `1.494`。因此目前不只不該補 `EMA trend` 的對稱 contract，還應避免把它誤當成同層且同等有效的 refinement。
