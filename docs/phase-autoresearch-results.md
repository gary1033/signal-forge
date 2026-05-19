# Phase Autoresearch Results

這份文件是 SignalForge autoresearch 的可見結果總表。前半段記錄 phase-mode 建置成果；後續 automation 已擴成每 15 分鐘推進量化策略、演算法、回測品質、程式完整度與研究筆記。

## 目前狀態

- Branch：`main`
- Remote：`origin/main`
- 最新 commit：以 `git log -1 --oneline` 為準；本文件的 run log 逐輪記錄 commit/push。
- Readiness score：`110`
- Guard：`27 tests OK`
- Live mode 狀態：只允許 dry-run order intent；不接 broker、不讀交易 API key、不呼叫外部交易 API、不送真實訂單。

## 結果在哪裡看

- 路線總表：`docs/phase-roadmap.md`
- 每 15 分鐘方法與驗證紀錄：`docs/phase-iteration-log.md`
- 本總表：`docs/phase-autoresearch-results.md`
- 使用方式與 PowerShell 指令：`README.md`
- 策略蒸餾模板：`docs/phase1-strategy-intake-template.md`
- CLI 產生的本機報告：`reports/generated/`
- Codex raw automation transcript：`C:\Users\gary1\.codex\sessions\2026\05\19\rollout-2026-05-19T10-08-01-019e3dfd-751d-7b33-b100-2a92001dea60.jsonl`

`reports/generated/` 是本機執行 CLI smoke 或研究命令後的輸出位置，包含 Markdown、JSON 與 trade log。這些檔案是研究產物，不是 autoresearch 的主要紀錄；autoresearch 的可追蹤紀錄以 docs 與 git commit 為主。

Codex heartbeat automation 目前不會在 `C:\Users\gary1\.codex\automations\signalforge-phase-autoresearch\` 下面建立每輪結果檔；該資料夾只有 `automation.toml` 排程設定。完整 stdout、tool calls、final heartbeat XML 會被寫進 target thread 的 session JSONL。後續 wakeup 已要求同步更新本文件的 run log，讓可讀結果留在 repo 內。

## 目前排程政策

- Automation ID：`signalforge-phase-autoresearch`
- Schedule：每 15 分鐘一次，持續執行，直到手動暫停或刪除。
- 每輪目標：思考並實作一個聚焦改善，範圍包含量化交易策略演算法、backtest 正確性、報告/metric、CLI、測試、文件與整體程式品質。
- 每輪筆記：更新本文件的 run log；行為或路線改變時同步更新 `docs/phase-iteration-log.md` 或 `docs/phase-roadmap.md`。
- 每輪追蹤：成功保留的程式或筆記變更都要建立小型 `experiment:` commit 並 push 到 `origin`。
- 安全邊界：仍禁止 broker connection、外部交易 API、credential lookup 與真實下單；live mode 只能 dry-run intent。

## Automation Run Log

| Wakeup | Milestone | Metric | Guard | Decision | Commit / Push | Notes |
|---|---|---|---|---|---|---|
| 2026-05-19 11:53 | Phase mode config | 45 -> 55 | pass | keep | `3231ecb`, pushed | `docs/phase-iteration-log.md` |
| 2026-05-19 12:08 | Phase runner adapters | 55 -> 100 | pass | keep | `b22a700`, pushed | `docs/phase-iteration-log.md` |
| 2026-05-19 12:23 | Phase CLI mode | 100 -> 110 | pass | keep | `ace3dc7`, pushed | `docs/phase-iteration-log.md` |
| 2026-05-19 12:38 | Phase report metadata | 110 -> 110 | pass | keep planned milestone | `24c2907`, pushed | `docs/phase-iteration-log.md` |
| 2026-05-19 12:53 | README/template workflow docs | 110 -> 110 | pass | keep planned milestone | `cfa1c5b`, pushed | `docs/phase-iteration-log.md` |
| 2026-05-19 13:08 | Phase failure modes | 110 -> 110 | pass | keep planned milestone | `972685d`, pushed | `docs/phase-iteration-log.md` |
| 2026-05-19 14:56 | Results index visibility | 110 -> 110 | pass | keep support note | `d63b456`, pushed | `docs/phase-autoresearch-results.md` |

## 已保留的 autoresearch commits

| 時間 | Commit | 內容 | 驗證 |
|---|---|---|---|
| 2026-05-19 11:53 | `3231ecb` | 新增 `PhaseMode`、`PhaseConfig` 與 live dry-run guard | score improved；tests OK |
| 2026-05-19 12:08 | `b22a700` | 新增 `PhaseRunner`、backtest/live adapters、dry-run `OrderIntent` | score improved；tests OK |
| 2026-05-19 12:23 | `ace3dc7` | 新增 `phase --mode backtest\|live` CLI | score improved；tests OK |
| 2026-05-19 12:38 | `24c2907` | 新增 phase Markdown/JSON report metadata | planned milestone；tests OK |
| 2026-05-19 12:53 | `cfa1c5b` | 補 README PowerShell workflow 與策略蒸餾模板欄位 | planned milestone；tests OK |
| 2026-05-19 13:08 | `972685d` | 補 phase failure modes 與測試 | planned milestone；27 tests OK |

Baseline commit：`7a4b42d experiment: bootstrap phase autoresearch baseline`。

## 已完成項目

- Phase 可切換 `backtest` / `live`。
- `backtest` 使用 `BacktestExecutionAdapter` 接現有 `EntryEdgeEvaluator`。
- `live` 使用 `LiveExecutionAdapter`，只輸出 dry-run order intent。
- CLI 支援 `phase --mode backtest` 與 `phase --mode live`。
- Phase report 會輸出 mode、adapter、dry-run、entry-edge result 或 order intents。
- 測試覆蓋 backtest routing、live dry-run intent、unknown mode、invalid hold period、缺資料、資料不足與 live 非 dry-run 禁止。
- README、roadmap、iteration log、策略蒸餾模板已同步。

## 待完成項目

- 補一份方法筆記，說明 backtest/live 邊界、dry-run intent 與暫不接 broker 的工程理由。
- 收斂最終 3 小時摘要與下一階段候選清單。

## 最新驗證命令

```powershell
python tools\phase_readiness_score.py
$env:PYTHONPATH='src'; python -m unittest discover -s tests
$env:PYTHONPATH='src'; python -m signal_forge.cli phase --csv data\sample\phase1_demo_ohlcv.csv --mode live --strategy sma-crossover --fast-window 2 --slow-window 3 --output-dir reports\generated --run-name phase-live-demo
```

最新結果：

- `python tools\phase_readiness_score.py` -> `110`
- `python -m unittest discover -s tests` -> `Ran 27 tests ... OK`
- Live CLI smoke -> `dry_run=True`、`submitted=False`
