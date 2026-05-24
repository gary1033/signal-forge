---
title: SignalForge 架構總覽
tags:
  - project/SignalForge
  - architecture
  - trading/backtest
status: active
updated: 2026-05-24
aliases:
  - SignalForge 架構
  - SignalForge Architecture
---

# SignalForge 架構總覽

SignalForge 是研究導向的交易訊號沙盒。它不是把 TradingView / Pine Script 直接搬成可交易系統，而是把腳本背後的 signal、filter、risk rule、exit rule 拆開，轉成可以在 Python 裡驗證的研究假設。

目前主線是 Phase 工作流：同一份 OHLCV CSV、同一個 strategy、同一組參數，必須產生可重複、可比較、可被測試鎖住的 artifacts。這份筆記專注說明架構與安全邊界；策略研究細節放在 [[../策略筆記/策略筆記索引|策略筆記索引]]，規劃方向放在 [[../02-規劃/SignalForge 大框架規劃|大框架規劃]]。

每個資料夾、Python 模組與測試檔案的責任分工，請看 [[SignalForge 資料夾與程式碼導覽|資料夾與程式碼導覽]]；實際 CLI、console script 與 Python API 的呼叫方式，請看 [[SignalForge 呼叫程式方式|呼叫程式方式]]。

> [!warning]
> 本專案只做研究與回測，不構成投資建議。`live` 模式目前只允許 dry-run order intent，不接 broker、不讀 API key、不送真實訂單。

## 核心模組

| 模組 | 位置 | 責任 |
|---|---|---|
| CLI | `src\signal_forge\cli\` | 提供 `fetch-data`、`entry-edge`、`phase` 指令，將 parser、command handler 與 strategy option glue 分開。 |
| Core | `src\signal_forge\core\` | 放 `Bar`、market data validation、indicators、`Strategy` contract、`SignalDigest` 與 signal normalization。 |
| Data fetch | `src\signal_forge\data\` | 下載免費日線資料，輸出 SignalForge 固定 CSV 與 manifest；`data_fetch.py` 保留相容入口。 |
| Strategy | `src\signal_forge\core\strategy.py`、`src\signal_forge\strategies\` | 提供 hook-based `BarByBarStrategy` 模板、strategy registry、entry / risk wrappers，並讓每根 bar 產生一筆 `Signal`。 |
| Entry Edge | `src\signal_forge\backtesting\entry_edge.py` | 第一階段 long-only 固定持有期進場優勢評估；支援 precomputed signals，避免 Phase 重複產生訊號。 |
| Target-state sweep | `tools\multi_stock_target_state_sweep.py` | Phase 2 研究用完整持倉評估工具，跨多股票、多策略與成本壓力比較 target exposure、benchmark relative、風險調整與 turnover。 |
| Portfolio rotation sweep | `tools\portfolio_rotation_sweep.py` | Phase 2 portfolio-level 評估工具，將多檔股票視為同一資金池，檢查相對動能輪動是否勝過 equal-weight buy-and-hold portfolio，並輸出 Information Ratio、tracking error、active max drawdown、自動 rolling windows、可選 market regime filter、breadth filter、volatility target、單檔連續入選上限、group cap、liquidity gate 與逐股選股歸因。 |
| Phase | `src\signal_forge\phase\` | 定義 `PhaseMode`、`PhaseConfig`、`PhaseRunner` 與 backtest/live adapters。 |
| Reporting | `src\signal_forge\reporting\` | 依 entry-edge、phase、signal digest、validator、markdown、paths 拆出 reporting API；`_legacy.py` 暫保留原 artifact contract 實作。 |
| Readiness | `tools\phase_readiness_score.py` | bounded autoresearch 使用的輕量 deterministic readiness metric。 |

## Package 邊界與相容層

2026-05-21 的重構把原本散在 `src\signal_forge\*.py` 的核心流程收斂成子套件，但保留既有 public import path。舊的 `signal_forge.market_data`、`signal_forge.strategy`、`signal_forge.entry_edge`、`signal_forge.backtester`、`signal_forge.data_fetch` 仍可匯入，內部改成薄 wrapper re-export 新位置；`signal_forge.phase`、`signal_forge.reporting`、`signal_forge.cli` 則由單檔改成 package。

最重要的行為修正是 Phase backtest 現在只呼叫一次 `Strategy.generate_signals(...)`。同一份 signals 會同時傳給 `EntryEdgeEvaluator.run_from_signals(...)` 與 `build_signal_digests(...)`，因此 entry-edge trade log、Phase summary、`*_signals.csv` 與 `*_trace_summary.json` 不會因 stateful strategy 或非 deterministic strategy 而彼此不同步。

## Strategy OOP 模板

策略開發目前採用 hook-based OOP 模板。外部 contract 仍是 `Strategy.generate_signals(bars) -> list[Signal]`，因此 `PhaseRunner`、`EntryEdgeEvaluator`、reporting schema 與 CLI 輸出都不需要知道策略內部如何拆分。

模板分工如下：

- `Signal`：每根 bar 的輸出格式，保留 `index`、`timestamp`、`target_position`、`reason`、`score`。
- `StrategyDecision`：策略在單根 bar 的內部決策結果，由 template 轉成 `Signal`。
- `BarByBarStrategy`：負責 `generate_signals()` 的固定流程，包含準備 context、逐根 bar 呼叫 hook、傳入 `previous_target_position`、維持 signal 與 bar 對齊。
- 具體策略只實作 `prepare_context(...)` 與 `decide_bar(...)`，例如 SMA context 放 fast / slow SMA，VWAP context 放 rolling VWAP / rolling std，Confluence context 放 SMA / VWAP / RSI / volume，Absolute Momentum context 放 close 與長期 trend SMA。
- `strategies.registry` 提供 Phase 1 strategy factory；CLI 可用 `sma-crossover`、`vwap-reversion`、`confluence-score`、`absolute-momentum` 建構 long-only 日線策略。
- `VolatilityTargetStrategy` 是風控 wrapper，不改底層策略的 entry reason，只在 realized volatility 高於目標年化波動時把非零 `target_position` 縮小；`max_scale=1.0` 的預設語意是只降曝險、不加槓桿。
- `DrawdownRiskOffStrategy` 是風控 wrapper，用與 target-state backtester 對齊的 proxy equity 追蹤單檔回撤；當本地高點回撤超過門檻時，暫時把非零 target 改成 flat，等待固定 bar 數後重設 high-water mark 再允許進場。

這個模板是工程結構重構，不改變既有策略的交易語意。`VolumeFilteredStrategy` 仍是外層 wrapper，只在 CLI 啟用 `--volume-filter` 時套用。

## PhaseMode 分流

`PhaseMode` 目前只有兩種：

- `backtest`：回測與 artifact 產生路徑，`dry_run=False`。
- `live`：dry-run intent 路徑，`dry_run=True`。

`PhaseConfig` 是 mode semantics 的單一來源。CLI 不應自己維護一份 dry-run 判斷，而是交給 `PhaseConfig.__post_init__()` 推導：

- `mode="backtest"` 時拒絕 `dry_run=True`。
- `mode="live"` 時拒絕 `dry_run=False`，並強制設成 `True`。
- `hold_bars_per_day` 必須為正數。

```mermaid
flowchart TD
    A["CSV OHLCV data"] --> B["load_bars_from_csv"]
    B --> C["validate_bars"]
    C --> D["generate_validated_signals"]
    D --> E{"PhaseConfig.mode"}
    E -->|backtest| F["BacktestExecutionAdapter"]
    E -->|live| G["LiveExecutionAdapter"]
    F --> H["EntryEdgeEvaluator.run_from_signals"]
    H --> I["EntryEdgeResult"]
    F --> J["build_signal_digests"]
    J --> K["*_signals.csv"]
    J --> L["*_trace_summary.json"]
    G --> M["OrderIntent only"]
```

## Backtest 路徑

`BacktestExecutionAdapter` 會先呼叫 strategy 產生 signals，再用 `EntryEdgeEvaluator` 評估 long entry edge。這個階段不是完整投資組合回測，而是在回答：訊號於 bar close 後成立，下一根 bar open 進場，固定持有 `hold_bars_per_day` 後離場，是否有短期進場優勢。

策略可以在 CLI 層套用可選 wrapper。第一個 wrapper 是 `VolumeFilteredStrategy`，啟用 `--volume-filter` 時才生效；它不改原策略本體，而是在原策略輸出 positive target 後，要求 `volume >= sma(volume, volume_window) * volume_multiplier` 才保留 long 狀態。預設不啟用，避免破壞既有回測 contract。

輸出包含：

- Phase summary JSON：固定 schema、排序與 trailing newline。
- Phase markdown：固定文字 contract，顯示 digest invariants、top reasons 與 trace summary 摘要。
- Entry Edge outputs：summary JSON、markdown、trade log CSV。
- `*_signals.csv`：每根 bar 的 signal digest。
- `*_trace_summary.json`：由 signal digest 派生的 counts、timestamp、reason、position buckets 與 hash。

## Target-state 研究路徑

`tools\multi_stock_target_state_sweep.py` 是 Phase 2 研究工具，和 Phase 1 entry-edge 的問題不同。它使用 `Backtester` 按每根 bar 的 `target_position` 做 close-to-close target exposure 回測，用來回答完整持倉規則是否真的比 benchmark 更值得承擔風險。

目前 target-state 報表包含：

- 多股票、多策略與多成本倍率 sweep。
- 策略 total return、CAGR、Sharpe、Sortino、Calmar、max drawdown。
- Buy-and-hold total return、CAGR、max drawdown 與 excess return。
- Trade count、turnover、time in market 與 total cost。
- Aggregate 層級的 positive return count、beat benchmark count、lower drawdown count。
- Drawdown attribution：定位 worst MDD 的股票、peak / trough / recovery 日期、duration / recovery bars，以及 peak-to-trough 平均曝險。
- 可選 `--volatility-target` 風控 overlay，用同一套 target-state 報表檢查「降低曝險」是否真的改善 worst MDD、成本壓力與 benchmark-relative tradeoff。
- 可選 `--drawdown-risk-off` 風控 overlay，用同一套 target-state 報表檢查「單檔回撤狀態下暫時降曝險」是否真的改善 MDD、風險調整與 benchmark-relative tradeoff。
- 可選 `--walk-forward-windows` 分段驗證，用 `label:start:end` 視窗重跑同一批策略 / 成本 / wrapper，並計算相鄰 window 的樣本外報酬、Sharpe 與 benchmark-relative 保留率。

這個工具不接 broker、不產生 order intent，也不改變 `live` dry-run 邊界。它只用於研究完整持倉候選是否值得進一步加入風控、volatility scaling 或 walk-forward 驗證。

`tools\portfolio_rotation_sweep.py` 是另一條 Phase 2 portfolio-level 研究路徑。它不把每檔股票各自回測，而是把同一批股票對齊成共同日期表，依 rebalance frequency 做相對動能排序與等權配置，並用 equal-weight buy-and-hold portfolio 作基準。它也支援預設關閉的 market regime filter、breadth filter、volatility target、單檔連續入選上限、group cap 與 liquidity gate，用同一套 rolling / OOS / active-risk / concentration / liquidity 報表比較不同風控 overlay。這用來避免用逐檔 B&H 指標誤判輪動策略。

## SignalDigest 與 trace summary

`SignalDigest` 是 backtest artifact 的核心中介格式。每根 bar 至少包含：

- `index`
- `timestamp`
- `target_position`
- `position_change`
- `reason`
- `score`
- `is_long_entry`
- `is_flatten`

Reporting 層再從 signals CSV 推導 trace summary，並交叉驗證：

- timestamp 必須遞增且 ISO-8601。
- reason 必須 deterministic、ASCII-only、single-line、non-empty。
- `position_change` 必須等於 target position delta。
- entry / flatten / hold / position bucket counts 必須一致。
- `signal_digest_sha256` 必須和 signals CSV 內容一致。

## Live dry-run 安全邊界

`LiveExecutionAdapter` 目前只允許產生 `OrderIntent`。以下 invariant 不能破壞：

- `dry_run=True`
- `submitted=False`
- `safety_note` 含 `LIVE_DRY_RUN_ONLY`
- 無 broker 連線
- 無 API key / credential 讀取
- 無真實訂單送出

`OrderIntent` 的存在是為了先驗證 live intent schema 與安全稽核，不代表已經開放交易能力。

## 驗證命令

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
cd C:\Projects\signal-forge
$env:PYTHONPATH = "src"
python tools\phase_readiness_score.py
python -m unittest discover -s tests
git diff --check
```

通過條件維持：readiness score `110`、unit tests 全部通過、`git diff --check` clean。
