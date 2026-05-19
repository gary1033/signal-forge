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
