# SignalForge

SignalForge 是研究導向的交易訊號沙盒。它的用途不是直接下單，而是把 TradingView / Pine Script 或自己的策略想法拆成 Python 可驗證的研究假設，再用固定資料、固定成本、固定 artifact contract 做回測與稽核。

目前主線分成三層：

| 層級 | 你要回答的問題 | 主要入口 |
|---|---|---|
| 資料準備 | 我要回測哪一檔股票、哪段日期？ | `fetch-data`、`data\processed\TWSE_<symbol>_1D.csv` |
| 單策略進場檢查 | 這個進場訊號在固定持有期下有沒有 entry edge？ | `entry-edge` |
| Phase / 多股票研究 | 同一策略能否產生 deterministic artifacts，或跨股票、成本、OOS 比較？ | `phase`、`tools\*.py` |

> SignalForge 只做研究、回測與 dry-run intent，不構成投資建議。`live` 模式目前固定 dry-run only，不接 broker、不讀 API key、不送真實訂單。

## 先看哪份文件

| 需求 | 文件 |
|---|---|
| 想理解整個 project、資料流、每個 module/function 在哪裡 | `docs\01-架構\SignalForge 資料夾與程式碼導覽.md` |
| 想看更完整的 CLI、工具與 Python API 呼叫方式 | `docs\01-架構\SignalForge 呼叫程式方式.md` |
| 想理解 Phase、Entry Edge、SignalDigest、live dry-run 架構 | `docs\01-架構\SignalForge 架構總覽.md` |
| 想判斷策略結果是 keep、discard 還是 compare-only | `docs\02-規劃\策略回測與優化評估準則.md` |
| 想看目前策略研究與實驗結論 | `docs\04-實驗記錄\Autoresearch 實驗記錄.md` |

## 環境設定

在 repo 內直接跑 source tree，使用這組 PowerShell 前置設定：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
cd C:\Projects\signal-forge
$env:PYTHONPATH = "src"
```

也可以安裝 editable package 後使用 console script：

```powershell
cd C:\Projects\signal-forge
python -m pip install -e .
signal-forge --help
```

本 README 以下範例使用 `python -m signal_forge.cli`，因為它最適合直接在 repo source tree 內執行。

## 固定驗證命令

文件或程式改完後固定跑：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
cd C:\Projects\signal-forge
$env:PYTHONPATH = "src"
python tools\phase_readiness_score.py
python -m unittest discover -s tests
git diff --check
```

通過條件：readiness score `110`、unit tests 全部通過、`git diff --check` clean。

## 下載股票資料

台股日線資料會輸出到 `data\raw\` 與 `data\processed\`，回測通常使用 processed CSV。

```powershell
python -m signal_forge.cli fetch-data `
  --market twse `
  --symbol 2330 `
  --start 2024-01-01 `
  --end 2024-12-31
```

下載完成後，台積電日線會在：

```text
data\processed\TWSE_2330_1D.csv
```

要換股票，只改 `--symbol` 和後續 `--csv` 檔名。例如聯發科用 `2454`：

```powershell
python -m signal_forge.cli fetch-data `
  --market twse `
  --symbol 2454 `
  --start 2024-01-01 `
  --end 2024-12-31
```

美股入口是 `--market us`，目前 Stooq CSV 端點要求免費 API key：

```powershell
$env:STOOQ_API_KEY = "<your-free-stooq-key>"
python -m signal_forge.cli fetch-data `
  --market us `
  --symbol AAPL `
  --start 2024-01-01 `
  --end 2024-12-31
```

## 單檔股票快速回測

先把要測的 CSV 放進變數，後面換股票只改這一行：

```powershell
$Csv = "data\processed\TWSE_2330_1D.csv"
```

用 default parameter 跑四個日線策略；intraday ORB 需要 5 分 K 或其他含時間戳的 intraday CSV，見下方單獨範例：

```powershell
python -m signal_forge.cli entry-edge --csv $Csv --strategy sma-crossover
python -m signal_forge.cli entry-edge --csv $Csv --strategy vwap-reversion
python -m signal_forge.cli entry-edge --csv $Csv --strategy confluence-score
python -m signal_forge.cli entry-edge --csv $Csv --strategy absolute-momentum
```

輸出預設在 `reports\generated\`。每次 `entry-edge` 會產生：

| 檔案 | 用途 |
|---|---|
| `*_entry_edge.md` | 人讀的回測摘要 |
| `*_entry_edge_summary.json` | 機器可比對的 summary |
| `*_entry_edge_trades.csv` | 每筆 entry / exit trade log |

## 策略呼叫方式

SignalForge 的 CLI 策略參數都在 `src\signal_forge\cli\strategy_options.py` 註冊，策略 factory 在 `src\signal_forge\strategies\registry.py`。未填的參數會使用該策略自己的 default。

### 先分清楚：策略、wrapper 與 portfolio gate

| 類型 | 呼叫方式 | 目前項目 | 主要位置 |
|---|---|---|---|
| 單檔策略 | `--strategy <name>` | `sma-crossover`、`vwap-reversion`、`confluence-score`、`absolute-momentum`、`orb-volume-vwap` | `src\signal_forge\strategies\registry.py` |
| Entry wrapper | 加在 `entry-edge` / `phase` 的策略外層 | `--volume-filter`、`--signal-cooldown-bars` | `src\signal_forge\cli\strategy_options.py` |
| Target-state overlay | 加在 `tools\multi_stock_target_state_sweep.py` | `--volatility-target`、`--drawdown-risk-off`、`--relative-momentum-filter` | `tools\multi_stock_target_state_sweep.py` |
| Portfolio rotation gate | 加在 `tools\portfolio_rotation_sweep.py` | market regime、breadth、group breadth、group regime、liquidity、group cap、re-entry cooldown、group contribution | `tools\portfolio_rotation_sweep.py` |

因此，不是所有新增研究功能都會出現在 `--strategy` 清單。`--strategy` 只負責產生底層訊號；wrapper / overlay / gate 會在底層訊號或投組權重外面再加控制條件。

### SMA Crossover

用途：趨勢追蹤 baseline。當 fast SMA 大於 slow SMA 時做多，否則空手。Phase 1 版本固定 long-only。

Default parameters：

| 參數 | 預設 |
|---|---:|
| `fast_window` | `20` |
| `slow_window` | `200` |
| `allow_short` | `False` |

精簡版：

```powershell
python -m signal_forge.cli entry-edge --csv $Csv --strategy sma-crossover
```

完整版：

```powershell
python -m signal_forge.cli entry-edge `
  --csv $Csv `
  --strategy sma-crossover `
  --fast-window 20 `
  --slow-window 200 `
  --hold-bars-per-day 1 `
  --initial-equity 10000 `
  --commission-bps 1 `
  --slippage-bps 1 `
  --transaction-tax-bps 0 `
  --pass-profit-factor 1.2 `
  --output-dir reports\generated `
  --run-name tsmc-sma-20-200
```

### VWAP Reversion

用途：均值回歸 baseline。價格跌到 rolling VWAP 下方一定 z-score 後做多，回到 VWAP 附近出場。Phase 1 版本固定 long-only。

Default parameters：

| 參數 | 預設 |
|---|---:|
| `vwap_window` | `20` |
| `entry_z` | `1.5` |
| `exit_z` | `0.25` |
| `vwap_regime_filter` | `False` |
| `vwap_regime_window` | `50` |
| `allow_short` | `False` |

精簡版：

```powershell
python -m signal_forge.cli entry-edge --csv $Csv --strategy vwap-reversion
```

完整版：

```powershell
python -m signal_forge.cli entry-edge `
  --csv $Csv `
  --strategy vwap-reversion `
  --vwap-window 20 `
  --entry-z 1.5 `
  --exit-z 0.25 `
  --vwap-regime-filter `
  --vwap-regime-window 50 `
  --hold-bars-per-day 1 `
  --initial-equity 10000 `
  --commission-bps 1 `
  --slippage-bps 1 `
  --transaction-tax-bps 0 `
  --pass-profit-factor 1.2 `
  --output-dir reports\generated `
  --run-name tsmc-vwap-regime
```

### Confluence Score

用途：多因子共振策略。用趨勢、價格相對 slow SMA、VWAP、RSI、成交量確認累積 score，達 threshold 後做多。

Default parameters：

| 參數 | 預設 |
|---|---:|
| `fast_window` | `20` |
| `slow_window` | `50` |
| `rsi_window` | `14` |
| `vwap_window` | `20` |
| `threshold` | `3.0` |
| `allow_short` | `False` |

精簡版：

```powershell
python -m signal_forge.cli entry-edge --csv $Csv --strategy confluence-score
```

完整版：

```powershell
python -m signal_forge.cli entry-edge `
  --csv $Csv `
  --strategy confluence-score `
  --fast-window 20 `
  --slow-window 50 `
  --rsi-window 14 `
  --vwap-window 20 `
  --threshold 3.0 `
  --signal-cooldown-bars 10 `
  --hold-bars-per-day 10 `
  --initial-equity 10000 `
  --commission-bps 1 `
  --slippage-bps 1 `
  --transaction-tax-bps 0 `
  --pass-profit-factor 1.2 `
  --output-dir reports\generated `
  --run-name tsmc-confluence-cooldown10-hold10
```

### Absolute Momentum

用途：長期趨勢持有候選。回看報酬為正，且收盤價站上長期 SMA 時做多。這是 compare-only 研究候選，不是穩定營利結論。

Default parameters：

| 參數 | 預設 |
|---|---:|
| `momentum_window` | `126`，CLI 用 `--fast-window` 覆寫 |
| `trend_window` | `200`，CLI 用 `--slow-window` 覆寫 |

精簡版：

```powershell
python -m signal_forge.cli entry-edge --csv $Csv --strategy absolute-momentum
```

完整版：

```powershell
python -m signal_forge.cli entry-edge `
  --csv $Csv `
  --strategy absolute-momentum `
  --fast-window 126 `
  --slow-window 200 `
  --hold-bars-per-day 20 `
  --initial-equity 10000 `
  --commission-bps 1 `
  --slippage-bps 1 `
  --transaction-tax-bps 0 `
  --pass-profit-factor 1.2 `
  --output-dir reports\generated `
  --run-name tsmc-absolute-momentum-126-200-hold20
```

### ORB + Volume + VWAP

用途：intraday opening range breakout 研究候選。它需要 intraday CSV，例如 `data\processed\TWSE_2330_5M.csv`。目前仍受 session / market-clock contract 限制，解讀時要特別看資料頻率與交易時段。

Default parameters：

| 參數 | 預設 |
|---|---:|
| `opening_range_minutes` | 策略檔預設 |
| `session_start_hour` / `session_start_minute` | 策略檔預設 |
| `session_end_hour` / `session_end_minute` | 策略檔預設 |
| `session_timezone` | 策略檔預設 |
| `ema_window` | 策略檔預設 |

精簡版：

```powershell
$Csv5m = "data\processed\TWSE_2330_5M.csv"
python -m signal_forge.cli entry-edge --csv $Csv5m --strategy orb-volume-vwap
```

完整版：

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
  --orb-vwap-slope-confirmation `
  --orb-ema-trend-confirmation `
  --orb-ema-window 20 `
  --orb-reject-ema-inside-range `
  --orb-signal-window-minutes 90 `
  --orb-min-range-pct 0.001 `
  --orb-max-range-pct 0.03 `
  --orb-min-breakout-pct 0.0005 `
  --orb-full-bar-above-range `
  --orb-min-breakout-body-pct 0.5 `
  --orb-fresh-breakout-from-or `
  --orb-use-opening-range-volume-baseline `
  --hold-bars-per-day 6 `
  --output-dir reports\generated `
  --run-name tsmc-orb-full
```

## Wrapper 與共用參數

這些不是獨立策略，而是包在底層策略外面的研究控制。使用時先選一個 `--strategy`，再依研究問題加 wrapper 或 sweep gate。

| Wrapper / 參數 | 預設 | 適用命令 | 用途 |
|---|---:|---|---|
| `--volume-filter` | 關閉 | `entry-edge`、`phase` | 只有成交量高於相對門檻時才保留 long signal |
| `--volume-window` | `20` | `entry-edge`、`phase` | 成交量 SMA 視窗 |
| `--volume-multiplier` | `1.2` | `entry-edge`、`phase` | 成交量需達均量倍數 |
| `--signal-cooldown-bars` | 關閉 | `entry-edge`、`phase`、target-state sweep | 接受 long entry 後，封鎖指定 bar 數內的新 long entry |
| `--volatility-target` | 關閉 | target-state sweep、portfolio rotation | realized volatility 高於目標時只降曝險、不加槓桿 |
| `--drawdown-risk-off` | 關閉 | target-state sweep | 單檔 proxy equity 回撤破門檻後暫時 flat |
| `--relative-momentum-filter` | 關閉 | target-state sweep | 只允許同日相對動能 top-N 股票保留非零曝險 |
| `--hold-bars-per-day` | `1` | `entry-edge` | entry-edge 固定持有幾根 bar |
| `--hold-bars-list` | 關閉 | `entry-edge` | 產生多持有期比較報表，例如 `1,3,5,10` |
| `--commission-bps` | `1` | 多數回測工具 | 單邊手續費 bps |
| `--slippage-bps` | `1` | 多數回測工具 | 單邊滑價 bps |
| `--transaction-tax-bps` | `0` | 多數回測工具 | 賣出交易稅 bps |
| `--pass-profit-factor` | `1.2` | `entry-edge` | Entry-edge 初篩 PF 門檻 |

成交量濾網範例：

```powershell
python -m signal_forge.cli entry-edge `
  --csv $Csv `
  --strategy sma-crossover `
  --volume-filter `
  --volume-window 20 `
  --volume-multiplier 1.2 `
  --run-name tsmc-sma-volume-filter
```

多持有期比較範例：

```powershell
python -m signal_forge.cli entry-edge `
  --csv $Csv `
  --strategy confluence-score `
  --hold-bars-per-day 1 `
  --hold-bars-list 1,3,5,10 `
  --run-name tsmc-confluence-hold-comparison
```

## Phase backtest 與 live dry-run

`phase` 會把資料、策略、adapter、reporting 串成主工作流。

Backtest：

```powershell
python -m signal_forge.cli phase `
  --csv $Csv `
  --mode backtest `
  --strategy sma-crossover `
  --output-dir reports\generated `
  --run-name tsmc-phase-backtest
```

Live dry-run，只產生 `OrderIntent`，不送單：

```powershell
python -m signal_forge.cli phase `
  --csv $Csv `
  --mode live `
  --strategy sma-crossover `
  --output-dir reports\generated `
  --run-name tsmc-phase-live-dry-run
```

`live` 的安全 invariant：

| 欄位 | 必須維持 |
|---|---|
| `dry_run` | `True` |
| `submitted` | `False` |
| `safety_note` | 包含 `LIVE_DRY_RUN_ONLY` |
| broker/API key | 不連線、不讀取 |
| 真實訂單 | 不送出 |

## 多股票與進階研究工具

當單檔策略有初步結果後，不要只看單一 PF 或單一股票。策略研究要回到 `docs\02-規劃\策略回測與優化評估準則.md`，至少檢查 edge、MDD、benchmark relative、cost stress、OOS / rolling、資料邊界。

### 多股票 entry-edge

用同一策略與持有期比較多檔股票：

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

### 多股票 target-state

用完整 target exposure 回測，包含成本壓力、風控 overlay 與 walk-forward / OOS：

精簡版：

```powershell
python tools\multi_stock_target_state_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --strategy absolute-momentum `
  --summary-json reports\generated\target-state-default.json `
  --summary-md reports\generated\target-state-default.md
```

完整版：

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
  --volatility-lookback-bars 20 `
  --target-annual-volatility 0.40 `
  --volatility-min-observations 20 `
  --drawdown-risk-off `
  --drawdown-risk-off-threshold 0.25 `
  --drawdown-risk-off-bars 120 `
  --relative-momentum-filter `
  --relative-momentum-lookback-bars 126 `
  --relative-momentum-top-n 3 `
  --relative-momentum-min-return 0 `
  --walk-forward-windows is:2020-01-01:2023-12-31,oos:2024-01-01:2026-05-20 `
  --summary-json reports\generated\target-state.json `
  --summary-md reports\generated\target-state.md
```

### Portfolio rotation

把多檔股票視為同一資金池，和 equal-weight buy-and-hold portfolio 比較。精簡版只指定股票池、日期與輸出路徑；未填參數會使用工具預設：`weekly` rebalance、`lookback_bars=126`、`top_n=3`、`min_return=0`、`1x` 成本、無額外風控 gate。

精簡版：

```powershell
python tools\portfolio_rotation_sweep.py `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --summary-json reports\generated\portfolio-rotation-default.json `
  --summary-md reports\generated\portfolio-rotation-default.md
```

完整版範例會把目前常用研究參數攤開，方便你換股票池、成本壓力、rebalance、ranking、breadth、liquidity、rolling window 與輸出檔名：

```powershell
python tools\portfolio_rotation_sweep.py `
  --csv data\processed\TWSE_1301_1D.csv `
  --csv data\processed\TWSE_1303_1D.csv `
  --csv data\processed\TWSE_2303_1D.csv `
  --csv data\processed\TWSE_2308_1D.csv `
  --csv data\processed\TWSE_2317_1D.csv `
  --csv data\processed\TWSE_2330_1D.csv `
  --csv data\processed\TWSE_2382_1D.csv `
  --csv data\processed\TWSE_2412_1D.csv `
  --csv data\processed\TWSE_2454_1D.csv `
  --csv data\processed\TWSE_2603_1D.csv `
  --csv data\processed\TWSE_2881_1D.csv `
  --csv data\processed\TWSE_2882_1D.csv `
  --csv data\processed\TWSE_2891_1D.csv `
  --csv data\processed\TWSE_3711_1D.csv `
  --symbol-group 1301:plastics `
  --symbol-group 1303:plastics `
  --symbol-group 2303:semiconductor `
  --symbol-group 2308:electronics `
  --symbol-group 2317:electronics `
  --symbol-group 2330:semiconductor `
  --symbol-group 2382:electronics `
  --symbol-group 2412:telecom `
  --symbol-group 2454:semiconductor `
  --symbol-group 2603:shipping `
  --symbol-group 2881:financial `
  --symbol-group 2882:financial `
  --symbol-group 2891:financial `
  --symbol-group 3711:semiconductor `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --cost-multipliers-list 1,2,3 `
  --rebalance-frequency monthly `
  --lookback-bars 21 `
  --ranking-skip-bars 10 `
  --top-n 4 `
  --min-return 0 `
  --breadth-filter `
  --breadth-lookback-bars 42 `
  --breadth-min-positive-count 3 `
  --group-breadth-filter `
  --group-breadth-lookback-bars 21 `
  --group-breadth-min-positive-share 0.50 `
  --group-breadth-min-members 1 `
  --group-regime-filter `
  --group-regime-lookback-bars 21 `
  --group-regime-min-return 0 `
  --group-regime-min-members 1 `
  --max-consecutive-selections-per-symbol 5 `
  --liquidity-lookback-bars 20 `
  --min-average-traded-value 500000000 `
  --rolling-window-months 24 `
  --rolling-step-months 12 `
  --rolling-min-months 12 `
  --summary-json reports\generated\portfolio-rotation.json `
  --summary-md reports\generated\portfolio-rotation.md
```

Portfolio rotation gate 速查：

| Gate | 預設 | 需要 `--symbol-group` | 解讀 |
|---|---:|---|---|
| `--market-regime-filter` | 關閉 | 否 | 市場等權 index 跌破 SMA 時持現金 |
| `--breadth-filter` | 關閉 | 否 | 正動能股票數不足時持現金 |
| `--group-breadth-filter` | 關閉 | 是 | 候選股票所屬群組內部正動能比例不足時排除 |
| `--group-regime-filter` | 關閉 | 是 | 候選股票所屬群組等權 lookback return 不足時排除 |
| `--max-selections-per-group` | 關閉 | 是 | 限制同一群組每次最多入選幾檔 |
| `--min-symbols-per-selected-group` | `1` | 是 | 阻擋單成員群組依賴 |
| `--reentry-cooldown-rebalances` | `0` | 否 | 股票退出後等待 N 次 rebalance 才能再入選 |
| `--group-contribution-lookback-bars` + `--max-group-contribution-share` | 關閉 | 是 | 用已實現群組貢獻集中度暫時排除過度主導的群組 |

### 調整價資料與 raw / adjusted 對照

單檔調整價：

```powershell
python tools\build_twse_adjusted_ohlcv.py `
  --symbol 2330 `
  --source-csv data\processed\TWSE_2330_1D.csv `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --output-csv reports\generated\adjusted-data\TWSEADJ_2330_1D.csv `
  --manifest-json reports\generated\adjusted-data\TWSEADJ_2330_1D_manifest.json
```

TWSE14 批次調整價：

```powershell
python tools\build_twse_adjusted_ohlcv_batch.py `
  --symbols-list 1301,1303,2303,2308,2317,2330,2382,2412,2454,2603,2881,2882,2891,3711 `
  --source-dir data\processed `
  --start 2020-01-01 `
  --end 2026-05-20 `
  --output-dir reports\generated\adjusted-data `
  --batch-manifest-json reports\generated\adjusted-data\TWSE14_adjusted_batch_manifest_20260524.json
```

Raw / adjusted portfolio rotation 對照：

```powershell
python tools\compare_portfolio_rotation_reports.py `
  --raw-summary-json reports\generated\raw-portfolio-rotation.json `
  --adjusted-summary-json reports\generated\adjusted-portfolio-rotation.json `
  --adjusted-batch-manifest-json reports\generated\adjusted-data\TWSE14_adjusted_batch_manifest_20260524.json `
  --raw-label raw-twse `
  --adjusted-label adjusted-ratio-batch `
  --rolling-cost-label 1x `
  --output-json reports\generated\raw-vs-adjusted-compare.json `
  --output-md reports\generated\raw-vs-adjusted-compare.md
```

### Portfolio rotation 進階工具鏈

Portfolio rotation 候選不能只看單一 summary。常用檢查順序是：先建資料與股票池，再跑 sweep / grid，最後用 diagnostics 與 promotion gate 決定 `keep`、`discard` 或 `compare-only`。

| 需求 | 工具 | 用途 |
|---|---|---|
| 批次掃 top-N / breadth / liquidity / max consecutive | `tools\portfolio_rotation_grid_search.py` | 產生候選排序，避免只手挑一組參數。 |
| 檢查股票池品質 | `tools\portfolio_rotation_universe_audit.py` | 檢查歷史長度、成交金額、群組成員數與 adjusted CSV availability。 |
| 從 audit 產生平衡子股票池 | `tools\portfolio_rotation_universe_select.py` | 依 group 與流動性挑 deterministic 子集合。 |
| 檢查群組集中度來源 | `tools\portfolio_rotation_group_regime_validation.py` | 判斷 dominant group 是長期曝險、特定 group return regime，或混合來源。 |
| 檢查 dominant group 內部廣度 | `tools\portfolio_rotation_group_breadth_validation.py` | 判斷是 broad group momentum、narrow group momentum 或 single-member dependency。 |
| 合併升級判斷 | `tools\portfolio_rotation_promotion_gate.py` | 把 summary、raw/adjusted、group regime、group breadth 合成單一 gate。 |

## 要修改功能時去哪裡

| 想改的東西 | 優先找 |
|---|---|
| CSV 載入、OHLCV 驗證、欄位規則 | `src\signal_forge\core\market_data.py` |
| SMA、EMA、RSI、VWAP 等指標 | `src\signal_forge\core\indicators.py` |
| Strategy / Signal contract、逐 bar template | `src\signal_forge\core\strategy.py` |
| 新增策略或修改策略邏輯 | `src\signal_forge\strategies\*.py`、`src\signal_forge\strategies\registry.py` |
| 新增 CLI 策略參數 | `src\signal_forge\cli\strategy_options.py` |
| 新增 subcommand 或調整 CLI 參數 | `src\signal_forge\cli\parser.py`、`src\signal_forge\cli\commands.py` |
| Entry-edge 計算與 trade log | `src\signal_forge\backtesting\entry_edge.py` |
| Phase mode、backtest/live 分流 | `src\signal_forge\phase\config.py`、`adapters.py`、`runner.py` |
| Markdown / JSON / CSV artifacts | `src\signal_forge\reporting\` |
| 多股票 sweep、target-state | `tools\multi_stock_*.py` |
| Portfolio rotation 回測與參數 | `tools\portfolio_rotation_sweep.py`、`tools\portfolio_rotation_grid_search.py` |
| Portfolio rotation 股票池與升級 gate | `tools\portfolio_rotation_universe_*.py`、`tools\portfolio_rotation_group_*_validation.py`、`tools\portfolio_rotation_promotion_gate.py` |
| 測試 fixture 或測試替身 | `tests\helpers.py` |
| 策略筆記與研究結論 | `docs\策略筆記\`、`docs\04-實驗記錄\` |

更完整的 function map 與維護路徑在 `docs\01-架構\SignalForge 資料夾與程式碼導覽.md`。

## 文件與 Obsidian 同步

`docs\` 是 Obsidian 專案筆記的 repo 鏡像。筆記主來源是：

```text
C:\Users\gary1\OneDrive\桌面\obsidian\project開發\SignalForge
```

push 前要先從 Obsidian 同步回 repo `docs\`，再跑固定驗證、commit、push。
