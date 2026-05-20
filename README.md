# SignalForge

SignalForge 是研究導向的交易訊號沙盒，用來把 TradingView / Pine Script 的策略想法拆成可驗證的 Python 研究流程。現在的主線是 Phase 工作流，可以在兩種模式之間切換：

- `backtest`：優先穩定性、可重複性與機械驗證。
- `live`：回測穩定前只允許 dry-run，不接 broker、不讀 API key、不送真實訂單。

## Live 安全邊界

`live` 模式目前只能產生 order intent，也就是乾跑用的下單意圖紀錄。以下條件必須永遠成立：

- `dry_run=True`
- `submitted=False`
- 不建立 broker 連線
- 不讀取 credential
- 不送出真實訂單

## 快速執行（PowerShell）

目前有兩個等價的命令列入口：

| 場景 | 呼叫方式 |
|---|---|
| 直接跑 source tree | 先設定 `$env:PYTHONPATH='src'`，再用 `python -m signal_forge.cli ...`。 |
| 安裝後使用 console script | 先跑 `python -m pip install -e .`，再用 `signal-forge ...`。 |

完整呼叫方式、subcommand 參數與 Python API 範例整理在 `docs\01-架構\SignalForge 呼叫程式方式.md`。

一般執行不需要把策略參數全部打出來。`entry-edge` 與 `phase` 會使用各策略自己的 default parameters；只有在比較同一策略的不同設定時，才覆寫 `--fast-window`、`--slow-window`、`--entry-z` 等參數。

| 策略 | Default parameters |
|---|---|
| `sma-crossover` | `fast_window=20`、`slow_window=200`、Phase 1 `allow_short=False`。 |
| `vwap-reversion` | `vwap_window=20`、`entry_z=1.5`、`exit_z=0.25`、`vwap_regime_filter=False`、`vwap_regime_window=50`、Phase 1 `allow_short=False`。 |
| `confluence-score` | `fast_window=20`、`slow_window=50`、`rsi_window=14`、`vwap_window=20`、`threshold=3.0`、Phase 1 `allow_short=False`。 |
| volume filter wrapper | 只有啟用 `--volume-filter` 時套用，預設 `volume_window=20`、`volume_multiplier=1.2`。 |

```powershell
# readiness metric
python tools\phase_readiness_score.py

# guard
$env:PYTHONPATH='src'
python -m unittest discover -s tests
git diff --check

# Download TWSE daily OHLCV into data/raw and data/processed
python -m signal_forge.cli fetch-data `
  --market twse `
  --symbol 2330 `
  --start 2024-01-01 `
  --end 2024-01-31

# Download US daily OHLCV from Stooq.
# Stooq currently requires a free API key for the CSV endpoint.
$env:STOOQ_API_KEY='<your-free-stooq-key>'
python -m signal_forge.cli fetch-data `
  --market us `
  --symbol AAPL `
  --start 2024-01-01 `
  --end 2024-01-31

# Phase backtest 範例
python -m signal_forge.cli phase `
  --csv data\sample\phase1_demo_ohlcv.csv `
  --mode backtest `
  --strategy sma-crossover `
  --output-dir reports\generated `
  --run-name phase-backtest-demo

# Entry-edge with optional relative-volume filter.
# Strategy and wrapper parameters use defaults unless explicitly overridden.
python -m signal_forge.cli entry-edge `
  --csv data\sample\phase1_demo_ohlcv.csv `
  --strategy sma-crossover `
  --volume-filter `
  --output-dir reports\generated `
  --run-name sma-volume-filter-demo

# Phase live dry-run 範例
python -m signal_forge.cli phase `
  --csv data\sample\phase1_demo_ohlcv.csv `
  --mode live `
  --strategy sma-crossover `
  --output-dir reports\generated `
  --run-name phase-live-demo

# Only override parameters when comparing variants of the same strategy
python -m signal_forge.cli entry-edge `
  --csv data\sample\phase1_demo_ohlcv.csv `
  --strategy sma-crossover `
  --fast-window 2 `
  --slow-window 3 `
  --output-dir reports\generated `
  --run-name sma-fast2-slow3-demo
```

## 簡單策略執行版：台積電 2330

下面是一個最短的台積電研究流程。第一次先下載 `2330` 日線資料；之後若 `data\processed\TWSE_2330_1D.csv` 已存在，可以直接從策略執行開始。

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
cd C:\Projects\signal-forge
$env:PYTHONPATH = "src"

# 1. 下載台積電日線 OHLCV
python -m signal_forge.cli fetch-data `
  --market twse `
  --symbol 2330 `
  --start 2024-01-01 `
  --end 2024-12-31

# 2. 用策略 default parameters 跑三個 entry-edge
python -m signal_forge.cli entry-edge `
  --csv data\processed\TWSE_2330_1D.csv `
  --strategy sma-crossover `
  --output-dir reports\generated `
  --run-name tsmc-sma-default

python -m signal_forge.cli entry-edge `
  --csv data\processed\TWSE_2330_1D.csv `
  --strategy vwap-reversion `
  --output-dir reports\generated `
  --run-name tsmc-vwap-default

python -m signal_forge.cli entry-edge `
  --csv data\processed\TWSE_2330_1D.csv `
  --strategy confluence-score `
  --output-dir reports\generated `
  --run-name tsmc-confluence-default
```

輸出會放在 `reports\generated\`，每個 run 會產生 markdown、summary JSON 與 trade log CSV。這些報表只是研究與回測稽核，不構成投資建議。

若要測同一策略不同參數，再覆寫參數即可：

```powershell
python -m signal_forge.cli entry-edge `
  --csv data\processed\TWSE_2330_1D.csv `
  --strategy sma-crossover `
  --fast-window 10 `
  --slow-window 60 `
  --output-dir reports\generated `
  --run-name tsmc-sma-10-60
```

## Phase 核心概念

- `PhaseConfig`：`backtest` / `live` 共用設定；`dry_run` 由 mode 推導，避免 CLI 與核心設定各自維護一份語意。
- `PhaseRunner`：依照 mode 路由到對應 execution adapter。
  - `BacktestExecutionAdapter`：透過 `EntryEdgeEvaluator` 產生可驗證的回測結果。
  - `LiveExecutionAdapter`：只產生 dry-run `OrderIntent`，不送出訂單。
- `OrderIntent`：live dry-run 的意圖紀錄；`safety_note` 會帶有 `LIVE_DRY_RUN_ONLY` 方便稽核。
- `VolumeFilteredStrategy`：可選策略 wrapper；啟用 `--volume-filter` 時，只有 `volume >= sma(volume, volume_window) * volume_multiplier` 的 positive target 會保留。預設不啟用，避免改變既有 regression contract。

## Autoresearch 筆記

- `docs/00-SignalForge 專案筆記索引.md`
- `docs/01-架構/SignalForge 架構總覽.md`
- `docs/02-規劃/SignalForge 大框架規劃.md`
- `docs/03-程式疊代/Phase 程式疊代紀錄.md`
- `docs/04-實驗記錄/Autoresearch 實驗記錄.md`
- `docs/策略筆記/策略筆記索引.md`

`docs/` 是 Obsidian 專案筆記的 repo 鏡像。筆記主來源是
`C:\Users\gary1\OneDrive\桌面\obsidian\project開發\SignalForge`；每次 push 前先從 Obsidian 同步回 `docs/`，再執行驗證、commit、push。

## 免費資料來源

- 台股：`fetch-data --market twse` 使用 TWSE 官方個股日成交資訊，輸出未調整日線 OHLCV。
- 美股：`fetch-data --market us` 使用 Stooq daily CSV。Stooq 單檔 CSV 端點目前要求免費 API key；沒有 key 時工具會中止並提示，不會產生空檔。
- 替代來源：Yahoo Finance / yfinance 與 Alpha Vantage 可作為後續 provider，但第一版不新增 Python dependency，也不要求交易 credential。
