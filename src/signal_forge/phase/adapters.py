from __future__ import annotations

from signal_forge.backtesting.entry_edge import EntryEdgeConfig, EntryEdgeEvaluator
from signal_forge.core.market_data import Bar
from signal_forge.core.signals import (
    build_signal_digests,
    generate_validated_signals,
    normalize_signal_reason,
)
from signal_forge.core.strategy import Strategy
from signal_forge.phase.config import PhaseConfig
from signal_forge.phase.intents import OrderIntent
from signal_forge.phase.results import PhaseExecutionResult


class BacktestExecutionAdapter:
    name = "backtest"

    def run(
        self, config: PhaseConfig, strategy: Strategy, bars: list[Bar]
    ) -> PhaseExecutionResult:
        """
        用途與流程：執行 backtest adapter，單次產生 signals 後同時供 entry-edge 與 signal digest 使用。
        參數：config 是 PhaseConfig；strategy 是待評估策略；bars 是已通過 PhaseRunner 基本驗證的 OHLCV 序列。
        回傳與錯誤：回傳 PhaseExecutionResult；若策略 signal 筆數不等於 bars，會由 generate_validated_signals 拋出 ValueError。
        """
        signals = generate_validated_signals(strategy, bars)
        result = EntryEdgeEvaluator(
            EntryEdgeConfig(hold_bars_per_day=config.hold_bars_per_day)
        ).run_from_signals(strategy.name, bars, signals)

        return PhaseExecutionResult(
            mode="backtest",
            adapter_name=self.name,
            dry_run=False,
            entry_edge_result=result,
            order_intents=[],
            signal_digests=build_signal_digests(signals),
        )


class LiveExecutionAdapter:
    name = "live"

    def run(
        self, config: PhaseConfig, strategy: Strategy, bars: list[Bar]
    ) -> PhaseExecutionResult:
        """
        用途與流程：執行 live dry-run adapter，只把新 long entry 轉成 OrderIntent，不連 broker 也不送單。
        參數：config 是 PhaseConfig 且 dry_run 必須為 True；strategy 是待評估策略；bars 是 OHLCV 序列。
        回傳與錯誤：回傳 PhaseExecutionResult；若 config 破壞 dry-run 邊界或 signal 筆數不一致，拋出 ValueError。
        """
        if not config.dry_run:
            raise ValueError("live mode is dry-run only until backtests are stable")

        signals = generate_validated_signals(strategy, bars)
        order_intents: list[OrderIntent] = []
        previous_target = 0.0
        epsilon = 1e-12
        for signal in signals:
            is_long_entry = signal.target_position > epsilon and previous_target <= epsilon
            previous_target = signal.target_position
            if not is_long_entry:
                continue
            order_intents.append(
                OrderIntent(
                    timestamp=signal.timestamp,
                    side="buy",
                    target_position=signal.target_position,
                    reason=normalize_signal_reason(signal.reason),
                )
            )

        return PhaseExecutionResult(
            mode="live",
            adapter_name=self.name,
            dry_run=True,
            entry_edge_result=None,
            order_intents=order_intents,
        )
