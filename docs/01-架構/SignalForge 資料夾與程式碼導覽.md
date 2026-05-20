---
title: SignalForge 資料夾與程式碼導覽
tags:
  - project/SignalForge
  - architecture
  - code-map
status: active
updated: 2026-05-21
aliases:
  - SignalForge Code Map
  - SignalForge 程式碼導覽
---

# SignalForge 資料夾與程式碼導覽

這份筆記是閱讀 repo 時的程式碼地圖，說明每個主要資料夾與 Python 模組的責任。它不記錄策略績效，也不取代 [[SignalForge 架構總覽|架構總覽]]；策略研究請看 [[../策略筆記/策略筆記索引|策略筆記索引]]，Phase 變更脈絡請看 [[../03-程式疊代/Phase 程式疊代紀錄|Phase 程式疊代紀錄]]。

> [!warning]
> SignalForge 目前仍是研究與回測工具。`live` 路徑只能產生 dry-run order intent，不接 broker、不讀 credential、不送真實訂單。

## Repo 根目錄

| 路徑 | 內容 | 維護重點 |
|---|---|---|
| `AGENTS.md` | Codex 與夜間 automation 的操作守則。 | 修改 workflow、驗證命令、文件同步規則時才更新。 |
| `README.md` | 專案入口說明與基本使用方式。 | 對外說明要保持簡短，細節放在 Obsidian / `docs\`。 |
| `pyproject.toml` | Python package metadata 與 CLI script 設定。 | 若改 CLI entry point、package discovery 或依賴才更新。 |
| `.gitignore` | 排除 generated reports、cache 與本機環境檔。 | 不應把回測輸出、credential 或本機暫存納入 Git。 |
| `.gitattributes` | Git 文字檔處理規則。 | 維持跨平台換行與文字偵測穩定。 |
| `data\` | 範例與本機資料輸入區。 | 可放 deterministic sample；大型或私有資料不應進 Git。 |
| `examples\` | 使用範例與 demo 入口。 | 保持和 CLI public contract 一致。 |
| `reports\` | generated artifacts 的輸出位置。 | 通常是本機產物，不作為 source of truth。 |
| `src\` | production package 原始碼。 | 所有可匯入的正式程式碼都從這裡進入。 |
| `tests\` | `unittest` regression suite 與 test-only helpers。 | 測試替身留在 `tests\helpers.py`，不要搬進 production code。 |
| `tools\` | 維護與 readiness 工具。 | 放 deterministic、可重跑的本機工具，不放產品邏輯。 |
| `docs\` | Obsidian `SignalForge` 筆記的 repo mirror。 | 同步方向固定為 Obsidian -> repo `docs\`。 |

## `src\signal_forge\` 套件入口

| 檔案 | 責任 | 使用時機 |
|---|---|---|
| `__init__.py` | 對外 re-export 主要 public API，例如 Phase runner、策略與資料結構。 | 使用者用 `from signal_forge import ...` 時的相容入口。 |
| `market_data.py` | 舊 import path 的薄 wrapper，轉出 `core.market_data`。 | 保留 `from signal_forge.market_data import Bar` 等既有用法。 |
| `strategy.py` | 舊 import path 的薄 wrapper，轉出 `core.strategy` 與相關 strategy contract。 | 保留既有 strategy 匯入路徑。 |
| `entry_edge.py` | 舊 import path 的薄 wrapper，轉出 `backtesting.entry_edge`。 | 保留舊版 entry-edge API import。 |
| `backtester.py` | 舊 import path 的薄 wrapper，轉出 `backtesting.backtester`。 | 保留 legacy `Backtester` import。 |
| `data_fetch.py` | 舊 import path 的薄 wrapper，轉出 `data.fetch`。 | 保留舊版 data fetch command / helper import。 |
| `indicators.py` | 舊 import path 的薄 wrapper，轉出 `core.indicators`。 | 保留既有 indicator 匯入路徑。 |

這一層的目標是相容，不應放新業務邏輯。新增 production behavior 時，優先放到下方子套件，再由這裡 re-export。

## `src\signal_forge\core\`

`core` 是所有工作流共用的基礎層，不應依賴 CLI、reporting 或 Phase runner。

| 檔案 | 責任 | 主要概念 |
|---|---|---|
| `__init__.py` | 集中 re-export core public API。 | 讓其他子套件用穩定路徑匯入 core 類型。 |
| `market_data.py` | 定義 `Bar`、CSV 載入、OHLCV 欄位驗證與 market data invariant。 | timestamp、open/high/low/close/volume 的資料邊界。 |
| `indicators.py` | 提供 SMA、VWAP、RSI 等策略會用到的純函式 indicator。 | 不保存狀態，輸入序列、輸出序列。 |
| `strategy.py` | 定義 `Signal`、`Strategy`、`StrategyDecision`、`BarByBarStrategy` 與 reason normalization。 | 策略輸出 contract 與逐 bar 模板流程。 |
| `signals.py` | 提供 `SignalDigest`、`generate_validated_signals(...)`、`build_signal_digests(...)`。 | Phase backtest 中「只產生一次 signals」的共同資料流。 |

## `src\signal_forge\strategies\`

`strategies` 放可由 CLI 或測試實際選用的策略實作。策略檔只描述訊號邏輯，不負責 artifact、CLI parser 或資料下載。

| 檔案 | 責任 | 備註 |
|---|---|---|
| `__init__.py` | re-export 內建策略與 registry helper。 | 對外匯入策略時的 package 入口。 |
| `registry.py` | 依 strategy name 與 CLI option 建立策略物件。 | CLI 與測試應透過 registry 建構策略，避免分散 factory。 |
| `sma_crossover.py` | SMA fast / slow crossover long-only 策略。 | 主要驗證 moving average 趨勢切換假設。 |
| `vwap_reversion.py` | VWAP reversion 策略。 | 主要驗證價格偏離 rolling VWAP 後的均值回歸假設。 |
| `confluence_score.py` | 多因子 confluence score 策略。 | 結合趨勢、VWAP、RSI、volume 等訊號形成 score。 |
| `volume_filter.py` | `VolumeFilteredStrategy` wrapper。 | 只在 CLI 啟用 `--volume-filter` 時包住原策略輸出。 |

## `src\signal_forge\backtesting\`

`backtesting` 負責研究型回測計算，不負責 CLI argument parsing，也不直接寫 Obsidian 筆記。

| 檔案 | 責任 | 主要輸出 |
|---|---|---|
| `__init__.py` | re-export backtesting public API。 | entry-edge evaluator 與 legacy backtester。 |
| `entry_edge.py` | 定義 `EntryEdgeEvaluator` 與 trade log / summary 計算。 | 支援 `run_from_signals(...)`，讓 Phase 使用 precomputed signals。 |
| `backtester.py` | 保留 legacy `Backtester`。 | 舊測試與舊 import path 的相容層。 |

## `src\signal_forge\phase\`

`phase` 是目前主工作流，把 data、strategy、backtesting、reporting 串成可重跑的研究流程。

| 檔案 | 責任 | 維護重點 |
|---|---|---|
| `__init__.py` | re-export Phase public API，取代舊 `signal_forge.phase` 單檔。 | 保持 `from signal_forge.phase import ...` 可用。 |
| `config.py` | 定義 `PhaseMode`、`PhaseConfig` 與 mode invariant。 | `live` 必須 dry-run，`backtest` 不接受 dry-run。 |
| `intents.py` | 定義 `OrderIntent` 與 live dry-run safety note。 | 不得新增真實送單能力。 |
| `results.py` | 定義 Phase 執行結果資料結構。 | 讓 runner 與 reporting 之間用清楚型別交接。 |
| `adapters.py` | 實作 `BacktestExecutionAdapter` 與 `LiveExecutionAdapter`。 | backtest 只呼叫一次 strategy，再重用同一份 signals。 |
| `runner.py` | 實作 `PhaseRunner`，負責依 `PhaseConfig` 分派 adapter 與寫出 artifacts。 | Phase workflow 的主要 orchestration 入口。 |

## `src\signal_forge\reporting\`

`reporting` 管理 artifact serialization、validation 與 markdown rendering。它應依輸入資料產生 deterministic output，不應重新計算策略 signals。

| 檔案 | 責任 | 備註 |
|---|---|---|
| `__init__.py` | re-export reporting public API。 | 保持 `from signal_forge.reporting import write_phase_outputs` 可用。 |
| `paths.py` | 集中 output path 與檔名組裝邏輯。 | 避免 CLI、Phase、tests 各自硬組檔名。 |
| `entry_edge.py` | Entry Edge summary、markdown、trade log 的 writer API。 | 專注 entry-edge artifact。 |
| `phase.py` | Phase summary、signals CSV、trace summary、markdown 的 writer API。 | Phase artifact 的主要入口。 |
| `signal_digest.py` | Signal digest CSV 與 trace summary builder / serializer。 | trace summary 應由 signal digest 穩定推導。 |
| `validators.py` | artifact ordering、reason、timestamp、position invariant 驗證。 | 新增 schema guard 時優先放這裡。 |
| `markdown.py` | Markdown 報表 rendering helper。 | exact-text regression test 要鎖住這層輸出。 |
| `_legacy.py` | 暫存原 reporting 單檔拆分前的核心實作。 | 只作相容與漸進搬移，不應繼續膨脹。 |

## `src\signal_forge\data\`

`data` 處理免費資料下載、正規化與 manifest 輸出。它應產生固定 CSV schema，讓後續 backtest 可以 deterministic 重跑。

| 檔案 | 責任 | 備註 |
|---|---|---|
| `__init__.py` | re-export data fetch public API。 | 給 CLI 與相容 wrapper 使用。 |
| `fetch.py` | 實作 data provider、normalizer、CSV / manifest 寫出。 | 不讀 credential，不接付費 broker API。 |

## `src\signal_forge\cli\`

`cli` 只負責命令列介面、參數轉型、呼叫正式 API 與輸出使用者訊息。策略語意、回測計算與 artifact schema 不應散在 CLI。

| 檔案 | 責任 | 備註 |
|---|---|---|
| `__init__.py` | 提供 `main` public entry。 | 保持 `from signal_forge.cli import main` 可用。 |
| `__main__.py` | 支援 `python -m signal_forge.cli`。 | 只呼叫 package entry。 |
| `parser.py` | 建立 argparse parser 與 subcommands。 | CLI 參數新增或調整時優先看這裡。 |
| `strategy_options.py` | 集中 strategy 與 volume filter 參數 glue。 | 避免 `entry-edge` / `phase` 重複定義策略選項。 |
| `commands.py` | 實作 `fetch-data`、`entry-edge`、`phase` command handler。 | 將 parser 結果轉成正式 API 呼叫。 |

## `tests\`

`tests` 只放 regression 與 test-only helper。測試替身、sample bars、CSV writer 應集中在 `tests\helpers.py`，不要搬進 `src\`。

| 檔案 | 驗證範圍 |
|---|---|
| `helpers.py` | 共用 sample bars、CSV writer 與測試策略替身。 |
| `test_market_data.py` | `Bar`、CSV 載入與 market data validation。 |
| `test_indicators.py` | indicator 純函式輸出。 |
| `test_strategy_template.py` | `BarByBarStrategy` 模板與逐 bar contract。 |
| `test_strategy_factory.py` | strategy registry / factory glue。 |
| `test_strategy_regression.py` | 既有策略語意 regression。 |
| `test_volume_filter.py` | volume filter wrapper 行為。 |
| `test_entry_edge.py` | entry-edge 評估、trade log 與 precomputed signals API。 |
| `test_backtester.py` | legacy backtester 相容行為。 |
| `test_phase.py` | Phase backtest / live adapters、artifact 與 dry-run invariant。 |
| `test_reporting.py` | reporting writer、validator、markdown 與 trace summary。 |
| `test_cli.py` | CLI parser、commands 與輸出 contract。 |
| `test_data_fetch.py` | data fetch normalizer / manifest 行為。 |
| `test_compatibility.py` | 舊 public import path 與 package re-export 相容性。 |

## `tools\`

| 檔案 | 責任 | 使用方式 |
|---|---|---|
| `phase_readiness_score.py` | 計算 bounded autoresearch 的 deterministic readiness score。 | 每輪固定執行，目標分數維持 `110`。 |

## 建議閱讀順序

1. 先讀 [[SignalForge 架構總覽|架構總覽]]，掌握 Phase、Entry Edge、SignalDigest 與 live dry-run 邊界。
2. 讀 `src\signal_forge\core\market_data.py`、`core\strategy.py`、`core\signals.py`，確認資料與 signal contract。
3. 讀 `src\signal_forge\strategies\registry.py` 與目標策略檔，理解策略如何被 CLI 建立。
4. 讀 `src\signal_forge\backtesting\entry_edge.py`，確認 trade log 與 summary 如何由 signals 推導。
5. 讀 `src\signal_forge\phase\config.py`、`phase\adapters.py`、`phase\runner.py`，看 Phase workflow 如何串接。
6. 讀 `src\signal_forge\reporting\phase.py`、`reporting\signal_digest.py`、`reporting\validators.py`，理解 artifact schema 與 validation。
7. 最後讀 `src\signal_forge\cli\parser.py`、`cli\strategy_options.py`、`cli\commands.py`，確認使用者輸入如何接到正式 API。

## 修改時的放置原則

- 新的 shared data type 或 validation：放 `core\`。
- 新策略或策略 wrapper：放 `strategies\`，並更新 registry 與策略筆記。
- 新回測評估邏輯：放 `backtesting\`。
- Phase mode、adapter 或 workflow：放 `phase\`。
- Artifact 寫出、schema validation、markdown：放 `reporting\`。
- CLI 參數與命令處理：放 `cli\`。
- 測試替身與 fixture：放 `tests\helpers.py`。
- 相容 import path：只在 `src\signal_forge\*.py` wrapper re-export，不新增業務邏輯。
