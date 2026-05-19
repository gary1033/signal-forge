# Phase Autoresearch Iteration Log

This log is the audit trail for bounded autoresearch.

- Method: modify -> verify -> keep/discard -> log
- Metric: `python tools/phase_readiness_score.py`
- Guard:
  - `$env:PYTHONPATH='src'`
  - `python -m unittest discover -s tests`
  - `git diff --check`

## 2026-05-19 16:27 +08:00

- Goal: make README/docs readable on Windows; keep Phase backtest/live safety explicit; keep readiness metric deterministic.
- Change set:
  - Rewrote `README.md`, `docs/phase-roadmap.md`, `docs/phase-autoresearch-results.md` using ASCII-only text to avoid encoding garbling.
  - Updated `tools/phase_readiness_score.py` "research notes" check to look for: Method / Verify / Next step.
- Method:
  - Replace garbled docs with stable ASCII content.
  - Keep required keywords for readiness checks (e.g., PhaseMode/backtest/live, PhaseRunner/BacktestExecutionAdapter/LiveExecutionAdapter).
- Verify commands:
  - `python tools\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass (27 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: see `git log -1 --oneline` (pushed to `origin/main`; includes `50ade1b`)
- Next step: with readiness at max, focus on backtest stability and output-contract regression tests (live remains dry-run only).

## 2026-05-19 16:42 +08:00

- Goal: keep Phase readiness at max while making live dry-run safety auditing stable (avoid locale/encoding-sensitive markers).
- Change set:
  - Added `LIVE_DRY_RUN_ONLY` marker into `OrderIntent.safety_note` (still dry-run only; still `submitted=False`).
  - Updated unit tests to assert the stable marker and keep the human-readable safety note.
  - Updated readiness metric to check `LIVE_DRY_RUN_ONLY` instead of locale-sensitive text.
- Method:
  - Introduce an ASCII marker for safety/audit invariants.
  - Keep backtest/live mode split unchanged; no broker, no API keys, no real orders.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass (27 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: see `git log -1 --oneline` (pushed to `origin/main`)
- Next step: start backtest determinism work (golden regression tests) without touching live broker integration.

## 2026-05-19 16:57 +08:00

- Goal: keep Phase readiness at max while removing non-ASCII safety-note text that can display inconsistently across terminals/encodings.
- Change set:
  - Replaced `OrderIntent.safety_note` with an ASCII-only invariant (keeps `LIVE_DRY_RUN_ONLY`; explicitly states no broker / no API keys / `submitted=False`).
  - Updated unit tests to assert the ASCII-only safety-note invariants.
- Method:
  - Keep the safety marker deterministic (ASCII) and validate via unit tests.
  - Keep live mode dry-run only; no broker, no credentials, no submissions.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass (27 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: see `git log -1 --oneline` (pushed to `origin/main`)
- Next step: add a small deterministic backtest golden test (fixed input bars -> fixed report/summary contract) without changing live safety.

## 2026-05-19 17:13 +08:00

- Goal: keep Phase readiness at max while adding a deterministic backtest "golden" regression test for the Phase report contract.
- Change set:
  - Added a unit test that asserts stable Phase backtest summary JSON + markdown fields (mode/adapter metadata, entry-edge invariants).
- Method:
  - Add a contract-level regression test (fixed input bars -> fixed Phase report outputs).
  - Keep live mode dry-run only; no broker, no credentials, no submissions.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass (28 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: see `git log -1 --oneline` (pushed to `origin/main`)
- Next step: expand backtest determinism to cover report schema validation and/or stable JSON ordering (still no live broker integration).

## 2026-05-19 17:27 +08:00

- Goal: keep Phase readiness at max while strengthening backtest verifiability via a schema-level contract guard for Phase summary JSON.
- Change set:
  - Added `validate_phase_summary(...)` and invoked it in `write_phase_outputs(...)` to enforce a deterministic summary contract.
  - Updated unit tests to assert the schema validator passes for live/backtest outputs and rejects missing required keys.
- Method:
  - Add a lightweight deterministic schema validator (type/required-field checks).
  - Keep backtest/live mode split unchanged; live remains dry-run only (no broker, no API keys, `submitted=False`).
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass (29 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: see `git log -1 --oneline` (pushed to `origin/main`)
- Next step: add a small backtest schema regression test that asserts stable key set + required ordering (keep live dry-run only).

## 2026-05-19 17:42 +08:00

- Goal: keep Phase readiness at max while improving backtest verifiability via deterministic JSON output ordering (stable diffs).
- Change set:
  - Added `sort_keys=True` to `json.dumps(...)` in `write_phase_outputs(...)` and `write_entry_edge_outputs(...)`.
- Method:
  - Make report JSON deterministic regardless of dict insertion order to support golden/regression workflows.
  - Live safety unchanged: live mode remains dry-run only; no broker; no API keys; `submitted=False`.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass (29 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: `3d99839` (pushed to `origin/main`)
- Next step: if stable, consider tightening backtest golden tests to compare exact JSON text (still no live trading integration).

## 2026-05-19 18:02 +08:00

- Goal: keep Phase readiness at max while making backtest reports readable/stable on Windows terminals (avoid non-ASCII / encoding-dependent labels).
- Change set:
  - Converted Entry Edge markdown report labels/headings to ASCII-only (English).
  - Converted CLI `strategy_spec` keys/values to ASCII-only so generated reports stay portable.
  - Updated unit tests to assert the new report section heading (`Strategy Spec (Distilled)`).
- Method:
  - Preserve backtest/live mode split and contracts; change only presentation text for report portability.
  - Keep live mode dry-run only; no broker, no credentials, no submissions.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass
- Decision: keep
- Commit: `d54d9e7`
- Next step: continue backtest determinism/golden tests while keeping live dry-run only.

## 2026-05-19 18:12 +08:00

- Goal: keep Phase readiness at max while tightening backtest verifiability with an exact Phase summary JSON text contract.
- Change set:
  - Added a unit test assertion that the backtest Phase summary JSON file matches `json.dumps(..., indent=2, sort_keys=True) + "\\n"` exactly (stable formatting and key ordering).
- Method:
  - Strengthen the deterministic contract: content + formatting (sorted keys + newline).
  - Live safety unchanged: live mode remains dry-run only; no broker; no API keys; `submitted=False`.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass (see this wakeup verification output)
- Decision: keep
- Commit: `c69428c` (pushed to `origin/main`)
- Next step: if stable, consider adding a similar exact-text contract for Phase markdown output (still no live trading integration).

## 2026-05-19 18:28 +08:00

- Goal: keep Phase readiness at max while tightening backtest verifiability with an exact Phase markdown text contract.
- Change set:
  - Added a unit test assertion that the backtest Phase markdown report matches the exact expected text, including the trailing newline.
- Method:
  - Treat Phase markdown output as a deterministic contract for regression testing and stable diffs.
  - Live safety unchanged: live mode remains dry-run only; no broker; no API keys; no submissions.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass (29 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: `773e52b` (pushed to `origin/main`)
- Next step: expand golden tests incrementally (keep live dry-run only).

## 2026-05-19 18:42 +08:00

- Goal: keep Phase readiness at max while strengthening safety invariants for mode switching (`backtest` vs `live`) at the Phase summary contract layer.
- Change set:
  - Tightened `validate_phase_summary(...)` to enforce cross-field invariants:
    - `live`: requires `phase.dry_run=True`, requires `order_intents`, forbids `entry_edge`, and forbids any `submitted=True` intent.
    - `backtest`: requires `phase.dry_run=False`, requires `entry_edge`, and forbids non-empty `order_intents`.
  - Added unit tests that assert the validator rejects (1) a submitted live intent and (2) a backtest summary missing `entry_edge`.
- Method:
  - Keep live safety unchanged (still dry-run only); make the JSON summary validator catch unsafe/mismatched states early.
  - Preserve deterministic output contracts; add safety invariants without introducing broker/API key flows.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass (31 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: see `git log -1 --oneline` (pushed to `origin/main`)
- Next step: add a small golden regression for live mode Phase outputs (still dry-run only; no broker integration).

## 2026-05-19 18:57 +08:00

- Goal: keep Phase readiness at max while improving verifiability via a deterministic golden contract for live Phase outputs (dry-run only).
- Change set:
  - Strengthened unit test to assert exact live Phase summary JSON formatting (`sort_keys=True` + newline) and exact markdown output.
- Method:
  - Treat live mode report text as a stable contract, while keeping live safety unchanged:
    - live remains dry-run only (`dry_run=True`)
    - intents remain order-intent only (`submitted=False`; no broker / no API keys)
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass (31 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: `55d37ac` (pushed to `origin/main`)
- Next step: extend golden regressions to Entry Edge outputs (keep live dry-run only).

## 2026-05-19 19:13 +08:00

- Goal: keep Phase readiness at max while removing encoding-dependent (non-ASCII) text from backtest outputs to improve cross-platform verifiability.
- Change set:
  - Replaced the `validate_bars(...)` low-sample warning string with an ASCII-only English message.
  - Replaced the Entry Edge `sample_risk` message for "PF infinite" with an ASCII-only English message.
- Method:
  - Treat report text as part of the verifiability contract; avoid console/encoding-dependent garbling on Windows.
  - Live safety unchanged: live mode remains dry-run only; no broker; no API keys; `submitted=False`.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass (31 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: see `git log -1 --oneline` (pushed to `origin/main`)
- Next step: add golden regressions for Entry Edge outputs (summary/markdown/trade log), keeping live dry-run only.

## 2026-05-19 19:29 +08:00

- Goal: keep Phase readiness at max while improving backtest verifiability by making Entry Edge outputs deterministic and human-readable.
- Change set:
  - Rounded Entry Edge report numeric fields in summary JSON (money to 2dp; ratios to fixed precision) to avoid float artifact noise.
  - Made Entry Edge trade log CSV numeric formatting deterministic (`.2f` money, `.6f` ratios).
  - Added a golden regression test asserting exact Entry Edge summary JSON + markdown + trade log CSV output for a fixed 2-bar input.
- Method:
  - Treat Entry Edge outputs as contracts (exact text) to enable stable diffs and easy regression detection.
  - Keep live safety unchanged: live mode remains dry-run only; no broker; no API keys; `submitted=False`.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass (32 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: see `git log -1 --oneline` (this wakeup)
- Next step: consider fixing Entry Edge `failure_reason` garbled/encoding-dependent text without changing the evaluation logic.

## 2026-05-19 19:42 +08:00

- Goal: keep Phase readiness at max while improving backtest portability by making Entry Edge `failure_reason` ASCII-only and deterministic.
- Change set:
  - Replaced Entry Edge `failure_reason` strings with stable ASCII-only English messages.
  - Added a unit test that asserts deterministic `failure_reason` values for two fail scenarios.
- Method:
  - Treat `failure_reason` as part of the verifiability contract; avoid terminal/encoding-dependent garbling on Windows.
  - Live safety unchanged: live mode remains dry-run only; no broker; no API keys; `submitted=False`.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass (33 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: `bf32c6e` (pushed to `origin/main`)
- Next step: consider adding lightweight coverage/trace visibility for backtest runs without introducing any broker/API key integration.

## 2026-05-19 19:58 +08:00

- Goal: keep Phase readiness at max while making backtest vs live switching in the CLI unambiguous (`dry_run` reflects mode).
- Change set:
  - Updated `signal-forge phase` CLI to pass `PhaseConfig(dry_run=False)` for backtest and `PhaseConfig(dry_run=True)` for live.
- Method:
  - Keep live safety unchanged (still dry-run only; `submitted=False`; no broker; no API keys).
  - Preserve deterministic output contracts; only adjust CLI wiring to match mode semantics.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass (33 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: see `git log -1 --oneline` (will be pushed to `origin/main`)
- Next step: add lightweight backtest trace visibility (e.g., deterministic per-bar signal digest) without any broker/API key integration.

## 2026-05-19 20:14 +08:00

- Goal: keep Phase readiness at max while adding deterministic backtest trace visibility without changing live dry-run safety.
- Change set:
  - Captured a per-bar signal digest in backtest mode (`SignalDigest`) and exported it as `*_signals.csv` via `write_phase_outputs(...)`.
  - Updated unit tests to assert the deterministic backtest signal digest CSV contract; live output intentionally has no signal digest file.
- Method:
  - Keep backtest vs live routing unchanged.
  - Live safety unchanged: live remains dry-run only; emits order intents only; `submitted=False`; no broker; no API keys.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass (33 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: see `git log -1 --oneline` (will be pushed to `origin/main`)
- Next step: consider enriching the backtest digest with stable derived fields (e.g., entry flag) while keeping contracts deterministic.

## 2026-05-19 20:27 +08:00

- Goal: make backtest vs live mode switching unambiguous in `PhaseConfig` itself (avoid backtest defaulting to dry-run).
- Change set:
  - Updated `PhaseConfig` so `dry_run` is derived from `mode` by default: backtest -> `dry_run=False`, live -> `dry_run=True`.
  - Added a validation guardrail: reject `PhaseConfig(mode="backtest", dry_run=True)` to prevent confusing/unsafe semantics.
  - Updated unit tests to reflect the new default behavior and validation rule.
- Method:
  - Keep live safety unchanged: live remains dry-run order intent only; `submitted=False`; no broker; no API keys.
  - Keep deterministic output contracts unchanged.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass
- Decision: keep
- Commit: see `git log -1 --oneline` (will be pushed to `origin/main`)
- Next step: keep tightening backtest trace/coverage visibility while preserving deterministic output contracts and live dry-run safety.

## 2026-05-19 21:42 +08:00

- Goal: keep Phase readiness at max while improving backtest trace visibility with a deterministic summary artifact (no live trading changes).
- Change set:
  - Backtest-only: emit `*_trace_summary.json` derived from `SignalDigest` (counts + last target position + sorted reasons).
  - Added an exact-text contract test for the new summary JSON output.
- Method:
  - Treat trace outputs as stable contracts: deterministic fields only, `sort_keys=True`, newline-terminated JSON.
  - Live safety unchanged: live remains dry-run order intent only; `submitted=False`; no broker; no API keys.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass (35 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: see `git log -1 --oneline` (will be pushed to `origin/main`)
- Next step: consider extending trace summary with deterministic timestamp range (from digests) or add a minimal backtest-only invariant checker (still no broker/API keys).

## 2026-05-19 20:42 +08:00

- Goal: keep Phase readiness at max while improving backtest verifiability by enriching the deterministic signal digest contract (no live trading changes).
- Change set:
  - Added a derived boolean `is_long_entry` field to backtest `SignalDigest` and exported it in `*_signals.csv`.
  - Updated unit tests to assert the new deterministic CSV contract.
- Method:
  - Treat the backtest signal digest as a stable contract; add derived fields only when deterministic and test-covered.
  - Live safety unchanged: live remains dry-run order intent only; `submitted=False`; no broker; no API keys.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass (34 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: see `git log -1 --oneline` (pushed to `origin/main`)
- Next step: consider adding more deterministic derived fields to the backtest digest (e.g., exit/flatten markers) only when test-covered.

## 2026-05-19 20:57 +08:00

- Goal: keep Phase readiness at max while enriching the deterministic backtest signal digest contract with an explicit flatten/exit marker (no live trading changes).
- Change set:
  - Added a derived boolean `is_flatten` field to backtest `SignalDigest` and exported it in `*_signals.csv`.
  - Updated unit tests to assert the deterministic CSV contract.
- Method:
  - Treat the backtest signal digest as a stable contract; add derived fields only when deterministic and test-covered.
  - Live safety unchanged: live remains dry-run order intent only; `submitted=False`; no broker; no API keys.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass (34 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: see `git log -1 --oneline` (will be pushed to `origin/main`)
- Next step: consider adding a deterministic `position_change` (delta) column to the digest only if it stays stable and is test-covered.

## 2026-05-19 21:12 +08:00

- Goal: keep Phase readiness at max while tightening the `live` dry-run output contract (no broker/API key integration; no real submissions).
- Change set:
  - Added a stable regression test that asserts the exact `live` Phase report markdown output, including `LIVE_DRY_RUN_ONLY` and `submitted=False`.
  - Ensured the `live` Phase summary JSON remains deterministic (`sort_keys=True` formatting + trailing newline).
- Method:
  - `live` remains DRY-RUN ONLY: emit order intents only; `dry_run=True`; `submitted=False`; no broker; no API keys.
  - Keep tests explicit and ASCII-stable to avoid platform encoding drift.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass (35 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: see `git log -1 --oneline` (will be pushed to `origin/main`)
- Next step: add deterministic `position_change` (delta) to backtest `*_signals.csv` only if it stays stable and is test-covered.

## 2026-05-19 21:27 +08:00

- Goal: keep Phase readiness at max while improving backtest verifiability by enriching the deterministic signal digest contract (no live trading changes).
- Change set:
  - Added a derived `position_change` field to backtest `SignalDigest` and exported it in `*_signals.csv`.
  - Updated unit tests to assert the new deterministic CSV contract.
- Method:
  - Treat the backtest signal digest as a stable contract; add derived fields only when deterministic and test-covered.
  - Live safety unchanged: live remains dry-run order intent only; `submitted=False`; no broker; no API keys.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass (35 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: see `git log -1 --oneline` (will be pushed to `origin/main`)
- Next step: consider adding backtest-only trace summary JSON (still deterministic; still no broker/API keys) to improve debugging without affecting live safety.

## 2026-05-19 21:57 +08:00

- Goal: keep Phase readiness at max while improving backtest trace verifiability with a deterministic timestamp range in `*_trace_summary.json` (no live trading changes).
- Change set:
  - Extended backtest `_signal_trace_summary_dict(...)` output to include `first_timestamp` and `last_timestamp` derived from `SignalDigest` ordering.
  - Updated unit tests to freeze the new trace summary JSON exact-text contract.
- Method:
  - Only enrich trace summary with deterministic, input-derived fields (timestamps already stable in digests).
  - Live safety unchanged: live remains dry-run order intent only; `submitted=False`; no broker; no API keys.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110 (expected)
- Guard: pass (35 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: see `git log -1 --oneline` (will be pushed to `origin/main`)
- Next step: consider adding backtest-only digest invariants (e.g., timestamp monotonicity) as a validator, still with deterministic tests and no broker/API keys.

## 2026-05-19 22:13 +08:00

- Goal: keep Phase readiness at max while adding backtest-only deterministic invariants for `SignalDigest` ordering (no live trading changes).
- Change set:
  - Added `validate_signal_digests(...)` to enforce monotonic index + non-decreasing timestamp.
  - Invoked the validator before writing backtest `*_signals.csv` / `*_trace_summary.json`.
  - Added unit tests that assert the validator rejects out-of-order digests.
- Method:
  - Treat backtest digests as an explicit contract: stable ordering is required for deterministic trace summaries.
  - Live safety unchanged: live remains dry-run order intent only; `submitted=False`; no broker; no API keys.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass (37 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: see `git log -1 --oneline` (pushed to `origin/main`)
- Next step: optionally add a backtest-only "digest invariant report" section into Phase markdown (still deterministic; still no broker/API keys).

## 2026-05-19 22:27 +08:00

- Goal: keep Phase readiness at max while making backtest results easier to audit by surfacing deterministic signal-digest invariants directly in the Phase markdown report.
- Change set:
  - Phase backtest markdown now includes a `Backtest Digest Invariants` section derived from `SignalDigest` (counts, timestamp range, last position, unique reasons).
  - Ensured backtest digest invariants are validated before any Phase artifacts are written to disk.
  - Updated unit tests to freeze the updated backtest Phase markdown contract.
- Method:
  - Keep `backtest` verifiable: only add deterministic, input-derived fields that do not depend on OS locale/encoding.
  - Live safety unchanged: live remains dry-run order intent only; `submitted=False`; no broker; no API keys.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass (37 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: see `git log -1 --oneline` (will be pushed to `origin/main`)
- Next step: consider adding a backtest-only invariant gate for digest content (e.g., allowlist reasons or explicit "hold" vs "entry" normalization) only if deterministic and test-covered; live remains dry-run only.

## 2026-05-19 22:42 +08:00

- Goal: keep Phase readiness at max while improving backtest audit readability by adding a deterministic "top reasons" frequency line into the Phase markdown invariants section (no live trading changes).
- Change set:
  - Phase backtest markdown now includes `Top reasons: <reason>(<count>)` derived from signal digests (sorted deterministically).
  - Updated the backtest Phase markdown exact-text contract test accordingly.
- Method:
  - Keep `backtest` verifiable: only add deterministic, input-derived summaries (reason counts are digest-derived).
  - Live safety unchanged: live remains dry-run order intent only; `submitted=False`; no broker; no API keys.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110
- Guard: pass (37 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: see `git log -1 --oneline` (will be pushed to `origin/main`)
- Next step: consider adding a deterministic allowlist/normalization for digest reasons only if stable and test-covered; live remains dry-run only.

## 2026-05-19 22:58 +08:00

- Goal: keep Phase readiness at max while enforcing deterministic backtest digest reason invariants (ASCII-only, single-line, non-empty), without changing live safety.
- Change set:
  - Extended `validate_signal_digests(...)` to validate `SignalDigest.reason` invariants (trimmed, ASCII-only, single-line, non-empty).
  - Surfaced the new reason invariants booleans in backtest Phase markdown under `Backtest Digest Invariants`.
  - Added unit tests for the new validator cases and updated the backtest Phase markdown exact-text contract.
- Method:
  - Treat backtest digest reason text as part of the deterministic contract (portable across OS/terminal encodings).
  - Live safety unchanged: live remains dry-run order intent only; `submitted=False`; no broker; no API keys.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110 (expected)
- Guard: pass (39 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: see `git log -1 --oneline` (will be pushed to `origin/main`)
- Next step: consider backtest-only digest reason allowlist/normalizer only if deterministic and test-covered; live remains dry-run only.

## 2026-05-19 23:13 +08:00

- Goal: keep Phase readiness at max while preventing strategy-provided `reason` strings (whitespace/non-ASCII) from breaking backtest digest contracts; keep live safety unchanged.
- Change set:
  - Added `normalize_signal_reason(...)` and applied it in both adapters:
    - Backtest `SignalDigest.reason` is normalized before reporting validators run.
    - Live dry-run `OrderIntent.reason` is normalized for stable markdown/JSON contracts.
  - Added unit tests covering normalization behavior (backtest digests + live intents).
- Method:
  - Convert control whitespace (`\\r\\n\\t`) to spaces, collapse whitespace runs, strip.
  - Replace non-ASCII characters with deterministic `uXXXX` hex markers; fallback to `unknown` when empty.
  - Live safety unchanged: live remains dry-run order intent only; `submitted=False`; no broker; no API keys.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110 (expected)
- Guard: pass (41 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: see `git log -1 --oneline` (will be pushed to `origin/main`)
- Next step: optionally add a backtest-only allowlist for normalized reasons (only if deterministic and test-covered); keep live dry-run only.

## 2026-05-19 23:28 +08:00

- Goal: keep Phase readiness at max while making reason text contracts more robust (prevent extremely long reasons from bloating backtest artifacts); live safety unchanged.
- Change set:
  - Added a deterministic max length (120 chars) to `normalize_signal_reason(...)` so both backtest digests and live dry-run intents remain stable and compact.
  - Updated unit tests to cover the truncation behavior (uses explicit unicode escapes to avoid encoding-dependent garbling).
- Method:
  - Normalize whitespace + non-ASCII to `uXXXX`, then truncate to a fixed max length for portability and deterministic diffs.
  - Live safety unchanged: live remains dry-run order intent only; `submitted=False`; no broker; no API keys.
- Verify commands:
  - `python tools\\phase_readiness_score.py`
  - `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
  - `git diff --check`
- Metric: 110 -> 110 (expected)
- Guard: pass (42 tests OK; `git diff --check` clean)
- Decision: keep
- Commit: (this wakeup) `experiment:` commit to be pushed after docs update
- Next step: consider backtest-only reason allowlist only if deterministic + test-covered; keep live dry-run only.
