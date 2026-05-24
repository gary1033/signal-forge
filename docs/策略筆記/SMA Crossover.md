---
title: SMA Crossover
tags:
  - project/SignalForge
  - trading/strategy
  - trading/trend
status: research
updated: 2026-05-24
repo_impl: C:\Projects\signal-forge\src\signal_forge\strategies\sma_crossover.py
---

# SMA Crossover

## 快速定位

| 問題 | 答案 |
|---|---|
| CLI 名稱 | `sma-crossover` |
| 適用資料 | 日線 OHLCV |
| 策略型態 | long-only 趨勢追蹤 baseline |
| 實作位置 | `src\signal_forge\strategies\sma_crossover.py` |
| 參數入口 | `src\signal_forge\cli\strategy_options.py` |

## 先懂這些詞

- **SMA**：簡單移動平均，把最近 N 根收盤價平均成一條趨勢線。
- **Fast SMA**：短期均線，反應較快。
- **Slow SMA**：長期均線，反應較慢。
- **Golden cross**：短期均線站上長期均線，視為趨勢轉強。

## 策略假設

當短期均線高於長期均線時，市場較可能處在上升趨勢；當短期均線低於長期均線時，先不要持有。這是最基本的趨勢追蹤 baseline，目的不是成為最強策略，而是提供可比較的長期趨勢基準。

## 進出場規則

| 判定點 | 目標曝險 | 維護語意 |
|---|---:|---|
| fast SMA 尚未暖機 | `0.0` | 短期趨勢線還沒有足夠資料，不允許用不完整均線判斷進場。 |
| slow SMA 尚未暖機 | `0.0` | 長期基準線尚未形成時，策略沒有趨勢濾網，因此保持空手。 |
| `fast_sma > slow_sma` | `1.0` | 短期價格平均已站上長期平均，視為趨勢轉強並持有 long。 |
| `fast_sma <= slow_sma` | `0.0` | 短期趨勢不再優於長期基準，既有 long 也應退回 flat。 |

## 主要參數

| 參數 | 預設 | CLI | 用途與調整判斷 |
|---|---:|---|---|
| `fast_window` | `20` | `--fast-window` | 控制短期趨勢反應速度；調小會更快進出但更容易被盤整雜訊干擾，調大則訊號更慢。 |
| `slow_window` | `200` | `--slow-window` | 定義長期趨勢基準；調小會讓 baseline 更敏感，調大會更保守但可能錯過反轉初期。 |
| `allow_short` | `False` | 不開放 Phase 1 short | Phase 1 刻意固定 long-only，避免把趨勢 baseline 和放空語意混在同一次研究裡。 |

## 怎麼跑

精簡版：

```powershell
$Csv = "data\processed\TWSE_2330_1D.csv"
python -m signal_forge.cli entry-edge --csv $Csv --strategy sma-crossover
```

完整版：

```powershell
python -m signal_forge.cli entry-edge `
  --csv $Csv `
  --strategy sma-crossover `
  --fast-window 20 `
  --slow-window 200 `
  --hold-bars-per-day 1 `
  --commission-bps 1 `
  --slippage-bps 1 `
  --transaction-tax-bps 0 `
  --output-dir reports\generated `
  --run-name tsmc-sma-20-200
```

## 股價走勢解說圖

![[assets/sma-crossover-trend-explainer.png]]

圖中用示意走勢說明：短期均線站上長期均線後才允許 long，跌回長期均線下方時回到空手。此圖不是績效保證。

## 風險與限制

- 趨勢盤清楚時較容易工作，盤整時容易反覆進出。
- `slow_window=200` 會讓策略反應慢，適合當 baseline，不適合拿來追短線轉折。
- 單檔結果不能直接代表策略有效，仍要做多股票、成本壓力與 benchmark relative 檢查。

## 下一步

- 若要降低盤整噪音，優先測 [[Volume Filter]] 或 [[Signal Cooldown]]，不要先改成更複雜的多因子策略。
- 若要比較長期趨勢，和 [[Absolute Momentum]] 一起跑同一批股票與同一組成本壓力。
