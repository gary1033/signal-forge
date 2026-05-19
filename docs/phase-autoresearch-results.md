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

## 總結

三小時 autoresearch 主要把 Phase 從「能切換模式」推進到「模式輸出可被 regression tests 鎖住」。回測路徑現在有 deterministic JSON、markdown、signals CSV 與 trace summary；live 路徑仍只保留 dry-run order intent，沒有真實交易整合。
