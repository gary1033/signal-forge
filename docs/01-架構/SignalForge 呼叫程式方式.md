---
title: SignalForge 呼叫程式方式
tags:
  - project/SignalForge
  - architecture
  - cli
status: active
updated: 2026-05-24
aliases:
  - SignalForge CLI
  - SignalForge invocation
---

# SignalForge 呼叫程式方式

這份筆記整理目前可以怎麼呼叫 SignalForge 程式。若你只想快速跑策略，先看 repo 根目錄 `README.md`；若你想理解每個 function / module 在哪裡，請看 [[SignalForge 資料夾與程式碼導覽|資料夾與程式碼導覽]]。

> [!warning]
> SignalForge 目前仍是研究與回測工具。`live` 只允許 dry-run order intent，不接 broker、不讀 credential、不送真實訂單。

## PowerShell 前置設定

在 repo 內直接跑 source tree 時，先設定中文輸出與 package 路徑：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
cd C:\Projects\signal-forge
$env:PYTHONPATH = "src"
```

若已用 editable install 安裝 package，也可以使用 `signal-forge` console script：

```powershell
cd C:\Projects\signal-forge
python -m pip install -e .
signal-forge --help
```

## 入口層級

| 場景 | 呼叫方式 | 用途 |
|---|---|---|
| 開發中直接跑 repo | `python -m signal_forge.cli <command> ...` | 不需要安裝 package，只要先設定 `$env:PYTHONPATH = "src"`。 |
| 安裝後使用 console script | `signal-forge <command> ...` | 由 `pyproject.toml` 的 `[project.scripts]` 指到 `signal_forge.cli:main`。 |
| Python 程式內呼叫 | `from signal_forge import ...` | 給 tests、notebook 或研究腳本直接使用 `PhaseRunner`、`EntryEdgeEvaluator`、策略 factory。 |
| 維護與驗證工具 | `python tools\phase_readiness_score.py`、`python -m unittest discover -s tests` | 每輪固定 guard。 |
| 研究工具 | `python tools\*.py ...` | 多股票 sweep、portfolio rotation、adjusted data、raw/adjusted comparison。 |

不要直接執行 `src\signal_forge\cli\__main__.py`。正式 CLI 入口是 module invocation 或 console script，才能維持 import path 與 parser contract 一致。

## CLI subcommands

`signal_forge.cli.parser.build_parser()` 目前定義三個 subcommand：

| Subcommand | 主要用途 | 核心輸入 | 主要輸出 |
|---|---|---|---|
| `fetch-data` | 下載免費日線 OHLCV 並轉成 SignalForge CSV。 | `--market twse|us`、`--symbol`、`--start`、`--end`。 | `data/raw`、`data/processed` CSV 與 manifest。 |
| `entry-edge` | 第一階段 long-only 固定持有期進場優勢稽核。 | `--csv`、`--strategy`、成本參數、`--hold-bars-per-day`，可選 `--hold-bars-list`。 | entry-edge markdown、summary JSON、trade log CSV；多持有期時另輸出 comparison JSON/Markdown。 |
| `phase` | 主工作流，依 mode 路由到 backtest 或 live dry-run。 | `--csv`、`--mode backtest|live`、`--strategy`、`--hold-bars-per-day`。 | Phase markdown、summary JSON；backtest 另寫 signals CSV 與 trace summary，live 只寫 dry-run order intents。 |

## 支援策略與預設參數

`entry-edge` 與 `phase` 共用 `src\signal_forge\cli\strategy_options.py` 的策略參數。未輸入的欄位會交給 `src\signal_forge\strategies\registry.py` 使用各策略自己的 default。

| 策略 | 用途 | Default parameters |
|---|---|---|
| `sma-crossover` | 趨勢追蹤 baseline。 | `fast_window=20`、`slow_window=200`、Phase 1 `allow_short=False`。 |
| `vwap-reversion` | rolling VWAP 均值回歸。 | `vwap_window=20`、`entry_z=1.5`、`exit_z=0.25`、`vwap_regime_filter=False`、`vwap_regime_window=50`、Phase 1 `allow_short=False`。 |
| `confluence-score` | 趨勢、VWAP、RSI、volume 共振打分。 | `fast_window=20`、`slow_window=50`、`rsi_window=14`、`vwap_window=20`、`threshold=3.0`、Phase 1 `allow_short=False`。 |
| `absolute-momentum` | 長期趨勢與絕對動能候選。 | `momentum_window=126`，CLI 用 `--fast-window` 覆寫；`trend_window=200`，CLI 用 `--slow-window` 覆寫。 |
| `orb-volume-vwap` | Intraday opening range breakout 研究候選。 | opening range、session clock、EMA 與 ORB gate 預設由 `OrbVolumeVwapStrategy` 提供。 |

## 共用 CLI 參數

| 參數 | 適用範圍 |
|---|---|
| `--strategy sma-crossover|vwap-reversion|confluence-score|absolute-momentum|orb-volume-vwap` | 選擇策略。 |
| `--fast-window`、`--slow-window` | SMA Crossover；Absolute Momentum 也用這兩個參數覆寫 momentum / trend windows。 |
| `--vwap-window`、`--entry-z`、`--exit-z` | VWAP Reversion。 |
| `--vwap-regime-filter`、`--vwap-regime-window` | VWAP Reversion entry-only regime filter。 |
| `--rsi-window`、`--threshold` | Confluence Score。 |
| `--orb-*` | ORB + Volume + VWAP 的 session、opening range、EMA、breakout 與 volume gate。 |
| `--volume-filter`、`--volume-window`、`--volume-multiplier` | 可選成交量 wrapper，預設關閉。 |
| `--signal-cooldown-bars` | 可選進場冷卻 wrapper，接受 long entry 後封鎖指定 bar 數內的新 long entry。 |
| `--hold-bars-per-day` | Entry-edge 固定持有幾根 bar。 |
| `--hold-bars-list` | 多持有期 comparison，例如 `1,3,5,10`。 |
| `--commission-bps`、`--slippage-bps`、`--transaction-tax-bps` | 成本設定。 |
| `--pass-profit-factor` | Entry-edge 初篩 PF 門檻。 |

## 常用 CLI 範例

下載台股日線：

```powershell
python -m signal_forge.cli fetch-data `
  --market twse `
  --symbol 2330 `
  --start 2024-01-01 `
  --end 2024-12-31
```

設定常用 CSV：

```powershell
$Csv = "data\processed\TWSE_2330_1D.csv"
```

用 default parameter 跑單策略：

```powershell
python -m signal_forge.cli entry-edge --csv $Csv --strategy sma-crossover
python -m signal_forge.cli entry-edge --csv $Csv --strategy vwap-reversion
python -m signal_forge.cli entry-edge --csv $Csv --strategy confluence-score
python -m signal_forge.cli entry-edge --csv $Csv --strategy absolute-momentum
```

覆寫參數跑 SMA：

```powershell
python -m signal_forge.cli entry-edge `
  --csv $Csv `
  --strategy sma-crossover `
  --fast-window 10 `
  --slow-window 60 `
  --hold-bars-per-day 5 `
  --output-dir reports\generated `
  --run-name tsmc-sma-10-60-hold5
```

跑多持有期 comparison：

```powershell
python -m signal_forge.cli entry-edge `
  --csv $Csv `
  --strategy confluence-score `
  --hold-bars-per-day 1 `
  --hold-bars-list 1,3,5,10 `
  --signal-cooldown-bars 10 `
  --output-dir reports\generated `
  --run-name tsmc-confluence-hold-comparison
```

啟用 VWAP regime filter：

```powershell
python -m signal_forge.cli entry-edge `
  --csv $Csv `
  --strategy vwap-reversion `
  --vwap-regime-filter `
  --vwap-regime-window 50 `
  --output-dir reports\generated `
  --run-name tsmc-vwap-regime
```

跑 ORB intraday 策略：

```powershell
$Csv5m = "data\processed\TWSE_2330_5M.csv"
python -m signal_forge.cli entry-edge `
  --csv $Csv5m `
  --strategy orb-volume-vwap `
  --orb-opening-range-minutes 15 `
  --orb-session-start-hour 9 `
  --orb-session-start-minute 0 `
  --orb-session-end-hour 13 `
  --orb-session-end-minute 30 `
  --orb-session-timezone Asia/Taipei `
  --hold-bars-per-day 6 `
  --output-dir reports\generated `
  --run-name tsmc-orb
```

跑 Phase backtest：

```powershell
python -m signal_forge.cli phase `
  --csv $Csv `
  --mode backtest `
  --strategy sma-crossover `
  --output-dir reports\generated `
  --run-name tsmc-phase-backtest
```

跑 Phase live dry-run：

```powershell
python -m signal_forge.cli phase `
  --csv $Csv `
  --mode live `
  --strategy sma-crossover `
  --output-dir reports\generated `
  --run-name tsmc-phase-live-dry-run
```

## 多股票與工具呼叫

一次比較多檔 entry-edge：

```powershell
python tools\multi_stock_entry_edge_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --strategy confluence-score `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --hold-bars-list 1,3,5,10 `
  --pass-profit-factor 1.5 `
  --signal-cooldown-bars 10 `
  --summary-json reports\generated\multi-stock-entry-edge.json `
  --summary-md reports\generated\multi-stock-entry-edge.md
```

完整持倉 target-state 與風控 overlay：

```powershell
python tools\multi_stock_target_state_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --strategy absolute-momentum `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-multipliers-list 1,2,3 `
  --volatility-target `
  --target-annual-volatility 0.40 `
  --drawdown-risk-off `
  --drawdown-risk-off-threshold 0.25 `
  --drawdown-risk-off-bars 120 `
  --walk-forward-windows is:2020-01-01:2023-12-31,oos:2024-01-01:2026-05-20 `
  --summary-json reports\generated\target-state.json `
  --summary-md reports\generated\target-state.md
```

Portfolio rotation：

```powershell
python tools\portfolio_rotation_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-multipliers-list 1,2,3 `
  --rebalance-frequency monthly `
  --lookback-bars 21 `
  --top-n 4 `
  --min-return 0 `
  --breadth-filter `
  --breadth-lookback-bars 42 `
  --breadth-min-positive-count 3 `
  --rolling-window-months 24 `
  --rolling-step-months 12 `
  --rolling-min-months 12 `
  --summary-json reports\generated\portfolio-rotation.json `
  --summary-md reports\generated\portfolio-rotation.md
```

## Portfolio rotation 進階工具鏈

如果目標是判斷一個 portfolio rotation 候選能否升級，不要只看 `portfolio_rotation_sweep.py` 的單一 summary。建議依序保留這些 artifact，讓結論可重跑、可比對：

| 順序 | 工具 | 主要用途 |
|---:|---|---|
| 1 | `tools\portfolio_rotation_universe_audit.py` | 先檢查股票池歷史長度、平均成交金額、群組成員數與 adjusted CSV availability。 |
| 2 | `tools\portfolio_rotation_universe_select.py` | 需要平衡子股票池時，從 audit 結果 deterministic 選股。 |
| 3 | `tools\portfolio_rotation_sweep.py` | 產生 full-window、cost stress、rolling windows、symbol / group attribution。 |
| 4 | `tools\portfolio_rotation_grid_search.py` | 掃描 top-N、breadth、liquidity、max consecutive 等候選參數。 |
| 5 | `tools\compare_portfolio_rotation_reports.py` | 對照 raw 與 adjusted summary，檢查資料調整後是否降級。 |
| 6 | `tools\portfolio_rotation_group_regime_validation.py` | 檢查 dominant group contribution 是曝險主導、return regime 主導或混合。 |
| 7 | `tools\portfolio_rotation_group_breadth_validation.py` | 檢查 dominant group 內部是 broad momentum、narrow momentum 或 single-member dependency。 |
| 8 | `tools\portfolio_rotation_promotion_gate.py` | 合併 summary、raw/adjusted、group regime、group breadth，輸出單一 `keep` / `compare-only` gate。 |

## Python API 呼叫

CLI 以外，可以直接走 public API。這是 tests、notebook 或研究腳本比較適合的方式：

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
