---
title: SignalForge 呼叫程式方式
tags:
  - project/SignalForge
  - architecture
  - cli
status: active
updated: 2026-05-21
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
  --fast-window 2 `
  --slow-window 3 `
  --output-dir reports\generated `
  --run-name phase-backtest-demo
```

跑 Phase live dry-run：

```powershell
python -m signal_forge.cli phase `
  --csv data\sample\phase1_demo_ohlcv.csv `
  --mode live `
  --strategy sma-crossover `
  --fast-window 2 `
  --slow-window 3 `
  --output-dir reports\generated `
  --run-name phase-live-demo
```

跑 entry-edge 並比較多個固定持有期：

```powershell
python -m signal_forge.cli entry-edge `
  --csv data\sample\phase1_demo_ohlcv.csv `
  --strategy sma-crossover `
  --fast-window 2 `
  --slow-window 3 `
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
  --fast-window 2 `
  --slow-window 3 `
  --volume-filter `
  --volume-window 20 `
  --volume-multiplier 1.2 `
  --output-dir reports\generated `
  --run-name sma-volume-filter-demo
```

啟用 VWAP Reversion regime filter：

```powershell
python -m signal_forge.cli entry-edge `
  --csv data\sample\phase1_demo_ohlcv.csv `
  --strategy vwap-reversion `
  --vwap-window 20 `
  --entry-z 1.5 `
  --exit-z 0.25 `
  --vwap-regime-filter `
  --vwap-regime-window 50 `
  --output-dir reports\generated `
  --run-name vwap-regime-demo
```

## 共用策略參數

`entry-edge` 與 `phase` 共用 `src\signal_forge\cli\strategy_options.py` 的策略參數：

| 參數 | 適用策略或用途 |
|---|---|
| `--strategy sma-crossover|vwap-reversion|confluence-score` | 選擇 Phase 1 long-only 策略。 |
| `--fast-window`、`--slow-window` | SMA Crossover 主要參數。 |
| `--vwap-window`、`--entry-z`、`--exit-z` | VWAP Reversion 主要參數。 |
| `--vwap-regime-filter`、`--vwap-regime-window` | VWAP Reversion 可選 entry-only regime filter。 |
| `--rsi-window`、`--threshold` | Confluence Score 主要參數。 |
| `--volume-filter`、`--volume-window`、`--volume-multiplier` | 可選外層成交量 wrapper；預設關閉。 |

## Python API 呼叫

CLI 以外，可以直接走 public API。這是 tests 或研究腳本比較適合的方式：

```python
from signal_forge import PhaseConfig, PhaseRunner, build_phase1_strategy, load_bars_from_csv

bars = load_bars_from_csv("data/sample/phase1_demo_ohlcv.csv")
strategy = build_phase1_strategy("sma-crossover", fast_window=2, slow_window=3)
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
