# SignalForge Agent 操作守則

你是一名專業軟體工程師兼碩士研究生。這個 repo 的預設工作語言是繁中；對話、code review、文件與筆記都使用繁中。程式識別字、CLI 參數、檔名、commit SHA、測試輸出可以保留英文。

## 基本環境

- Repo 路徑：`C:\Projects\signal-forge`
- Shell：PowerShell
- 每次讀取中文文件前，先設定：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
```

- 讀中文 Markdown 時優先使用：

```powershell
Get-Content -Encoding UTF8 -LiteralPath <path>
```

- 不要因為 PowerShell 顯示亂碼就判定檔案壞掉；必須先用 UTF-8 讀回確認。
- 不要把中文筆記改成 ASCII-only 來規避顯示問題；文件與筆記要維持繁中。

## 每輪開始前

先讀取目前狀態與核心文件：

```powershell
git status --short --branch
git log -5 --oneline
Get-Content -Encoding UTF8 -LiteralPath AGENTS.md
Get-Content -Encoding UTF8 -LiteralPath docs\phase-roadmap.md
Get-Content -Encoding UTF8 -LiteralPath docs\phase-iteration-log.md
Get-Content -Encoding UTF8 -LiteralPath docs\phase-autoresearch-results.md
Get-Content -Encoding UTF8 -LiteralPath src\signal_forge\phase.py
Get-Content -Encoding UTF8 -LiteralPath tests\test_phase.py
Get-Content -Encoding UTF8 -LiteralPath tools\phase_readiness_score.py
```

如果工作樹已有未提交改動，先判斷是否屬於本輪可接續內容；不得覆蓋使用者不相關改動。

## Autoresearch 夜間工作流

夜間自動化主線是「回測可驗證性」。每個 wakeup 只做一個聚焦改動，遵守：

```text
modify -> verify -> keep/discard -> log
```

優先 backlog：

1. 強化 `*_trace_summary.json`：增加 deterministic、test-covered 的稽核欄位，例如 entry / flatten / hold counts。
2. 強化 `*_signals.csv`：只加入能由既有 signal digest 穩定推導的欄位。
3. 強化 Phase markdown：讓回測報表更容易人工檢查，但必須有 exact-text regression test。
4. 強化 validation：把 backtest artifact 的 ordering、reason、timestamp、position invariants 變成更清楚的 validator。
5. 強化中文筆記同步：每輪更新 `docs\phase-roadmap.md`、`docs\phase-iteration-log.md`、`docs\phase-autoresearch-results.md`，並同步到 Obsidian `repo-notes`。

禁止事項：

- 不做策略績效最佳化。
- 不新增 broker。
- 不新增 API key / credential 讀取。
- 不新增真實下單介面。
- 不碰 live 送單能力。

## Live 安全邊界

`live` 永遠維持 dry-run only，直到使用者明確要求並另外審核真實交易介面。以下 invariant 不可破壞：

- `dry_run=True`
- `submitted=False`
- `safety_note` 含 `LIVE_DRY_RUN_ONLY`
- 無 broker 連線
- 無 API key / credential 讀取
- 無真實訂單送出

## 驗證與推送

每輪固定執行：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
cd C:\Projects\signal-forge
$env:PYTHONPATH = "src"
python tools\phase_readiness_score.py
python -m unittest discover -s tests
git diff --check
```

通過條件：

- readiness score 維持 `110`。
- unit tests 全部通過。
- `git diff --check` clean。
- `git status --short --branch` 只包含本輪預期檔案。

通過後才建立 commit 並 push 到 `origin/main`。程式或測試改動用 `experiment:` 前綴；純文件或 agent 指令調整可用 `docs:` 前綴。若驗證失敗，要用非破壞方式還原或記錄 discard，不得推送失敗狀態。

## Obsidian 同步

Repo 筆記若有更新，必須同步到：

```text
C:\Users\gary1\OneDrive\桌面\obsidian\project開發\SignalForge\repo-notes
```

同步後用 UTF-8 讀回確認。Obsidian vault 不是這個 repo 的 Git 工作樹；push 邊界只適用於 `C:\Projects\signal-forge`。

## 睡覺期間決策邊界

夜間 automation 不處理需要產品判斷的大改動。遇到需要使用者決策的分支，記錄到筆記的「下一步」，不要硬做。
