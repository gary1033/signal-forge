# SignalForge Phase 路線圖

這份路線圖用來驅動 bounded autoresearch。目標是在維持 Phase readiness 高分的同時，明確保留 `backtest` 與 `live` 的安全分界。

## 方向

- `backtest`：優先穩定、可重複、可驗證；輸出要有固定 contract，方便 regression test。
- `live`：回測穩定前只允許 dry-run；只產生 order intent，不接 broker、不讀 API key、不送真實訂單。

## 型別與架構（keyword: PhaseMode）

- `PhaseMode`：`backtest` / `live`
- `PhaseConfig`：共用設定；`dry_run` 由 mode 推導，`backtest=False`、`live=True`
- `PhaseRunner`：依照 mode 路由執行
  - `BacktestExecutionAdapter`：回測執行路徑
  - `LiveExecutionAdapter`：live dry-run 路徑，只產生 order intent
- `OrderIntent`：`safety_note` 含 `LIVE_DRY_RUN_ONLY`，讓不同 OS / encoding 下都能穩定稽核

## 已完成里程碑

2026-05-19 已完成：

1. Phase mode 與設定：加入 `PhaseMode`、`PhaseConfig`，並建立 live dry-run guard。
2. Phase runner 與 adapters：加入 `PhaseRunner`、`BacktestExecutionAdapter`、`LiveExecutionAdapter`。
3. Live adapter stub：只產生 dry-run `OrderIntent`，`submitted=False`。
4. CLI：支援 `phase --mode backtest|live`，其中 live 永遠是 dry-run。
5. Phase report：輸出 mode、adapter、dry-run metadata。
6. Failure modes：補上 unknown mode、hold period、bar validation 測試。
7. PowerShell workflow：文件化 Phase 執行方式。
8. 回測 regression：固定 bars 對應穩定 summary / markdown contract。
9. Phase report：驗證 summary JSON schema。
10. Reporting：JSON key ordering 固定，讓 diff deterministic。
11. 回測 portability：Entry Edge report 與 CLI strategy spec 改成 Windows 友善文字。
12. 回測 determinism：Phase summary JSON exact-text contract（sorted keys + newline）。
13. 回測 determinism：Phase markdown exact-text contract（固定文字 + trailing newline）。
14. Phase report：加強 cross-field invariants；live 只能 dry-run，backtest 必須有 `entry_edge`。
15. Live determinism：Phase summary + markdown exact-text contract，確認 order intent 安全。
16. 回測 portability：warning / sample risk 文字避免 encoding-dependent garbling。
17. 回測 determinism：Entry Edge outputs contract（summary JSON、markdown、trade log CSV）。
18. 回測 portability：Entry Edge `failure_reason` 改成 deterministic 文字。
19. CLI correctness：`backtest` 使用 `dry_run=False`，`live` 使用 `dry_run=True`。
20. 回測 trace visibility：Phase report 產生 deterministic `*_signals.csv`。
21. Mode semantics：`PhaseConfig` 預設由 `mode` 推導並驗證 `dry_run`。
22. 回測 trace visibility：`*_signals.csv` 加入 deterministic `is_long_entry`。
23. 回測 digest：`*_signals.csv` 加入 deterministic `is_flatten`。
24. Live output determinism：Phase report markdown 固定 contract，仍只允許 dry-run intent。
25. 回測 digest：`*_signals.csv` 加入 deterministic `position_change`。
26. 回測 trace visibility：加入 deterministic `*_trace_summary.json`。
27. 回測 trace visibility：`*_trace_summary.json` 加入 first/last timestamp。
28. 回測 trace safety：驗證 signal digest ordering invariants。
29. 回測 visibility：Phase markdown 顯示 digest invariants summary。
30. 回測 visibility：Phase markdown 顯示 top reasons frequency，方便稽核。
31. 回測 digest determinism：強制 `SignalDigest.reason` 為 ASCII-only、single-line、non-empty。
32. Phase adapter：將 signal `reason` 正規化成 deterministic ASCII-only contract。
33. Phase adapter：限制正規化後的 `reason` 最大長度，避免 artifact 膨脹。
34. Phase CLI：改由 `PhaseConfig` 推導 `dry_run`，移除重複 wiring。

## 下一步候選

- 繼續補強回測 trace / coverage visibility，但不引入真實交易整合。
- 只在 deterministic 且 test-covered 的前提下擴充 backtest artifact。
- `live` 繼續維持 dry-run only，直到回測穩定且另行審核 broker 介面。
