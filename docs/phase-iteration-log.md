# Phase Autoresearch Iteration Log

這份筆記記錄每 15 分鐘 heartbeat 的方法、程式碼變更、驗證命令、結果與下一步。

## 2026-05-19 11:53 Asia/Taipei

- 方法：先完成 roadmap 第 1 項，建立 `PhaseMode` 與 `PhaseConfig`，讓後續 adapter 與 runner 有共同設定邊界。
- 程式碼：新增 `src/signal_forge/phase.py`，匯出 `PhaseConfig`、`PhaseMode`、`parse_phase_mode`，並新增 `tests/test_phase.py`。
- 安全邊界：`live` mode 目前只能 `dry_run=True`；若設定 `dry_run=False` 會直接拒絕，避免任何真實交易接入。
- 驗證命令：`python tools\phase_readiness_score.py`；`$env:PYTHONPATH='src'; python -m unittest discover -s tests`。
- 結果：本輪目標是讓 readiness score 增加並維持全部測試通過。
- 下一步：建立 `PhaseRunner` 與 execution adapter skeleton，先接 `BacktestExecutionAdapter`，再補 `LiveExecutionAdapter` dry-run intent。

## 2026-05-19 12:08 Asia/Taipei

- 方法：完成 roadmap 第 2、3、6、7 項的最小可驗證 adapter skeleton，先把 execution 邊界接起來，不碰 CLI 與外部交易接入。
- 程式碼：在 `src/signal_forge/phase.py` 新增 `PhaseRunner`、`BacktestExecutionAdapter`、`LiveExecutionAdapter`、`PhaseExecutionResult` 與 `OrderIntent`。
- 安全邊界：`LiveExecutionAdapter` 只產生 dry-run order intent；`OrderIntent.submitted` 固定為 `False`，`safety_note` 標示 `不送單`。
- 測試：更新 `tests/test_phase.py`，確認 backtest mode 會產生 entry-edge result，live mode 僅回傳 dry-run intent 且不送單。
- 驗證命令：`python tools\phase_readiness_score.py`；`$env:PYTHONPATH='src'; python -m unittest discover -s tests`；`git diff --check`。
- 結果：本輪目標是讓 readiness score 增加並維持全部測試通過。
- 下一步：替 CLI 加上 `phase --mode backtest|live` 入口，live 入口仍只能 dry-run。

## 2026-05-19 12:23 Asia/Taipei

- 方法：完成 roadmap 第 4 項，新增 CLI `phase` subcommand，讓 PhaseRunner 可從 PowerShell 直接切換 `backtest` 與 `live`。
- 程式碼：更新 `src/signal_forge/cli.py`，新增 `phase --mode backtest|live`，並復用現有 strategy builder 與 CSV loader。
- 安全邊界：`phase --mode live` 仍由 `PhaseConfig(dry_run=True)` 與 `LiveExecutionAdapter` 執行，只列出 dry-run intent，不接 broker、不送單。
- 測試：新增 `tests/test_cli.py`，確認 backtest CLI 會列出 entry-edge trades，live CLI 會列出 `dry_run=True`、`submitted=False`。
- 驗證命令：`python tools\phase_readiness_score.py`；`$env:PYTHONPATH='src'; python -m unittest discover -s tests`；`git diff --check`。
- 結果：本輪目標是讓 readiness score 增加並維持全部測試通過。
- 下一步：讓 phase report / CLI output 補上 adapter metadata，並更新 README 的 PowerShell 操作流程。

## 2026-05-19 12:38 Asia/Taipei

- 方法：完成 roadmap 第 5 項，讓 phase execution result 有獨立 Markdown/JSON 報告，不只印在 CLI stdout。
- 程式碼：在 `src/signal_forge/reporting.py` 新增 `write_phase_outputs()`、`PhaseReportPaths`、phase summary JSON 與 phase markdown report。
- CLI：`phase` subcommand 新增 `--output-dir` 與 `--run-name`，並印出 `phase_markdown`、`phase_summary_json` 路徑。
- 安全邊界：live phase report 只序列化 dry-run `OrderIntent`，包含 `submitted=False` 與 `不送單` safety note，不包含 broker、API key 或送單介面。
- 測試：更新 `tests/test_reporting.py` 與 `tests/test_cli.py`，確認 phase metadata、adapter name、dry-run intent 與 submitted 狀態都會被寫入/印出。
- 驗證命令：`python tools\phase_readiness_score.py`；`$env:PYTHONPATH='src'; python -m unittest discover -s tests`；`$env:PYTHONPATH='src'; python -m signal_forge.cli phase --csv data\sample\phase1_demo_ohlcv.csv --mode live --strategy sma-crossover --fast-window 2 --slow-window 3 --output-dir reports\generated --run-name phase-live-demo`；`git diff --check`。
- 結果：本輪完成 planned milestone，readiness score 預期維持 110 並保持測試全綠。
- 下一步：更新 README 的 PowerShell phase 操作流程，並把 phase mode 欄位加進策略蒸餾模板。

## 2026-05-19 12:53 Asia/Taipei

- 方法：完成 roadmap 第 9、10 項，把已完成的 `phase --mode backtest|live` 行為寫進使用流程與策略蒸餾模板。
- 文件：更新 `README.md`，加入 PowerShell phase backtest/live dry-run 範例、Phase output 檔名與 adapter 邊界說明。
- 模板：更新 `docs/phase1-strategy-intake-template.md`，新增 Phase 執行紀錄欄位，要求記錄 mode、adapter、order intent 與 live dry-run 安全確認。
- 安全邊界：本輪沒有修改 live execution code；文件明確保留 `LiveExecutionAdapter` 只產生 dry-run intent，且不接 broker、不讀交易 API key、不送單。
- 驗證命令：`python tools\phase_readiness_score.py`；`$env:PYTHONPATH='src'; python -m unittest discover -s tests`；`$env:PYTHONPATH='src'; python -m signal_forge.cli phase --csv data\sample\phase1_demo_ohlcv.csv --mode live --strategy sma-crossover --fast-window 2 --slow-window 3 --output-dir reports\generated --run-name phase-live-demo`；`git diff --check`。
- 結果：本輪完成 planned milestone，readiness score 應維持 110 並保持 guard 全綠。
- 下一步：補一份方法筆記，說明 backtest/live 邊界、dry-run intent 與暫不接 broker 的工程理由。
