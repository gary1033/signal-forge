# SignalForge

SignalForge 是一個把 TradingView 開源 Pine Script 想法轉成可驗證量化研究流程的 Python 專案。

這個 repo 的第一階段目標不是自動下單，而是建立一個乾淨的研究工作台：

- 把 TradingView 腳本拆成 `signal`、`filter`、`risk rule`、`exit rule`。
- 用 Python 重寫成可測試策略。
- 用同一個回測器比較不同策略想法。
- 先跑 baseline，再逐步加入多商品、多時間框架、成本、滑價、out-of-sample 與 walk-forward。

> 本專案只做研究與工程驗證，不構成投資建議。

## 第一版內容

- `SmaCrossoverStrategy`：20/200 SMA 趨勢 baseline。
- `VwapReversionStrategy`：VWAP 均值回歸策略雛形。
- `ConfluenceScoreStrategy`：多因子打分策略雛形。
- `Backtester`：標準函式庫實作的簡單 close-to-close 回測器。
- `EntryEdgeEvaluator`：第一期專用的純多進場優勢驗證器。
- `python -m signal_forge.cli entry-edge`：從 OHLCV CSV 產出 Markdown、JSON、trade log。
- `examples/run_sample_backtest.py`：用合成資料跑三個策略。
- `tests/`：指標、策略與回測器的基本測試。

## 快速開始

PowerShell：

```powershell
cd C:\Projects\signal-forge
$env:PYTHONPATH = "src"
python -m unittest discover -s tests
python examples\run_sample_backtest.py
python -m signal_forge.cli entry-edge --csv data\sample\phase1_demo_ohlcv.csv --strategy sma-crossover --fast-window 2 --slow-window 3 --output-dir reports\generated --run-name phase1-demo
```

`reports/generated/` 會輸出：

- `phase1-demo.md`：研究報告與 pass/fail 結論。
- `phase1-demo.json`：machine-readable summary。
- `phase1-demo_trades.csv`：逐筆固定持有交易紀錄。

## 第一期研究流程

第一期只回答一個問題：蒸餾後的純多進場訊號，在「下一根 bar 進場、固定持有 1 天」的條件下，是否有足夠進場優勢。

驗收口徑：

- TradingView Pine Script 只作為策略來源；不直接搬運成 Python。
- 只抽取純多進場條件；short、停損、停利、濾網、加碼與出場邏輯先記錄但不納入第一期。
- 資料先使用本地 OHLCV CSV，不接外部 API。
- CSV 欄位固定為 `timestamp,open,high,low,close,volume`。
- 訊號於 bar close 後成立，下一根 bar open 進場，固定持有 `hold_bars_per_day` 後以 exit bar close 出場。
- Profit Factor 使用扣除手續費與滑價後的 closed trade PnL。
- `PF > 1.2` 才通過第一關；沒有 closed trade 直接淘汰；沒有虧損交易時會標示樣本風險。

相關模板：

- `docs/phase1-data-preparation.md`
- `docs/phase1-strategy-intake-template.md`

## 專案路線

1. **策略想法收集**
   - 從 TradingView 開源腳本整理策略類型：均線趨勢、VWAP、RSI/divergence、order block、多因子共振、價格密度等。

2. **策略拆解**
   - 每個腳本先拆成資料需求、訊號條件、過濾條件、出場條件、風控條件。

3. **Python 重寫**
   - 不直接搬 Pine Script，而是保留交易想法，重寫成可測、可比較、可替換的 Python 模組。

4. **驗證擴充**
   - 加入交易成本、滑價、不同商品、不同時間框架、out-of-sample、walk-forward。

5. **研究報告**
   - 每個策略輸出 metrics、equity curve、trade log 與白話結論。

## 目前限制

- 回測器是第一版簡化模型，使用 close-to-close 報酬與 target exposure，不模擬真實掛單成交。
- 第一批真實資料需手動放入 `data/raw/` 或整理成 `data/processed/`；這兩個資料夾不納入 Git。
- 尚未加入 pandas/vectorbt/backtrader，避免第一版依賴膨脹。
