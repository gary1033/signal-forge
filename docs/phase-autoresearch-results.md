# Phase Autoresearch 結果

這份文件彙整目前 Phase readiness、驗證命令與每次 wakeup 的執行紀錄。所有敘述採繁中；程式識別字、CLI 參數、commit SHA 保留原樣。

## 目前狀態

- Branch：`main`
- Remote：`origin/main`
- Readiness score：`110`
- Guard：unit tests 通過
- Live mode：只允許 dry-run order intent（`dry_run=True`、`submitted=False`）

## 驗證命令（PowerShell）

```powershell
python tools\phase_readiness_score.py
$env:PYTHONPATH='src'; python -m unittest discover -s tests
git diff --check
```

## Automation 執行紀錄

| Wakeup（Asia/Taipei） | 里程碑 | Metric | Guard | 決策 | Commit / Push | 備註 |
|---|---|---|---|---|---|---|
| 2026-05-19 16:27 | 文件 encoding 與 readiness needle 整理 | 110 -> 110 | pass | keep | 包含 `50ade1b` | 先把文件恢復成穩定可讀版本 |
| 2026-05-19 16:42 | 穩定 live dry-run marker：`LIVE_DRY_RUN_ONLY` | 110 -> 110 | pass | keep | pushed to `origin/main` | 用穩定 marker 表示安全稽核 invariant |
| 2026-05-19 16:57 | `OrderIntent.safety_note` 改為穩定安全 invariant | 110 -> 110 | pass | keep | pushed to `origin/main` | 避免終端 encoding 影響安全文字 |
| 2026-05-19 17:13 | Backtest Phase report contract regression test | 110 -> 110 | pass | keep | pushed to `origin/main` | 固定 bars 對應穩定 summary / markdown |
| 2026-05-19 17:27 | Phase report summary schema validation | 110 -> 110 | pass | keep | pushed to `origin/main` | 強化 summary JSON contract |
| 2026-05-19 17:42 | Reporting JSON key ordering 固定 | 110 -> 110 | pass | keep | `3d99839` pushed | 讓 report JSON diff deterministic |
| 2026-05-19 18:02 | Entry Edge report label 穩定化 | 110 -> 110 | pass | keep | `d54d9e7` pushed | 改善 Windows 回測報表可讀性 |
| 2026-05-19 18:12 | Phase summary JSON exact-text contract | 110 -> 110 | pass | keep | `c69428c` pushed | 驗證 sorted keys 與 newline |
| 2026-05-19 18:28 | Phase markdown exact-text contract | 110 -> 110 | pass | keep | `773e52b` pushed | 驗證 markdown 固定輸出 |
| 2026-05-19 18:42 | Phase summary live/backtest invariants | 110 -> 110 | pass | keep | pushed to `origin/main` | live 必須 dry-run；backtest 必須有 entry_edge |
| 2026-05-19 18:57 | Live Phase report contract regression test | 110 -> 110 | pass | keep | `55d37ac` pushed | 確認 live markdown / JSON 只含安全 intent |
| 2026-05-19 19:13 | Backtest portability 文字整理 | 110 -> 110 | pass | keep | pushed to `origin/main` | 避免 Windows terminal 顯示亂碼 |
| 2026-05-19 19:29 | Entry Edge outputs deterministic contract | 110 -> 110 | pass | keep | pushed to `origin/main` | 固定 summary / markdown / trade log |
| 2026-05-19 19:42 | Entry Edge `failure_reason` deterministic test | 110 -> 110 | pass | keep | pushed to `origin/main` | 回測失敗原因固定化 |
| 2026-05-19 19:58 | CLI wiring：`dry_run` 反映 mode | 110 -> 110 | pass | keep | pushed to `origin/main` | backtest=False，live=True |
| 2026-05-19 20:14 | Backtest trace visibility：`*_signals.csv` | 110 -> 110 | pass | keep | `bf32c6e` pushed | 每根 bar 的 signal digest |
| 2026-05-19 20:27 | `PhaseConfig` 由 `mode` 推導 `dry_run` | 110 -> 110 | pass | keep | pushed to `origin/main` | 單一語意來源 |
| 2026-05-19 20:42 | Backtest digest 加入 `is_long_entry` | 110 -> 110 | pass | keep | pushed to `origin/main` | test-covered derived field |
| 2026-05-19 20:57 | Backtest digest 加入 `is_flatten` | 110 -> 110 | pass | keep | pushed to `origin/main` | 標示 exit / flatten transition |
| 2026-05-19 21:12 | Live output determinism | 110 -> 110 | pass | keep | pushed to `origin/main` | 固定 live markdown 與 safety invariants |
| 2026-05-19 21:27 | Backtest digest 加入 `position_change` | 110 -> 110 | pass | keep | pushed to `origin/main` | target_position delta |
| 2026-05-19 21:42 | Backtest `*_trace_summary.json` | 110 -> 110 | pass | keep | pushed to `origin/main` | signal-derived counts / reasons summary |
| 2026-05-19 21:57 | Trace summary 加入 timestamp range | 110 -> 110 | pass | keep | pushed to `origin/main` | first / last timestamp |
| 2026-05-19 22:13 | Backtest digest ordering invariants | 110 -> 110 | pass | keep | pushed to `origin/main` | 寫入 artifact 前驗證排序 |
| 2026-05-19 22:27 | Phase markdown digest invariant section | 110 -> 110 | pass | keep | pushed to `origin/main` | 在報表顯示 deterministic invariants |
| 2026-05-19 22:42 | Phase markdown top reasons frequency | 110 -> 110 | pass | keep | pushed to `origin/main` | 增加稽核可讀性 |
| 2026-05-19 22:58 | 強制 `SignalDigest.reason` invariants | 110 -> 110 | pass | keep | pushed to `origin/main` | trimmed、ASCII-only、single-line、non-empty |
| 2026-05-19 23:13 | Phase adapter 正規化 `reason` | 110 -> 110 | pass | keep | pushed to `origin/main` | 防止 strategy reason 破壞 backtest artifacts |
| 2026-05-19 23:28 | 正規化 `reason` 加入最大長度 | 110 -> 110 | pass | keep | pushed to `origin/main` | artifact 更穩定且精簡 |
| 2026-05-19 23:41 | Phase CLI 改依賴 `PhaseConfig` 推導 `dry_run` | 110 -> 110 | pass | keep | `77ca204` pushed | 移除重複 CLI wiring |
| 2026-05-20 01:04 | Trace summary 加入 `hold_count` | 110 -> 110 | pass | keep | `8411af0` pushed | 由 signal digest 派生 deterministic 持倉 bar count |
| 2026-05-20 01:20 | Signals CSV 加入 `previous_target_position` | 110 -> 110 | pass | keep | pushed to `origin/main` | 由 digest 欄位穩定推導前一根 bar 的 target position |
| 2026-05-20 01:35 | Signals CSV 加入 `is_hold` | 110 -> 110 | pass | keep | pushed to `origin/main` | 由 `target_position` 與 `position_change` 穩定推導持倉 bar |
| 2026-05-20 01:50 | Backtest digest validator 強化 position delta 連續性 | 110 -> 110 | pass | keep | pushed to `origin/main` | 讓 `position_change` 的稽核欄位可被一致性驗證 |
| 2026-05-20 02:05 | Trace summary 加入 deterministic `reason_counts` | 110 -> 110 | pass | keep | pushed to `origin/main` | 用 frequency list 強化回測 artifacts 稽核可讀性 |
| 2026-05-20 02:20 | Trace summary 加入 deterministic `open_count` / `close_count` | 110 -> 110 | pass | keep | pushed to `origin/main` | 用 position 0/非0 transition 計數，便於稽核開倉/平倉次數 |
| 2026-05-20 02:36 | Trace summary validator（schema + invariants） | 110 -> 110 | pass | keep | pushed to `origin/main` | 加入 `validate_trace_summary`，檢查 deterministic ordering 與 counts 內部一致性 |
| 2026-05-20 02:51 | Trace summary 加入 `nonzero_target_position_count` | 110 -> 110 | pass | keep | pushed to `origin/main` | 增加非零持倉 bar 的稽核欄位，並驗證 `hold_count <= nonzero_target_position_count` |
| 2026-05-20 03:07 | Trace summary 增加首尾部位稽核欄位 | 110 -> 110 | pass | keep | pushed to `origin/main` | `*_trace_summary.json` 加入 `first_target_position` / `last_previous_target_position` |
| 2026-05-20 03:22 | Trace summary 加入 `entry_count` | 110 -> 110 | pass | keep | pushed to `origin/main` | `entry_count` = `open_count`（alias），讓開倉次數欄位更直覺可讀 |
| 2026-05-20 03:36 | Cross-check backtest artifacts | 110 -> 110 | pass | keep | `beb803e` pushed | `write_phase_outputs` 交叉驗證 `*_signals.csv` 與 `*_trace_summary.json`（counts + 首尾欄位一致） |
| 2026-05-20 03:51 | 強化 signals CSV validator（per-row semantics） | 110 -> 110 | pass | keep | `43257ef` pushed | `validate_signal_digest_csv(...)` 加入 position delta 與 flags per-row 一致性檢查，避免局部篡改仍通過 counts 檢查 |
| 2026-05-20 04:05 | Phase markdown 顯示 trace summary 摘要 | 110 -> 110 | pass | keep | `a32fada` pushed | Backtest mode 時在 Phase markdown 追加 `Backtest Trace Summary` 區段（counts/首尾部位/原因數），並用 exact-text regression test 鎖住 |
| 2026-05-20 04:19 | Phase markdown digest/trace 對照 | 110 -> 110 | pass | keep | pushed to `origin/main` | Backtest Digest Invariants 追加 trace summary cross-check（bar_count / unique reasons / last target position）並更新 exact-text regression |
| 2026-05-20 04:35 | Trace summary 加入 `short_entry_count` | 110 -> 110 | pass | keep | `19efe87` pushed | `*_trace_summary.json` 擴充 deterministic short entry 稽核欄位，並驗證 `long_entry_count + short_entry_count == entry_count` |
| 2026-05-20 04:50 | Trace summary 拆解 flatten 類型 | 110 -> 110 | pass | keep | pushed to `origin/main` | `*_trace_summary.json` 追加 `flatten_to_zero_count` / `flatten_to_short_count`，並驗證加總等於 `flatten_count` |
| 2026-05-20 05:06 | Trace summary 加入 min/max target position | 110 -> 110 | pass | keep | pushed to `origin/main` | `*_trace_summary.json` 追加 deterministic `min_target_position` / `max_target_position`，並用 validator 驗證首尾部位落在範圍內 |
| 2026-05-20 05:22 | Backtest timestamp ISO-8601 稽核 | 110 -> 110 | pass | keep | `b404c55` pushed | 強制 `SignalDigest.timestamp` 為 ISO-8601；`*_trace_summary.json` 追加 `timestamps_iso8601`，並在 Phase markdown 顯示 timestamps 稽核結果 |
| 2026-05-20 05:34 | Signals CSV timestamp ISO-8601 稽核 | 110 -> 110 | pass | keep | pushed to `origin/main` | `validate_signal_digest_csv(...)` 強制每列 `timestamp` 必須為 ISO-8601（test-covered），避免 CSV timestamp drift |
| 2026-05-20 05:50 | Signals CSV 數值格式稽核 | 110 -> 110 | pass | keep | pushed to `origin/main` | `validate_signal_digest_csv(...)` 強制 signals CSV 數值欄位採 fixed 6-decimal formatting（並拒絕非 finite score），避免浮點格式 drift（test-covered） |
| 2026-05-20 06:06 | Trace summary schema version | 110 -> 110 | pass | keep | pushed to `origin/main` | `*_trace_summary.json` 追加 deterministic `schema_version`，用於 schema 演進稽核（test-covered）。 |
| 2026-05-20 06:23 | Trace summary `flip_count` | 110 -> 110 | pass | keep | pushed to `origin/main` | `*_trace_summary.json` 追加 deterministic `flip_count`（反手次數），並驗證 `flip_count <= nonzero_position_change_count`（test-covered）。 |
| 2026-05-20 06:35 | Signals CSV `is_hold` epsilon 一致性 | 110 -> 110 | pass | keep | `8d321e9` pushed | `write_signal_digest_csv(...)` 與 trace summary 的 `hold_count` / `nonzero_position_change_count` 統一 epsilon 定義，並補上 tiny position regression test，避免 flags drift。 |
| 2026-05-20 06:51 | Signals CSV vs trace summary cross-check 擴充 | 110 -> 110 | pass | keep | pushed to `origin/main` | `validate_signal_digest_csv(...)` 追加 `entry_count` / `short_entry_count` / flatten buckets / `flip_count` / `timestamps_iso8601` 對齊檢查（test-covered）。 |
| 2026-05-20 07:06 | Trace summary 加入 `start_date` / `end_date` | 110 -> 110 | pass | keep | `1f1cd9c` pushed | `*_trace_summary.json` 從 ISO-8601 timestamp 萃取日期（schema_version=2），讓人工核對 backtest 期間更直覺（test-covered）。 |
| 2026-05-20 07:22 | Trace summary 擴充 `flatten_to_long_count` | 110 -> 110 | pass | keep | pushed to `origin/main` | `*_trace_summary.json` 追加 deterministic `flatten_to_long_count`（schema_version=3），並驗證 flatten buckets 加總等於 `flatten_count`（test-covered）。 |
| 2026-05-20 07:38 | Trace summary 擴充 `hold_long_count` / `hold_short_count` | 110 -> 110 | pass | keep | pushed to `origin/main` | `*_trace_summary.json` 追加 deterministic hold side buckets，並驗證 `hold_long_count + hold_short_count == hold_count`（schema_version=4，test-covered）。 |
| 2026-05-20 07:52 | Signals CSV 擴充 `hold_side` | 110 -> 110 | pass | keep | pushed to `origin/main` | `*_signals.csv` 追加 deterministic `hold_side`（none/long/short），並在 `validate_signal_digest_csv(...)` 交叉驗證 per-row hold side 語意與 `hold_long_count` / `hold_short_count` 一致（test-covered）。 |
| 2026-05-20 08:05 | Phase markdown 顯示 hold long/short | 110 -> 110 | pass | keep | pushed to `origin/main` | Phase markdown 的 `Backtest Trace Summary` 追加 `hold_long_count` / `hold_short_count`（hold long/short）顯示，並更新 exact-text regression test contract（test-covered）。 |
| 2026-05-20 08:20 | Trace summary 加入 `signal_digest_sha256` | 110 -> 110 | pass | keep | pushed to `origin/main` | `*_trace_summary.json` 追加 deterministic `signal_digest_sha256`（schema_version=5），並在 `validate_signal_digest_csv(...)` 驗證 signals CSV hash 與 trace summary 一致（test-covered）；同時固定 `*_signals.csv` 換行為 `\\n`，避免 hash 因 OS newline 正規化 drift。 |
| 2026-05-20 08:52 | Trace summary 加入 position bucket counts | 110 -> 110 | pass | keep | pushed to `origin/main` | `*_trace_summary.json` 追加 deterministic `position_bucket_counts`（flat/long/short），並在 `validate_signal_digest_csv(...)` 交叉驗證 bucket counts 與 `*_signals.csv` 一致（schema_version=6，test-covered）。 |
| 2026-05-20 09:08 | Signals CSV vs trace summary cross-check 擴充（reasons） | 110 -> 110 | pass | keep | pushed to `origin/main` | `validate_signal_digest_csv(...)` 追加 deterministic `reason` 稽核：要求 `*_signals.csv` 的 `reasons` / `reason_counts` 與 `*_trace_summary.json` 完全一致，避免 reason drift（test-covered）。 |
| 2026-05-20 09:22 | Phase markdown 顯示 trace schema 與 position buckets | 110 -> 110 | pass | keep | pushed to `origin/main` | Phase markdown 的 `Backtest Trace Summary` 追加 `schema_version` 與 `position_bucket_counts`（flat/long/short）顯示，並以 exact-text regression test 鎖住 backtest markdown contract（test-covered）。 |
| 2026-05-20 09:36 | Trace summary 加入 `first_previous_target_position` | 110 -> 110 | pass | keep | pending | `*_trace_summary.json` 追加 deterministic `first_previous_target_position`（schema_version=7），並在 `validate_signal_digest_csv(...)` 交叉驗證與 signals CSV 一致；Phase markdown 顯示該欄位（test-covered）。 |

## 總結

三小時 autoresearch 主要把 Phase 從「能切換模式」推進到「模式輸出可被 regression tests 鎖住」。回測路徑現在有 deterministic JSON、markdown、signals CSV 與 trace summary；live 路徑仍只保留 dry-run order intent，沒有真實交易整合。
