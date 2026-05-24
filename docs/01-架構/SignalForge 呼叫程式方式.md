---
title: SignalForge 呼叫程式方式
tags:
  - project/SignalForge
  - architecture
  - cli
status: active
updated: 2026-05-23
aliases:
  - SignalForge CLI
  - SignalForge invocation
---

# SignalForge 呼叫程式方式

這份筆記整理目前可以怎麼呼叫 SignalForge 程式。SignalForge 目前仍是研究與回測工具；`live` 只允許 dry-run order intent，不接 broker、不讀 credential、不送真實訂單。

## PowerShell 前置設定

在 repo 內直接跑 source tree 時，先設定中文輸出與 package 路徑：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
cd C:\Projects\signal-forge
$env:PYTHONPATH = "src"
```

若已用 editable install 安裝過 package，也可以使用 `signal-forge` console script：

```powershell
cd C:\Projects\signal-forge
python -m pip install -e .
signal-forge --help
```

## 入口層級

| 場景 | 建議呼叫方式 | 用途 |
|---|---|---|
| 開發中直接跑 repo | `python -m signal_forge.cli <command> ...` | 不需要安裝 package，只要先設定 `$env:PYTHONPATH = "src"`。 |
| 安裝後給使用者或本機腳本跑 | `signal-forge <command> ...` | 由 `pyproject.toml` 的 `[project.scripts]` 指到 `signal_forge.cli:main`。 |
| Python 程式內呼叫 | `from signal_forge import ...` | 給 tests、notebook 或研究腳本直接使用 `PhaseRunner`、`EntryEdgeEvaluator`、策略 factory。 |
| 維護與驗證工具 | `python tools\phase_readiness_score.py`、`python -m unittest discover -s tests` | 不屬於產品 CLI，用於每輪 guard。 |
| 多股票研究工具 | `python tools\multi_stock_entry_edge_sweep.py ...` | 用同一個 common window 一次比較多檔股票、多個策略與多個固定持有期，避免只看單一標的 PF。 |
| 範例腳本 | `python examples\run_sample_backtest.py` | legacy `Backtester` demo，用來快速看三個內建策略的 toy backtest 輸出。 |

目前不要直接執行 `src\signal_forge\cli\__main__.py`。正式 CLI 入口是 module invocation 或 console script，才能維持 import path 與 parser contract 一致。

## CLI subcommands

`signal_forge.cli.parser.build_parser()` 目前定義三個 subcommand：

| Subcommand | 主要用途 | 核心輸入 | 主要輸出 |
|---|---|---|---|
| `fetch-data` | 下載免費日線 OHLCV 並轉成 SignalForge CSV。 | `--market twse|us`、`--symbol`、`--start`、`--end`。 | `data/raw`、`data/processed` CSV 與 manifest；命令列印出檔案路徑。 |
| `entry-edge` | 第一階段 long-only 固定持有期進場優勢稽核。 | `--csv`、策略參數、成本參數、`--hold-bars-per-day`，可選 `--hold-bars-list`。 | entry-edge markdown、summary JSON、trade log CSV；多持有期時另輸出 comparison JSON/Markdown。 |
| `phase` | 目前主工作流，依 mode 路由到 backtest 或 live dry-run。 | `--csv`、`--mode backtest|live`、策略參數、`--hold-bars-per-day`。 | Phase markdown、summary JSON；backtest 另寫 signals CSV 與 trace summary，live 只寫 dry-run order intents。 |

## 常用 CLI 範例

一般呼叫只需要指定資料、mode 與策略。策略參數會使用該策略自己的 default；只有在比較同一策略不同參數時，才加上 `--fast-window`、`--slow-window`、`--entry-z` 這類覆寫參數。

下載台股日線：

```powershell
python -m signal_forge.cli fetch-data `
  --market twse `
  --symbol 2330 `
  --start 2024-01-01 `
  --end 2024-01-31
```

跑 Phase backtest：

```powershell
python -m signal_forge.cli phase `
  --csv data\sample\phase1_demo_ohlcv.csv `
  --mode backtest `
  --strategy sma-crossover `
  --output-dir reports\generated `
  --run-name phase-backtest-demo
```

跑 Phase live dry-run：

```powershell
python -m signal_forge.cli phase `
  --csv data\sample\phase1_demo_ohlcv.csv `
  --mode live `
  --strategy sma-crossover `
  --output-dir reports\generated `
  --run-name phase-live-demo
```

跑 entry-edge 並比較多個固定持有期：

```powershell
python -m signal_forge.cli entry-edge `
  --csv data\sample\phase1_demo_ohlcv.csv `
  --strategy sma-crossover `
  --hold-bars-per-day 1 `
  --hold-bars-list 1,3,5,10 `
  --output-dir reports\generated `
  --run-name sma-hold-comparison-demo
```

啟用可選成交量濾網：

```powershell
python -m signal_forge.cli entry-edge `
  --csv data\sample\phase1_demo_ohlcv.csv `
  --strategy sma-crossover `
  --volume-filter `
  --output-dir reports\generated `
  --run-name sma-volume-filter-demo
```

啟用可選進場冷卻，避免接受 long entry 後短期內重複觸發新的 long entry：

```powershell
python -m signal_forge.cli entry-edge `
  --csv data\sample\phase1_demo_ohlcv.csv `
  --strategy confluence-score `
  --hold-bars-per-day 10 `
  --signal-cooldown-bars 10 `
  --output-dir reports\generated `
  --run-name confluence-cooldown-demo
```

啟用 VWAP Reversion regime filter：

```powershell
python -m signal_forge.cli entry-edge `
  --csv data\sample\phase1_demo_ohlcv.csv `
  --strategy vwap-reversion `
  --vwap-regime-filter `
  --output-dir reports\generated `
  --run-name vwap-regime-demo
```

若要比較同一策略的不同參數，再明確覆寫：

```powershell
python -m signal_forge.cli entry-edge `
  --csv data\sample\phase1_demo_ohlcv.csv `
  --strategy sma-crossover `
  --fast-window 2 `
  --slow-window 3 `
  --output-dir reports\generated `
  --run-name sma-fast2-slow3-demo
```

一次比較多檔台股與多個持有期：

```powershell
python tools\multi_stock_entry_edge_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --hold-bars-list 1,3,5,10 `
  --pass-profit-factor 1.5 `
  --signal-cooldown-bars 10
```

完整持倉 target-state 與 volatility target 風控 overlay：

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
  --volatility-min-observations 20
```

## 共用策略參數

`entry-edge` 與 `phase` 共用 `src\signal_forge\cli\strategy_options.py` 的策略參數。未輸入的欄位會交給 `src\signal_forge\strategies\registry.py` 使用各策略自己的 default，不再用單一全域預設硬套所有策略。

| 策略 | Default parameters |
|---|---|
| `sma-crossover` | `fast_window=20`、`slow_window=200`、Phase 1 `allow_short=False`。 |
| `vwap-reversion` | `vwap_window=20`、`entry_z=1.5`、`exit_z=0.25`、`vwap_regime_filter=False`、`vwap_regime_window=50`、Phase 1 `allow_short=False`。 |
| `confluence-score` | `fast_window=20`、`slow_window=50`、`rsi_window=14`、`vwap_window=20`、`threshold=3.0`、Phase 1 `allow_short=False`。 |
| volume filter wrapper | 只有啟用 `--volume-filter` 時套用，預設 `volume_window=20`、`volume_multiplier=1.2`。 |
| signal cooldown wrapper | 只有啟用 `--signal-cooldown-bars` 時套用，接受 long entry 後封鎖指定 bar 數內的新 long entry；不強制平倉既有持倉。 |
| volatility target wrapper | 只有 target-state 研究啟用 `--volatility-target` 時套用，預設只降曝險、不加槓桿。 |

| 參數 | 適用策略或用途 |
|---|---|
| `--strategy sma-crossover|vwap-reversion|confluence-score` | 選擇 Phase 1 long-only 策略。 |
| `--fast-window`、`--slow-window` | SMA Crossover 主要參數。 |
| `--vwap-window`、`--entry-z`、`--exit-z` | VWAP Reversion 主要參數。 |
| `--vwap-regime-filter`、`--vwap-regime-window` | VWAP Reversion 可選 entry-only regime filter。 |
| `--rsi-window`、`--threshold` | Confluence Score 主要參數。 |
| `--volume-filter`、`--volume-window`、`--volume-multiplier` | 可選外層成交量 wrapper；預設關閉。 |
| `--signal-cooldown-bars` | 可選外層進場冷卻 wrapper；正整數代表接受 long entry 後要封鎖幾根 bar 內的新 long entry。 |

## Python API 呼叫

CLI 以外，可以直接走 public API。這是 tests 或研究腳本比較適合的方式：

```python
from signal_forge import PhaseConfig, PhaseRunner, build_phase1_strategy, load_bars_from_csv

bars = load_bars_from_csv("data/sample/phase1_demo_ohlcv.csv")
strategy = build_phase1_strategy("sma-crossover")
result = PhaseRunner().run(
    PhaseConfig(
        mode="backtest",
        strategy="sma-crossover",
        csv_path="data/sample/phase1_demo_ohlcv.csv",
        hold_bars_per_day=1,
    ),
    strategy,
    bars,
)
```

API 呼叫時仍應優先使用 `PhaseRunner`、`EntryEdgeEvaluator` 與 `reporting` writer，不要在外部腳本重新實作 artifact schema。

## 固定驗證呼叫

每輪程式或文件調整後固定跑：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
cd C:\Projects\signal-forge
$env:PYTHONPATH = "src"
python tools\phase_readiness_score.py
python -m unittest discover -s tests
git diff --check
```

目前通過條件維持 readiness score `110`、unit tests 全部通過、`git diff --check` clean。
