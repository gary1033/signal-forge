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
Get-Content -Encoding UTF8 -LiteralPath docs\00-SignalForge 專案筆記索引.md
Get-Content -Encoding UTF8 -LiteralPath docs\01-架構\SignalForge 架構總覽.md
Get-Content -Encoding UTF8 -LiteralPath docs\02-規劃\SignalForge 大框架規劃.md
Get-Content -Encoding UTF8 -LiteralPath docs\03-程式疊代\Phase 程式疊代紀錄.md
Get-Content -Encoding UTF8 -LiteralPath docs\04-實驗記錄\Autoresearch 實驗記錄.md
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
5. 強化中文筆記同步：每輪先更新 Obsidian `SignalForge` 專案筆記，再同步回 repo `docs\` 作為可 push 的鏡像副本。

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

Obsidian 是 SignalForge 筆記主來源。整理、研究、策略解說與實驗紀錄先更新：

```text
C:\Users\gary1\OneDrive\桌面\obsidian\project開發\SignalForge
```

push 前必須將上述 Obsidian 資料夾同步到：

```text
C:\Projects\signal-forge\docs
```

同步方向是 Obsidian -> repo `docs\`。同步時先清空 repo `docs\` 的舊內容，再複製目前整理後的 Obsidian 筆記與策略圖片。同步後用 UTF-8 讀回確認。Obsidian vault 不是這個 repo 的 Git 工作樹；push 邊界只適用於 `C:\Projects\signal-forge`。

目前 repo `docs\` 的 canonical 結構：

- `00-SignalForge 專案筆記索引.md`
- `01-架構\SignalForge 架構總覽.md`
- `02-規劃\SignalForge 大框架規劃.md`
- `策略筆記\`
- `03-程式疊代\Phase 程式疊代紀錄.md`
- `04-實驗記錄\`

## 策略筆記同步

策略研究與策略實作的專用筆記放在：

```text
C:\Users\gary1\OneDrive\桌面\obsidian\project開發\SignalForge\策略筆記
```

每一種已使用、已回測或已納入文件的策略，都必須在此資料夾建立一份獨立策略筆記。新增策略、修改策略邏輯、調整策略參數、改變訊號判定、或修改回測解讀時，都要同步更新對應策略筆記。

策略筆記至少包含：

- 策略名稱與 repo 對應實作位置。
- 策略假設、進出場條件、主要參數與風險邊界。
- 使用的資料來源、回測期間、輸出 artifact 與驗證命令。
- 最近一次策略變更紀錄與下一步。
- 使用 image generation 產生的股價走勢解說圖，並在筆記中嵌入圖片，說明策略如何對價格趨勢、進場、出場或持倉狀態做判斷。

圖片必須是用來解說策略，不得暗示真實績效保證；若策略仍在研究或 dry-run 階段，筆記需明確標示。

## 睡覺期間決策邊界

夜間 automation 不處理需要產品判斷的大改動。遇到需要使用者決策的分支，記錄到筆記的「下一步」，不要硬做。
