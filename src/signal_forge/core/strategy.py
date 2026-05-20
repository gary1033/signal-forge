from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generic, TypeVar

from signal_forge.core.market_data import Bar


ContextT = TypeVar("ContextT")


@dataclass(frozen=True)
class Signal:
    index: int
    timestamp: str
    target_position: float
    reason: str
    score: float = 0.0


@dataclass(frozen=True)
class StrategyDecision:
    target_position: float
    reason: str
    score: float = 0.0


class Strategy(ABC):
    name: str

    @abstractmethod
    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        """
        用途與流程：根據輸入 K 線序列產生逐 bar 對齊的 Signal 清單，維持策略輸出 contract。
        參數：self 表示目前物件實例；bars（list[Bar]）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 list[Signal]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """


class BarByBarStrategy(Strategy, Generic[ContextT]):
    def generate_signals(self, bars: list[Bar]) -> list[Signal]:
        """
        用途與流程：根據輸入 K 線序列產生逐 bar 對齊的 Signal 清單，維持策略輸出 contract。
        參數：self 表示目前物件實例；bars（list[Bar]）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 list[Signal]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        context = self.prepare_context(bars)
        previous_target_position = 0.0
        signals: list[Signal] = []

        for index, bar in enumerate(bars):
            decision = self.decide_bar(
                index=index,
                bar=bar,
                bars=bars,
                context=context,
                previous_target_position=previous_target_position,
            )
            signals.append(
                Signal(
                    index=index,
                    timestamp=bar.timestamp,
                    target_position=decision.target_position,
                    reason=decision.reason,
                    score=decision.score,
                )
            )
            previous_target_position = decision.target_position

        return signals

    @abstractmethod
    def prepare_context(self, bars: list[Bar]) -> ContextT:
        """
        用途與流程：預先計算策略決策會重複使用的技術指標或中介資料，避免逐 bar 重複計算。
        參數：self 表示目前物件實例；bars（list[Bar]）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 ContextT；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """

    @abstractmethod
    def decide_bar(
        self,
        *,
        index: int,
        bar: Bar,
        bars: list[Bar],
        context: ContextT,
        previous_target_position: float,
    ) -> StrategyDecision:
        """
        用途與流程：針對單一 bar 與前一根目標部位做策略判斷，輸出 target position、reason 與 score。
        參數：self 表示目前物件實例；index（int）由呼叫端傳入，需符合函式 contract；bar（Bar）由呼叫端傳入，需符合函式 contract；bars（list[Bar]）由呼叫端傳入，需符合函式 contract；context（ContextT）由呼叫端傳入，需符合函式 contract；previous_target_position（float）由呼叫端傳入，需符合函式 contract
        回傳與錯誤：回傳 StrategyDecision；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
