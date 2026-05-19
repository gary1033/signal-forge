# SignalForge Phase Roadmap

這份路線圖是 autoresearch 循環的主紀錄。每 15 分鐘的更新都要讓程式碼、路線與筆記同步前進，不只改程式，也要留下方法、驗證命令與下一步。

## 大方向

SignalForge 的 Phase 架構要同時支援兩種模式：

- `backtest`：真正執行回測、產生 metrics、report、trade log，是目前唯一允許做完整驗證的模式。
- `live`：只保留介面與資料結構，不接券商、不送單、不連外部交易 API；等回測架構穩定、測試充足後才考慮接入。

第一階段的重點不是把 live trading 做出來，而是避免未來接入時必須重寫整個 pipeline。也就是先把 phase、execution adapter、order intent、result/report 的邊界切清楚。

## 建議 Phase 切換設計

核心概念：

- `PhaseMode`：`backtest` 或 `live`。
- `PhaseConfig`：記錄資料來源、策略、交易方向、成本、持有規則與 mode。
- `PhaseRunner`：讀取 config，根據 mode 選擇 execution adapter。
- `BacktestExecutionAdapter`：呼叫現有 `EntryEdgeEvaluator` 或後續完整回測器。
- `LiveExecutionAdapter`：只產生 order intent / dry-run event，不送單。
- `PhaseReport`：統一輸出，不論 backtest 或 live dry-run 都能被 README、roadmap、研究筆記引用。

## Autoresearch 三小時目標

12 個 15 分鐘 heartbeat，每次做一個聚焦 iteration：

1. 建立 phase mode 型別與設定資料結構。`2026-05-19 11:53` 完成：新增 `PhaseMode`、`PhaseConfig` 與 live dry-run guard。
2. 建立 backtest adapter，接上現有 entry-edge evaluator。
3. 建立 live adapter stub，只輸出 intent，不接交易 API。
4. CLI 增加 phase/backtest 入口，保留 live dry-run 入口。
5. 報告輸出補 phase mode 與 adapter metadata。
6. 測試 backtest mode 能維持既有結果。
7. 測試 live mode 不會送單，只產生 dry-run intent。
8. 補 failure mode：未知 mode、缺資料、live 未啟用。
9. 更新 README 的 PowerShell 操作流程。
10. 更新策略蒸餾模板，把 phase mode 與 live stub 欄位加進去。
11. 補一份方法筆記，記錄 backtest/live 邊界與不接 broker 的理由。
12. 收斂測試、文件、roadmap，輸出最終 3 小時摘要。

## Autoresearch 執行規格

每輪 heartbeat 使用 `$autoresearch` 的 bounded iteration：

- Goal：提高 SignalForge phase readiness，讓 phase 可在 `backtest` 與 `live` 兩種模式之間切換；live 只保留介面與 dry-run intent。
- Scope：`src/signal_forge/**/*.py`、`tests/**/*.py`、`docs/**/*.md`、`README.md`、`tools/**/*.py`。
- Metric：`python tools\phase_readiness_score.py`，分數越高越好。
- Verify：`python tools\phase_readiness_score.py`。
- Guard：`$env:PYTHONPATH='src'; python -m unittest discover -s tests`。
- Iterations：每次 heartbeat 只跑 1 iteration。
- Record：每輪更新 `docs/phase-roadmap.md` 或相關 docs，並在可行時用 `experiment:` commit 保存成功變更。

## 接入真實交易前的硬門檻

live mode 只能在以下條件都滿足後才考慮接入外部交易 API：

- backtest mode 有穩定 PhaseRunner 與 adapter tests。
- strategy signal、order intent、execution result 已分層。
- report 可同時記錄 backtest result 與 live dry-run intent。
- 所有 live tests 都證明不會送出真實訂單。
- README 明確標示本專案不是投資建議，也不是自動交易系統。

## 迭代紀錄

詳細方法、程式碼、驗證命令、結果與下一步記錄在 `docs/phase-iteration-log.md`。
