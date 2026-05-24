# SignalForge

SignalForge 是研究導向的交易訊號沙盒。它的用途不是直接下單，而是把 TradingView / Pine Script 或自己的策略想法拆成 Python 可驗證的研究假設，再用固定資料、固定成本、固定 artifact contract 做回測與稽核。

> SignalForge 目前只做研究、回測與 live dry-run intent，不構成投資建議。`live` 模式固定 dry-run only，不接 broker、不讀 API key、不送真實訂單。

## 先看哪裡

| 你想做什麼 | 看哪裡 |
|---|---|
| 快速跑策略 | 本 README 的「最簡執行法」 |
| 看完整參數、進出場流程與最新回測 | `docs\策略筆記\策略筆記索引.md` |
| 看策略筆記格式 | `docs\策略筆記\策略筆記模板.md` |
| 判斷 keep / discard / compare-only | `docs\02-規劃\策略回測與優化評估準則.md` |
| 找程式位置與修改路線 | `docs\01-架構\SignalForge 資料夾與程式碼導覽.md` |
| 追最近實驗證據 | `docs\04-實驗記錄\Autoresearch 實驗記錄.md` |

## 基本啟動

```powershell
cd C:\Projects\signal-forge
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONPATH = "src"
python -m unittest discover -s tests
```

取得台股日線資料：

```powershell
python -m signal_forge.cli fetch-data `
  --symbol 2330 `
  --start 2020-01-01 `
  --end 2026-05-20
```

回測通常使用 processed CSV：

```powershell
$Csv = "data\processed\TWSE_2330_1D.csv"
$Csv5m = "data\processed\TWSE_2330_5M.csv"
```

## 先分清楚

| 類型 | 是什麼 | 最常修改哪裡 |
|---|---|---|
| 策略 | 用 `--strategy <name>` 產生單檔股票底層訊號 | `src\signal_forge\strategies\`、`src\signal_forge\strategies\registry.py` |
| Wrapper / overlay | 包在策略外面，改 entry、曝險或風控，不是新的底層策略 | `src\signal_forge\strategies\*_filter.py`、`tools\multi_stock_target_state_sweep.py` |
| Portfolio gate | 在多股票輪動時篩掉整個持股候選或控制集中度 | `tools\portfolio_rotation_sweep.py` |

完整參數表、控制語意、進出場流程與最新回測 table 都在各自策略筆記。README 只保留最短可執行方法。

## 最簡執行法

### 單檔策略

```powershell
python -m signal_forge.cli entry-edge --csv $Csv --strategy sma-crossover --hold-bars-per-day 10
python -m signal_forge.cli entry-edge --csv $Csv --strategy vwap-reversion --hold-bars-per-day 3
python -m signal_forge.cli entry-edge --csv $Csv --strategy confluence-score --signal-cooldown-bars 10 --hold-bars-per-day 10
python -m signal_forge.cli entry-edge --csv $Csv --strategy absolute-momentum
python -m signal_forge.cli entry-edge --csv $Csv5m --strategy orb-volume-vwap --hold-bars-per-day 5
```

| 策略 | 詳細筆記 |
|---|---|
| `sma-crossover` | `docs\策略筆記\SMA Crossover.md` |
| `vwap-reversion` | `docs\策略筆記\VWAP Reversion.md` |
| `confluence-score` | `docs\策略筆記\Confluence Score.md` |
| `absolute-momentum` | `docs\策略筆記\Absolute Momentum.md` |
| `orb-volume-vwap` | `docs\策略筆記\ORB + Volume + VWAP.md` |

### Wrapper / overlay

```powershell
python -m signal_forge.cli entry-edge --csv $Csv --strategy confluence-score --volume-filter
python -m signal_forge.cli entry-edge --csv $Csv --strategy confluence-score --signal-cooldown-bars 10 --hold-bars-per-day 10

python tools\multi_stock_target_state_sweep.py --csv $Csv --strategy absolute-momentum --volatility-target
python tools\multi_stock_target_state_sweep.py --csv $Csv --strategy absolute-momentum --drawdown-risk-off --drawdown-risk-off-threshold 0.25 --drawdown-risk-off-bars 120
python tools\multi_stock_target_state_sweep.py --csv $Csv --strategy absolute-momentum --relative-momentum-filter --relative-momentum-top-n 3
```

| Wrapper / overlay | 詳細筆記 |
|---|---|
| `--volume-filter` | `docs\策略筆記\Volume Filter.md` |
| `--signal-cooldown-bars` | `docs\策略筆記\Signal Cooldown.md` |
| `--volatility-target` | `docs\策略筆記\Volatility Target.md` |
| `--drawdown-risk-off` | `docs\策略筆記\Drawdown Risk-Off.md` |
| `--relative-momentum-filter` | `docs\策略筆記\Relative Momentum Stock-Pool Filter.md` |

### Portfolio rotation / gates

```powershell
python tools\portfolio_rotation_sweep.py --csv $Csv --csv data\processed\TWSE_2317_1D.csv --csv data\processed\TWSE_2454_1D.csv --summary-json reports\generated\portfolio-rotation.json --summary-md reports\generated\portfolio-rotation.md

python tools\portfolio_rotation_sweep.py --csv $Csv --csv data\processed\TWSE_2454_1D.csv --symbol-group 2330:semiconductor --symbol-group 2454:semiconductor --group-breadth-filter --group-regime-filter --summary-json reports\generated\portfolio-group-gates.json --summary-md reports\generated\portfolio-group-gates.md
```

| Portfolio 策略 / gate | 詳細筆記 |
|---|---|
| Portfolio Relative Momentum Rotation | `docs\策略筆記\Portfolio Relative Momentum Rotation.md` |
| Portfolio Rotation Group Gates | `docs\策略筆記\Portfolio Rotation Group Gates.md` |

## 輸出檔案

`entry-edge` 預設輸出到 `reports\generated\`：

| 檔案 | 用途 |
|---|---|
| `*_entry_edge.md` | 人讀的回測摘要 |
| `*_entry_edge_summary.json` | 機器可比對的 summary |
| `*_entry_edge_trades.csv` | 每筆 entry / exit trade log |

多股票與 portfolio 工具通常用 `--summary-json` 與 `--summary-md` 指定輸出位置。

## 要改哪裡

| 目標 | 主要檔案 |
|---|---|
| 新增或修改底層策略 | `src\signal_forge\strategies\` |
| 註冊 `--strategy` 名稱 | `src\signal_forge\strategies\registry.py` |
| 新增 CLI 參數 | `src\signal_forge\cli\strategy_options.py` |
| 修改 entry-edge / phase 命令 | `src\signal_forge\cli\commands.py`、`src\signal_forge\cli\parser.py` |
| 修改多股票 target-state | `tools\multi_stock_target_state_sweep.py` |
| 修改 portfolio rotation / gates | `tools\portfolio_rotation_sweep.py` |
| 補測試 | `tests\` |
| 補策略文件 | `docs\策略筆記\`，Obsidian canonical 來源是 `C:\Users\gary1\OneDrive\桌面\obsidian\project開發\SignalForge` |

## Phase 與 live dry-run

`phase` 會把資料、策略、adapter、reporting 串成主工作流：

```powershell
python -m signal_forge.cli phase --csv $Csv --mode backtest --strategy sma-crossover
python -m signal_forge.cli phase --csv $Csv --mode live --strategy sma-crossover
```

`live` 只產生 dry-run `OrderIntent`，安全 invariant 必須維持：

| 欄位 | 必須維持 |
|---|---|
| `dry_run` | `True` |
| `submitted` | `False` |
| `safety_note` | 包含 `LIVE_DRY_RUN_ONLY` |
| broker/API key | 不連線、不讀取 |
| 真實訂單 | 不送出 |

## 驗證

每輪文件或程式改動後固定跑：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
cd C:\Projects\signal-forge
$env:PYTHONPATH = "src"
python tools\phase_readiness_score.py
python -m unittest discover -s tests
git diff --check
```

策略結論不要只看單一 PF、勝率或單一股票結果。每次策略筆記底部都要用 table 標出最新回測註記與 `keep`、`compare-only` 或 `discard` 判斷。
