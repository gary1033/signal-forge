# 第一期資料準備規格

SignalForge 第一期需要三類資料。目標是讓 TradingView 腳本蒸餾、K 棒資料與研究流程彼此分離，避免一開始就把資料源、語法轉換與回測判定混在一起。

## 1. 平台語法資料

每個策略至少保留：

- TradingView 來源 URL。
- 原始 Pine Script 文字。
- Pine 版本。
- 是否使用 `strategy.*` 或 `indicator.*`。
- 是否使用 `request.security`、pivot、realtime bar、lookahead 或其他可能 repaint 的功能。
- 原始預設參數。

第一期不直接搬 Pine Script，而是把它蒸餾成 SignalForge 的純多進場規格。

## 2. K 棒資料

CSV 欄位固定為：

```text
timestamp,open,high,low,close,volume
```

資料規則：

- `timestamp` 必須遞增且不可重複。
- `open/high/low/close` 必須為正數。
- `high` 不得低於 `open` 或 `close`。
- `low` 不得高於 `open` 或 `close`。
- `volume` 不得為負數。
- 原始資料放 `data/raw/`，清洗後資料放 `data/processed/`。
- 只有小型、可公開、可重現的 sample 才放 `data/sample/` 並納入 Git。

建議 manifest 欄位：

```json
{
  "symbol": "SPY",
  "timeframe": "1D",
  "timezone": "America/New_York",
  "session": "regular",
  "data_source": "manual export",
  "csv_path": "data/processed/SPY_1D.csv",
  "hold_bars_per_day": 1,
  "notes": "Describe adjustments, split handling, and missing data."
}
```

## 3. 策略研發流程架構

固定流程：

1. 收集 TradingView 原始腳本。
2. 填寫 `docs/phase1-strategy-intake-template.md`。
3. 將純多進場條件重寫成 `Strategy.generate_signals()`。
4. 準備 OHLCV CSV 與 manifest。
5. 執行 entry-edge CLI。
6. 檢查 Markdown report、JSON summary 與 trade log CSV。
7. `PF > 1.2` 才進入下一期；未通過則淘汰或回到策略假設整理。

PowerShell smoke test：

```powershell
cd C:\Projects\signal-forge
$env:PYTHONPATH = "src"
python -m signal_forge.cli entry-edge --csv data\sample\phase1_demo_ohlcv.csv --strategy sma-crossover --fast-window 2 --slow-window 3 --output-dir reports\generated --run-name phase1-demo
```
