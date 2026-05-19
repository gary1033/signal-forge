# 第一期策略蒸餾模板

## 基本資料

- 策略名稱：
- TradingView 來源：
- Pine Script 版本：
- 研究日期：
- 研究者：
- 目標商品：
- 目標週期：

## 原始腳本保存

```pine
// Paste original Pine Script here.
```

## Pine 語法與重繪風險

- 是否使用 `request.security`：
- 是否使用 pivot 或延遲確認訊號：
- 是否使用未收盤 bar：
- 是否有 lookahead 或 repaint 風險：
- 需要改寫成已確認 bar 的地方：

## 策略拆解

- 純多進場條件：
- short 條件：
- 濾網條件：
- 停損規則：
- 停利規則：
- 出場規則：
- 加碼或減碼規則：
- 倉位或風控規則：

## 第一期採用規格

- SignalForge 策略名稱：
- 採用參數：
- 純多進場事件：
- 第一階段排除項目：
- 預期資料欄位：
- `hold_bars_per_day`：

## Phase 執行紀錄

- Phase mode：`backtest` / `live`
- Backtest PowerShell 命令：
- Live dry-run PowerShell 命令：
- Backtest adapter：`BacktestExecutionAdapter`
- Live adapter：`LiveExecutionAdapter`
- Live adapter 範圍：只產生 dry-run order intent，不接 broker、不讀交易 API key、不送出真實訂單。
- Order intent 欄位：symbol、side、quantity、reason、dry_run、submitted、safety_note。
- `live` 安全確認：`dry_run=True`、`submitted=False`、safety note 必須明確標示不送單。

## Entry Edge 結論

- 資料期間：
- 交易數：
- Profit Factor：
- 是否通過 `PF > 1.2`：
- 樣本風險：
- 下一步：
