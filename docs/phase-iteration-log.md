# Phase Autoresearch 迭代紀錄

這份紀錄是 bounded autoresearch 的 audit trail。所有敘述使用繁中；程式識別字、CLI 參數與 commit SHA 保留原樣。

- 方法：modify -> verify -> keep/discard -> log
- Metric：`python tools/phase_readiness_score.py`
- Guard：
  - `$env:PYTHONPATH='src'`
  - `python -m unittest discover -s tests`
  - `git diff --check`

## 執行總覽

| 時間（+08:00） | 目標 | 主要改動 | 驗證結果 | 決策 |
|---|---|---|---|---|
| 2026-05-19 16:27 | 讓 README / docs 在 Windows 可讀，並維持 Phase 安全邊界 | 重寫 `README.md`、`phase-roadmap.md`、`phase-autoresearch-results.md`；調整 readiness needle | 110 -> 110；27 tests OK | keep |
| 2026-05-19 16:42 | 讓 live dry-run safety 稽核穩定 | 在 `OrderIntent.safety_note` 加入 `LIVE_DRY_RUN_ONLY` | 110 -> 110；27 tests OK | keep |
| 2026-05-19 16:57 | 移除 safety note 中 encoding-dependent 文字 | `safety_note` 改成穩定 invariant；補 unit tests | 110 -> 110；27 tests OK | keep |
| 2026-05-19 17:13 | 建立 backtest Phase report golden regression | 固定 bars 對應固定 summary JSON / markdown 欄位 | 110 -> 110；28 tests OK | keep |
| 2026-05-19 17:27 | 強化 Phase summary JSON schema contract | 加入 schema validator；測試 live/backtest 必填欄位 | 110 -> 110；29 tests OK | keep |
| 2026-05-19 17:42 | 讓 report JSON diff deterministic | `json.dumps(..., sort_keys=True)` | 110 -> 110；29 tests OK | keep |
| 2026-05-19 18:02 | 讓 Entry Edge report 在 Windows terminal 友善 | 報表 label 改成穩定文字；維持 backtest/live contract | 110 -> 110；guard pass | keep |
| 2026-05-19 18:12 | 鎖住 Phase summary JSON exact text | 測試 `json.dumps(..., indent=2, sort_keys=True) + "\n"` | 110 -> 110；guard pass | keep |
| 2026-05-19 18:28 | 鎖住 Phase markdown exact text | 測試 markdown 內容與 trailing newline | 110 -> 110；29 tests OK | keep |
| 2026-05-19 18:42 | 在 summary contract 層強化 mode switching safety | live 必須 dry-run / order_intents；backtest 必須 entry_edge | 110 -> 110；guard pass | keep |
| 2026-05-19 18:57 | 鎖住 live Phase report contract | 固定 live summary / markdown，確認 `submitted=False` | 110 -> 110；31 tests OK | keep |
| 2026-05-19 19:13 | 改善 backtest portability | warning / sample risk 文字改成穩定格式 | 110 -> 110；31 tests OK | keep |
| 2026-05-19 19:29 | 鎖住 Entry Edge outputs | 固定 summary JSON、markdown、trade log CSV | 110 -> 110；32 tests OK | keep |
| 2026-05-19 19:42 | 固定 Entry Edge `failure_reason` | failure reason 改成 deterministic，補測試 | 110 -> 110；33 tests OK | keep |
| 2026-05-19 19:58 | 讓 CLI 的 `dry_run` 反映 mode | `phase` CLI 對 backtest / live 傳入清楚的 `PhaseConfig` | 110 -> 110；33 tests OK | keep |
| 2026-05-19 20:14 | 增加 backtest trace visibility | 產生 deterministic `*_signals.csv` | 110 -> 110；33 tests OK | keep |
| 2026-05-19 20:27 | 讓 `PhaseConfig` 成為 mode semantics 單一來源 | 由 `mode` 推導 `dry_run`；拒絕 confusing config | 110 -> 110；guard pass | keep |
| 2026-05-19 20:42 | 擴充 signal digest | 加入 `is_long_entry` | 110 -> 110；34 tests OK | keep |
| 2026-05-19 20:57 | 擴充 signal digest | 加入 `is_flatten` | 110 -> 110；34 tests OK | keep |
| 2026-05-19 21:12 | 鎖住 live markdown exact contract | 固定 live markdown 與 safety invariants | 110 -> 110；35 tests OK | keep |
| 2026-05-19 21:27 | 擴充 signal digest | 加入 `position_change` | 110 -> 110；35 tests OK | keep |
| 2026-05-19 21:42 | 加入 backtest trace summary JSON | 產生 signal-derived counts / reasons summary | 110 -> 110；35 tests OK | keep |
| 2026-05-19 21:57 | 擴充 trace summary | 加入 first / last timestamp | 110 -> 110；35 tests OK | keep |
| 2026-05-19 22:13 | 驗證 backtest digest ordering invariants | 寫入 signals / trace artifacts 前先驗證排序 | 110 -> 110；37 tests OK | keep |
| 2026-05-19 22:27 | 在 Phase markdown 顯示 digest invariants | 報表顯示 counts、timestamp range、last position、unique reasons | 110 -> 110；37 tests OK | keep |
| 2026-05-19 22:42 | 在 Phase markdown 顯示 top reasons frequency | 由 signal digest deterministic 排序產生 | 110 -> 110；37 tests OK | keep |
| 2026-05-19 22:58 | 強化 `SignalDigest.reason` invariants | 驗證 trimmed、ASCII-only、single-line、non-empty | 110 -> 110；39 tests OK | keep |
| 2026-05-19 23:13 | 正規化 strategy-provided `reason` | whitespace collapse、non-ASCII 轉 `uXXXX`、空值為 `unknown` | 110 -> 110；41 tests OK | keep |
| 2026-05-19 23:28 | 限制正規化後 `reason` 長度 | max length 120，避免 artifact 膨脹 | 110 -> 110；42 tests OK | keep |
| 2026-05-19 23:41 | 移除 CLI 重複 `dry_run` wiring | CLI 改依賴 `PhaseConfig.__post_init__` 推導 | 110 -> 110；42 tests OK | keep |
| 2026-05-20 01:04 | 擴充 trace summary 稽核欄位 | `*_trace_summary.json` 加入 deterministic `hold_count` | 110 -> 110；42 tests OK | keep |
| 2026-05-20 01:20 | 擴充 signals CSV 稽核欄位 | `*_signals.csv` 加入 deterministic `previous_target_position` | 110 -> 110；42 tests OK | keep |
| 2026-05-20 01:35 | 擴充 signals CSV 稽核欄位 | `*_signals.csv` 加入 deterministic `is_hold` | 110 -> 110；42 tests OK | keep |
| 2026-05-20 01:50 | 強化 backtest digest validator | 驗證 `position_change` 與 `target_position` delta 連續性一致 | 110 -> 110；43 tests OK | keep |
| 2026-05-20 02:05 | 擴充 trace summary 稽核欄位 | `*_trace_summary.json` 加入 deterministic `reason_counts` | 110 -> 110；43 tests OK | keep |
| 2026-05-20 02:20 | 擴充 trace summary 稽核欄位 | `*_trace_summary.json` 加入 deterministic `open_count` / `close_count` | 110 -> 110；43 tests OK | keep |
| 2026-05-20 02:36 | 強化 trace summary validator | 新增 trace summary schema + invariants validator（deterministic ordering / counts 稽核） | 110 -> 110；44 tests OK | keep |
| 2026-05-20 02:51 | 擴充 trace summary 稽核欄位 | `*_trace_summary.json` 加入 deterministic `nonzero_target_position_count`（並驗證 `hold_count` 子集合不超出） | 110 -> 110；44 tests OK | keep |
| 2026-05-20 06:51 | 強化 signals CSV vs trace summary cross-check | `validate_signal_digest_csv(...)` 追加 `entry_count` / `short_entry_count` / flatten buckets / `flip_count` / `timestamps_iso8601` 對齊檢查 | 110 -> 110；52 tests OK | keep |
| 2026-05-20 03:07 | 擴充 trace summary 首尾部位稽核欄位 | `*_trace_summary.json` 加入 `first_target_position` / `last_previous_target_position` | 110 -> 110；44 tests OK | keep |
| 2026-05-20 03:22 | 擴充 trace summary 稽核欄位 | `*_trace_summary.json` 加入 deterministic `entry_count`（alias `open_count`） | 110 -> 110；44 tests OK | keep |
| 2026-05-20 03:36 | 強化 backtest artifacts 一致性驗證 | `write_phase_outputs` 寫出 artifact 後交叉驗證 `*_signals.csv` 與 `*_trace_summary.json`（counts + 首尾欄位一致） | 110 -> 110；45 tests OK | keep |
| 2026-05-20 03:51 | 強化 signals CSV validator（per-row semantics） | `validate_signal_digest_csv(...)` 加入 position delta 與 flags per-row 一致性檢查，避免局部篡改仍通過 counts 檢查 | 110 -> 110；46 tests OK | keep |
| 2026-05-20 04:05 | Phase markdown 顯示 trace summary 摘要 | Backtest mode 時在 Phase markdown 追加 `Backtest Trace Summary` 區段（counts/首尾部位/原因數）並用 exact-text test 鎖住 | 110 -> 110；46 tests OK | keep |
| 2026-05-20 04:19 | Phase markdown digest/trace summary 對照 | Backtest Digest Invariants 追加 trace summary cross-check（bar_count / unique reasons / last target position）並更新 exact-text regression | 110 -> 110；46 tests OK | keep |
| 2026-05-20 04:35 | 擴充 trace summary 稽核欄位 | `*_trace_summary.json` 加入 deterministic `short_entry_count`（並驗證 `long_entry_count + short_entry_count == entry_count`） | 110 -> 110；46 tests OK | keep |
| 2026-05-20 04:50 | 擴充 trace summary flatten 分解稽核欄位 | `*_trace_summary.json` 追加 `flatten_to_zero_count` / `flatten_to_short_count`，並驗證兩者加總等於 `flatten_count` | 110 -> 110；46 tests OK | keep |
| 2026-05-20 05:06 | 擴充 trace summary min/max 部位稽核欄位 | `*_trace_summary.json` 追加 deterministic `min_target_position` / `max_target_position`，並驗證首尾部位落在 min/max 範圍內 | 110 -> 110；46 tests OK | keep |
| 2026-05-20 05:22 | 強化 backtest timestamp 格式稽核 | 強制 `SignalDigest.timestamp` 為 ISO-8601，並在 `*_trace_summary.json` 追加 `timestamps_iso8601` 欄位 | 110 -> 110；47 tests OK | keep |
| 2026-05-20 05:34 | 強化 signals CSV timestamp 稽核 | `validate_signal_digest_csv(...)` 強制每列 `timestamp` 必須為 ISO-8601，避免 CSV timestamp drift | 110 -> 110；48 tests OK | keep |
| 2026-05-20 05:50 | 強化 signals CSV 數值格式稽核 | `validate_signal_digest_csv(...)` 強制數值欄位採用 fixed 6-decimal formatting，避免浮點格式 drift（並拒絕非 finite score） | 110 -> 110；49 tests OK | keep |
| 2026-05-20 06:06 | Trace summary schema version | `*_trace_summary.json` 追加 deterministic `schema_version`（validator + exact-text regression contract 更新） | 110 -> 110；49 tests OK | keep |
| 2026-05-20 06:23 | 擴充 trace summary 稽核欄位 | `*_trace_summary.json` 加入 deterministic `flip_count`（反手次數），並驗證 `flip_count <= nonzero_position_change_count` | 110 -> 110；49 tests OK | keep |
| 2026-05-20 06:35 | 修正 signals CSV `is_hold` epsilon 一致性 | `write_signal_digest_csv(...)` 與 `*_trace_summary.json` 的 `hold_count` 統一使用 epsilon（避免 tiny position 造成 flags mismatch），並加入 regression test | 110 -> 110；50 tests OK | keep |
| 2026-05-20 07:06 | 擴充 trace summary timestamp 稽核欄位 | `*_trace_summary.json` 加入 deterministic `start_date` / `end_date`（由 ISO-8601 timestamp 萃取） | 110 -> 110；52 tests OK | keep |
| 2026-05-20 07:22 | Trace summary 擴充 flatten buckets | `*_trace_summary.json` 追加 deterministic `flatten_to_long_count`，並用 validator 驗證 `flatten_to_long_count + flatten_to_short_count + flatten_to_zero_count == flatten_count`（schema_version=3） | 110 -> 110；52 tests OK | keep |
| 2026-05-20 07:38 | Trace summary 擴充 hold side buckets | `*_trace_summary.json` 追加 deterministic `hold_long_count` / `hold_short_count`，並用 validator 驗證 `hold_long_count + hold_short_count == hold_count`（schema_version=4） | 110 -> 110；52 tests OK | keep |
| 2026-05-20 07:52 | Signals CSV 增加 `hold_side` 稽核欄位 | `*_signals.csv` 追加 deterministic `hold_side`（none/long/short），並在 `validate_signal_digest_csv(...)` 交叉驗證 per-row hold side 語意與 `hold_long_count` / `hold_short_count` 一致 | 110 -> 110；53 tests OK | keep |
| 2026-05-20 08:05 | Phase markdown 顯示 hold long/short | Phase markdown 的 `Backtest Trace Summary` 追加 `hold_long_count` / `hold_short_count`（hold long/short）顯示，並更新 exact-text regression test contract | 110 -> 110；53 tests OK | keep |
| 2026-05-20 08:20 | Trace summary 加入 `signal_digest_sha256` | `*_trace_summary.json` 追加 deterministic `signal_digest_sha256`（schema_version=5），並在 `validate_signal_digest_csv(...)` 驗證 signals CSV hash 與 trace summary 一致（含測試）；同時固定 CSV 換行為 `\\n` 以避免 hash 因 OS newline 正規化 drift | 110 -> 110；53 tests OK | keep |

## 方法紀錄

每一輪都遵守一個原則：只做一個聚焦改動，先維持 `readiness=110`，再用測試把回測輸出 contract 鎖住。若改動碰到 `live` 路徑，只允許 dry-run intent，不增加 broker、credential 或真實送單。

實作上，回測路徑被逐步加上 deterministic artifact：

- Phase summary JSON：固定 schema、排序與 exact text。
- Phase markdown：固定 exact text，並逐步加入 digest invariants 與 top reasons。
- Entry Edge outputs：固定 summary JSON、markdown 與 trade log CSV。
- Signal digest：加入 `is_long_entry`、`is_flatten`、`position_change`。
- Trace summary：由 signal digest 派生 counts、reasons、timestamp range。
- Reason normalization：將 strategy 提供的 `reason` 正規化成 deterministic、single-line、ASCII-only、長度受控的文字。

## Live 安全紀錄

截至最後一輪，`live` 仍維持以下限制：

- 只產生 dry-run `OrderIntent`
- `dry_run=True`
- `submitted=False`
- `safety_note` 含 `LIVE_DRY_RUN_ONLY`
- 不接 broker
- 不讀 API key / credential
- 不送出真實訂單

## 最後狀態

- 最新已知 metric：`110`
- 最新已知 guard：52 tests OK，`git diff --check` clean
- 最後一輪 commit：已推送到 `origin/main`（以 `git log -5` 為準）
- 下一步：只擴充 backtest verifiability 與 deterministic artifacts；live 在回測穩定前維持 dry-run only。
