---
title: SignalForge 專案筆記索引
tags:
  - project/SignalForge
  - trading/research
  - autoresearch
status: active
repo: C:\Projects\signal-forge
updated: 2026-05-24
---

# SignalForge 專案筆記索引

這份筆記是 Obsidian 內的 SignalForge 入口。從現在開始，Obsidian 這個資料夾是專案筆記主來源；push 前再把整理後的筆記同步回 repo 的 `docs/`，讓 GitHub 也保留同一份閱讀版文件。

> [!warning]
> SignalForge 目前只做研究、資料管線驗證與回測稽核，不構成投資建議。`live` 模式仍是 dry-run only，不接 broker、不讀 API key、不送真實訂單。

## 主要入口

- [[01-架構/SignalForge 架構總覽|SignalForge 架構總覽]]
- [[01-架構/SignalForge 資料夾與程式碼導覽|SignalForge 資料夾與程式碼導覽]]
- [[01-架構/SignalForge 呼叫程式方式|SignalForge 呼叫程式方式]]
- [[02-規劃/SignalForge 大框架規劃|SignalForge 大框架規劃]]
- [[02-規劃/策略回測與優化評估準則|策略回測與優化評估準則]]
- [[策略筆記/策略筆記索引|策略筆記索引]]
- [[03-程式疊代/Phase 程式疊代紀錄|Phase 程式疊代紀錄]]
- [[04-實驗記錄/Autoresearch 實驗記錄|Autoresearch 實驗記錄]]
- [[04-實驗記錄/台積電資料與三策略回測|台積電資料與三策略回測]]
- [[04-實驗記錄/台積電四策略延伸研究|台積電四策略延伸研究]]
- [[04-實驗記錄/台股多股票策略基準回測|台股多股票策略基準回測]]

## 目前狀態

- Repo：`C:\Projects\signal-forge`
- GitHub：`gary1033/signal-forge`
- 主線：Phase 工作流可切換 `backtest` 與 `live`。
- `backtest`：優先 deterministic artifacts、regression tests、報表可稽核性。
- `entry-edge`：支援單一固定持有期，也可用 `--hold-bars-list` 輸出多持有期 comparison JSON/Markdown。
- `multi_stock_entry_edge_sweep.py`：支援多檔股票、多策略、多持有期一次 sweep，避免只看單一標的 PF。
- `multi_stock_target_state_sweep.py`：支援多檔股票、多策略、1x / 2x / 3x 成本壓力與最大回撤歸因的完整持倉 target-state sweep。
- `vwap-reversion`：可選 `--vwap-regime-filter`，用 `close >= SMA` 阻擋強下跌中的新 long entry。
- `absolute-momentum`：長期趨勢持有 compare-only 候選，要求回看報酬為正且收盤站上長期 SMA。
- `volatility-target`：可選風控 wrapper，只在 realized volatility 過高時縮小 target exposure；目前 `absolute-momentum + vol-target` 是 drawdown control compare-only，不是主候選，因為 drawdown attribution 顯示 worst MDD 仍集中在 `2454` 且 trough 當天仍滿倉。
- `drawdown-risk-off`：可選風控 wrapper，用策略層 proxy equity 追蹤單檔回撤並暫時降到 flat；`20%/60` 已 discard，`25%/120` 與 `vol-target 0.40 + dd-risk-off 25%/120` 只保留 compare-only。
- `walk-forward / OOS`：target-state sweep 已支援 `--walk-forward-windows`；2024-2026 樣本外檢查顯示 Absolute Momentum 系列仍缺 benchmark-relative edge，尚未能視為穩定營利主候選。
- `relative-momentum filter`：target-state sweep 已支援 `--relative-momentum-filter`，用跨股票 lookback return top-N 當股票池白名單；2024-2026 OOS 掃描 `lookback=63/126/252` 與 `topN=1/2/3/4/5/7` 後沒有改善 `Beat B&H`，目前只作 compare-only / discard 結論。
- `portfolio rotation`：新增投組層級相對動能輪動工具 `tools\portfolio_rotation_sweep.py`，用 equal-weight buy-and-hold portfolio 作 benchmark，並輸出 IR、tracking error、active MDD、自動 rolling windows、可選 market regime filter、breadth filter、volatility target、逐股 attribution、concentration guard、可選單檔連續入選上限、可選 group cap、可選單成員群組 gate、可選 liquidity gate、group-level attribution 與 group exposure summary；股票池已由 7 檔擴到 14 檔，並暫時擴到 TWSE23 做 concentration diagnostic。`monthly + 21 bars + top3 + breadth 42/min3` 是最高報酬錨點；`top4 + breadth 42/min3 + max consecutive 5 + liquidity 500M/20 bars` 是 execution-aware compare candidate，未調整價 full-window IR 約 `1.521`、MDD 約 `-18.61%`、3x 成本後 IR 約 `1.490`。sector/group cap 沒有解 rolling concentration；group attribution 顯示前三群組 full-window 貢獻約 `89.27%`；dominant group exclusion 顯示固定移除 `shipping`、`electronics` 或 `semiconductor` 都不能同時改善 edge、回撤與 concentration；單成員群組 gate 實測 `min_symbols_per_selected_group=2` 會讓 adjusted `roll02` excess 轉負、IR 約 `-0.994`，因此該設定 discard；TWSE23 可把 max rolling top-3 share 降到約 `65.32%`，但 edge 與回撤惡化；Canary9 held-out universe 未通過，full excess 約 `-0.91%`、MDD 約 `-44.29%`；TWSE14 adjusted batch 版本 full IR 降到約 `1.156`、MDD 惡化到約 `-27.97%`、min rolling IR 只剩約 `0.104`，且 batch manifest 已正式記錄 14 檔、21479 rows、missing adjustment 26；TWSE23 universe audit 顯示 23 檔中只有 16 檔通過歷史長度、流動性與群組成員數，補齊 `1101,2327,2357,2379` adjusted CSV 後可形成 TWSE16 adjusted universe，但同一 `top4 / breadth42-min3 / maxconsec5 / liq500M` adjusted promotion gate 仍是 `compare-only`：full IR `0.863`、3x IR `0.832`、min rolling IR `-1.123`、min rolling excess `-29.26%`、max rolling top3 group share `98.26%`；36 組小網格也全數失敗。新增 `--ranking-skip-bars` 後，`skip10` 可把 TWSE16 adjusted full IR 改到約 `1.186`、3x IR 約 `1.158`、MDD 約 `-27.80%`，但 min rolling IR 仍約 `-0.856`、min rolling excess 約 `-22.55%`、max rolling top3 group share 仍到 `100%`，因此只作 compare-only 錨點；`skip21` discard。新增 `--ranking-mode group-residual` 後，`skip10 + group-residual` full IR 約 `1.059`、3x IR 約 `1.031`、MDD 約 `-35.83%`、min rolling IR 約 `-0.852`、min rolling excess 約 `-22.91%`、max rolling top3 group share 仍到 `100%`，比 `skip10 total-return` 傷害 full-window edge 與回撤，僅保留為 deterministic compare tool，不升級。目前仍不是穩定營利證明。
- `TWSE35 expanded universe`：參考 0050 近期大型股成分補齊 12 檔 raw / processed OHLCV，建立 `TWSE35_adjusted_batch_manifest_20260524.json`（35 檔、53403 rows、missing adjustment 68、skipped rows 2524）。同一 `skip10 + top4 + breadth42/min3 + maxconsec5 + liq500M` adjusted baseline full IR 升到 `1.685`、3x IR `1.668`、min rolling IR `0.429`、min rolling excess `11.33%`，比 TWSE16 明顯改善；但 MDD `-37.80%`、active MDD `-29.98%`、full top3 group share `93.49%`、max rolling top3 group share `100%`，promotion gate 仍是 `compare-only`。`min_symbols_per_selected_group=2` 在 TWSE35 也失敗，min rolling IR 轉為 `-1.482`、min rolling excess `-37.95%`，因此硬擋單成員群組不是主規則。
- `realized group contribution gate`：`portfolio_rotation_sweep.py` 已支援 `--group-contribution-lookback-bars` 與 `--max-group-contribution-share`，只用已完成持倉貢獻在下一次 rebalance 暫時排除 dominant group。TWSE35 adjusted `gcontrib21/share0.90` full IR 提到 `1.742`、3x IR `1.721`，MDD 改到 `-32.91%`，但 min rolling IR 轉為 `-0.022`、min rolling excess `-5.93%`，max rolling top3 group share 仍約 `98.08%`；promotion gate 仍是 `compare-only`，所以此 gate keep as tool、discard as current strategy upgrade。
- `live`：只產生 dry-run `OrderIntent`，安全邊界由 `LIVE_DRY_RUN_ONLY` 鎖住。
- 最新整理基線：readiness score 目標仍為 `110`，固定 guard 是 `python -m unittest discover -s tests` 與 `git diff --check`。

## 筆記分工

| 區塊 | 用途 |
|---|---|
| `01-架構/` | 說明 SignalForge 的模組、資料流、PhaseMode、呼叫入口與 live dry-run 安全邊界。 |
| `02-規劃/` | 放大框架方向、Phase 分期、資料準備、策略蒸餾規則、回測評估準則與下一步 backlog。 |
| `策略筆記/` | 一種策略一份筆記，包含策略假設、進出場條件、風險、圖片解說。 |
| `03-程式疊代/` | 保存程式與 artifact contract 的疊代紀錄。 |
| `04-實驗記錄/` | 保存 automation / backtest / 資料實驗結果。 |

## Push 前同步契約

每次準備 push 前，先以這個 Obsidian 資料夾為主來源，將目前整理後的筆記與策略圖片同步到 repo：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
cd C:\Projects\signal-forge
# 清空 docs 後複製 Obsidian SignalForge 筆記進 docs
```

同步後再跑固定驗證：

```powershell
$env:PYTHONPATH = "src"
python tools\phase_readiness_score.py
python -m unittest discover -s tests
git diff --check
```

## Live 安全邊界

```mermaid
flowchart TD
    A["OHLCV CSV"] --> B["Strategy.generate_signals()"]
    B --> C{"PhaseMode"}
    C -->|backtest| D["BacktestExecutionAdapter"]
    C -->|live| E["LiveExecutionAdapter"]
    D --> F["EntryEdgeEvaluator"]
    F --> G["summary / markdown / signals CSV / trace summary"]
    E --> H["OrderIntent"]
    H --> I["dry_run=True"]
    H --> J["submitted=False"]
    H --> K["LIVE_DRY_RUN_ONLY"]
```
