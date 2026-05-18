# Sample Data

第一版範例使用 `examples/run_sample_backtest.py` 內建的合成 OHLCV 資料，避免把資料源和策略框架綁死。

後續若加入真實資料，建議流程如下：

1. 原始資料放在 `data/raw/`。
2. 清洗後資料放在 `data/processed/`。
3. 小型、可公開、可重現的測試資料才放在 `data/sample/` 並納入 Git。

