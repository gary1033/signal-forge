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
- 若要把這個策略用在台積電 `2330` 的 regular-session 研究，market-clock metadata 應改成 `Asia/Taipei 09:00-13:30`，而不是沿用美股預設；目前 repo 已有一份手動匯入的台積電 intraday 檔 `C:\Projects\signal-forge\data\processed\TWSE_2330_5M.csv` 可供這種研究使用。
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
- 若要把 ORB 研究往下一個 family 推進，較合理的方向不是再堆同日內部 refinement，而是研究 `previous day high/low`、`gap direction/fill`、`overnight range` 這類前日 / higher-timeframe 結構脈絡。不過這一類條件會直接牽涉 previous-day 邊界定義與 higher-timeframe 資料處理，因此現階段更適合先列為研究題，而不是直接做成下一個夜間執行輪。
- phase markdown 的 `ORB Filter Attribution` 現在也會明講：目前報表只覆蓋同 session 的 compact blocked/accepted summary，`previous day high/low`、gap、overnight range 這類前日 / higher-timeframe context 仍在現有 ORB contract 外，直到那個 family 被明確定義。
- 針對這個 phase markdown 邊界提示，已用同一份 `MSFT 5m demo` 的 `EMA inside-range` 版本重新驗證：PF `4.452`、Trades `13`、blocked `1754`、hold `873` 都和修補前一致，表示這次改動只提升報表可讀性，不改變 ORB runtime 行為。
- 若未來真的要替 ORB 落第一個 previous-day family 條件，較低風險的第一刀應優先考慮 `prior-day close / gap bias`，而不是直接上 `PDH/PDL + premarket`。原因是 `prior-day close` 只需要一個前日 scalar，較接近目前 optional filter 的工程形狀；相對地，`PDH/PDL + premarket` 會同時打開 regular/full-session 邊界、premarket 定義、`request.security` 對齊，以及多條前日線的 artifact 表示問題。
- 進一步把 `MSFT 5m demo` 的第一個 session 拿掉後（模擬「先不讓沒有 in-sample prior close 的第一天影響結論」），`EMA inside-range` 主線仍維持 `PASS`，而且 PF 從 `4.452` 升到 `6.423`。這表示目前唯一的 5m 樣本，還不足以支持「應該立刻把 prior-day family 落進 ORB contract」；更合理的下一步仍是先補第二份 intraday 樣本與 prior-close 邊界定義。
- 若未來真的要讓 `prior-day close / gap bias` 落第一刀，最小資料邊界應先固定成：`prior_day_close_regular_session = 前一個已完成 regular session 的最後確認 close`。它必須和 ORB 現有的 `session start / end / timezone` 屬於同一套 market-clock 定義，且在資料集第一個沒有 prior close 的 session 上明確標成 unavailable，而不是補值或偷用當日資料。
- 工程上，repo 現在不只用文件與 regression 說明這個邊界，還在 `strategy_spec` 建構點加了 same-session contract validator：任何 `orb_previous_day_*`、`orb_gap_*`、`orb_overnight_*` 類欄位若在 previous-day family 尚未正式定義前混入 ORB surface，都應視為 contract drift，而不是正常擴充。
- 目前 repo 已有兩份真正可供 ORB 使用的 intraday processed 樣本：`ALPHAVANTAGE_MSFT_5M_demo.csv` 與手動匯入的 `TWSE_2330_5M.csv`。`TWSE_2330_1D.csv` 屬日線資料，`phase1_demo_ohlcv.csv` 屬 fixture 性質示範資料，兩者都不應被視為 ORB intraday 驗證樣本。
- 因此，現階段還不能把 `prior-day close / gap bias` 視為已具備跨樣本證據支持的下一刀；更合理的順序仍是先補第二份獨立 intraday 樣本，再決定 previous-day family 是否值得真正落地。
- 若未來真的要讓 previous-day family 進入 ORB，第一個正面 contract 應優先是單一 scalar `prior_day_close_regular_session`，而不是直接展開成 `PDH/PDL/gap/overnight` 一整組 surface。它至少要綁住三件事：來源是前一個已完成 regular session、值必須是 confirmed close、資料集第一個沒有 prior close 的 session 必須明確標成 unavailable。
- 工程上，這個 previous-day family 的第一個落地動作也不應直接是 gap-bias filter，而應先把 `prior_day_close_regular_session` 的最小 validator contract 寫成可測試 helper：來源固定 `regular_session`、timezone 對齊 `orb_session_timezone`、availability 只允許 `available | unavailable_first_session`、fill policy 固定 `no_forward_fill`，而且 `unavailable_first_session` 時不得再偷放數值。
- 進一步把這個 helper 與現有 ORB 主線重新比對後，可以確認它目前仍是純 contract guard，不會改變 `EMA inside-range` 主線的 PF、交易數、blocked reasons 或 same-session artifact surface。也就是說，repo 現在多的是「未來 previous-day family 該遵守什麼邊界」，不是「今天已經把 previous-day 語意接進 ORB」。
- 進一步把 `EMA inside-range` 主線拿去對照 repo 目前兩份 intraday 樣本後，可以看到它不是跨樣本穩定的普適條件：在 `MSFT 5m demo` 上，hold 1 版本是明確 `PASS`（PF `4.452`）；但在 `TWSE_2330_5M` 上，hold 1 / 3 / 5 / 10 全部 `FAIL`，最佳的 hold 10 也只有 PF `0.927`。
- 這個結果也不能被誤讀成「`EMA inside-range` 沒用」。從 trace summary 看，`TWSE_2330_5M` 被 `ema_inside_opening_range` 擋掉的次數只有 `86`，比 `MSFT 5m demo` 的 `126` 還少；也就是說，2330 的失敗不是因為這條 gate 太嚴，而是放行後的突破品質本身較差。
- 因此目前更合理的結論是：`EMA inside-range` 對現有美股 sample 有主線價值，但不能直接升格成 market-agnostic invariant；若要對台股樣本做更公平的比較，下一步應先把 ORB 的 market-clock 明確切到 `Asia/Taipei 09:00-13:30`，而不是直接堆更多 filter 或把 attention 轉去 previous-day family。
- 進一步回頭看公開 ORB 腳本，這個排序其實很合理：像 `SessionVWAP + ORB`、`ORB Multi Preset` 這類多市場腳本，第一步通常不是先增加 breakout refinement，而是先把各市場自己的 session、open time 與 timezone 拉成顯式設定。這代表對目前 SignalForge 來說，`TWSE_2330_5M` 的下一步也應優先是 market-clock 對齊，而不是直接往 previous-day family 或更多 filter 擴張。
- 因此目前 ORB artifact 也開始補這層 sample-aware metadata：對已知的 `TWSE_2330_5M.csv`，artifact 會直接寫出它預期的 `Asia/Taipei 09:00-13:30` market-clock，並標示這次 run 是 `aligned` 還是 `mismatch`。這樣後續比較台股結果時，不必再先翻研究筆記才能知道這次是不是沿用了錯的 market-clock。
- 進一步把 `TWSE_2330_5M` 做 `mismatch vs aligned` A/B 後，可以確認 market-clock 對齊是必要修正：hold 1 的 PF 會從 `0.083` 拉到 `0.513`，hold 3 從 `0.236` 拉到 `0.538`，hold 5 從 `0.248` 拉到 `0.685`。但它仍然沒有翻成 `PASS`，代表台股樣本的弱表現不是只有時鐘錯位，這條 ORB 主線本身對台股 regular session 的相容性也仍偏弱。
- 因此目前更合理的做法是：把 `Asia/Taipei 09:00-13:30` 視為台股 ORB 的 canonical 基線，之後若還要比較 `EMA inside-range` 或其他 refinement，都應建立在這個 aligned 版本之上；不要再拿 `mismatch` 版結果去推導新的 previous-day family。
- 從公開 ORB 腳本的 UI 慣例來看，跨市場版本通常不只允許設定 session / timezone，還會把 **active preset / active market-clock** 直接顯示給使用者看。這表示對 SignalForge 而言，下一個較合理的小改動不是再堆 filter，而是讓 artifact / reporting 更明白地提示：`TWSE_2330_5M` 的 canonical baseline 是 `Asia/Taipei 09:00-13:30 aligned`。
- repo 現在已把這個提示往前推進到 artifact：對已知的 `TWSE_2330_5M.csv`，`strategy_spec` 會固定補一行 `orb_known_sample_market_clock_baseline_note`，直接說明台股 ORB 的 canonical baseline 與本次 run 的 aligned / mismatch 狀態。
- 目前這個 baseline 提示又再往前推進一層：只要 entry-edge 報表帶有這組 known-sample metadata，markdown 會在 `Strategy Spec (Distilled)` 之前先輸出 `## Known Sample Baseline` 區塊，直接列出 canonical baseline note、當前 aligned / mismatch 狀態，以及預期的 `Asia/Taipei 09:00-13:30` market clock。這樣台股樣本的主結論不必再靠後段 spec key 才能讀懂。

## 台股 aligned baseline 上的次要 refinement 結論

以 `TWSE_2330_5M.csv` 的 canonical baseline `Asia/Taipei 09:00-13:30 aligned` 重新比較後，可以先固定一個很直接的結論：

- `EMA inside-range` 仍然是這條 ORB 主線在台股樣本上的主要結構 gate。
- `VWAP slope confirmation` 在這份樣本上沒有新增資訊。

具體來說，以下兩組在 `hold 1 / 3 / 5 / 10` 的回測結果完全相同：

1. `ORB + Volume + VWAP + EMA inside-range`
2. `ORB + Volume + VWAP + EMA inside-range + VWAP slope`

這代表在 `TWSE_2330_5M aligned` 上，`VWAP slope` 目前不是「弱但有幫助」的次要 refinement，而是**零增量 refinement**。它沒有增加新的 blocked reason，也沒有改變 accepted / blocked / hold 分布；因此若後續要繼續研究台股 ORB，優先順序不應再放在 `VWAP slope`，而應轉向：

- 其他更有機會補到市場差異的 refinement；
- 或直接承認現有 ORB 主線對台股 regular session 的適配度有限。

換句話說，`VWAP slope` 目前仍可保留在美股樣本的 compare-only 位置，但不應再被當成台股 baseline 上值得優先討論的主題。

## 台股 baseline 的提示方式

針對 `TWSE_2330_5M.csv` 這類已知有 canonical market-clock 的樣本，公開 ORB 腳本比較常見的做法，不是直接阻止使用者執行，而是把 **active market / session / timezone** 顯示得非常清楚。

這對目前的 ORB 主線有兩個直接含義：

1. `TWSE_2330_5M` 的 canonical baseline 仍應固定是 `Asia/Taipei 09:00-13:30 aligned`。
2. 下一步若要繼續補工程邊界，較合理的是讓 artifact / reporting 更顯眼地提示這件事，而不是直接把 `mismatch` run 變成不可執行。

原因是 `mismatch` run 仍有研究價值：它能幫助我們理解 market-clock 是否扭曲結果；但正式比較與結論應明確站在 aligned baseline 上。

## 台股 aligned baseline 上的 OR average volume baseline

把 `TWSE_2330_5M.csv` 固定在 `Asia/Taipei 09:00-13:30 aligned` baseline 後，再比較：

1. `ORB + EMA inside-range`
2. `ORB + EMA inside-range + OR average volume baseline`

可以先固定一個和 `VWAP slope` 不同的結論：

- `OR average volume baseline` **不是零增量 refinement**。
- 它會明顯壓縮交易數，並改善最短持有期的品質：
  - hold 1 PF：`0.513 -> 0.948`
  - trades：`21 -> 12`
  - average net PnL：`-7.47 -> -0.60`
  - max drawdown：`-2.88% -> -1.16%`

但這個改善沒有跨 hold 穩定：

- hold 3 PF：`0.538 -> 0.369`
- hold 5 PF：`0.685 -> 0.406`
- hold 10 PF：`0.309 -> 0.268`

而且它改變的主因不是新的 OR 結構資訊：

- `ema_inside_opening_range` 維持 `86` 不變
- `breakout_volume_blocked` 從 `80` 升到 `231`

這代表 `OR average volume baseline` 在台股 aligned baseline 上，比較像一個 **trade-compression refinement**：

- 它會更嚴格地壓掉量能不足的突破；
- 對最短持有期有幫助；
- 但會犧牲後續多持有期的穩定性。

所以它和 `VWAP slope` 的定位不同：

- `VWAP slope` 在台股樣本上是零增量；
- `OR average volume baseline` 則是**有資訊、但帶明顯 tradeoff** 的市場特化 refinement 候選。

## 台股樣本上的下一個優先研究方向

針對 `TWSE_2330_5M` 的 `Asia/Taipei 09:00-13:30 aligned` baseline，目前較合理的下一個 refinement，不是直接跳去 previous-day family，而是先看 **OR retest / re-break confirmation**。

原因很直接：

- 台股樣本目前暴露的問題，比較像「第一次突破後 follow-through 不夠穩」；
- `VWAP slope` 在這份樣本上是零增量；
- `OR average volume baseline` 雖然有資訊，但更像透過量能把交易壓少，主要只改善最短持有期。

相較之下，`OR retest / re-break confirmation` 的研究價值在於：

1. 它是**同 session 內的價格結構確認**，不需要先把 previous-day / higher-timeframe data 拉進來。
2. 它對應的是「突破後回測 OR 高點/低點，再重新站回去才算有效」，這比單純加嚴量能更接近 follow-through 本身。
3. 工程上它也比較適合目前 SignalForge 的 deterministic 邊界，因為只要維持 confirmed-bar-only 與既有 session contract，就能先做出可驗證版本。

這不代表 retest confirmation 一定會把台股 ORB 直接翻成 `PASS`；它同樣可能只是另一種 trade-compression refinement。但以目前研究排序來看，它比 previous-day family 更適合作為下一個台股 market-specific refinement 候選。

## OR retest / re-break confirmation 的目前工程邊界

目前 `OR retest / re-break confirmation` 還不是已證明有效的台股主線條件，但它已先被收斂成可測試的研究 contract：

- 只允許 **同 session** 內判定
- 只接受 **confirmed bar close** 後的 reclaim
- level reference 固定是 **opening range high reclaim**
- 目前不混入 previous-day / higher-timeframe data

這個邊界的意義是：後續若真的把它拿去和 `TWSE_2330_5M aligned baseline` 比較，我們先能保證測的不是一個混了 premarket、prior-day 或 intrabar probe 的模糊版本，而是一個比較乾淨、可重複的 OR 結構確認假設。

## 台股樣本上的 OR retest / re-break confirmation

把 `OR retest / re-break confirmation` 放到 `TWSE_2330_5M` 的 `Asia/Taipei 09:00-13:30 aligned` baseline 後，可以先固定一個很直接的結論：

- 它**不是零增量 refinement**，因為它會新增 `retest_not_touched`、`waiting_for_retest_confirmation` 這類結構性 blocked reason。
- 但它目前整體表現仍弱於 `OR average volume baseline`。

具體來說：

- hold 1 PF：`0.513 -> 0.282`，比 baseline 更差。
- hold 3 PF：`0.538 -> 0.542`，只有很小的持平改善，但 trades 從 `21` 壓到 `9`。
- hold 5 / 10：都比 baseline 更差。

這代表 `OR retest / re-break confirmation` 在台股樣本上的角色，比較像：

- 有資訊的價格結構確認；
- 但目前偏向**過度壓縮**，還不足以成為比 `OR average volume baseline` 更合理的下一個主線改善方向。

因此目前較合理的定位是：**台股 compare-only structure refinement 候選**。後續若要測新的台股 refinement，應優先拿它對照 `aligned baseline` 與 `OR average volume baseline`，而不是把 retest 本身再升成主要研究軸。

## 公開 ORB 腳本對 retest 的常見定位

從公開 ORB 腳本的做法來看，`retest / re-break confirmation` 更常被放在：

- 可切換的 entry style
- 或較保守的 confirmation mode

而不是 baseline 主線本身。

這個觀察和目前台股樣本的結果是對齊的：

- `OR retest` 在 `TWSE_2330_5M aligned` 上確實有新資訊；
- 但它更像一種偏保守、偏壓縮交易數的結構確認；
- 因此目前較合理的角色不是主線改善，而是 compare-only entry style 候選。

也就是說，後續若還要研究新的台股 refinement，`OR retest` 比較像用來做風格對照，而不是拿來取代 `aligned baseline` 或 `OR average volume baseline` 的主要比較地位。

## 台股報表目前的 benchmark 解讀順序

在 `TWSE_2330_5M` 這個台股樣本上，entry-edge 報表現在應該固定用同一個順序解讀：

1. 先確認是否為 `Asia/Taipei 09:00-13:30 aligned` baseline。
2. 若是台股 market-specific refinement，比較時先對照 aligned baseline。
3. 再對照 `OR average volume baseline`，因為它目前是最有資訊的台股 benchmark。
4. `OR retest / re-break confirmation` 則先停在 compare-only entry style 候選，不應和 baseline 或 benchmark 放在同一優先級。

這個排序的作用不是宣告哪個條件已經夠好可以上主線，而是避免後續閱讀台股報表時，把不同層級的 refinement 混成同一種訊號：

- `aligned baseline`：主比較基準
- `OR average volume baseline`：有資訊、但帶明顯 tradeoff 的 benchmark
- `OR retest`：偏保守、偏壓縮交易數的 style 候選

## Full bar above range 在台股樣本上的角色

在 `TWSE_2330_5M` 的 `Asia/Taipei 09:00-13:30 aligned` baseline 上，`full bar above range` 目前是更強的結構 refinement 候選。

它的重點不只是把交易數壓少，而是要求突破 K 棒的 **low 也必須站在 OR high 上方**，避免那種收盤雖然突破，但整根 K 棒仍明顯回插到 opening range 盒子內的情況。

目前觀察到的結果是：

- hold 1 已經直接翻成 `PASS`
- hold 5 / 10 雖然還沒 pass，但比純 aligned baseline 與 `OR average volume baseline` 都穩
- 新增的主要 blocked reason 是 `breakout_bar_reentered_range`，代表它更像在處理 follow-through 結構，而不是單純量能壓縮

因此在台股這條線上，現在較合理的優先級應該改成：

1. `aligned baseline`
2. `full bar above range` 作為目前最強的結構 refinement 候選
3. `OR average volume baseline` 作為次一層的 trade-compression benchmark
4. `OR retest` 作為 compare-only entry style 候選

這個排序仍然不表示 `full bar above range` 已經足夠升成所有台股 ORB 的正式主線；它只是目前在既有同 session refinement 裡，給出最好 hold 1 結果、且對較長 hold 也沒有明顯崩掉的候選。

## 公開 ORB 腳本對 full bar / close-confirmation 的常見定位

從公開 ORB 腳本的設計來看，`full bar above range` 這類條件更常被放在：

- breakout qualification
- 或 breakout confirmation mode

而不是單純的 volume 替代 filter。

這類腳本常見的共同點是：

1. 不再接受單純 touch OR high / low 就算突破。
2. 改要求 `body cross`、`close cross`、或整根 K 棒明確站在 breakout 邊界外。
3. 若採更嚴格確認，通常是為了減少假突破，而不是單純把交易數壓少。

這和 `TWSE_2330_5M aligned` 的觀察一致：

- `full bar above range` 的關鍵 blocked reason 是 `breakout_bar_reentered_range`
- 它主要在過濾突破後又掉回 OR 盒子內的弱 follow-through
- 因此它比較像結構確認，不像 `OR average volume baseline` 那樣更偏 trade compression

所以目前較合理的台股 ORB 解讀順序應是：

1. `aligned baseline`
2. `full bar above range` 作為高優先級 breakout qualification / benchmark
3. `OR average volume baseline` 作為次層 trade-compression benchmark
4. `OR retest` 作為 compare-only entry style

目前 entry-edge 報表也應跟著用同一個順序提示：

- `full bar above range`：primary structural benchmark
- `OR average volume baseline`：secondary trade-compression benchmark
- `OR retest`：compare-only entry style

這樣後續在台股樣本上看 refinement，比較不會再把 volume baseline 誤讀成第一順位 benchmark。
