---
title: SMA Crossover
tags:
  - project/SignalForge
  - trading/strategy
  - trading/trend
status: research
updated: 2026-05-21
repo_impl: C:\Projects\signal-forge\src\signal_forge\strategies\sma_crossover.py
---

# SMA Crossover

## 先懂這些詞

- **Close / 收盤價**：一天交易結束後的最後成交價格。這個策略只用收盤價算均線。
- **SMA（Simple Moving Average，簡單移動平均）**：把最近 N 天收盤價加總後除以 N。例如 20 日 SMA 就是最近 20 天平均收盤價。它用來把每天價格的雜訊變平滑。
- **Fast SMA / 快線**：天數比較短的 SMA，例如 20 日。它反應比較快，比較貼近近期價格。
- **Slow SMA / 慢線**：天數比較長的 SMA，例如 200 日。它反應比較慢，用來代表較長期趨勢。
- **Crossover / 交叉**：快線和慢線的位置發生改變。快線從慢線下方跑到上方，叫上穿；快線從慢線上方跌回下方，叫下穿。
- **Long-only / 只做多**：策略只允許買進持有或空手，不做放空。SignalForge CLI 目前就是這個設定。
- **`target_position` / 目標部位**：策略想要的持倉狀態。`1.0` 代表應該持有多單，`0.0` 代表空手，`-1.0` 代表做空；這份筆記只看 `1.0` 和 `0.0`。
- **Warmup / 暖機期**：資料還不夠算均線的期間。例如 200 日 SMA 至少要等到有 200 筆收盤價才算得出來。
- **相對成交量 / Relative volume**：把今天成交量和近期平均量比較。SignalForge 可選成交量過濾器使用 `volume >= sma(volume, 20) * 1.2` 判斷量能是否足夠。

## 策略假設

SMA Crossover 是趨勢追蹤 baseline。它假設短期平均價格高於長期平均價格時，市場進入偏多趨勢；短期平均低於長期平均時，趨勢不足，long-only 模式下應回到空手。

這個策略適合作為研究基準，因為訊號簡單、可解釋、容易跨標的比較。但它本質上偏向中長期趨勢辨識，不一定適合只用隔日固定持有的 entry-edge 方法評估。

## 進出場條件

先分清楚兩件事：

1. **策略訊號**：每天收盤後，用當天以前的收盤價計算 `fast_sma` 與 `slow_sma`，決定明天應該是「持有多單」還是「空手」。
2. **entry-edge 回測**：只抓「從空手變成持有」的那一刻當作進場訊號，下一根 K 棒開盤買進，固定持有 `hold_bars_per_day` 後賣出。

白話規則：

- 還沒有足夠資料算均線時，不交易。這叫 `warmup`。
- 快線在慢線下方或等於慢線時，不交易，保持空手。
- 快線從慢線下方轉到慢線上方後，代表短期趨勢轉強，策略切成「應該持有多單」。
- 只要快線仍然高於慢線，策略狀態就是繼續持有多單，不是每天都重新進場。
- 快線重新跌回慢線下方或等於慢線時，策略狀態回到空手。若是完整持倉策略，這裡會視為離場；但目前 `entry-edge` 第一階段主要評估進場點，不是完整持倉系統。

| 今天收盤後看到的狀態 | `target_position` | 意思 | reason |
|---|---:|---|---|
| 均線還算不出來 | `0.0` | 資料不足，空手 | `warmup` |
| `fast_sma > slow_sma` | `1.0` | 應該持有多單 | `fast_sma_above_slow_sma` |
| `fast_sma <= slow_sma` | `0.0` | long-only 模式下空手 | `fast_sma_below_slow_sma_flat` |

真正的「進場」不是單純看到 `fast_sma > slow_sma`，而是看到狀態從 `0.0` 變成 `1.0`：

```text
昨天 target_position = 0.0
今天 fast_sma > slow_sma，所以今天 target_position = 1.0
=> 今天收盤後出現 entry signal
=> entry-edge 回測在下一根 K 棒 open 進場
```

真正的「離場」在完整策略語意上是狀態從 `1.0` 變回 `0.0`：

```text
昨天 target_position = 1.0
今天 fast_sma <= slow_sma，所以今天 target_position = 0.0
=> 趨勢條件消失，策略回到空手
```

但要注意：目前 SignalForge 的第一階段 `entry-edge` 不是完整出場策略。它會在 entry signal 出現後，用固定規則測「下一根 open 進場，持有 N 根 bar，exit bar close 出場」。所以這份回測結果是在問「這個交叉進場點隔日有沒有優勢」，不是在問「完整 SMA 趨勢持有系統能不能賺錢」。

## 小例子

假設使用比較短的教學參數 `fast_window=2`、`slow_window=3`，方便看懂。真實預設是 `20/200`。

| Day | Close | Fast SMA | Slow SMA | 狀態 | 動作解讀 |
|---:|---:|---:|---:|---|---|
| 1 | 10 | - | - | warmup | 資料不足，不交易 |
| 2 | 11 | 10.5 | - | warmup | 慢線還算不出來 |
| 3 | 12 | 11.5 | 11.0 | `target=1.0` | 第一次快線高於慢線，出現 entry signal |
| 4 | 13 | 12.5 | 12.0 | `target=1.0` | 繼續持有，不是新進場 |
| 5 | 11 | 12.0 | 12.0 | `target=0.0` | 快線不再高於慢線，回到空手 |
| 6 | 10 | 10.5 | 11.3 | `target=0.0` | 繼續空手 |

用一句話記：**快線上穿慢線是進場點；快線仍在慢線上方是持有；快線跌回慢線下方或等於慢線是離場/空手。**

程式本身支援 `allow_short=True` 時轉成 `target_position=-1.0`，但目前 CLI 建構策略時固定使用 `allow_short=False`，所以這份筆記只討論做多與空手。

可選的成交量過濾器不是 SMA Crossover 本體，而是外層 wrapper。啟用 `--volume-filter` 時，原策略仍先判斷 `fast_sma > slow_sma`；若原策略輸出 positive target，但當日成交量未達 `20` 日均量的 `1.2` 倍，wrapper 會把 target 改成 `0.0`。

## 主要參數

- `fast_window`：預設 `20`。
- `slow_window`：預設 `200`。
- `allow_short`：實作預設支援，但 CLI 目前固定 `False`。
- 可選成交量過濾器：CLI 使用 `--volume-filter --volume-window 20 --volume-multiplier 1.2`，實作位置是 `C:\Projects\signal-forge\src\signal_forge\strategies\volume_filter.py`。
- entry-edge 評估：訊號於 bar close 後確認，下一根 open 進場，固定持有 `hold_bars_per_day=1` 後以 exit bar close 出場。
- 多持有期比較：CLI 可用 `--hold-bars-list 1,3,5,10` 產生同一策略在不同固定持有期下的 comparison JSON/Markdown。這是評估工具，不會改變 SMA 訊號，也不會自動挑最佳參數。

## 股價走勢解說圖

![[assets/sma-crossover-trend-explainer.png]]

圖中用合成走勢說明：灰色區域代表 warmup / 空手階段；藍色快速均線上穿橘色慢速均線後，策略才把狀態切成 long entry。此圖為 image generation 產生的教學示意圖，不是真實市場資料，也不代表績效保證。

## 風險與限制

- 盤整市場容易來回洗訊號。
- 進場通常較慢，會犧牲初段行情。
- 固定 `20/200` 不一定適合所有標的。
- 若把成交量過濾器套成 target-state filter，低量日會讓 target 回到空手，可能把原本的趨勢持有狀態切成許多短期進出。
- 用一日 entry-edge 評估可能低估中長期趨勢策略的用途。
- 目前不含停損、停利、部位管理、regime filter 或成本敏感度分析。

## 下一步

- `2330` 的 `hold=3`、`hold=5`、`hold=10` 已經顯示這個策略明顯不是一日 edge；下一步應把它當成 Phase 2 趨勢持有候選，而不是繼續只看隔日 entry-edge。
- 優先比較 `hold=3` 與 `hold=5` 哪一種更符合「報酬改善但回撤仍可接受」的趨勢持有語意。
- 比較 entry-only volume filter 與 target-state volume filter，確認哪一種比較符合趨勢策略語意。
- 檢查不同標的與不同 market regime 下的表現差異。
