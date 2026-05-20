from __future__ import annotations

from signal_forge.core.market_data import Bar, validate_bars
from signal_forge.core.strategy import Strategy
from signal_forge.phase.adapters import BacktestExecutionAdapter, LiveExecutionAdapter
from signal_forge.phase.config import PhaseConfig
from signal_forge.phase.results import PhaseExecutionResult


class PhaseRunner:
    def __init__(
        self,
        *,
        backtest_adapter: BacktestExecutionAdapter | None = None,
        live_adapter: LiveExecutionAdapter | None = None,
    ) -> None:
        """
        用途與流程：初始化 PhaseRunner，保存 backtest/live adapter，讓測試可注入替身 adapter。
        參數：backtest_adapter 與 live_adapter 可為 None；None 時使用預設 adapter。
        回傳與錯誤：回傳 None；adapter 型別錯誤會在後續呼叫 run 時自然暴露。
        """
        self.backtest_adapter = backtest_adapter or BacktestExecutionAdapter()
        self.live_adapter = live_adapter or LiveExecutionAdapter()

    def run(
        self, config: PhaseConfig, strategy: Strategy, bars: list[Bar]
    ) -> PhaseExecutionResult:
        """
        用途與流程：先驗證 bars 滿足 hold period 需求，再依 PhaseConfig mode 分派到 backtest 或 live adapter。
        參數：config 是 Phase 設定；strategy 是符合 Strategy contract 的策略；bars 是 OHLCV Bar 清單。
        回傳與錯誤：回傳 PhaseExecutionResult；資料驗證失敗時拋出 ValueError 並列出 validate_bars errors。
        """
        validation = validate_bars(bars, min_bars=config.hold_bars_per_day + 1)
        if not validation.is_valid:
            errors = "; ".join(validation.errors)
            raise ValueError(f"phase input data invalid: {errors}")

        if config.is_backtest:
            return self.backtest_adapter.run(config, strategy, bars)
        return self.live_adapter.run(config, strategy, bars)
