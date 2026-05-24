from __future__ import annotations

import argparse
import json
import sys
from calendar import monthrange
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from math import sqrt
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from signal_forge import BacktestConfig
from signal_forge.core.market_data import Bar
from tools.multi_stock_target_state_sweep import (
    WalkForwardWindow,
    infer_symbol_from_path,
    load_filtered_bars,
    parse_cost_multipliers_list,
    parse_walk_forward_windows,
)


PORTFOLIO_ROTATION_STRATEGY = "portfolio-relative-momentum-rotation"
RANKING_MODES = ("total-return", "group-residual")


@dataclass(frozen=True)
class PortfolioPoint:
    """Portfolio rotation 權益曲線的一個時間點，保留曝險與當下持倉股票。"""

    timestamp: str
    equity: float
    exposure: float
    selected_symbols: tuple[str, ...]


@dataclass(frozen=True)
class PortfolioRotationResult:
    """單一成本倍率與日期窗下的 portfolio rotation 回測摘要。"""

    strategy: str
    cost_multiplier: float
    cost_label: str
    rebalance_frequency: str
    lookback_bars: int
    ranking_skip_bars: int
    ranking_mode: str
    top_n: int
    min_return: float
    market_regime_filter: bool
    market_regime_sma_bars: int
    breadth_filter: bool
    breadth_lookback_bars: int
    breadth_min_positive_count: int
    breadth_positive_threshold: float
    group_breadth_filter: bool
    group_breadth_lookback_bars: int
    group_breadth_min_positive_share: float
    group_breadth_positive_threshold: float
    group_breadth_min_members: int
    liquidity_lookback_bars: int
    min_average_traded_value: float | None
    symbol_groups: dict[str, str]
    max_selections_per_group: int | None
    max_consecutive_selections_per_symbol: int | None
    reentry_cooldown_rebalances: int
    volatility_target: bool
    volatility_lookback_bars: int
    target_annual_volatility: float
    volatility_min_observations: int
    volatility_max_scale: float
    symbol_count: int
    start_timestamp: str
    end_timestamp: str
    total_return: float
    cagr: float | None
    sharpe_ratio: float | None
    sortino_ratio: float | None
    calmar_ratio: float | None
    max_drawdown: float
    benchmark_total_return: float
    benchmark_cagr: float | None
    benchmark_max_drawdown: float
    benchmark_excess_return: float
    benchmark_excess_cagr: float | None
    annualized_active_return: float | None
    tracking_error: float | None
    information_ratio: float | None
    active_max_drawdown: float
    trade_count: int
    rebalance_count: int
    regime_block_count: int
    breadth_block_count: int
    breadth_warmup_count: int
    group_breadth_block_count: int
    group_breadth_warmup_count: int
    liquidity_block_count: int
    liquidity_warmup_count: int
    group_selection_block_count: int
    consecutive_selection_block_count: int
    reentry_cooldown_block_count: int
    volatility_scaled_rebalance_count: int
    volatility_warmup_count: int
    total_cost: float
    average_turnover: float
    average_breadth_positive_count: float | None
    average_group_breadth_positive_share: float | None
    average_liquidity_eligible_count: float | None
    average_volatility_scale: float | None
    average_exposure: float
    average_selected_count: float
    end_equity: float
    max_symbol_abs_contribution_symbol: str | None
    max_symbol_abs_contribution_share: float
    top3_symbol_abs_contribution_share: float
    symbol_attribution: list["PortfolioSymbolAttribution"]
    max_group_abs_contribution_group: str | None
    max_group_abs_contribution_share: float
    top3_group_abs_contribution_share: float
    max_group_average_weight_group: str | None
    max_group_average_weight: float
    top3_group_average_weight: float
    group_attribution: list["PortfolioGroupAttribution"]
    min_symbols_per_selected_group: int = 1
    group_member_block_count: int = 0
    group_contribution_lookback_bars: int = 0
    max_group_contribution_share: float | None = None
    group_contribution_block_count: int = 0
    group_regime_filter: bool = False
    group_regime_lookback_bars: int = 63
    group_regime_min_return: float = 0.0
    group_regime_min_members: int = 1
    group_regime_block_count: int = 0
    group_regime_warmup_count: int = 0
    average_group_regime_return: float | None = None


@dataclass(frozen=True)
class PortfolioSymbolAttribution:
    """單檔股票在 portfolio rotation 回測中的持倉與報酬貢獻摘要。"""

    symbol: str
    selected_bar_count: int
    selected_bar_share: float
    rebalance_selected_count: int
    rebalance_selected_share: float
    average_weight: float
    average_selected_weight: float
    return_contribution: float
    absolute_contribution_share: float


@dataclass(frozen=True)
class PortfolioGroupAttribution:
    """股票群組在 portfolio rotation 回測中的持倉與報酬貢獻摘要。"""

    group: str
    member_symbols: tuple[str, ...]
    selected_bar_count: int
    rebalance_selected_count: int
    average_weight: float
    return_contribution: float
    absolute_contribution_share: float


@dataclass(frozen=True)
class PortfolioWalkForwardResult:
    """單一 walk-forward window 的 portfolio rotation 結果集合。"""

    window: WalkForwardWindow
    results: list[PortfolioRotationResult]


@dataclass(frozen=True)
class PortfolioRetentionRow:
    """相鄰 portfolio rotation windows 的 OOS retention 摘要。"""

    train_label: str
    test_label: str
    cost_multiplier: float
    cost_label: str
    train_total_return: float
    test_total_return: float
    total_return_retention: float | None
    train_benchmark_excess_return: float
    test_benchmark_excess_return: float
    benchmark_excess_retention: float | None
    train_information_ratio: float | None
    test_information_ratio: float | None
    information_ratio_retention: float | None
    train_sharpe_ratio: float | None
    test_sharpe_ratio: float | None
    sharpe_retention: float | None
    train_max_drawdown: float
    test_max_drawdown: float
    drawdown_change: float
    train_active_max_drawdown: float
    test_active_max_drawdown: float
    active_drawdown_change: float


def load_rotation_inputs(
    csv_paths: list[Path],
    *,
    start: str | None,
    end: str | None,
) -> list[tuple[str, Path, list[Bar]]]:
    """
    用途與流程：載入 portfolio rotation 所需的多檔 OHLCV CSV，並套用同一日期窗。
    參數：csv_paths 是多檔 CSV 路徑；start/end 是可選 `YYYY-MM-DD` 日期邊界。
    回傳與錯誤：回傳 `(symbol, path, bars)` 清單；資料區間無 bar 時由 load_filtered_bars 拋出 ValueError。
    """
    return [
        (infer_symbol_from_path(path), path, load_filtered_bars(path, start=start, end=end))
        for path in csv_paths
    ]


def align_close_table(
    loaded: list[tuple[str, Path, list[Bar]]],
) -> tuple[list[str], dict[str, list[float]]]:
    """
    用途與流程：把多檔股票資料對齊到共同 timestamp，建立 portfolio-level 回測使用的 close matrix。
    參數：loaded 是 load_rotation_inputs 的結果，每檔 bars 必須包含 timestamp 與正 close。
    回傳與錯誤：回傳共同 timestamps 與 symbol 到 close list 的 dict；共同日期少於兩根或 close 非正時拋出 ValueError。
    """
    if not loaded:
        raise ValueError("portfolio rotation requires at least one CSV")

    timestamp_sets = [
        {bar.timestamp for bar in bars}
        for _, _, bars in loaded
    ]
    common_timestamps = sorted(set.intersection(*timestamp_sets))
    if len(common_timestamps) < 2:
        raise ValueError("portfolio rotation requires at least two common timestamps")

    closes_by_symbol: dict[str, list[float]] = {}
    for symbol, _, bars in loaded:
        close_by_timestamp = {bar.timestamp: bar.close for bar in bars}
        closes = [close_by_timestamp[timestamp] for timestamp in common_timestamps]
        if any(close <= 0 for close in closes):
            raise ValueError("portfolio rotation requires positive close prices")
        closes_by_symbol[symbol] = closes
    return common_timestamps, closes_by_symbol


def align_traded_value_table(
    loaded: list[tuple[str, Path, list[Bar]]],
    timestamps: list[str],
) -> dict[str, list[float]]:
    """
    用途與流程：依共同 timestamp 建立逐股成交金額矩陣，供 liquidity / capacity gate 使用。
    參數：loaded 是 load_rotation_inputs 的結果；timestamps 是 align_close_table 產生的共同日期序列。
    回傳與錯誤：回傳 symbol 到 `close * volume` 清單；若 close 非正或 volume 為負，拋出 ValueError。
    """
    traded_values_by_symbol: dict[str, list[float]] = {}
    for symbol, _, bars in loaded:
        bar_by_timestamp = {bar.timestamp: bar for bar in bars}
        traded_values: list[float] = []
        for timestamp in timestamps:
            bar = bar_by_timestamp[timestamp]
            if bar.close <= 0:
                raise ValueError("liquidity filter requires positive close prices")
            if bar.volume < 0:
                raise ValueError("liquidity filter requires non-negative volume")
            traded_values.append(bar.close * bar.volume)
        traded_values_by_symbol[symbol] = traded_values
    return traded_values_by_symbol


def run_portfolio_rotation(
    loaded: list[tuple[str, Path, list[Bar]]],
    *,
    config: BacktestConfig,
    cost_multiplier: float,
    rebalance_frequency: str,
    lookback_bars: int,
    top_n: int,
    min_return: float,
    periods_per_year: int,
    ranking_skip_bars: int = 0,
    ranking_mode: str = "total-return",
    market_regime_filter: bool = False,
    market_regime_sma_bars: int = 126,
    breadth_filter: bool = False,
    breadth_lookback_bars: int = 21,
    breadth_min_positive_count: int = 1,
    breadth_positive_threshold: float = 0.0,
    group_breadth_filter: bool = False,
    group_breadth_lookback_bars: int = 21,
    group_breadth_min_positive_share: float = 0.50,
    group_breadth_positive_threshold: float = 0.0,
    group_breadth_min_members: int = 1,
    group_regime_filter: bool = False,
    group_regime_lookback_bars: int = 63,
    group_regime_min_return: float = 0.0,
    group_regime_min_members: int = 1,
    liquidity_lookback_bars: int = 20,
    min_average_traded_value: float | None = None,
    symbol_groups: dict[str, str] | None = None,
    max_selections_per_group: int | None = None,
    min_symbols_per_selected_group: int = 1,
    max_consecutive_selections_per_symbol: int | None = None,
    reentry_cooldown_rebalances: int = 0,
    group_contribution_lookback_bars: int = 0,
    max_group_contribution_share: float | None = None,
    volatility_target: bool = False,
    volatility_lookback_bars: int = 21,
    target_annual_volatility: float = 0.20,
    volatility_min_observations: int | None = None,
    volatility_max_scale: float = 1.0,
) -> PortfolioRotationResult:
    """
    用途與流程：執行 long-only 相對動能投組輪動，依 rebalance 頻率選出 lookback return top-N 且報酬大於門檻的股票等權持有；ranking_skip_bars 可排除最近 N 根 bar 再計算排名，用來測試 skip-recent-period / intermediate momentum；ranking_mode 可用總報酬排序，或改用個股報酬扣掉同組平均報酬的 group-residual 排序，以測試降低產業/群組動能曝險的假設；可選 market regime filter 會在市場等權指數跌破 SMA 時改持現金，可選 breadth filter 會在正動能股票數不足時改持現金，可選 group breadth filter 會排除同群組內正動能比例不足的候選股票；可選 group regime filter 會排除自身群組等權 lookback return 不足的候選股票；可選 liquidity filter 會排除近期平均成交金額不足的股票，可選 group cap / group member gate / consecutive cap / re-entry cooldown 會限制同組、單成員群組、同檔股票持續主導或剛退出後快速回補；可選 group contribution gate 會用最近已實現的 group 權重報酬貢獻暫時排除過度主導的群組；可選 volatility target 會在再平衡日依目標投組近期波動下修曝險；同時累積每檔股票的持倉天數、入選次數與實際權重報酬貢獻。
    參數：loaded 是多檔資料；config 提供初始資金與交易成本；cost_multiplier 放大成本壓力；rebalance_frequency 可為 daily/weekly/monthly；lookback_bars、ranking_skip_bars、ranking_mode、top_n、min_return 定義排序規則；periods_per_year 用於風險年化；market_regime_filter/market_regime_sma_bars 定義是否使用市場趨勢濾網；breadth_filter 相關參數定義市場寬度 crash-protection gate；group_breadth_filter 相關參數定義同產業或自訂群組內部廣度 gate；group_regime_filter 相關參數定義群組自身絕對動能 gate；liquidity_lookback_bars/min_average_traded_value 定義成交金額可交易性 gate；symbol_groups/max_selections_per_group 定義同組最多入選檔數；min_symbols_per_selected_group 定義入選股票所屬群組至少要有幾個成員，用來阻擋單成員群組依賴；max_consecutive_selections_per_symbol 定義單檔連續入選上限；reentry_cooldown_rebalances 定義股票退出後需等待幾次 rebalance 才能再入選；group_contribution_lookback_bars/max_group_contribution_share 定義以已實現 group 貢獻占比阻擋 dominant group 的線上 gate；volatility_target 相關參數定義是否只降曝險、不加槓桿的 realized-volatility scaling。
    回傳與錯誤：回傳 PortfolioRotationResult；頻率、lookback、top_n 或資料矩陣不合法時拋出 ValueError。
    """
    if lookback_bars <= 0:
        raise ValueError("lookback bars must be positive")
    if ranking_skip_bars < 0:
        raise ValueError("ranking skip bars cannot be negative")
    if ranking_mode not in RANKING_MODES:
        raise ValueError("ranking mode must be one of: " + ", ".join(RANKING_MODES))
    if ranking_mode == "group-residual" and not symbol_groups:
        raise ValueError("group-residual ranking mode requires symbol groups")
    if top_n <= 0:
        raise ValueError("top-n must be positive")
    if rebalance_frequency not in {"daily", "weekly", "monthly"}:
        raise ValueError("rebalance frequency must be daily, weekly, or monthly")
    if market_regime_sma_bars <= 0:
        raise ValueError("market regime SMA bars must be positive")
    if breadth_lookback_bars <= 0:
        raise ValueError("breadth lookback bars must be positive")
    if breadth_min_positive_count <= 0:
        raise ValueError("breadth min positive count must be positive")
    if group_breadth_lookback_bars <= 0:
        raise ValueError("group breadth lookback bars must be positive")
    if group_breadth_min_positive_share <= 0 or group_breadth_min_positive_share > 1:
        raise ValueError("group breadth min positive share must be within (0, 1]")
    if group_breadth_min_members <= 0:
        raise ValueError("group breadth min members must be positive")
    if group_breadth_filter and not symbol_groups:
        raise ValueError("group breadth filter requires symbol groups")
    if group_regime_lookback_bars <= 0:
        raise ValueError("group regime lookback bars must be positive")
    if group_regime_min_members <= 0:
        raise ValueError("group regime min members must be positive")
    if group_regime_filter and not symbol_groups:
        raise ValueError("group regime filter requires symbol groups")
    if liquidity_lookback_bars <= 0:
        raise ValueError("liquidity lookback bars must be positive")
    if min_average_traded_value is not None and min_average_traded_value <= 0:
        raise ValueError("minimum average traded value must be positive")
    if max_selections_per_group is not None and max_selections_per_group <= 0:
        raise ValueError("max selections per group must be positive")
    if min_symbols_per_selected_group <= 0:
        raise ValueError("min symbols per selected group must be positive")
    if min_symbols_per_selected_group > 1 and not symbol_groups:
        raise ValueError(
            "min symbols per selected group greater than 1 requires symbol groups"
        )
    if (
        max_consecutive_selections_per_symbol is not None
        and max_consecutive_selections_per_symbol <= 0
    ):
        raise ValueError("max consecutive selections per symbol must be positive")
    if reentry_cooldown_rebalances < 0:
        raise ValueError("reentry cooldown rebalances cannot be negative")
    if group_contribution_lookback_bars < 0:
        raise ValueError("group contribution lookback bars cannot be negative")
    if max_group_contribution_share is not None:
        if max_group_contribution_share <= 0 or max_group_contribution_share > 1:
            raise ValueError("max group contribution share must be within (0, 1]")
        if group_contribution_lookback_bars <= 0:
            raise ValueError(
                "group contribution lookback bars must be positive when the guard is enabled"
            )
        if not symbol_groups:
            raise ValueError("group contribution guard requires symbol groups")
    volatility_required_observations = (
        volatility_min_observations
        if volatility_min_observations is not None
        else volatility_lookback_bars
    )
    if volatility_lookback_bars <= 1:
        raise ValueError("volatility lookback bars must be greater than 1")
    if target_annual_volatility <= 0:
        raise ValueError("target annual volatility must be positive")
    if volatility_required_observations <= 1:
        raise ValueError("volatility min observations must be greater than 1")
    if volatility_required_observations > volatility_lookback_bars:
        raise ValueError("volatility min observations cannot exceed lookback bars")
    if volatility_max_scale <= 0 or volatility_max_scale > 1:
        raise ValueError("volatility max scale must be greater than 0 and no more than 1")

    timestamps, closes_by_symbol = align_close_table(loaded)
    traded_values_by_symbol = align_traded_value_table(loaded, timestamps)
    symbols = sorted(closes_by_symbol)
    effective_symbol_groups = _normalize_symbol_groups(
        symbols,
        symbol_groups=symbol_groups,
    )
    group_member_counts = _group_member_counts(effective_symbol_groups)
    if lookback_bars + ranking_skip_bars >= len(timestamps):
        raise ValueError(
            "lookback bars plus ranking skip bars must be smaller than the common timestamp count"
        )
    if breadth_min_positive_count > len(symbols):
        raise ValueError("breadth min positive count cannot exceed symbol count")

    effective_config = BacktestConfig(
        initial_equity=config.initial_equity,
        commission_bps=config.commission_bps * cost_multiplier,
        slippage_bps=config.slippage_bps * cost_multiplier,
        transaction_tax_bps=config.transaction_tax_bps * cost_multiplier,
    )
    entry_cost_rate = (
        effective_config.commission_bps + effective_config.slippage_bps
    ) / 10_000.0
    exit_cost_rate = (
        effective_config.commission_bps
        + effective_config.slippage_bps
        + effective_config.transaction_tax_bps
    ) / 10_000.0

    equity = effective_config.initial_equity
    weights = {symbol: 0.0 for symbol in symbols}
    points = [PortfolioPoint(timestamps[0], equity, 0.0, ())]
    trade_count = 0
    rebalance_count = 0
    total_cost = 0.0
    turnover_values: list[float] = []
    breadth_count_values: list[int] = []
    group_breadth_share_values: list[float] = []
    group_regime_return_values: list[float] = []
    liquidity_eligible_count_values: list[int] = []
    volatility_scale_values: list[float] = []
    selected_counts: list[int] = [0]
    exposure_values: list[float] = [0.0]
    regime_block_count = 0
    breadth_block_count = 0
    breadth_warmup_count = 0
    group_breadth_block_count = 0
    group_breadth_warmup_count = 0
    group_regime_block_count = 0
    group_regime_warmup_count = 0
    liquidity_block_count = 0
    liquidity_warmup_count = 0
    group_selection_block_count = 0
    group_member_block_count = 0
    group_contribution_block_count = 0
    consecutive_selection_block_count = 0
    reentry_cooldown_block_count = 0
    volatility_scaled_rebalance_count = 0
    volatility_warmup_count = 0
    market_index_values = _equal_weight_price_index(symbols, closes_by_symbol)
    selected_bar_counts = {symbol: 0 for symbol in symbols}
    rebalance_selected_counts = {symbol: 0 for symbol in symbols}
    total_weight_sums = {symbol: 0.0 for symbol in symbols}
    selected_weight_sums = {symbol: 0.0 for symbol in symbols}
    return_contributions = {symbol: 0.0 for symbol in symbols}
    consecutive_selection_counts = {symbol: 0 for symbol in symbols}
    reentry_cooldown_counts = {symbol: 0 for symbol in symbols}
    group_contribution_history: list[dict[str, float]] = []

    for index in range(1, len(timestamps)):
        period_return = 0.0
        period_group_contributions = {
            group: 0.0 for group in sorted(set(effective_symbol_groups.values()))
        }
        for symbol in symbols:
            weight = weights[symbol]
            symbol_return = (
                closes_by_symbol[symbol][index] / closes_by_symbol[symbol][index - 1]
            ) - 1.0
            contribution = weight * symbol_return
            group = effective_symbol_groups.get(symbol, symbol)
            period_return += contribution
            period_group_contributions[group] = (
                period_group_contributions.get(group, 0.0) + contribution
            )
            total_weight_sums[symbol] += abs(weight)
            if abs(weight) > 1e-12:
                selected_bar_counts[symbol] += 1
                selected_weight_sums[symbol] += abs(weight)
                return_contributions[symbol] += contribution

        equity *= 1.0 + period_return
        group_contribution_history.append(period_group_contributions)

        if index >= lookback_bars + ranking_skip_bars and _is_rebalance_index(
            timestamps,
            index=index,
            frequency=rebalance_frequency,
        ):
            should_select = False
            if market_regime_filter and not _market_regime_is_risk_on(
                market_index_values,
                index=index,
                sma_bars=market_regime_sma_bars,
            ):
                target_weights = {symbol: 0.0 for symbol in symbols}
                regime_block_count += 1
            elif breadth_filter:
                breadth_count = _breadth_positive_count(
                    symbols,
                    closes_by_symbol,
                    index=index,
                    lookback_bars=breadth_lookback_bars,
                    positive_threshold=breadth_positive_threshold,
                )
                if breadth_count is None:
                    target_weights = {symbol: 0.0 for symbol in symbols}
                    breadth_warmup_count += 1
                elif breadth_count < breadth_min_positive_count:
                    target_weights = {symbol: 0.0 for symbol in symbols}
                    breadth_count_values.append(breadth_count)
                    breadth_block_count += 1
                else:
                    breadth_count_values.append(breadth_count)
                    should_select = True
            else:
                should_select = True

            group_breadth_eligible_groups: set[str] | None = None
            group_regime_eligible_groups: set[str] | None = None
            if should_select and group_breadth_filter:
                group_breadth_shares = _group_breadth_positive_shares(
                    symbols,
                    closes_by_symbol,
                    index=index,
                    lookback_bars=group_breadth_lookback_bars,
                    positive_threshold=group_breadth_positive_threshold,
                    symbol_groups=effective_symbol_groups,
                )
                if group_breadth_shares is None:
                    target_weights = {symbol: 0.0 for symbol in symbols}
                    group_breadth_warmup_count += 1
                    should_select = False
                else:
                    group_breadth_share_values.extend(group_breadth_shares.values())
                    group_breadth_eligible_groups = {
                        group
                        for group, positive_share in group_breadth_shares.items()
                        if group_member_counts.get(group, 0)
                        >= group_breadth_min_members
                        and positive_share >= group_breadth_min_positive_share
                    }

            if should_select and group_regime_filter:
                group_regime_returns = _group_regime_returns(
                    symbols,
                    closes_by_symbol,
                    index=index,
                    lookback_bars=group_regime_lookback_bars,
                    symbol_groups=effective_symbol_groups,
                )
                if group_regime_returns is None:
                    target_weights = {symbol: 0.0 for symbol in symbols}
                    group_regime_warmup_count += 1
                    should_select = False
                else:
                    group_regime_return_values.extend(group_regime_returns.values())
                    group_regime_eligible_groups = {
                        group
                        for group, group_return in group_regime_returns.items()
                        if group_member_counts.get(group, 0) >= group_regime_min_members
                        and group_return > group_regime_min_return
                    }

            if should_select:
                consecutive_exclusions = _consecutive_selection_exclusions(
                    consecutive_selection_counts,
                    max_consecutive_selections=max_consecutive_selections_per_symbol,
                )
                reentry_cooldown_exclusions = _reentry_cooldown_exclusions(
                    reentry_cooldown_counts,
                    cooldown_rebalances=reentry_cooldown_rebalances,
                )
                group_contribution_exclusions = _group_contribution_exclusions(
                    group_contribution_history,
                    lookback_bars=group_contribution_lookback_bars,
                    max_contribution_share=max_group_contribution_share,
                )
                liquidity_exclusions: set[str] = set()
                if min_average_traded_value is not None:
                    liquidity_eligible_symbols = _liquidity_eligible_symbols(
                        symbols,
                        traded_values_by_symbol,
                        index=index,
                        lookback_bars=liquidity_lookback_bars,
                        min_average_traded_value=min_average_traded_value,
                    )
                    if liquidity_eligible_symbols is None:
                        target_weights = {symbol: 0.0 for symbol in symbols}
                        liquidity_warmup_count += 1
                        should_select = False
                    else:
                        liquidity_eligible_count_values.append(
                            len(liquidity_eligible_symbols)
                        )
                        liquidity_exclusions = (
                            set(symbols) - liquidity_eligible_symbols
                        )
                        (
                            pre_liquidity_weights,
                            _pre_consecutive,
                            _pre_group,
                            _pre_group_member,
                            _pre_group_contribution,
                            _pre_group_breadth,
                            _pre_group_regime,
                            _pre_reentry,
                        ) = _target_rotation_weights_with_block_counts(
                            symbols,
                            closes_by_symbol,
                            index=index,
                            lookback_bars=lookback_bars,
                            ranking_skip_bars=ranking_skip_bars,
                            ranking_mode=ranking_mode,
                            top_n=top_n,
                            min_return=min_return,
                            excluded_symbols=consecutive_exclusions,
                            reentry_excluded_symbols=reentry_cooldown_exclusions,
                            excluded_groups=group_contribution_exclusions,
                            group_breadth_eligible_groups=group_breadth_eligible_groups,
                            group_regime_eligible_groups=group_regime_eligible_groups,
                            symbol_groups=effective_symbol_groups,
                            max_selections_per_group=max_selections_per_group,
                            group_member_counts=group_member_counts,
                            min_symbols_per_selected_group=(
                                min_symbols_per_selected_group
                            ),
                        )
                        if any(
                            weight > 1e-12 and symbol in liquidity_exclusions
                            for symbol, weight in pre_liquidity_weights.items()
                        ):
                            liquidity_block_count += 1

            if should_select:
                (
                    target_weights,
                    consecutive_blocked_symbol_count,
                    group_blocked_symbol_count,
                    group_member_blocked_symbol_count,
                    group_contribution_blocked_symbol_count,
                    group_breadth_blocked_symbol_count,
                    group_regime_blocked_symbol_count,
                    reentry_blocked_symbol_count,
                ) = _target_rotation_weights_with_block_counts(
                    symbols,
                    closes_by_symbol,
                    index=index,
                    lookback_bars=lookback_bars,
                    ranking_skip_bars=ranking_skip_bars,
                    ranking_mode=ranking_mode,
                    top_n=top_n,
                    min_return=min_return,
                    excluded_symbols=consecutive_exclusions | liquidity_exclusions,
                    reentry_excluded_symbols=reentry_cooldown_exclusions,
                    excluded_groups=group_contribution_exclusions,
                    group_breadth_eligible_groups=group_breadth_eligible_groups,
                    group_regime_eligible_groups=group_regime_eligible_groups,
                    symbol_groups=effective_symbol_groups,
                    max_selections_per_group=max_selections_per_group,
                    group_member_counts=group_member_counts,
                    min_symbols_per_selected_group=min_symbols_per_selected_group,
                )
                if consecutive_blocked_symbol_count > 0:
                    consecutive_selection_block_count += 1
                if group_blocked_symbol_count > 0:
                    group_selection_block_count += 1
                if group_member_blocked_symbol_count > 0:
                    group_member_block_count += 1
                if group_contribution_blocked_symbol_count > 0:
                    group_contribution_block_count += 1
                if group_breadth_blocked_symbol_count > 0:
                    group_breadth_block_count += 1
                if group_regime_blocked_symbol_count > 0:
                    group_regime_block_count += 1
                if reentry_blocked_symbol_count > 0:
                    reentry_cooldown_block_count += 1
            if volatility_target and _has_exposure(target_weights):
                volatility_scale = _volatility_target_scale(
                    symbols,
                    closes_by_symbol,
                    target_weights,
                    index=index,
                    lookback_bars=volatility_lookback_bars,
                    min_observations=volatility_required_observations,
                    target_annual_volatility=target_annual_volatility,
                    periods_per_year=periods_per_year,
                    max_scale=volatility_max_scale,
                )
                if volatility_scale is None:
                    target_weights = {symbol: 0.0 for symbol in symbols}
                    volatility_warmup_count += 1
                else:
                    target_weights = {
                        symbol: weight * volatility_scale
                        for symbol, weight in target_weights.items()
                    }
                    volatility_scale_values.append(volatility_scale)
                    if volatility_scale < volatility_max_scale - 1e-9:
                        volatility_scaled_rebalance_count += 1
            turnover = sum(
                abs(target_weights[symbol] - weights[symbol])
                for symbol in symbols
            )
            turnover_values.append(turnover)
            rebalance_count += 1
            _update_reentry_cooldowns(
                reentry_cooldown_counts,
                previous_weights=weights,
                target_weights=target_weights,
                cooldown_rebalances=reentry_cooldown_rebalances,
            )
            _update_consecutive_selection_counts(
                consecutive_selection_counts,
                target_weights,
            )
            for symbol in symbols:
                if target_weights[symbol] > 1e-12:
                    rebalance_selected_counts[symbol] += 1
            if turnover > 1e-12:
                for symbol in symbols:
                    delta = target_weights[symbol] - weights[symbol]
                    if abs(delta) <= 1e-12:
                        continue
                    cost_rate = exit_cost_rate if delta < 0 else entry_cost_rate
                    cost = abs(delta) * equity * cost_rate
                    equity -= cost
                    total_cost += cost
                    trade_count += 1
                weights = target_weights

        selected_symbols = tuple(
            symbol for symbol in symbols if weights[symbol] > 1e-12
        )
        exposure = sum(abs(value) for value in weights.values())
        selected_counts.append(len(selected_symbols))
        exposure_values.append(exposure)
        points.append(
            PortfolioPoint(
                timestamp=timestamps[index],
                equity=equity,
                exposure=exposure,
                selected_symbols=selected_symbols,
            )
        )

    benchmark_equity_values = _equal_weight_benchmark_equity_values(
        timestamps,
        closes_by_symbol,
        config=effective_config,
    )
    benchmark = _summarize_equal_weight_benchmark(
        timestamps,
        benchmark_equity_values,
        initial_equity=effective_config.initial_equity,
    )
    equity_values = [point.equity for point in points]
    equity_returns = _equity_returns(equity_values)
    benchmark_returns = _equity_returns(benchmark_equity_values)
    active_returns = _active_returns(equity_returns, benchmark_returns)
    tracking_error = _annualized_tracking_error(active_returns, periods_per_year)
    annualized_active_return = _annualized_mean_return(
        active_returns,
        periods_per_year,
    )
    years = _elapsed_years(timestamps)
    cagr = _compound_annual_growth_rate(
        effective_config.initial_equity,
        equity,
        years,
    )
    symbol_attribution = _build_symbol_attribution(
        symbols,
        selected_bar_counts=selected_bar_counts,
        rebalance_selected_counts=rebalance_selected_counts,
        total_weight_sums=total_weight_sums,
        selected_weight_sums=selected_weight_sums,
        return_contributions=return_contributions,
        period_count=len(timestamps) - 1,
        rebalance_count=rebalance_count,
    )
    max_symbol, max_share, top3_share = _symbol_concentration_metrics(
        symbol_attribution
    )
    group_attribution = _build_group_attribution(
        symbols,
        symbol_groups=effective_symbol_groups,
        selected_bar_counts=selected_bar_counts,
        rebalance_selected_counts=rebalance_selected_counts,
        total_weight_sums=total_weight_sums,
        return_contributions=return_contributions,
        period_count=len(timestamps) - 1,
    )
    max_group, max_group_share, top3_group_share = _group_concentration_metrics(
        group_attribution
    )
    (
        max_group_exposure,
        max_group_average_weight,
        top3_group_average_weight,
    ) = _group_exposure_metrics(group_attribution)
    return PortfolioRotationResult(
        strategy=PORTFOLIO_ROTATION_STRATEGY,
        cost_multiplier=cost_multiplier,
        cost_label=_format_cost_label(cost_multiplier),
        rebalance_frequency=rebalance_frequency,
        lookback_bars=lookback_bars,
        ranking_skip_bars=ranking_skip_bars,
        ranking_mode=ranking_mode,
        top_n=top_n,
        min_return=min_return,
        market_regime_filter=market_regime_filter,
        market_regime_sma_bars=market_regime_sma_bars,
        breadth_filter=breadth_filter,
        breadth_lookback_bars=breadth_lookback_bars,
        breadth_min_positive_count=breadth_min_positive_count,
        breadth_positive_threshold=breadth_positive_threshold,
        group_breadth_filter=group_breadth_filter,
        group_breadth_lookback_bars=group_breadth_lookback_bars,
        group_breadth_min_positive_share=group_breadth_min_positive_share,
        group_breadth_positive_threshold=group_breadth_positive_threshold,
        group_breadth_min_members=group_breadth_min_members,
        liquidity_lookback_bars=liquidity_lookback_bars,
        min_average_traded_value=min_average_traded_value,
        symbol_groups=effective_symbol_groups,
        max_selections_per_group=max_selections_per_group,
        min_symbols_per_selected_group=min_symbols_per_selected_group,
        max_consecutive_selections_per_symbol=max_consecutive_selections_per_symbol,
        reentry_cooldown_rebalances=reentry_cooldown_rebalances,
        group_contribution_lookback_bars=group_contribution_lookback_bars,
        max_group_contribution_share=max_group_contribution_share,
        group_contribution_block_count=group_contribution_block_count,
        group_regime_filter=group_regime_filter,
        group_regime_lookback_bars=group_regime_lookback_bars,
        group_regime_min_return=group_regime_min_return,
        group_regime_min_members=group_regime_min_members,
        group_regime_block_count=group_regime_block_count,
        group_regime_warmup_count=group_regime_warmup_count,
        average_group_regime_return=_average_optional(group_regime_return_values),
        volatility_target=volatility_target,
        volatility_lookback_bars=volatility_lookback_bars,
        target_annual_volatility=target_annual_volatility,
        volatility_min_observations=volatility_required_observations,
        volatility_max_scale=volatility_max_scale,
        symbol_count=len(symbols),
        start_timestamp=timestamps[0],
        end_timestamp=timestamps[-1],
        total_return=(equity / effective_config.initial_equity) - 1.0,
        cagr=cagr,
        sharpe_ratio=_annualized_sharpe_ratio(equity_returns, periods_per_year),
        sortino_ratio=_annualized_sortino_ratio(equity_returns, periods_per_year),
        calmar_ratio=_calmar_ratio(cagr, _max_drawdown(equity_values)),
        max_drawdown=_max_drawdown(equity_values),
        benchmark_total_return=benchmark["total_return"],
        benchmark_cagr=benchmark["cagr"],
        benchmark_max_drawdown=benchmark["max_drawdown"],
        benchmark_excess_return=((equity / effective_config.initial_equity) - 1.0)
        - benchmark["total_return"],
        benchmark_excess_cagr=_subtract_optional(cagr, benchmark["cagr"]),
        annualized_active_return=annualized_active_return,
        tracking_error=tracking_error,
        information_ratio=_information_ratio(
            annualized_active_return,
            tracking_error,
        ),
        active_max_drawdown=_active_max_drawdown(
            equity_values,
            benchmark_equity_values,
            effective_config.initial_equity,
        ),
        trade_count=trade_count,
        rebalance_count=rebalance_count,
        regime_block_count=regime_block_count,
        breadth_block_count=breadth_block_count,
        breadth_warmup_count=breadth_warmup_count,
        group_breadth_block_count=group_breadth_block_count,
        group_breadth_warmup_count=group_breadth_warmup_count,
        liquidity_block_count=liquidity_block_count,
        liquidity_warmup_count=liquidity_warmup_count,
        group_selection_block_count=group_selection_block_count,
        group_member_block_count=group_member_block_count,
        consecutive_selection_block_count=consecutive_selection_block_count,
        reentry_cooldown_block_count=reentry_cooldown_block_count,
        volatility_scaled_rebalance_count=volatility_scaled_rebalance_count,
        volatility_warmup_count=volatility_warmup_count,
        total_cost=total_cost,
        average_turnover=_average(turnover_values),
        average_breadth_positive_count=_average_int_optional(breadth_count_values),
        average_group_breadth_positive_share=_average_optional(
            group_breadth_share_values
        ),
        average_liquidity_eligible_count=_average_int_optional(
            liquidity_eligible_count_values
        ),
        average_volatility_scale=_average_optional(volatility_scale_values),
        average_exposure=_average(exposure_values),
        average_selected_count=_average_float(selected_counts),
        end_equity=equity,
        max_symbol_abs_contribution_symbol=max_symbol,
        max_symbol_abs_contribution_share=max_share,
        top3_symbol_abs_contribution_share=top3_share,
        symbol_attribution=symbol_attribution,
        max_group_abs_contribution_group=max_group,
        max_group_abs_contribution_share=max_group_share,
        top3_group_abs_contribution_share=top3_group_share,
        max_group_average_weight_group=max_group_exposure,
        max_group_average_weight=max_group_average_weight,
        top3_group_average_weight=top3_group_average_weight,
        group_attribution=group_attribution,
    )


def _build_symbol_attribution(
    symbols: list[str],
    *,
    selected_bar_counts: dict[str, int],
    rebalance_selected_counts: dict[str, int],
    total_weight_sums: dict[str, float],
    selected_weight_sums: dict[str, float],
    return_contributions: dict[str, float],
    period_count: int,
    rebalance_count: int,
) -> list[PortfolioSymbolAttribution]:
    """
    用途與流程：把 portfolio rotation 回測過程累積的逐股持倉與權重報酬貢獻，整理成 deterministic attribution rows，讓研究者判斷報酬是否集中在少數股票。
    參數：symbols 是排序後股票代號；selected_bar_counts 是每檔實際持倉期間數；rebalance_selected_counts 是每檔在再平衡日被目標權重選中的次數；total_weight_sums / selected_weight_sums 是整段期間與被選中期間的權重加總；return_contributions 是每檔 `weight * close-to-close return` 的加總；period_count 與 rebalance_count 是比例分母。
    回傳與錯誤：回傳依 absolute contribution share 由大到小排序的 PortfolioSymbolAttribution 清單；分母為 0 時比例欄位回傳 0，不主動拋錯。
    """
    absolute_total_contribution = sum(
        abs(return_contributions.get(symbol, 0.0)) for symbol in symbols
    )
    rows: list[PortfolioSymbolAttribution] = []
    for symbol in symbols:
        selected_bar_count = selected_bar_counts.get(symbol, 0)
        rebalance_selected_count = rebalance_selected_counts.get(symbol, 0)
        return_contribution = return_contributions.get(symbol, 0.0)
        rows.append(
            PortfolioSymbolAttribution(
                symbol=symbol,
                selected_bar_count=selected_bar_count,
                selected_bar_share=(
                    selected_bar_count / period_count if period_count > 0 else 0.0
                ),
                rebalance_selected_count=rebalance_selected_count,
                rebalance_selected_share=(
                    rebalance_selected_count / rebalance_count
                    if rebalance_count > 0
                    else 0.0
                ),
                average_weight=(
                    total_weight_sums.get(symbol, 0.0) / period_count
                    if period_count > 0
                    else 0.0
                ),
                average_selected_weight=(
                    selected_weight_sums.get(symbol, 0.0) / selected_bar_count
                    if selected_bar_count > 0
                    else 0.0
                ),
                return_contribution=return_contribution,
                absolute_contribution_share=(
                    abs(return_contribution) / absolute_total_contribution
                    if absolute_total_contribution > 0
                    else 0.0
                ),
            )
        )
    return sorted(
        rows,
        key=lambda row: (-row.absolute_contribution_share, row.symbol),
    )


def _symbol_concentration_metrics(
    symbol_attribution: list[PortfolioSymbolAttribution],
) -> tuple[str | None, float, float]:
    """
    用途與流程：從已排序的逐股 attribution 推導集中度摘要，作為策略是否過度依賴少數股票的 guard 指標。
    參數：symbol_attribution 是 `_build_symbol_attribution(...)` 產生的清單，通常已依絕對貢獻占比排序。
    回傳與錯誤：回傳 `(max_symbol, max_share, top3_share)`；清單為空時股票代號為 None、比例為 0，此函式不主動拋錯。
    """
    if not symbol_attribution:
        return None, 0.0, 0.0
    top_rows = sorted(
        symbol_attribution,
        key=lambda row: (-row.absolute_contribution_share, row.symbol),
    )
    return (
        top_rows[0].symbol,
        top_rows[0].absolute_contribution_share,
        sum(row.absolute_contribution_share for row in top_rows[:3]),
    )


def _build_group_attribution(
    symbols: list[str],
    *,
    symbol_groups: dict[str, str],
    selected_bar_counts: dict[str, int],
    rebalance_selected_counts: dict[str, int],
    total_weight_sums: dict[str, float],
    return_contributions: dict[str, float],
    period_count: int,
) -> list[PortfolioGroupAttribution]:
    """
    用途與流程：把逐股持倉與報酬貢獻彙總到自訂 group / sector，判斷 portfolio rotation 是否從單檔集中轉成群組集中。
    參數：symbols 是本次回測股票代號；symbol_groups 是 symbol 到群組名稱的完整映射；selected_bar_counts、rebalance_selected_counts、total_weight_sums 與 return_contributions 是回測過程累積的逐股統計；period_count 是平均權重分母。
    回傳與錯誤：回傳依群組絕對貢獻占比排序的 PortfolioGroupAttribution 清單；缺少分組時用 symbol 本身作 fallback，不主動拋錯。
    """
    symbols_by_group: dict[str, list[str]] = {}
    for symbol in symbols:
        group = symbol_groups.get(symbol, symbol)
        symbols_by_group.setdefault(group, []).append(symbol)

    group_return_contributions = {
        group: sum(return_contributions.get(symbol, 0.0) for symbol in members)
        for group, members in symbols_by_group.items()
    }
    absolute_total_contribution = sum(
        abs(return_contribution)
        for return_contribution in group_return_contributions.values()
    )

    rows: list[PortfolioGroupAttribution] = []
    for group in sorted(symbols_by_group):
        members = tuple(sorted(symbols_by_group[group]))
        return_contribution = group_return_contributions[group]
        rows.append(
            PortfolioGroupAttribution(
                group=group,
                member_symbols=members,
                selected_bar_count=sum(
                    selected_bar_counts.get(symbol, 0) for symbol in members
                ),
                rebalance_selected_count=sum(
                    rebalance_selected_counts.get(symbol, 0) for symbol in members
                ),
                average_weight=(
                    sum(total_weight_sums.get(symbol, 0.0) for symbol in members)
                    / period_count
                    if period_count > 0
                    else 0.0
                ),
                return_contribution=return_contribution,
                absolute_contribution_share=(
                    abs(return_contribution) / absolute_total_contribution
                    if absolute_total_contribution > 0
                    else 0.0
                ),
            )
        )
    return sorted(
        rows,
        key=lambda row: (-row.absolute_contribution_share, row.group),
    )


def _group_concentration_metrics(
    group_attribution: list[PortfolioGroupAttribution],
) -> tuple[str | None, float, float]:
    """
    用途與流程：從群組 attribution 推導最大群組與 top-3 群組貢獻占比，作為 sector / group concentration guard。
    參數：group_attribution 是 `_build_group_attribution(...)` 產生的清單，通常已依絕對貢獻占比排序。
    回傳與錯誤：回傳 `(max_group, max_share, top3_share)`；清單為空時 group 為 None、比例為 0，不主動拋錯。
    """
    if not group_attribution:
        return None, 0.0, 0.0
    top_rows = sorted(
        group_attribution,
        key=lambda row: (-row.absolute_contribution_share, row.group),
    )
    return (
        top_rows[0].group,
        top_rows[0].absolute_contribution_share,
        sum(row.absolute_contribution_share for row in top_rows[:3]),
    )


def _group_exposure_metrics(
    group_attribution: list[PortfolioGroupAttribution],
) -> tuple[str | None, float, float]:
    """
    用途與流程：從群組 attribution 的 average_weight 推導最大群組與前三群組平均曝險，判斷策略是否長期把資金集中在少數群組。
    參數：group_attribution 是 `_build_group_attribution(...)` 產生的群組 attribution 清單，需包含每個群組的平均權重。
    回傳與錯誤：回傳 `(max_group, max_average_weight, top3_average_weight)`；空清單時 group 為 None、比例為 0，不主動拋錯。
    """
    if not group_attribution:
        return None, 0.0, 0.0
    top_rows = sorted(
        group_attribution,
        key=lambda row: (-row.average_weight, row.group),
    )
    return (
        top_rows[0].group,
        top_rows[0].average_weight,
        sum(row.average_weight for row in top_rows[:3]),
    )


def run_equal_weight_benchmark(
    timestamps: list[str],
    closes_by_symbol: dict[str, list[float]],
    *,
    config: BacktestConfig,
    periods_per_year: int,
) -> dict[str, float | None]:
    """
    用途與流程：建立 equal-weight buy-and-hold portfolio benchmark，作為輪動策略的 portfolio-level 比較基準。
    參數：timestamps 是共同日期序列；closes_by_symbol 是對齊後 close matrix；config 提供初始資金與入場成本；periods_per_year 保留給既有呼叫介面相容。
    回傳與錯誤：回傳 total_return、cagr、max_drawdown；若資料不足或無 symbol，拋出 ValueError。
    """
    equity_values = _equal_weight_benchmark_equity_values(
        timestamps,
        closes_by_symbol,
        config=config,
    )
    return _summarize_equal_weight_benchmark(
        timestamps,
        equity_values,
        initial_equity=config.initial_equity,
    )


def _equal_weight_benchmark_equity_values(
    timestamps: list[str],
    closes_by_symbol: dict[str, list[float]],
    *,
    config: BacktestConfig,
) -> list[float]:
    """
    用途與流程：建立 equal-weight buy-and-hold benchmark 的權益曲線，供總報酬與 active-risk 指標共用。
    參數：timestamps 是共同日期序列；closes_by_symbol 是對齊後 close matrix；config 提供期初資金與入場成本。
    回傳與錯誤：回傳每個 timestamp 的 benchmark equity；資料不足或 symbol 為空時拋出 ValueError。
    """
    if len(timestamps) < 2 or not closes_by_symbol:
        raise ValueError("equal-weight benchmark requires aligned close data")
    symbols = sorted(closes_by_symbol)
    entry_cost_rate = (config.commission_bps + config.slippage_bps) / 10_000.0
    equity = config.initial_equity * (1.0 - entry_cost_rate)
    equity_values = [equity]
    weights = {symbol: 1.0 / len(symbols) for symbol in symbols}
    for index in range(1, len(timestamps)):
        equity *= 1.0 + _portfolio_price_return(
            symbols,
            closes_by_symbol,
            weights,
            previous_index=index - 1,
            current_index=index,
        )
        equity_values.append(equity)
    return equity_values


def _summarize_equal_weight_benchmark(
    timestamps: list[str],
    equity_values: list[float],
    *,
    initial_equity: float,
) -> dict[str, float | None]:
    """
    用途與流程：把 benchmark 權益曲線轉成摘要欄位，避免報表與 active-risk 計算使用不同基準。
    參數：timestamps 是 benchmark 日期序列；equity_values 是同長度權益曲線；initial_equity 是比較基準的期初資金。
    回傳與錯誤：回傳 total_return、cagr、max_drawdown；權益曲線不足時拋出 ValueError。
    """
    if len(equity_values) < 2:
        raise ValueError("equal-weight benchmark requires at least two equity points")
    equity = equity_values[-1]
    years = _elapsed_years(timestamps)
    return {
        "total_return": (equity / initial_equity) - 1.0,
        "cagr": _compound_annual_growth_rate(initial_equity, equity, years),
        "max_drawdown": _max_drawdown(equity_values),
    }


def run_portfolio_rotation_sweep(
    *,
    csv_paths: list[Path],
    start: str | None,
    end: str | None,
    cost_multipliers: tuple[float, ...],
    initial_equity: float,
    commission_bps: float,
    slippage_bps: float,
    transaction_tax_bps: float,
    rebalance_frequency: str,
    lookback_bars: int,
    top_n: int,
    min_return: float,
    periods_per_year: int,
    ranking_skip_bars: int = 0,
    ranking_mode: str = "total-return",
    market_regime_filter: bool = False,
    market_regime_sma_bars: int = 126,
    breadth_filter: bool = False,
    breadth_lookback_bars: int = 21,
    breadth_min_positive_count: int = 1,
    breadth_positive_threshold: float = 0.0,
    group_breadth_filter: bool = False,
    group_breadth_lookback_bars: int = 21,
    group_breadth_min_positive_share: float = 0.50,
    group_breadth_positive_threshold: float = 0.0,
    group_breadth_min_members: int = 1,
    group_regime_filter: bool = False,
    group_regime_lookback_bars: int = 63,
    group_regime_min_return: float = 0.0,
    group_regime_min_members: int = 1,
    liquidity_lookback_bars: int = 20,
    min_average_traded_value: float | None = None,
    symbol_groups: dict[str, str] | None = None,
    max_selections_per_group: int | None = None,
    min_symbols_per_selected_group: int = 1,
    max_consecutive_selections_per_symbol: int | None = None,
    reentry_cooldown_rebalances: int = 0,
    group_contribution_lookback_bars: int = 0,
    max_group_contribution_share: float | None = None,
    volatility_target: bool = False,
    volatility_lookback_bars: int = 21,
    target_annual_volatility: float = 0.20,
    volatility_min_observations: int | None = None,
    volatility_max_scale: float = 1.0,
) -> list[PortfolioRotationResult]:
    """
    用途與流程：對同一批股票資料在多個成本倍率下執行 portfolio rotation 回測。
    參數：csv_paths、start/end 定義資料；cost_multipliers 定義成本壓力；ranking_skip_bars 定義排名時計算到幾根 bar 以前；ranking_mode 定義總報酬或 group residual 排序；market_regime_filter/market_regime_sma_bars 是可選市場趨勢濾網；breadth_filter 相關參數是可選市場寬度 gate；group_breadth_filter 相關參數是可選群組內部廣度 gate；group_regime_filter 相關參數是可選群組自身絕對動能 gate；liquidity_lookback_bars/min_average_traded_value 是可選成交金額 gate；symbol_groups/max_selections_per_group 是可選同組持股數限制；min_symbols_per_selected_group 是可選群組成員數下限；max_consecutive_selections_per_symbol 是單檔連續入選上限；reentry_cooldown_rebalances 是退出後等待再入選的 rebalance 次數；group_contribution_lookback_bars/max_group_contribution_share 是已實現群組貢獻集中度 gate；volatility_target 相關參數是可選波動降曝險 overlay；其餘參數傳給 run_portfolio_rotation。
    回傳與錯誤：回傳每個成本倍率一筆 PortfolioRotationResult；資料或參數不合法時由底層拋出 ValueError。
    """
    loaded = load_rotation_inputs(csv_paths, start=start, end=end)
    config = BacktestConfig(
        initial_equity=initial_equity,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        transaction_tax_bps=transaction_tax_bps,
    )
    return [
        run_portfolio_rotation(
            loaded,
            config=config,
            cost_multiplier=cost_multiplier,
            rebalance_frequency=rebalance_frequency,
            lookback_bars=lookback_bars,
            ranking_skip_bars=ranking_skip_bars,
            ranking_mode=ranking_mode,
            top_n=top_n,
            min_return=min_return,
            periods_per_year=periods_per_year,
            market_regime_filter=market_regime_filter,
            market_regime_sma_bars=market_regime_sma_bars,
            breadth_filter=breadth_filter,
            breadth_lookback_bars=breadth_lookback_bars,
            breadth_min_positive_count=breadth_min_positive_count,
            breadth_positive_threshold=breadth_positive_threshold,
            group_breadth_filter=group_breadth_filter,
            group_breadth_lookback_bars=group_breadth_lookback_bars,
            group_breadth_min_positive_share=group_breadth_min_positive_share,
            group_breadth_positive_threshold=group_breadth_positive_threshold,
            group_breadth_min_members=group_breadth_min_members,
            group_regime_filter=group_regime_filter,
            group_regime_lookback_bars=group_regime_lookback_bars,
            group_regime_min_return=group_regime_min_return,
            group_regime_min_members=group_regime_min_members,
            liquidity_lookback_bars=liquidity_lookback_bars,
            min_average_traded_value=min_average_traded_value,
            symbol_groups=symbol_groups,
            max_selections_per_group=max_selections_per_group,
            min_symbols_per_selected_group=min_symbols_per_selected_group,
            max_consecutive_selections_per_symbol=max_consecutive_selections_per_symbol,
            reentry_cooldown_rebalances=reentry_cooldown_rebalances,
            group_contribution_lookback_bars=group_contribution_lookback_bars,
            max_group_contribution_share=max_group_contribution_share,
            volatility_target=volatility_target,
            volatility_lookback_bars=volatility_lookback_bars,
            target_annual_volatility=target_annual_volatility,
            volatility_min_observations=volatility_min_observations,
            volatility_max_scale=volatility_max_scale,
        )
        for cost_multiplier in cost_multipliers
    ]


def run_walk_forward_rotation(
    *,
    windows: tuple[WalkForwardWindow, ...],
    csv_paths: list[Path],
    cost_multipliers: tuple[float, ...],
    initial_equity: float,
    commission_bps: float,
    slippage_bps: float,
    transaction_tax_bps: float,
    rebalance_frequency: str,
    lookback_bars: int,
    top_n: int,
    min_return: float,
    periods_per_year: int,
    ranking_skip_bars: int = 0,
    ranking_mode: str = "total-return",
    market_regime_filter: bool = False,
    market_regime_sma_bars: int = 126,
    breadth_filter: bool = False,
    breadth_lookback_bars: int = 21,
    breadth_min_positive_count: int = 1,
    breadth_positive_threshold: float = 0.0,
    group_breadth_filter: bool = False,
    group_breadth_lookback_bars: int = 21,
    group_breadth_min_positive_share: float = 0.50,
    group_breadth_positive_threshold: float = 0.0,
    group_breadth_min_members: int = 1,
    group_regime_filter: bool = False,
    group_regime_lookback_bars: int = 63,
    group_regime_min_return: float = 0.0,
    group_regime_min_members: int = 1,
    liquidity_lookback_bars: int = 20,
    min_average_traded_value: float | None = None,
    symbol_groups: dict[str, str] | None = None,
    max_selections_per_group: int | None = None,
    min_symbols_per_selected_group: int = 1,
    max_consecutive_selections_per_symbol: int | None = None,
    reentry_cooldown_rebalances: int = 0,
    group_contribution_lookback_bars: int = 0,
    max_group_contribution_share: float | None = None,
    volatility_target: bool = False,
    volatility_lookback_bars: int = 21,
    target_annual_volatility: float = 0.20,
    volatility_min_observations: int | None = None,
    volatility_max_scale: float = 1.0,
) -> tuple[list[PortfolioWalkForwardResult], list[PortfolioRetentionRow]]:
    """
    用途與流程：依 walk-forward windows 重跑 portfolio rotation，並計算相鄰 window 的 OOS retention。
    參數：windows 是分段日期；ranking_skip_bars 定義排名時計算到幾根 bar 以前；ranking_mode 定義總報酬或 group residual 排序；market_regime_filter/market_regime_sma_bars 是可選市場趨勢濾網；breadth_filter 相關參數是可選市場寬度 gate；group_breadth_filter 相關參數是可選群組內部廣度 gate；group_regime_filter 相關參數是可選群組自身絕對動能 gate；liquidity_lookback_bars/min_average_traded_value 是可選成交金額 gate；symbol_groups/max_selections_per_group 是可選同組持股數限制；min_symbols_per_selected_group 是可選群組成員數下限；max_consecutive_selections_per_symbol 是單檔連續入選上限；reentry_cooldown_rebalances 是退出後等待再入選的 rebalance 次數；group_contribution_lookback_bars/max_group_contribution_share 是已實現群組貢獻集中度 gate；volatility_target 相關參數是可選波動降曝險 overlay；其他參數與 run_portfolio_rotation_sweep 相同，只改每個 window 的 start/end。
    回傳與錯誤：回傳 window 結果與 retention rows；若某 window 資料不足，底層會拋出 ValueError。
    """
    window_results: list[PortfolioWalkForwardResult] = []
    for window in windows:
        window_results.append(
            PortfolioWalkForwardResult(
                window=window,
                results=run_portfolio_rotation_sweep(
                    csv_paths=csv_paths,
                    start=window.start,
                    end=window.end,
                    cost_multipliers=cost_multipliers,
                    initial_equity=initial_equity,
                    commission_bps=commission_bps,
                    slippage_bps=slippage_bps,
                    transaction_tax_bps=transaction_tax_bps,
                    rebalance_frequency=rebalance_frequency,
                    lookback_bars=lookback_bars,
                    ranking_skip_bars=ranking_skip_bars,
                    ranking_mode=ranking_mode,
                    top_n=top_n,
                    min_return=min_return,
                    periods_per_year=periods_per_year,
                    market_regime_filter=market_regime_filter,
                    market_regime_sma_bars=market_regime_sma_bars,
                    breadth_filter=breadth_filter,
                    breadth_lookback_bars=breadth_lookback_bars,
                    breadth_min_positive_count=breadth_min_positive_count,
                    breadth_positive_threshold=breadth_positive_threshold,
                    group_breadth_filter=group_breadth_filter,
                    group_breadth_lookback_bars=group_breadth_lookback_bars,
                    group_breadth_min_positive_share=group_breadth_min_positive_share,
                    group_breadth_positive_threshold=group_breadth_positive_threshold,
                    group_breadth_min_members=group_breadth_min_members,
                    group_regime_filter=group_regime_filter,
                    group_regime_lookback_bars=group_regime_lookback_bars,
                    group_regime_min_return=group_regime_min_return,
                    group_regime_min_members=group_regime_min_members,
                    liquidity_lookback_bars=liquidity_lookback_bars,
                    min_average_traded_value=min_average_traded_value,
                    symbol_groups=symbol_groups,
                    max_selections_per_group=max_selections_per_group,
                    min_symbols_per_selected_group=min_symbols_per_selected_group,
                    max_consecutive_selections_per_symbol=max_consecutive_selections_per_symbol,
                    reentry_cooldown_rebalances=reentry_cooldown_rebalances,
                    group_contribution_lookback_bars=group_contribution_lookback_bars,
                    max_group_contribution_share=max_group_contribution_share,
                    volatility_target=volatility_target,
                    volatility_lookback_bars=volatility_lookback_bars,
                    target_annual_volatility=target_annual_volatility,
                    volatility_min_observations=volatility_min_observations,
                    volatility_max_scale=volatility_max_scale,
                ),
            )
        )
    return window_results, build_portfolio_retention(window_results)


def build_rolling_windows(
    *,
    start: str | None,
    end: str | None,
    window_months: int,
    step_months: int,
    min_window_months: int,
) -> tuple[WalkForwardWindow, ...]:
    """
    用途與流程：由 full-window 起訖日期自動產生滑動日期窗，讓 portfolio rotation 可重複做 rolling stability 檢查。
    參數：start/end 是整體回測日期邊界；window_months 是每個 rolling window 長度；step_months 是下一窗起點間隔；min_window_months 是最後一個不完整 window 的最低月數。
    回傳與錯誤：回傳 WalkForwardWindow tuple；缺少日期、月份參數非正、日期反向或沒有足夠長度時拋出 ValueError。
    """
    if start is None or end is None:
        raise ValueError("rolling windows require --start and --end")
    if window_months <= 0:
        raise ValueError("rolling window months must be positive")
    if step_months <= 0:
        raise ValueError("rolling step months must be positive")
    if min_window_months <= 0:
        raise ValueError("rolling min months must be positive")
    if min_window_months > window_months:
        raise ValueError("rolling min months cannot exceed window months")

    start_date = _parse_timestamp(start).date()
    end_date = _parse_timestamp(end).date()
    if start_date > end_date:
        raise ValueError("rolling window start must be on or before end")

    windows: list[WalkForwardWindow] = []
    cursor = start_date
    while cursor <= end_date:
        full_window_end = min(
            _add_months(cursor, window_months) - timedelta(days=1),
            end_date,
        )
        minimum_end = _add_months(cursor, min_window_months) - timedelta(days=1)
        if full_window_end < minimum_end:
            break
        windows.append(
            WalkForwardWindow(
                label=f"roll{len(windows) + 1:02d}",
                start=cursor.isoformat(),
                end=full_window_end.isoformat(),
            )
        )
        cursor = _add_months(cursor, step_months)

    if not windows:
        raise ValueError("rolling windows produced no valid date windows")
    return tuple(windows)


def build_portfolio_retention(
    window_results: list[PortfolioWalkForwardResult],
) -> list[PortfolioRetentionRow]:
    """
    用途與流程：比較相鄰 portfolio rotation windows 的同一成本倍率結果，計算 OOS 保留率與回撤變化。
    參數：window_results 是 run_walk_forward_rotation 回傳的分段結果。
    回傳與錯誤：回傳 PortfolioRetentionRow 清單；若相鄰 window 缺少同一成本倍率則略過。
    """
    rows: list[PortfolioRetentionRow] = []
    for train_result, test_result in zip(window_results, window_results[1:]):
        test_by_cost = {
            result.cost_multiplier: result for result in test_result.results
        }
        for train in train_result.results:
            test = test_by_cost.get(train.cost_multiplier)
            if test is None:
                continue
            rows.append(
                PortfolioRetentionRow(
                    train_label=train_result.window.label,
                    test_label=test_result.window.label,
                    cost_multiplier=train.cost_multiplier,
                    cost_label=train.cost_label,
                    train_total_return=train.total_return,
                    test_total_return=test.total_return,
                    total_return_retention=_retention_ratio(
                        test.total_return,
                        train.total_return,
                    ),
                    train_benchmark_excess_return=train.benchmark_excess_return,
                    test_benchmark_excess_return=test.benchmark_excess_return,
                    benchmark_excess_retention=_retention_ratio(
                        test.benchmark_excess_return,
                        train.benchmark_excess_return,
                    ),
                    train_information_ratio=train.information_ratio,
                    test_information_ratio=test.information_ratio,
                    information_ratio_retention=_retention_ratio(
                        test.information_ratio,
                        train.information_ratio,
                    ),
                    train_sharpe_ratio=train.sharpe_ratio,
                    test_sharpe_ratio=test.sharpe_ratio,
                    sharpe_retention=_retention_ratio(
                        test.sharpe_ratio,
                        train.sharpe_ratio,
                    ),
                    train_max_drawdown=train.max_drawdown,
                    test_max_drawdown=test.max_drawdown,
                    drawdown_change=test.max_drawdown - train.max_drawdown,
                    train_active_max_drawdown=train.active_max_drawdown,
                    test_active_max_drawdown=test.active_max_drawdown,
                    active_drawdown_change=(
                        test.active_max_drawdown - train.active_max_drawdown
                    ),
                )
            )
    return rows


def format_markdown(
    results: list[PortfolioRotationResult],
    *,
    start: str | None,
    end: str | None,
    periods_per_year: int,
) -> str:
    """
    用途與流程：將 portfolio rotation 回測結果格式化為 Markdown，包含投組層級績效、逐股 attribution 與群組曝險摘要，方便貼入實驗紀錄與人工審查。
    參數：results 是多成本倍率結果；start/end 是日期窗；periods_per_year 是風險年化期數。
    回傳與錯誤：回傳 Markdown 字串；此函式不做 I/O，也不主動拋錯。
    """
    window = f"{start or 'earliest'} to {end or 'latest'}"
    lines = [
        "# Portfolio Rotation Sweep",
        "",
        f"- Window: `{window}`",
        f"- Periods per year: `{periods_per_year}`",
        "",
        "## Portfolio Result",
        "",
        "| Strategy | Cost | Rebalance | Lookback | Ranking skip | Ranking mode | Top N | Regime | Regime SMA | Breadth | Breadth lookback | Breadth min | Avg breadth | Liquidity min | Liquidity lookback | Avg liquid | Liquidity blocks | Liquidity warmup | Group cap | Group blocks | Min group members | Group member blocks | Group breadth | Group breadth lookback | Group breadth min share | Group breadth threshold | Group breadth min members | Avg group breadth | Group breadth blocks | Group breadth warmup | Group regime | Group regime lookback | Group regime min return | Group regime min members | Avg group regime | Group regime blocks | Group regime warmup | Group contrib lookback | Max group contrib | Group contrib blocks | Consec cap | Consec blocks | Reentry cooldown | Reentry blocks | Vol target | Target vol | Avg vol scale | Return | CAGR | Benchmark return | Excess | Excess CAGR | Annual active | Tracking error | IR | MDD | Benchmark MDD | Active MDD | Sharpe | Sortino | Calmar | Trades | Rebalances | Regime blocks | Breadth blocks | Breadth warmup | Vol scaled | Vol warmup | Avg turnover | Avg exposure | Avg selected | Max contrib symbol | Max contrib share | Top3 contrib share | Max group | Max group share | Top3 group share | Max exposure group | Max group avg weight | Top3 group avg weight |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in results:
        lines.append(
            "| "
            f"{result.strategy} | {result.cost_label} | "
            f"{result.rebalance_frequency} | {result.lookback_bars} | "
            f"{result.ranking_skip_bars} | {result.ranking_mode} | "
            f"{result.top_n} | "
            f"{_format_bool(result.market_regime_filter)} | "
            f"{result.market_regime_sma_bars} | {_format_bool(result.breadth_filter)} | "
            f"{result.breadth_lookback_bars} | {result.breadth_min_positive_count} | "
            f"{_format_optional_ratio(result.average_breadth_positive_count)} | "
            f"{_format_optional_float(result.min_average_traded_value)} | "
            f"{result.liquidity_lookback_bars} | "
            f"{_format_optional_ratio(result.average_liquidity_eligible_count)} | "
            f"{result.liquidity_block_count} | "
            f"{result.liquidity_warmup_count} | "
            f"{_format_optional_int(result.max_selections_per_group)} | "
            f"{result.group_selection_block_count} | "
            f"{result.min_symbols_per_selected_group} | "
            f"{result.group_member_block_count} | "
            f"{_format_bool(result.group_breadth_filter)} | "
            f"{result.group_breadth_lookback_bars} | "
            f"{_format_optional_ratio(result.group_breadth_min_positive_share)} | "
            f"{_format_optional_ratio(result.group_breadth_positive_threshold)} | "
            f"{result.group_breadth_min_members} | "
            f"{_format_optional_ratio(result.average_group_breadth_positive_share)} | "
            f"{result.group_breadth_block_count} | "
            f"{result.group_breadth_warmup_count} | "
            f"{_format_bool(result.group_regime_filter)} | "
            f"{result.group_regime_lookback_bars} | "
            f"{_format_optional_ratio(result.group_regime_min_return)} | "
            f"{result.group_regime_min_members} | "
            f"{_format_optional_ratio(result.average_group_regime_return)} | "
            f"{result.group_regime_block_count} | "
            f"{result.group_regime_warmup_count} | "
            f"{result.group_contribution_lookback_bars} | "
            f"{_format_optional_ratio(result.max_group_contribution_share)} | "
            f"{result.group_contribution_block_count} | "
            f"{_format_optional_int(result.max_consecutive_selections_per_symbol)} | "
            f"{result.consecutive_selection_block_count} | "
            f"{result.reentry_cooldown_rebalances} | "
            f"{result.reentry_cooldown_block_count} | "
            f"{_format_bool(result.volatility_target)} | "
            f"{result.target_annual_volatility:.2%} | "
            f"{_format_optional_ratio(result.average_volatility_scale)} | "
            f"{result.total_return:.2%} | "
            f"{_format_optional_percent(result.cagr)} | "
            f"{result.benchmark_total_return:.2%} | "
            f"{result.benchmark_excess_return:.2%} | "
            f"{_format_optional_percent(result.benchmark_excess_cagr)} | "
            f"{_format_optional_percent(result.annualized_active_return)} | "
            f"{_format_optional_percent(result.tracking_error)} | "
            f"{_format_optional_ratio(result.information_ratio)} | "
            f"{result.max_drawdown:.2%} | "
            f"{result.benchmark_max_drawdown:.2%} | "
            f"{result.active_max_drawdown:.2%} | "
            f"{_format_optional_ratio(result.sharpe_ratio)} | "
            f"{_format_optional_ratio(result.sortino_ratio)} | "
            f"{_format_optional_ratio(result.calmar_ratio)} | "
            f"{result.trade_count} | {result.rebalance_count} | "
            f"{result.regime_block_count} | {result.breadth_block_count} | "
            f"{result.breadth_warmup_count} | "
            f"{result.volatility_scaled_rebalance_count} | "
            f"{result.volatility_warmup_count} | "
            f"{result.average_turnover:.2f} | "
            f"{result.average_exposure:.2%} | "
            f"{result.average_selected_count:.2f} | "
            f"{result.max_symbol_abs_contribution_symbol or 'none'} | "
            f"{result.max_symbol_abs_contribution_share:.2%} | "
            f"{result.top3_symbol_abs_contribution_share:.2%} | "
            f"{result.max_group_abs_contribution_group or 'none'} | "
            f"{result.max_group_abs_contribution_share:.2%} | "
            f"{result.top3_group_abs_contribution_share:.2%} | "
            f"{result.max_group_average_weight_group or 'none'} | "
            f"{result.max_group_average_weight:.2%} | "
            f"{result.top3_group_average_weight:.2%} |"
        )
    lines.extend(_format_symbol_attribution_lines(results, heading="Top Symbol Attribution", limit=5))
    lines.extend(_format_group_attribution_lines(results, heading="Top Group Attribution", limit=5))
    return "\n".join(lines) + "\n"


def format_walk_forward_markdown(
    window_results: list[PortfolioWalkForwardResult],
    retention_rows: list[PortfolioRetentionRow],
) -> str:
    """
    用途與流程：將 portfolio rotation walk-forward 結果格式化成 Markdown 附加章節，包含各窗口的群組曝險摘要。
    參數：window_results 是每個日期窗結果；retention_rows 是相鄰窗的保留率比較。
    回傳與錯誤：沒有 window 結果時回傳空字串；此函式不做 I/O。
    """
    if not window_results:
        return ""
    lines = [
        "",
        "## Walk-forward Windows",
        "",
        "| Window | Range | Cost | Return | Benchmark return | Excess | Excess CAGR | Annual active | Tracking error | IR | MDD | Benchmark MDD | Active MDD | Sharpe | Trades | Regime blocks | Breadth blocks | Group breadth blocks | Group regime blocks | Liquidity blocks | Group cap | Group blocks | Min group members | Group member blocks | Group breadth | Group breadth min share | Avg group breadth | Group regime | Group regime min return | Avg group regime | Group contrib lookback | Max group contrib | Group contrib blocks | Consec cap | Consec blocks | Reentry cooldown | Reentry blocks | Avg breadth | Avg liquid | Vol scaled | Avg vol scale | Avg exposure | Max contrib symbol | Max contrib share | Top3 contrib share | Max group | Max group share | Top3 group share | Max exposure group | Max group avg weight | Top3 group avg weight |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for window_result in window_results:
        window_range = f"{window_result.window.start or 'earliest'} to {window_result.window.end or 'latest'}"
        for result in window_result.results:
            lines.append(
                "| "
                f"{window_result.window.label} | {window_range} | "
                f"{result.cost_label} | {result.total_return:.2%} | "
                f"{result.benchmark_total_return:.2%} | "
                f"{result.benchmark_excess_return:.2%} | "
                f"{_format_optional_percent(result.benchmark_excess_cagr)} | "
                f"{_format_optional_percent(result.annualized_active_return)} | "
                f"{_format_optional_percent(result.tracking_error)} | "
                f"{_format_optional_ratio(result.information_ratio)} | "
                f"{result.max_drawdown:.2%} | "
                f"{result.benchmark_max_drawdown:.2%} | "
                f"{result.active_max_drawdown:.2%} | "
                f"{_format_optional_ratio(result.sharpe_ratio)} | "
                f"{result.trade_count} | {result.regime_block_count} | "
                f"{result.breadth_block_count} | "
                f"{result.group_breadth_block_count} | "
                f"{result.group_regime_block_count} | "
                f"{result.liquidity_block_count} | "
                f"{_format_optional_int(result.max_selections_per_group)} | "
                f"{result.group_selection_block_count} | "
                f"{result.min_symbols_per_selected_group} | "
                f"{result.group_member_block_count} | "
                f"{_format_bool(result.group_breadth_filter)} | "
                f"{_format_optional_ratio(result.group_breadth_min_positive_share)} | "
                f"{_format_optional_ratio(result.average_group_breadth_positive_share)} | "
                f"{_format_bool(result.group_regime_filter)} | "
                f"{_format_optional_ratio(result.group_regime_min_return)} | "
                f"{_format_optional_ratio(result.average_group_regime_return)} | "
                f"{result.group_contribution_lookback_bars} | "
                f"{_format_optional_ratio(result.max_group_contribution_share)} | "
                f"{result.group_contribution_block_count} | "
                f"{_format_optional_int(result.max_consecutive_selections_per_symbol)} | "
                f"{result.consecutive_selection_block_count} | "
                f"{result.reentry_cooldown_rebalances} | "
                f"{result.reentry_cooldown_block_count} | "
                f"{_format_optional_ratio(result.average_breadth_positive_count)} | "
                f"{_format_optional_ratio(result.average_liquidity_eligible_count)} | "
                f"{result.volatility_scaled_rebalance_count} | "
                f"{_format_optional_ratio(result.average_volatility_scale)} | "
                f"{result.average_exposure:.2%} | "
                f"{result.max_symbol_abs_contribution_symbol or 'none'} | "
                f"{result.max_symbol_abs_contribution_share:.2%} | "
                f"{result.top3_symbol_abs_contribution_share:.2%} | "
                f"{result.max_group_abs_contribution_group or 'none'} | "
                f"{result.max_group_abs_contribution_share:.2%} | "
                f"{result.top3_group_abs_contribution_share:.2%} | "
                f"{result.max_group_average_weight_group or 'none'} | "
                f"{result.max_group_average_weight:.2%} | "
                f"{result.top3_group_average_weight:.2%} |"
            )
    lines.extend(
        _format_window_symbol_attribution_lines(
            window_results,
            heading="Walk-forward Top Symbol Attribution",
            limit=3,
        )
    )
    lines.extend(
        _format_window_group_attribution_lines(
            window_results,
            heading="Walk-forward Top Group Attribution",
            limit=3,
        )
    )
    lines.extend(
        [
            "",
            "## Walk-forward Retention",
            "",
            "| Train | Test | Cost | Return retention | Excess retention | IR retention | Sharpe retention | Train return | Test return | Train excess | Test excess | Train IR | Test IR | Train MDD | Test MDD | MDD change | Train active MDD | Test active MDD | Active MDD change |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in retention_rows:
        lines.append(
            "| "
            f"{row.train_label} | {row.test_label} | {row.cost_label} | "
            f"{_format_optional_percent(row.total_return_retention)} | "
            f"{_format_optional_percent(row.benchmark_excess_retention)} | "
            f"{_format_optional_percent(row.information_ratio_retention)} | "
            f"{_format_optional_percent(row.sharpe_retention)} | "
            f"{row.train_total_return:.2%} | {row.test_total_return:.2%} | "
            f"{row.train_benchmark_excess_return:.2%} | "
            f"{row.test_benchmark_excess_return:.2%} | "
            f"{_format_optional_ratio(row.train_information_ratio)} | "
            f"{_format_optional_ratio(row.test_information_ratio)} | "
            f"{row.train_max_drawdown:.2%} | {row.test_max_drawdown:.2%} | "
            f"{row.drawdown_change:.2%} | "
            f"{row.train_active_max_drawdown:.2%} | "
            f"{row.test_active_max_drawdown:.2%} | "
            f"{row.active_drawdown_change:.2%} |"
        )
    return "\n".join(lines) + "\n"


def _format_symbol_attribution_lines(
    results: list[PortfolioRotationResult],
    *,
    heading: str,
    limit: int,
) -> list[str]:
    """
    用途與流程：把 full-window 每個成本倍率的逐股 attribution 轉成 Markdown 表格，優先顯示絕對貢獻占比最高的股票。
    參數：results 是 portfolio rotation 結果；heading 是 Markdown 區段標題；limit 是每個成本倍率最多顯示幾檔股票。
    回傳與錯誤：回傳 Markdown 行清單；limit 小於等於 0 或沒有 attribution 時只回傳空清單。
    """
    if limit <= 0 or not any(result.symbol_attribution for result in results):
        return []
    lines = [
        "",
        f"## {heading}",
        "",
        "| Cost | Rank | Symbol | Return contribution | Abs contribution share | Selected bars | Selected bar share | Rebalance selected | Rebalance share | Avg weight | Avg selected weight |",
        "|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        for rank, row in enumerate(result.symbol_attribution[:limit], start=1):
            lines.append(_format_symbol_attribution_row(result.cost_label, rank, row))
    return lines


def _format_window_symbol_attribution_lines(
    window_results: list[PortfolioWalkForwardResult],
    *,
    heading: str,
    limit: int,
) -> list[str]:
    """
    用途與流程：把每個 rolling / walk-forward window 的逐股 attribution 轉成 Markdown 表格，讓研究者檢查不同時段是否由同一批股票貢獻。
    參數：window_results 是分段回測結果；heading 是 Markdown 區段標題；limit 是每個 window 與成本倍率最多顯示幾檔股票。
    回傳與錯誤：回傳 Markdown 行清單；limit 小於等於 0 或沒有 attribution 時回傳空清單。
    """
    if limit <= 0:
        return []
    has_attribution = any(
        result.symbol_attribution
        for window_result in window_results
        for result in window_result.results
    )
    if not has_attribution:
        return []
    lines = [
        "",
        f"## {heading}",
        "",
        "| Window | Cost | Rank | Symbol | Return contribution | Abs contribution share | Selected bars | Selected bar share | Rebalance selected | Rebalance share | Avg weight | Avg selected weight |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for window_result in window_results:
        for result in window_result.results:
            for rank, row in enumerate(result.symbol_attribution[:limit], start=1):
                lines.append(
                    "| "
                    f"{window_result.window.label} | "
                    f"{_format_symbol_attribution_row(result.cost_label, rank, row).lstrip('| ')}"
                )
    return lines


def _format_group_attribution_lines(
    results: list[PortfolioRotationResult],
    *,
    heading: str,
    limit: int,
) -> list[str]:
    """
    用途與流程：把 full-window 每個成本倍率的群組 attribution 轉成 Markdown 表格，讓策略報表能檢查 sector / group 集中度。
    參數：results 是 portfolio rotation 結果；heading 是 Markdown 區段標題；limit 是每個成本倍率最多顯示幾個群組。
    回傳與錯誤：回傳 Markdown 行清單；limit 小於等於 0 或沒有 group attribution 時只回傳空清單。
    """
    if limit <= 0 or not any(result.group_attribution for result in results):
        return []
    lines = [
        "",
        f"## {heading}",
        "",
        "| Cost | Rank | Group | Members | Return contribution | Abs contribution share | Selected bars | Rebalance selected | Avg weight |",
        "|---:|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        for rank, row in enumerate(result.group_attribution[:limit], start=1):
            lines.append(_format_group_attribution_row(result.cost_label, rank, row))
    return lines


def _format_window_group_attribution_lines(
    window_results: list[PortfolioWalkForwardResult],
    *,
    heading: str,
    limit: int,
) -> list[str]:
    """
    用途與流程：把 rolling / walk-forward window 的群組 attribution 轉成 Markdown 表格，定位不同時段是否由同一產業或自訂群組貢獻。
    參數：window_results 是分段回測結果；heading 是 Markdown 區段標題；limit 是每個 window 與成本倍率最多顯示幾個群組。
    回傳與錯誤：回傳 Markdown 行清單；limit 小於等於 0 或沒有 attribution 時回傳空清單。
    """
    if limit <= 0:
        return []
    has_attribution = any(
        result.group_attribution
        for window_result in window_results
        for result in window_result.results
    )
    if not has_attribution:
        return []
    lines = [
        "",
        f"## {heading}",
        "",
        "| Window | Cost | Rank | Group | Members | Return contribution | Abs contribution share | Selected bars | Rebalance selected | Avg weight |",
        "|---|---:|---:|---|---|---:|---:|---:|---:|---:|",
    ]
    for window_result in window_results:
        for result in window_result.results:
            for rank, row in enumerate(result.group_attribution[:limit], start=1):
                lines.append(
                    "| "
                    f"{window_result.window.label} | "
                    f"{_format_group_attribution_row(result.cost_label, rank, row).lstrip('| ')}"
                )
    return lines


def _format_symbol_attribution_row(
    cost_label: str,
    rank: int,
    row: PortfolioSymbolAttribution,
) -> str:
    """
    用途與流程：把單一 PortfolioSymbolAttribution row 格式化成 Markdown 表格列，供 full-window 與 window-level 表格共用。
    參數：cost_label 是成本倍率標籤；rank 是顯示排名；row 是單檔股票 attribution 結果。
    回傳與錯誤：回傳 Markdown 表格列字串；此函式不做 I/O，也不主動拋錯。
    """
    return (
        "| "
        f"{cost_label} | {rank} | {row.symbol} | "
        f"{row.return_contribution:.2%} | "
        f"{row.absolute_contribution_share:.2%} | "
        f"{row.selected_bar_count} | {row.selected_bar_share:.2%} | "
        f"{row.rebalance_selected_count} | {row.rebalance_selected_share:.2%} | "
        f"{row.average_weight:.2%} | {row.average_selected_weight:.2%} |"
    )


def _format_group_attribution_row(
    cost_label: str,
    rank: int,
    row: PortfolioGroupAttribution,
) -> str:
    """
    用途與流程：把單一 PortfolioGroupAttribution row 格式化成 Markdown 表格列，供 full-window 與 window-level 群組表共用。
    參數：cost_label 是成本倍率標籤；rank 是顯示排名；row 是群組 attribution 結果。
    回傳與錯誤：回傳 Markdown 表格列字串；此函式不做 I/O，也不主動拋錯。
    """
    return (
        "| "
        f"{cost_label} | {rank} | {row.group} | "
        f"{', '.join(row.member_symbols)} | "
        f"{row.return_contribution:.2%} | "
        f"{row.absolute_contribution_share:.2%} | "
        f"{row.selected_bar_count} | "
        f"{row.rebalance_selected_count} | "
        f"{row.average_weight:.2%} |"
    )


def parse_symbol_group_assignments(assignments: list[str] | None) -> dict[str, str]:
    """
    用途與流程：解析 CLI 傳入的 `symbol:group` 清單，轉成 portfolio rotation group cap 使用的股票分組表。
    參數：assignments 是可選字串清單，每筆格式必須是 `股票代號:群組名稱`；None 或空清單表示不提供分組。
    回傳與錯誤：回傳依 symbol 排序的 dict；格式缺少冒號、symbol/group 空白或同一 symbol 重複指定不同 group 時拋出 ValueError。
    """
    if not assignments:
        return {}
    mapping: dict[str, str] = {}
    for raw_assignment in assignments:
        if ":" not in raw_assignment:
            raise ValueError("symbol group assignments must use SYMBOL:GROUP")
        symbol, group = (part.strip() for part in raw_assignment.split(":", 1))
        if not symbol or not group:
            raise ValueError("symbol group assignments require non-empty symbol and group")
        previous_group = mapping.get(symbol)
        if previous_group is not None and previous_group != group:
            raise ValueError(f"symbol {symbol} assigned to multiple groups")
        mapping[symbol] = group
    return dict(sorted(mapping.items()))


def build_parser() -> argparse.ArgumentParser:
    """
    用途與流程：建立 portfolio rotation sweep 的 CLI parser，支援多 CSV、多成本倍率與 walk-forward/OOS。
    參數：無。
    回傳與錯誤：回傳 argparse.ArgumentParser；解析錯誤由 argparse 處理。
    """
    parser = argparse.ArgumentParser(
        description="Run portfolio-level relative momentum rotation across stock CSV files."
    )
    parser.add_argument("--csv", action="append", required=True, help="OHLCV CSV path")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--initial-equity", type=float, default=10_000.0)
    parser.add_argument("--commission-bps", type=float, default=1.0)
    parser.add_argument("--slippage-bps", type=float, default=1.0)
    parser.add_argument("--transaction-tax-bps", type=float, default=0.0)
    parser.add_argument(
        "--cost-multipliers-list",
        default="1",
        help="comma-separated cost stress multipliers, for example 1,2,3",
    )
    parser.add_argument(
        "--rebalance-frequency",
        choices=("daily", "weekly", "monthly"),
        default="weekly",
    )
    parser.add_argument("--lookback-bars", type=int, default=126)
    parser.add_argument(
        "--ranking-skip-bars",
        type=int,
        default=0,
        help=(
            "number of most recent bars to skip before calculating ranking momentum; "
            "use positive values to test skip-recent-period momentum"
        ),
    )
    parser.add_argument(
        "--ranking-mode",
        choices=RANKING_MODES,
        default="total-return",
        help=(
            "ranking score mode: total-return ranks raw lookback returns; "
            "group-residual ranks return minus same-group average return"
        ),
    )
    parser.add_argument("--top-n", type=int, default=3)
    parser.add_argument("--min-return", type=float, default=0.0)
    parser.add_argument("--periods-per-year", type=int, default=252)
    parser.add_argument(
        "--market-regime-filter",
        action="store_true",
        help="hold cash on rebalance dates when equal-weight market index is below its SMA",
    )
    parser.add_argument(
        "--market-regime-sma-bars",
        type=int,
        default=126,
        help="SMA bars for the equal-weight market regime filter",
    )
    parser.add_argument(
        "--breadth-filter",
        action="store_true",
        help="hold cash on rebalance dates when too few symbols have positive breadth momentum",
    )
    parser.add_argument(
        "--breadth-lookback-bars",
        type=int,
        default=21,
        help="lookback bars for breadth momentum count",
    )
    parser.add_argument(
        "--breadth-min-positive-count",
        type=int,
        default=1,
        help="minimum number of symbols with positive breadth momentum required to hold rotation positions",
    )
    parser.add_argument(
        "--breadth-positive-threshold",
        type=float,
        default=0.0,
        help="minimum lookback return for a symbol to count as positive breadth momentum",
    )
    parser.add_argument(
        "--group-breadth-filter",
        action="store_true",
        help=(
            "exclude candidate symbols whose group has insufficient internal "
            "positive momentum breadth on the rebalance date"
        ),
    )
    parser.add_argument(
        "--group-breadth-lookback-bars",
        type=int,
        default=21,
        help="lookback bars for group internal breadth momentum share",
    )
    parser.add_argument(
        "--group-breadth-min-positive-share",
        type=float,
        default=0.50,
        help="minimum positive member share required for a group to be selectable",
    )
    parser.add_argument(
        "--group-breadth-positive-threshold",
        type=float,
        default=0.0,
        help="minimum lookback return for a group member to count as positive",
    )
    parser.add_argument(
        "--group-breadth-min-members",
        type=int,
        default=1,
        help="minimum total group members required before a group can pass group breadth",
    )
    parser.add_argument(
        "--group-regime-filter",
        action="store_true",
        help=(
            "exclude candidate symbols whose group equal-weight lookback return "
            "does not clear the group regime threshold"
        ),
    )
    parser.add_argument(
        "--group-regime-lookback-bars",
        type=int,
        default=63,
        help="lookback bars for group equal-weight absolute momentum",
    )
    parser.add_argument(
        "--group-regime-min-return",
        type=float,
        default=0.0,
        help="minimum group equal-weight lookback return required for selection",
    )
    parser.add_argument(
        "--group-regime-min-members",
        type=int,
        default=1,
        help="minimum total group members required before a group can pass group regime",
    )
    parser.add_argument(
        "--liquidity-lookback-bars",
        type=int,
        default=20,
        help="lookback bars for average traded value liquidity filtering",
    )
    parser.add_argument(
        "--min-average-traded-value",
        type=float,
        help="minimum average close * volume required for a symbol to be selectable",
    )
    parser.add_argument(
        "--symbol-group",
        action="append",
        help="symbol-to-group mapping for group caps, for example 2330:semiconductor",
    )
    parser.add_argument(
        "--max-selections-per-group",
        type=int,
        help="maximum selected symbols per group on each rebalance date",
    )
    parser.add_argument(
        "--min-symbols-per-selected-group",
        type=int,
        default=1,
        help=(
            "minimum member count required for a symbol's group to be selectable; "
            "use values above 1 with --symbol-group to block single-member group dependency"
        ),
    )
    parser.add_argument(
        "--max-consecutive-selections-per-symbol",
        type=int,
        help=(
            "maximum consecutive rebalance selections allowed for one symbol "
            "before it must sit out one rebalance"
        ),
    )
    parser.add_argument(
        "--reentry-cooldown-rebalances",
        type=int,
        default=0,
        help=(
            "number of future rebalance dates a symbol must sit out after it exits; "
            "0 disables the re-entry cooldown gate"
        ),
    )
    parser.add_argument(
        "--group-contribution-lookback-bars",
        type=int,
        default=0,
        help=(
            "trailing realized contribution bars used by the group contribution "
            "concentration guard; 0 disables the guard unless a max share is set"
        ),
    )
    parser.add_argument(
        "--max-group-contribution-share",
        type=float,
        help=(
            "maximum trailing absolute contribution share allowed for one group "
            "before that group is excluded on the next rebalance"
        ),
    )
    parser.add_argument(
        "--volatility-target",
        action="store_true",
        help="scale selected portfolio weights down when realized basket volatility is above target",
    )
    parser.add_argument(
        "--volatility-lookback-bars",
        type=int,
        default=21,
        help="lookback bars for realized volatility scaling",
    )
    parser.add_argument(
        "--target-annual-volatility",
        type=float,
        default=0.20,
        help="annualized volatility target for portfolio weight scaling",
    )
    parser.add_argument(
        "--volatility-min-observations",
        type=int,
        help="minimum return observations before volatility scaling is allowed",
    )
    parser.add_argument(
        "--volatility-max-scale",
        type=float,
        default=1.0,
        help="maximum volatility target scale; defaults to 1.0 so the overlay never adds leverage",
    )
    parser.add_argument(
        "--walk-forward-windows",
        help=(
            "comma-separated label:start:end windows, for example "
            "is:2020-01-01:2023-12-31,oos:2024-01-01:2026-05-20"
        ),
    )
    parser.add_argument(
        "--rolling-window-months",
        type=int,
        help="auto-generate rolling windows with this many calendar months",
    )
    parser.add_argument(
        "--rolling-step-months",
        type=int,
        default=12,
        help="calendar months between rolling window starts",
    )
    parser.add_argument(
        "--rolling-min-months",
        type=int,
        default=12,
        help="minimum calendar months required for the final partial rolling window",
    )
    parser.add_argument("--summary-json")
    parser.add_argument("--summary-md")
    return parser


def main(argv: list[str] | None = None) -> int:
    """
    用途與流程：CLI 入口，解析 portfolio rotation 參數，執行 full-window 與可選 walk-forward 回測並輸出 Markdown/JSON。
    參數：argv 是可選命令列參數清單；None 時使用 sys.argv。
    回傳與錯誤：成功回傳 0；資料、日期窗或策略參數不合法時由底層拋出 ValueError。
    """
    args = build_parser().parse_args(argv)
    csv_paths = [Path(path) for path in args.csv]
    cost_multipliers = parse_cost_multipliers_list(args.cost_multipliers_list)
    symbol_groups = parse_symbol_group_assignments(args.symbol_group)
    results = run_portfolio_rotation_sweep(
        csv_paths=csv_paths,
        start=args.start,
        end=args.end,
        cost_multipliers=cost_multipliers,
        initial_equity=args.initial_equity,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
        transaction_tax_bps=args.transaction_tax_bps,
        rebalance_frequency=args.rebalance_frequency,
        lookback_bars=args.lookback_bars,
        ranking_skip_bars=args.ranking_skip_bars,
        ranking_mode=args.ranking_mode,
        top_n=args.top_n,
        min_return=args.min_return,
        periods_per_year=args.periods_per_year,
        market_regime_filter=args.market_regime_filter,
        market_regime_sma_bars=args.market_regime_sma_bars,
        breadth_filter=args.breadth_filter,
        breadth_lookback_bars=args.breadth_lookback_bars,
        breadth_min_positive_count=args.breadth_min_positive_count,
        breadth_positive_threshold=args.breadth_positive_threshold,
        group_breadth_filter=args.group_breadth_filter,
        group_breadth_lookback_bars=args.group_breadth_lookback_bars,
        group_breadth_min_positive_share=args.group_breadth_min_positive_share,
        group_breadth_positive_threshold=args.group_breadth_positive_threshold,
        group_breadth_min_members=args.group_breadth_min_members,
        group_regime_filter=args.group_regime_filter,
        group_regime_lookback_bars=args.group_regime_lookback_bars,
        group_regime_min_return=args.group_regime_min_return,
        group_regime_min_members=args.group_regime_min_members,
        liquidity_lookback_bars=args.liquidity_lookback_bars,
        min_average_traded_value=args.min_average_traded_value,
        symbol_groups=symbol_groups,
        max_selections_per_group=args.max_selections_per_group,
        min_symbols_per_selected_group=args.min_symbols_per_selected_group,
        max_consecutive_selections_per_symbol=args.max_consecutive_selections_per_symbol,
        reentry_cooldown_rebalances=args.reentry_cooldown_rebalances,
        group_contribution_lookback_bars=args.group_contribution_lookback_bars,
        max_group_contribution_share=args.max_group_contribution_share,
        volatility_target=args.volatility_target,
        volatility_lookback_bars=args.volatility_lookback_bars,
        target_annual_volatility=args.target_annual_volatility,
        volatility_min_observations=args.volatility_min_observations,
        volatility_max_scale=args.volatility_max_scale,
    )
    markdown = format_markdown(
        results,
        start=args.start,
        end=args.end,
        periods_per_year=args.periods_per_year,
    )
    walk_forward_windows: tuple[WalkForwardWindow, ...] = ()
    walk_forward_results: list[PortfolioWalkForwardResult] = []
    retention_rows: list[PortfolioRetentionRow] = []
    if args.walk_forward_windows and args.rolling_window_months:
        raise ValueError("choose either --walk-forward-windows or --rolling-window-months")

    if args.walk_forward_windows or args.rolling_window_months:
        if args.walk_forward_windows:
            walk_forward_windows = parse_walk_forward_windows(args.walk_forward_windows)
        else:
            walk_forward_windows = build_rolling_windows(
                start=args.start,
                end=args.end,
                window_months=args.rolling_window_months,
                step_months=args.rolling_step_months,
                min_window_months=args.rolling_min_months,
            )
        walk_forward_results, retention_rows = run_walk_forward_rotation(
            windows=walk_forward_windows,
            csv_paths=csv_paths,
            cost_multipliers=cost_multipliers,
            initial_equity=args.initial_equity,
            commission_bps=args.commission_bps,
            slippage_bps=args.slippage_bps,
            transaction_tax_bps=args.transaction_tax_bps,
            rebalance_frequency=args.rebalance_frequency,
            lookback_bars=args.lookback_bars,
            ranking_skip_bars=args.ranking_skip_bars,
            ranking_mode=args.ranking_mode,
            top_n=args.top_n,
            min_return=args.min_return,
            periods_per_year=args.periods_per_year,
            market_regime_filter=args.market_regime_filter,
            market_regime_sma_bars=args.market_regime_sma_bars,
            breadth_filter=args.breadth_filter,
            breadth_lookback_bars=args.breadth_lookback_bars,
            breadth_min_positive_count=args.breadth_min_positive_count,
            breadth_positive_threshold=args.breadth_positive_threshold,
            group_breadth_filter=args.group_breadth_filter,
            group_breadth_lookback_bars=args.group_breadth_lookback_bars,
            group_breadth_min_positive_share=args.group_breadth_min_positive_share,
            group_breadth_positive_threshold=args.group_breadth_positive_threshold,
            group_breadth_min_members=args.group_breadth_min_members,
            group_regime_filter=args.group_regime_filter,
            group_regime_lookback_bars=args.group_regime_lookback_bars,
            group_regime_min_return=args.group_regime_min_return,
            group_regime_min_members=args.group_regime_min_members,
            liquidity_lookback_bars=args.liquidity_lookback_bars,
            min_average_traded_value=args.min_average_traded_value,
            symbol_groups=symbol_groups,
            max_selections_per_group=args.max_selections_per_group,
            min_symbols_per_selected_group=args.min_symbols_per_selected_group,
            max_consecutive_selections_per_symbol=args.max_consecutive_selections_per_symbol,
            reentry_cooldown_rebalances=args.reentry_cooldown_rebalances,
            group_contribution_lookback_bars=args.group_contribution_lookback_bars,
            max_group_contribution_share=args.max_group_contribution_share,
            volatility_target=args.volatility_target,
            volatility_lookback_bars=args.volatility_lookback_bars,
            target_annual_volatility=args.target_annual_volatility,
            volatility_min_observations=args.volatility_min_observations,
            volatility_max_scale=args.volatility_max_scale,
        )
        markdown += format_walk_forward_markdown(walk_forward_results, retention_rows)

    if args.summary_json:
        Path(args.summary_json).parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "results": [asdict(result) for result in results],
        }
        if walk_forward_results:
            payload.update(
                {
                    "walk_forward_windows": [
                        asdict(window) for window in walk_forward_windows
                    ],
                    "walk_forward_results": [
                        asdict(result) for result in walk_forward_results
                    ],
                    "walk_forward_retention": [
                        asdict(row) for row in retention_rows
                    ],
                }
            )
        Path(args.summary_json).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
    if args.summary_md:
        Path(args.summary_md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.summary_md).write_text(markdown, encoding="utf-8", newline="")
    print(markdown, end="")
    return 0


def _portfolio_price_return(
    symbols: list[str],
    closes_by_symbol: dict[str, list[float]],
    weights: dict[str, float],
    *,
    previous_index: int,
    current_index: int,
) -> float:
    """
    用途與流程：用目前投組權重計算上一根 close 到目前 close 的 portfolio return。
    參數：symbols 是排序後股票代號；closes_by_symbol 是 close matrix；weights 是目前投組權重；previous_index/current_index 是相鄰日期索引。
    回傳與錯誤：回傳小數形式報酬；若 close matrix 索引不合法會自然拋出 IndexError。
    """
    return sum(
        weights[symbol]
        * (
            (closes_by_symbol[symbol][current_index] / closes_by_symbol[symbol][previous_index])
            - 1.0
        )
        for symbol in symbols
    )


def _normalize_symbol_groups(
    symbols: list[str],
    *,
    symbol_groups: dict[str, str] | None,
) -> dict[str, str]:
    """
    用途與流程：把外部提供的部分股票分組補齊成每檔股票都有 group 的完整映射，未指定者以自身 symbol 作為獨立 group。
    參數：symbols 是本次回測實際使用的股票代號；symbol_groups 是可選外部分組設定。
    回傳與錯誤：回傳 symbol 到 group 的 dict；若外部分組包含本次資料不存在的 symbol，拋出 ValueError 以避免拼字錯誤讓 group cap 失效。
    """
    provided_groups = symbol_groups or {}
    unknown_symbols = sorted(set(provided_groups) - set(symbols))
    if unknown_symbols:
        raise ValueError(
            "symbol groups contain unknown symbols: " + ", ".join(unknown_symbols)
        )
    return {symbol: provided_groups.get(symbol, symbol) for symbol in symbols}


def _group_member_counts(symbol_groups: dict[str, str]) -> dict[str, int]:
    """
    用途與流程：由 symbol 到 group 的完整映射計算每個 group 的成員數，供單成員群組風險 gate 使用。
    參數：symbol_groups 是已經補齊所有 symbol 的 group 映射。
    回傳與錯誤：回傳 group 到成員數的 dict；輸入為空時回傳空 dict，不主動拋錯。
    """
    counts: dict[str, int] = {}
    for group in symbol_groups.values():
        counts[group] = counts.get(group, 0) + 1
    return counts


def _target_rotation_weights(
    symbols: list[str],
    closes_by_symbol: dict[str, list[float]],
    *,
    index: int,
    lookback_bars: int,
    top_n: int,
    min_return: float,
    ranking_skip_bars: int = 0,
    ranking_mode: str = "total-return",
) -> dict[str, float]:
    """
    用途與流程：依指定日期的 lookback return 排名，產生 top-N 等權 portfolio target weights。
    參數：symbols 是股票代號；closes_by_symbol 是 close matrix；index 是 rebalance 日期索引；lookback_bars 是回看期；ranking_skip_bars 是排名前要略過的最近 bar 數；ranking_mode 是總報酬或 group residual 排序模式；top_n 是最多持有檔數；min_return 是最低動能門檻。
    回傳與錯誤：回傳 symbol 到權重的 dict；若沒有入選股票則全部為 0。
    """
    (
        weights,
        _consecutive_blocked_count,
        _group_blocked_count,
        _group_member_blocked_count,
        _group_contribution_blocked_count,
        _group_breadth_blocked_count,
        _group_regime_blocked_count,
        _reentry_blocked_count,
    ) = _target_rotation_weights_with_block_counts(
        symbols,
        closes_by_symbol,
        index=index,
        lookback_bars=lookback_bars,
        ranking_skip_bars=ranking_skip_bars,
        ranking_mode=ranking_mode,
        top_n=top_n,
        min_return=min_return,
        excluded_symbols=set(),
        reentry_excluded_symbols=set(),
        excluded_groups=set(),
        group_breadth_eligible_groups=None,
        group_regime_eligible_groups=None,
        symbol_groups={symbol: symbol for symbol in symbols},
        max_selections_per_group=None,
        group_member_counts={symbol: 1 for symbol in symbols},
        min_symbols_per_selected_group=1,
    )
    return weights


def _target_rotation_weights_with_block_counts(
    symbols: list[str],
    closes_by_symbol: dict[str, list[float]],
    *,
    index: int,
    lookback_bars: int,
    ranking_skip_bars: int,
    ranking_mode: str,
    top_n: int,
    min_return: float,
    excluded_symbols: set[str],
    reentry_excluded_symbols: set[str],
    excluded_groups: set[str],
    group_breadth_eligible_groups: set[str] | None,
    group_regime_eligible_groups: set[str] | None,
    symbol_groups: dict[str, str],
    max_selections_per_group: int | None,
    group_member_counts: dict[str, int],
    min_symbols_per_selected_group: int,
) -> tuple[dict[str, float], int, int, int, int, int, int, int]:
    """
    用途與流程：依 lookback return 產生 top-N target weights，同時計算單檔連續入選、re-entry cooldown、同組上限、群組成員數下限、realized contribution group gate、group breadth gate 與 group regime gate 造成的 block 數。
    參數：symbols 是股票代號；closes_by_symbol 是 close matrix；index/lookback_bars/ranking_skip_bars/ranking_mode/top_n/min_return 定義相對動能排序；excluded_symbols 是本次 rebalance 暫時不可入選的股票集合；reentry_excluded_symbols 是剛退出投組且仍在 cooldown 內的股票集合；excluded_groups 是因 trailing realized contribution 過度集中而暫時不可入選的群組；group_breadth_eligible_groups 是通過同群組內部正動能比例 gate 的群組集合，None 表示停用；group_regime_eligible_groups 是通過群組自身絕對動能 gate 的群組集合，None 表示停用；symbol_groups 將股票映射到產業或自訂群組；max_selections_per_group 是每組最多入選檔數，None 表示停用；group_member_counts 是每個 group 的成員數；min_symbols_per_selected_group 是可入選群組的最低成員數。
    回傳與錯誤：回傳 `(target_weights, consecutive_blocked_count, group_blocked_count, group_member_blocked_count, group_contribution_blocked_count, group_breadth_blocked_count, group_regime_blocked_count, reentry_blocked_count)`；沒有入選股票時權重全為 0；block count 只計算正動能候選被各 gate 排除的次數。
    """
    if ranking_mode not in RANKING_MODES:
        raise ValueError("ranking mode must be one of: " + ", ".join(RANKING_MODES))
    ranked: list[tuple[str, float]] = []
    consecutive_blocked_count = 0
    group_member_blocked_count = 0
    group_contribution_blocked_count = 0
    group_breadth_blocked_count = 0
    group_regime_blocked_count = 0
    reentry_blocked_count = 0
    ranking_index = index - ranking_skip_bars
    momentum_returns: dict[str, float] = {}
    for symbol in symbols:
        previous_close = closes_by_symbol[symbol][ranking_index - lookback_bars]
        current_close = closes_by_symbol[symbol][ranking_index]
        momentum_returns[symbol] = (current_close / previous_close) - 1.0
    group_average_returns = _group_average_returns(
        momentum_returns,
        symbol_groups=symbol_groups,
    )
    for symbol in symbols:
        momentum_return = momentum_returns[symbol]
        group = symbol_groups.get(symbol, symbol)
        ranking_score = momentum_return
        if ranking_mode == "group-residual":
            ranking_score = momentum_return - group_average_returns.get(group, 0.0)
        if momentum_return > min_return:
            if symbol in excluded_symbols:
                consecutive_blocked_count += 1
                continue
            if symbol in reentry_excluded_symbols:
                reentry_blocked_count += 1
                continue
            if group_member_counts.get(group, 1) < min_symbols_per_selected_group:
                group_member_blocked_count += 1
                continue
            if group in excluded_groups:
                group_contribution_blocked_count += 1
                continue
            if (
                group_breadth_eligible_groups is not None
                and group not in group_breadth_eligible_groups
            ):
                group_breadth_blocked_count += 1
                continue
            if (
                group_regime_eligible_groups is not None
                and group not in group_regime_eligible_groups
            ):
                group_regime_blocked_count += 1
                continue
            ranked.append((symbol, ranking_score))

    selected: list[str] = []
    selected_group_counts: dict[str, int] = {}
    group_blocked_count = 0
    for symbol, _momentum_return in sorted(ranked, key=lambda item: (-item[1], item[0])):
        group = symbol_groups.get(symbol, symbol)
        if (
            max_selections_per_group is not None
            and selected_group_counts.get(group, 0) >= max_selections_per_group
        ):
            group_blocked_count += 1
            continue
        selected.append(symbol)
        selected_group_counts[group] = selected_group_counts.get(group, 0) + 1
        if len(selected) >= top_n:
            break

    target = {symbol: 0.0 for symbol in symbols}
    if not selected:
        return (
            target,
            consecutive_blocked_count,
            group_blocked_count,
            group_member_blocked_count,
            group_contribution_blocked_count,
            group_breadth_blocked_count,
            group_regime_blocked_count,
            reentry_blocked_count,
        )
    weight = 1.0 / len(selected)
    for symbol in selected:
        target[symbol] = weight
    return (
        target,
        consecutive_blocked_count,
        group_blocked_count,
        group_member_blocked_count,
        group_contribution_blocked_count,
        group_breadth_blocked_count,
        group_regime_blocked_count,
        reentry_blocked_count,
    )


def _target_rotation_weights_with_block_count(
    symbols: list[str],
    closes_by_symbol: dict[str, list[float]],
    *,
    index: int,
    lookback_bars: int,
    top_n: int,
    min_return: float,
    ranking_skip_bars: int = 0,
    ranking_mode: str = "total-return",
    excluded_symbols: set[str],
) -> tuple[dict[str, float], int]:
    """
    用途與流程：保留舊 helper contract，供只需要單檔連續入選 block count 的內部測試或相容呼叫使用。
    參數：symbols 是股票代號；closes_by_symbol 是 close matrix；index/lookback_bars/ranking_skip_bars/ranking_mode/top_n/min_return 定義相對動能排序；excluded_symbols 是本次 rebalance 暫時不可入選的股票集合。
    回傳與錯誤：回傳 `(target_weights, blocked_count)`；若沒有入選股票則權重全為 0。
    """
    (
        weights,
        consecutive_blocked_count,
        _group_blocked_count,
        _group_member_blocked_count,
        _group_contribution_blocked_count,
        _group_breadth_blocked_count,
        _group_regime_blocked_count,
        _reentry_blocked_count,
    ) = _target_rotation_weights_with_block_counts(
        symbols,
        closes_by_symbol,
        index=index,
        lookback_bars=lookback_bars,
        ranking_skip_bars=ranking_skip_bars,
        ranking_mode=ranking_mode,
        top_n=top_n,
        min_return=min_return,
        excluded_symbols=excluded_symbols,
        reentry_excluded_symbols=set(),
        excluded_groups=set(),
        group_breadth_eligible_groups=None,
        group_regime_eligible_groups=None,
        symbol_groups={symbol: symbol for symbol in symbols},
        max_selections_per_group=None,
        group_member_counts={symbol: 1 for symbol in symbols},
        min_symbols_per_selected_group=1,
    )
    return weights, consecutive_blocked_count


def _group_average_returns(
    momentum_returns: dict[str, float],
    *,
    symbol_groups: dict[str, str],
) -> dict[str, float]:
    """
    用途與流程：把每檔股票的 lookback return 依 symbol group 彙總成同組平均報酬，供 group-residual ranking 扣除群組動能因子。
    參數：momentum_returns 是 symbol 到原始 lookback return 的映射；symbol_groups 是完整或部分 symbol 到群組名稱的映射，缺漏時以 symbol 自身作為單獨群組。
    回傳與錯誤：回傳 group 到平均 return 的 dict；輸入為空時回傳空 dict，不主動拋錯。
    """
    grouped_returns: dict[str, list[float]] = {}
    for symbol, momentum_return in momentum_returns.items():
        group = symbol_groups.get(symbol, symbol)
        grouped_returns.setdefault(group, []).append(momentum_return)
    return {
        group: sum(values) / len(values)
        for group, values in grouped_returns.items()
        if values
    }


def _group_contribution_exclusions(
    group_contribution_history: list[dict[str, float]],
    *,
    lookback_bars: int,
    max_contribution_share: float | None,
) -> set[str]:
    """
    用途與流程：用已實現的 trailing group 權重報酬貢獻，找出絕對貢獻占比超過門檻的 dominant groups。
    參數：group_contribution_history 是每根已完成 bar 的 group contribution dict；lookback_bars 是只回看最近幾根已完成 bar；max_contribution_share 是允許單一 group 佔總絕對貢獻的上限，None 表示停用。
    回傳與錯誤：回傳本次 rebalance 應排除的 group set；樣本不足、總貢獻為 0 或 guard 停用時回傳空集合，不主動拋錯。
    """
    if max_contribution_share is None or lookback_bars <= 0:
        return set()
    if len(group_contribution_history) < lookback_bars:
        return set()

    trailing = group_contribution_history[-lookback_bars:]
    group_totals: dict[str, float] = {}
    for row in trailing:
        for group, contribution in row.items():
            group_totals[group] = group_totals.get(group, 0.0) + contribution

    absolute_total_contribution = sum(
        abs(contribution) for contribution in group_totals.values()
    )
    if absolute_total_contribution <= 0:
        return set()
    return {
        group
        for group, contribution in group_totals.items()
        if abs(contribution) / absolute_total_contribution > max_contribution_share
    }


def _consecutive_selection_exclusions(
    consecutive_selection_counts: dict[str, int],
    *,
    max_consecutive_selections: int | None,
) -> set[str]:
    """
    用途與流程：根據每檔股票目前連續入選次數，產生本次 rebalance 需要暫時排除的股票集合。
    參數：consecutive_selection_counts 是 symbol 到連續入選次數的 dict；max_consecutive_selections 是可選上限，None 表示停用。
    回傳與錯誤：回傳需排除的 symbol set；此函式假設上限已由呼叫端驗證為正數，不主動拋錯。
    """
    if max_consecutive_selections is None:
        return set()
    return {
        symbol
        for symbol, count in consecutive_selection_counts.items()
        if count >= max_consecutive_selections
    }


def _reentry_cooldown_exclusions(
    reentry_cooldown_counts: dict[str, int],
    *,
    cooldown_rebalances: int,
) -> set[str]:
    """
    用途與流程：依每檔股票退出後剩餘的 cooldown 次數，產生本次 rebalance 不可重新入選的股票集合。
    參數：reentry_cooldown_counts 是 symbol 到剩餘封鎖 rebalance 次數的狀態表；cooldown_rebalances 是使用者設定的等待次數，0 表示停用。
    回傳與錯誤：回傳需暫時排除的 symbol set；輸入由上層驗證，函式本身不主動拋錯。
    """
    if cooldown_rebalances <= 0:
        return set()
    return {
        symbol
        for symbol, count in reentry_cooldown_counts.items()
        if count > 0
    }


def _update_reentry_cooldowns(
    reentry_cooldown_counts: dict[str, int],
    *,
    previous_weights: dict[str, float],
    target_weights: dict[str, float],
    cooldown_rebalances: int,
) -> None:
    """
    用途與流程：在每次 rebalance 產生新目標權重後更新 re-entry cooldown；剛從持倉轉為空手的股票會被設定為等待 N 次 rebalance，已在等待中的股票每經過一次 rebalance 遞減一次。
    參數：reentry_cooldown_counts 是就地更新的狀態表；previous_weights 是 rebalance 前實際持倉；target_weights 是本次 rebalance 後目標持倉；cooldown_rebalances 是退出後要封鎖的未來 rebalance 次數。
    回傳與錯誤：回傳 None；若權重 dict 缺少 symbol，會以 0.0 視為未持倉，不主動拋錯。
    """
    if cooldown_rebalances <= 0:
        return
    for symbol in reentry_cooldown_counts:
        was_selected = previous_weights.get(symbol, 0.0) > 1e-12
        is_selected = target_weights.get(symbol, 0.0) > 1e-12
        if was_selected and not is_selected:
            reentry_cooldown_counts[symbol] = cooldown_rebalances
        elif is_selected:
            reentry_cooldown_counts[symbol] = 0
        elif reentry_cooldown_counts[symbol] > 0:
            reentry_cooldown_counts[symbol] -= 1


def _update_consecutive_selection_counts(
    consecutive_selection_counts: dict[str, int],
    target_weights: dict[str, float],
) -> None:
    """
    用途與流程：在每次 rebalance 後更新連續入選狀態，入選股票加一，未入選股票歸零。
    參數：consecutive_selection_counts 是就地更新的狀態 dict；target_weights 是本次 rebalance 產生的目標權重。
    回傳與錯誤：回傳 None；若 target_weights 缺少既有 symbol，會自然由 dict key access 或後續測試暴露。
    """
    for symbol in consecutive_selection_counts:
        if target_weights.get(symbol, 0.0) > 1e-12:
            consecutive_selection_counts[symbol] += 1
        else:
            consecutive_selection_counts[symbol] = 0


def _breadth_positive_count(
    symbols: list[str],
    closes_by_symbol: dict[str, list[float]],
    *,
    index: int,
    lookback_bars: int,
    positive_threshold: float,
) -> int | None:
    """
    用途與流程：計算指定 rebalance 日期有多少股票的 lookback return 高於市場寬度門檻，供 breadth filter 判斷是否允許輪動持倉。
    參數：symbols 是股票代號；closes_by_symbol 是共同 timestamp 對齊後的 close matrix；index 是目前 rebalance 索引；lookback_bars 是市場寬度回看期；positive_threshold 是股票被視為正動能的最低報酬。
    回傳與錯誤：樣本不足時回傳 None；否則回傳通過門檻的股票數；若 lookback_bars 非正或 close 非正會拋出 ValueError。
    """
    if lookback_bars <= 0:
        raise ValueError("breadth lookback bars must be positive")
    if index < lookback_bars:
        return None

    positive_count = 0
    for symbol in symbols:
        previous_close = closes_by_symbol[symbol][index - lookback_bars]
        current_close = closes_by_symbol[symbol][index]
        if previous_close <= 0 or current_close <= 0:
            raise ValueError("breadth filter requires positive closes")
        if (current_close / previous_close) - 1.0 > positive_threshold:
            positive_count += 1
    return positive_count


def _group_breadth_positive_shares(
    symbols: list[str],
    closes_by_symbol: dict[str, list[float]],
    *,
    index: int,
    lookback_bars: int,
    positive_threshold: float,
    symbol_groups: dict[str, str],
) -> dict[str, float] | None:
    """
    用途與流程：計算每個股票群組內有多少成員的 lookback return 高於門檻，將事後 group breadth diagnostic 轉成 rebalance 當下可用的事前 gate。
    參數：symbols 是股票代號；closes_by_symbol 是共同 timestamp 對齊後的 close matrix；index 是目前 rebalance 索引；lookback_bars 是群組廣度回看期；positive_threshold 是成員被視為正動能的最低報酬；symbol_groups 是完整 symbol 到 group 的映射。
    回傳與錯誤：樣本不足時回傳 None；否則回傳 group 到正動能成員比例的 dict；若 lookback 非正或 close 非正會拋出 ValueError。
    """
    if lookback_bars <= 0:
        raise ValueError("group breadth lookback bars must be positive")
    if index < lookback_bars:
        return None

    member_counts: dict[str, int] = {}
    positive_counts: dict[str, int] = {}
    for symbol in symbols:
        previous_close = closes_by_symbol[symbol][index - lookback_bars]
        current_close = closes_by_symbol[symbol][index]
        if previous_close <= 0 or current_close <= 0:
            raise ValueError("group breadth filter requires positive closes")
        group = symbol_groups.get(symbol, symbol)
        member_counts[group] = member_counts.get(group, 0) + 1
        if (current_close / previous_close) - 1.0 > positive_threshold:
            positive_counts[group] = positive_counts.get(group, 0) + 1

    return {
        group: positive_counts.get(group, 0) / member_count
        for group, member_count in member_counts.items()
        if member_count > 0
    }


def _group_regime_returns(
    symbols: list[str],
    closes_by_symbol: dict[str, list[float]],
    *,
    index: int,
    lookback_bars: int,
    symbol_groups: dict[str, str],
) -> dict[str, float] | None:
    """
    用途與流程：計算每個群組的等權 lookback return，將 dual momentum 的 absolute-momentum gate 套到產業或自訂群組層級。
    參數：symbols 是股票代號；closes_by_symbol 是共同 timestamp 對齊後的 close matrix；index 是目前 rebalance 索引；lookback_bars 是群組趨勢回看期；symbol_groups 是完整 symbol 到 group 的映射。
    回傳與錯誤：樣本不足時回傳 None；否則回傳 group 到等權平均報酬的 dict；lookback 非正或 close 非正時拋出 ValueError。
    """
    if lookback_bars <= 0:
        raise ValueError("group regime lookback bars must be positive")
    if index < lookback_bars:
        return None

    group_return_sums: dict[str, float] = {}
    group_member_counts: dict[str, int] = {}
    for symbol in symbols:
        previous_close = closes_by_symbol[symbol][index - lookback_bars]
        current_close = closes_by_symbol[symbol][index]
        if previous_close <= 0 or current_close <= 0:
            raise ValueError("group regime filter requires positive closes")
        group = symbol_groups.get(symbol, symbol)
        group_return_sums[group] = (
            group_return_sums.get(group, 0.0)
            + (current_close / previous_close)
            - 1.0
        )
        group_member_counts[group] = group_member_counts.get(group, 0) + 1

    return {
        group: group_return_sums[group] / member_count
        for group, member_count in group_member_counts.items()
        if member_count > 0
    }


def _liquidity_eligible_symbols(
    symbols: list[str],
    traded_values_by_symbol: dict[str, list[float]],
    *,
    index: int,
    lookback_bars: int,
    min_average_traded_value: float,
) -> set[str] | None:
    """
    用途與流程：計算指定 rebalance 日期哪些股票近 N 根平均成交金額達標，供 portfolio rotation 排除流動性不足標的。
    參數：symbols 是股票代號；traded_values_by_symbol 是對齊後 `close * volume` 矩陣；index 是 rebalance 日期；lookback_bars 是平均成交金額視窗；min_average_traded_value 是最低合格門檻。
    回傳與錯誤：樣本不足時回傳 None；否則回傳合格 symbol set；lookback 非正或成交金額為負時拋出 ValueError。
    """
    if lookback_bars <= 0:
        raise ValueError("liquidity lookback bars must be positive")
    if index + 1 < lookback_bars:
        return None

    start = index + 1 - lookback_bars
    eligible: set[str] = set()
    for symbol in symbols:
        window = traded_values_by_symbol[symbol][start:index + 1]
        if any(value < 0 for value in window):
            raise ValueError("liquidity filter requires non-negative traded values")
        average_traded_value = sum(window) / len(window)
        if average_traded_value >= min_average_traded_value:
            eligible.add(symbol)
    return eligible


def _equal_weight_price_index(
    symbols: list[str],
    closes_by_symbol: dict[str, list[float]],
) -> list[float]:
    """
    用途與流程：把多檔 close matrix 轉成以第一根為 1 的等權價格指數，供 market regime filter 判斷大盤趨勢。
    參數：symbols 是已排序股票代號；closes_by_symbol 是共同 timestamp 對齊後的 close matrix。
    回傳與錯誤：回傳每根 bar 的等權 normalized index；若 symbol 為空或起始 close 非正時拋出 ValueError。
    """
    if not symbols:
        raise ValueError("market regime index requires at least one symbol")
    base_closes = {symbol: closes_by_symbol[symbol][0] for symbol in symbols}
    if any(close <= 0 for close in base_closes.values()):
        raise ValueError("market regime index requires positive base closes")
    length = len(closes_by_symbol[symbols[0]])
    return [
        sum(closes_by_symbol[symbol][index] / base_closes[symbol] for symbol in symbols)
        / len(symbols)
        for index in range(length)
    ]


def _market_regime_is_risk_on(
    market_index_values: list[float],
    *,
    index: int,
    sma_bars: int,
) -> bool:
    """
    用途與流程：判斷等權市場指數是否站上自身 SMA；未累積足夠 SMA 樣本時保守視為 risk-off。
    參數：market_index_values 是 _equal_weight_price_index 的結果；index 是目前 rebalance 索引；sma_bars 是 SMA 視窗長度。
    回傳與錯誤：回傳 True 表示可持有輪動標的；sma_bars 非正時拋出 ValueError。
    """
    if sma_bars <= 0:
        raise ValueError("market regime SMA bars must be positive")
    if index + 1 < sma_bars:
        return False
    window = market_index_values[index + 1 - sma_bars:index + 1]
    sma = sum(window) / len(window)
    return market_index_values[index] >= sma


def _has_exposure(weights: dict[str, float]) -> bool:
    """
    用途與流程：判斷目標權重是否含有非零曝險，供 volatility target 避免對全現金狀態做無意義縮放。
    參數：weights 是 symbol 到 target weight 的 dict。
    回傳與錯誤：任一權重絕對值大於極小值時回傳 True；此函式不主動拋錯。
    """
    return any(abs(weight) > 1e-12 for weight in weights.values())


def _volatility_target_scale(
    symbols: list[str],
    closes_by_symbol: dict[str, list[float]],
    weights: dict[str, float],
    *,
    index: int,
    lookback_bars: int,
    min_observations: int,
    target_annual_volatility: float,
    periods_per_year: int,
    max_scale: float,
) -> float | None:
    """
    用途與流程：用目前目標投組的歷史 close-to-close 報酬估算 realized volatility，計算只降曝險、不加槓桿的縮放倍率。
    參數：symbols 與 closes_by_symbol 是共同日期矩陣；weights 是未縮放的目標權重；index 是目前 rebalance 索引；lookback/min_observations 控制使用的歷史報酬；target_annual_volatility、periods_per_year 與 max_scale 定義縮放上限。
    回傳與錯誤：樣本不足時回傳 None；波動為 0 時回傳 max_scale；否則回傳不超過 max_scale 的正縮放倍率。
    """
    returns = _portfolio_weighted_returns(
        symbols,
        closes_by_symbol,
        weights,
        index=index,
        lookback_bars=lookback_bars,
    )
    if len(returns) < min_observations:
        return None
    daily_volatility = _sample_standard_deviation(returns)
    if daily_volatility <= 0:
        return max_scale
    annualized_volatility = daily_volatility * sqrt(periods_per_year)
    if annualized_volatility <= 0:
        return max_scale
    return min(max_scale, target_annual_volatility / annualized_volatility)


def _portfolio_weighted_returns(
    symbols: list[str],
    closes_by_symbol: dict[str, list[float]],
    weights: dict[str, float],
    *,
    index: int,
    lookback_bars: int,
) -> list[float]:
    """
    用途與流程：依固定目標權重回看近期投組報酬，作為 portfolio-level volatility target 的 realized volatility 輸入。
    參數：symbols 是排序後股票代號；closes_by_symbol 是 close matrix；weights 是目標權重；index 是目前 rebalance 索引；lookback_bars 是最多使用的報酬筆數。
    回傳與錯誤：回傳逐期投組報酬；遇到非正前期 close 時略過該段以避免除零。
    """
    if index <= 0:
        return []
    start = max(1, index - lookback_bars + 1)
    returns: list[float] = []
    for current_index in range(start, index + 1):
        period_return = 0.0
        valid_period = True
        for symbol in symbols:
            previous_close = closes_by_symbol[symbol][current_index - 1]
            if previous_close <= 0:
                valid_period = False
                break
            current_close = closes_by_symbol[symbol][current_index]
            period_return += weights[symbol] * ((current_close / previous_close) - 1.0)
        if valid_period:
            returns.append(period_return)
    return returns


def _sample_standard_deviation(values: list[float]) -> float:
    """
    用途與流程：計算樣本標準差，供 realized volatility 與風險縮放使用。
    參數：values 是浮點數清單，至少兩筆才有樣本變異。
    回傳與錯誤：樣本不足或變異數非正時回傳 0；否則回傳樣本標準差。
    """
    if len(values) < 2:
        return 0.0
    mean_value = sum(values) / len(values)
    variance = sum((value - mean_value) ** 2 for value in values) / (
        len(values) - 1
    )
    if variance <= 0:
        return 0.0
    return sqrt(variance)


def _is_rebalance_index(
    timestamps: list[str],
    *,
    index: int,
    frequency: str,
) -> bool:
    """
    用途與流程：判斷目前 timestamp 是否為指定 rebalance frequency 的第一根可交易 bar。
    參數：timestamps 是共同日期序列；index 是目前日期索引；frequency 可為 daily、weekly 或 monthly。
    回傳與錯誤：符合 rebalance 時回傳 True；frequency 不合法時拋出 ValueError。
    """
    if frequency == "daily":
        return True
    current = _parse_timestamp(timestamps[index])
    previous = _parse_timestamp(timestamps[index - 1])
    if frequency == "weekly":
        return current.isocalendar()[:2] != previous.isocalendar()[:2]
    if frequency == "monthly":
        return (current.year, current.month) != (previous.year, previous.month)
    raise ValueError("rebalance frequency must be daily, weekly, or monthly")


def _parse_timestamp(timestamp: str) -> datetime:
    """
    用途與流程：將 SignalForge timestamp 轉成 datetime，供 weekly/monthly rebalance 與 CAGR 年數計算使用。
    參數：timestamp 是 `YYYY-MM-DD` 或 ISO datetime 字串。
    回傳與錯誤：回傳 datetime；格式不合法時由 datetime.fromisoformat 拋出 ValueError。
    """
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def _add_months(value: date, months: int) -> date:
    """
    用途與流程：把日期往後推指定月份，供 rolling window 起訖日期產生器使用。
    參數：value 是原始 date；months 是正整數月份數。
    回傳與錯誤：回傳平移後 date；若目標月份沒有原日期 day，會夾到該月最後一天。
    """
    target_month_index = value.month - 1 + months
    target_year = value.year + target_month_index // 12
    target_month = (target_month_index % 12) + 1
    target_day = min(value.day, monthrange(target_year, target_month)[1])
    return date(target_year, target_month, target_day)


def _elapsed_years(timestamps: list[str]) -> float:
    """
    用途與流程：由共同 timestamp 起訖推估樣本年數，供 CAGR 使用。
    參數：timestamps 是按時間排序的共同日期序列。
    回傳與錯誤：回傳正浮點年數；時間格式錯誤或期間非正時退回 bars / 252。
    """
    if len(timestamps) < 2:
        return 0.0
    try:
        start = _parse_timestamp(timestamps[0])
        end = _parse_timestamp(timestamps[-1])
    except ValueError:
        return len(timestamps) / 252.0
    elapsed_days = (end - start).total_seconds() / 86_400.0
    if elapsed_days <= 0:
        return len(timestamps) / 252.0
    return elapsed_days / 365.25


def _compound_annual_growth_rate(
    start_equity: float,
    end_equity: float,
    years: float,
) -> float | None:
    """
    用途與流程：用起訖權益與樣本年數計算 CAGR，避免不同日期窗只比較總報酬。
    參數：start_equity 是期初資金；end_equity 是期末權益；years 是樣本年數。
    回傳與錯誤：起訖資金或年數不合法時回傳 None；否則回傳 CAGR。
    """
    if start_equity <= 0 or end_equity <= 0 or years < (30.0 / 365.25):
        return None
    try:
        return (end_equity / start_equity) ** (1.0 / years) - 1.0
    except OverflowError:
        return None


def _equity_returns(equity_values: list[float]) -> list[float]:
    """
    用途與流程：把 equity curve 轉為相鄰期間報酬，供 Sharpe 與 Sortino 使用。
    參數：equity_values 是按時間排序的權益序列。
    回傳與錯誤：回傳報酬序列；前一期權益小於等於 0 時該段以 0 表示。
    """
    returns: list[float] = []
    for previous, current in zip(equity_values, equity_values[1:]):
        if previous <= 0:
            returns.append(0.0)
        else:
            returns.append((current / previous) - 1.0)
    return returns


def _active_returns(
    strategy_returns: list[float],
    benchmark_returns: list[float],
) -> list[float]:
    """
    用途與流程：將策略每期報酬扣除 benchmark 每期報酬，形成 active return 序列。
    參數：strategy_returns 與 benchmark_returns 是相鄰 equity return 序列，應使用同一 timestamps。
    回傳與錯誤：回傳逐期 active returns；若長度不一致，會只取共同前綴以避免索引錯誤。
    """
    return [
        strategy_return - benchmark_return
        for strategy_return, benchmark_return in zip(
            strategy_returns,
            benchmark_returns,
        )
    ]


def _annualized_mean_return(
    returns: list[float],
    periods_per_year: int,
) -> float | None:
    """
    用途與流程：計算逐期報酬的年化算術平均，供 Information Ratio 的 active return 分子使用。
    參數：returns 是逐期報酬序列；periods_per_year 是年化期數。
    回傳與錯誤：樣本不足或期數非正時回傳 None；否則回傳年化平均報酬。
    """
    if not returns or periods_per_year <= 0:
        return None
    return (sum(returns) / len(returns)) * periods_per_year


def _annualized_tracking_error(
    active_returns: list[float],
    periods_per_year: int,
) -> float | None:
    """
    用途與流程：計算 active return 序列的年化標準差，也就是 tracking error / active risk。
    參數：active_returns 是策略報酬扣 benchmark 報酬的逐期序列；periods_per_year 是年化期數。
    回傳與錯誤：樣本不足、變異數為 0 或期數非正時回傳 None；否則回傳年化 tracking error。
    """
    if len(active_returns) < 2 or periods_per_year <= 0:
        return None
    mean_return = sum(active_returns) / len(active_returns)
    variance = sum((value - mean_return) ** 2 for value in active_returns) / (
        len(active_returns) - 1
    )
    if variance <= 0:
        return None
    return sqrt(variance) * sqrt(periods_per_year)


def _information_ratio(
    annualized_active_return: float | None,
    tracking_error: float | None,
) -> float | None:
    """
    用途與流程：用年化 active return 除以年化 tracking error，衡量每單位主動風險帶來的超額報酬。
    參數：annualized_active_return 是 active return 年化平均；tracking_error 是 active return 年化標準差。
    回傳與錯誤：任一輸入缺失或 tracking error 為 0 時回傳 None；否則回傳 Information Ratio。
    """
    if annualized_active_return is None or tracking_error in {None, 0.0}:
        return None
    return annualized_active_return / tracking_error


def _active_max_drawdown(
    strategy_equity_values: list[float],
    benchmark_equity_values: list[float],
    initial_equity: float,
) -> float:
    """
    用途與流程：用 normalized relative equity 計算 active max drawdown，觀察策略相對 benchmark 的高點回落。
    參數：strategy_equity_values 與 benchmark_equity_values 是同 timestamps 權益曲線；initial_equity 只作為相對曲線縮放基準。
    回傳與錯誤：回傳小於等於 0 的相對權益最大回撤；資料不足或 benchmark 權益非正時回傳 0。
    """
    if not strategy_equity_values or not benchmark_equity_values:
        return 0.0
    first_strategy = strategy_equity_values[0]
    first_benchmark = benchmark_equity_values[0]
    if first_strategy <= 0 or first_benchmark <= 0:
        return 0.0
    start_ratio = first_strategy / first_benchmark
    relative_equity: list[float] = []
    for strategy_equity, benchmark_equity in zip(
        strategy_equity_values,
        benchmark_equity_values,
    ):
        if benchmark_equity <= 0:
            continue
        relative_equity.append(
            initial_equity * ((strategy_equity / benchmark_equity) / start_ratio)
        )
    return _max_drawdown(relative_equity)


def _annualized_sharpe_ratio(
    returns: list[float],
    periods_per_year: int,
) -> float | None:
    """
    用途與流程：用 equity returns 估算年化 Sharpe，作為 portfolio rotation 風險調整指標。
    參數：returns 是相鄰 equity returns；periods_per_year 是年化期數。
    回傳與錯誤：樣本不足、標準差為 0 或期數非正時回傳 None；否則回傳 Sharpe。
    """
    if len(returns) < 2 or periods_per_year <= 0:
        return None
    mean_return = sum(returns) / len(returns)
    variance = sum((value - mean_return) ** 2 for value in returns) / (
        len(returns) - 1
    )
    if variance <= 0:
        return None
    return (mean_return / sqrt(variance)) * sqrt(periods_per_year)


def _annualized_sortino_ratio(
    returns: list[float],
    periods_per_year: int,
) -> float | None:
    """
    用途與流程：用 downside deviation 估算年化 Sortino，避免把上行波動視為風險。
    參數：returns 是相鄰 equity returns；periods_per_year 是年化期數。
    回傳與錯誤：樣本不足、downside deviation 為 0 或期數非正時回傳 None；否則回傳 Sortino。
    """
    if len(returns) < 2 or periods_per_year <= 0:
        return None
    mean_return = sum(returns) / len(returns)
    downside = [min(0.0, value) for value in returns]
    downside_variance = sum(value * value for value in downside) / len(returns)
    if downside_variance <= 0:
        return None
    return (mean_return / sqrt(downside_variance)) * sqrt(periods_per_year)


def _max_drawdown(equity_values: list[float]) -> float:
    """
    用途與流程：從權益序列計算小於等於 0 的最大回撤。
    參數：equity_values 是按時間排序的權益值。
    回傳與錯誤：空清單回傳 0；否則回傳最大回撤。
    """
    if not equity_values:
        return 0.0
    peak = equity_values[0]
    max_drawdown = 0.0
    for equity in equity_values:
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = min(max_drawdown, (equity / peak) - 1.0)
    return max_drawdown


def _calmar_ratio(cagr: float | None, max_drawdown: float) -> float | None:
    """
    用途與流程：計算 CAGR / abs(max_drawdown)，衡量報酬相對最大回撤的承受度。
    參數：cagr 是可選年化報酬；max_drawdown 是小於等於 0 的回撤。
    回傳與錯誤：缺 CAGR 或回撤為 0 時回傳 None；否則回傳 Calmar ratio。
    """
    if cagr is None or max_drawdown == 0:
        return None
    return cagr / abs(max_drawdown)


def _subtract_optional(left: float | None, right: float | None) -> float | None:
    """
    用途與流程：安全計算兩個可選數值的差，用於 excess CAGR。
    參數：left/right 是 float 或 None。
    回傳與錯誤：任一側為 None 時回傳 None；否則回傳 left - right。
    """
    if left is None or right is None:
        return None
    return left - right


def _retention_ratio(
    test_value: float | None,
    train_value: float | None,
) -> float | None:
    """
    用途與流程：計算 OOS 指標相對 IS 指標的保留率，只在樣本內值為正時回傳比值。
    參數：test_value 是樣本外值；train_value 是樣本內值，兩者可為 None。
    回傳與錯誤：train_value 無效或小於等於 0 時回傳 None；否則回傳 test/train。
    """
    if test_value is None or train_value is None or train_value <= 0:
        return None
    return test_value / train_value


def _average(values: Iterable[float]) -> float:
    """
    用途與流程：計算浮點 iterable 平均值，供 turnover 與 exposure 摘要使用。
    參數：values 是 float iterable。
    回傳與錯誤：沒有元素時回傳 0；否則回傳平均。
    """
    items = list(values)
    if not items:
        return 0.0
    return sum(items) / len(items)


def _average_float(values: Iterable[int]) -> float:
    """
    用途與流程：計算整數 iterable 的浮點平均，供平均持股檔數使用。
    參數：values 是 int iterable。
    回傳與錯誤：沒有元素時回傳 0；否則回傳平均浮點數。
    """
    items = list(values)
    if not items:
        return 0.0
    return sum(items) / len(items)


def _average_int_optional(values: Iterable[int]) -> float | None:
    """
    用途與流程：計算可選整數平均值，供只在 breadth filter 有有效樣本時才輸出的市場寬度摘要使用。
    參數：values 是 int iterable，通常是每個 rebalance 日期的正動能股票數。
    回傳與錯誤：沒有元素時回傳 None；否則回傳浮點平均值。
    """
    items = list(values)
    if not items:
        return None
    return sum(items) / len(items)


def _average_optional(values: Iterable[float]) -> float | None:
    """
    用途與流程：計算可選平均值，供只在功能啟用時才有樣本的報表欄位使用。
    參數：values 是 float iterable。
    回傳與錯誤：沒有元素時回傳 None；否則回傳平均值。
    """
    items = list(values)
    if not items:
        return None
    return sum(items) / len(items)


def _format_cost_label(multiplier: float) -> str:
    """
    用途與流程：把成本倍率轉成短標籤，供 Markdown 與 JSON 閱讀。
    參數：multiplier 是正浮點倍率。
    回傳與錯誤：整數輸出如 `2x`；非整數保留兩位後去除多餘 0。
    """
    if multiplier.is_integer():
        return f"{int(multiplier)}x"
    return f"{multiplier:.2f}".rstrip("0").rstrip(".") + "x"


def _format_optional_percent(value: float | None) -> str:
    """
    用途與流程：把可選小數百分比格式化成 Markdown 表格文字。
    參數：value 是 None 或小數形式百分比。
    回傳與錯誤：None 回傳 `undefined`；否則回傳兩位百分比。
    """
    if value is None:
        return "undefined"
    return f"{value:.2%}"


def _format_optional_ratio(value: float | None) -> str:
    """
    用途與流程：把可選比率格式化成 Markdown 表格文字。
    參數：value 是 None 或浮點比率。
    回傳與錯誤：None 回傳 `undefined`；否則回傳三位小數。
    """
    if value is None:
        return "undefined"
    return f"{value:.3f}"


def _format_optional_int(value: int | None) -> str:
    """
    用途與流程：將可選整數格式化為 Markdown 表格文字，讓停用的限制顯示為 undefined。
    參數：value 是可選整數，通常代表策略限制的設定值。
    回傳與錯誤：None 回傳 `undefined`，否則回傳十進位字串；不主動拋錯。
    """
    if value is None:
        return "undefined"
    return str(value)


def _format_optional_float(value: float | None) -> str:
    """
    用途與流程：將可選浮點數格式化為 Markdown 表格文字，供成交金額門檻等非百分比欄位使用。
    參數：value 是可選浮點數。
    回傳與錯誤：None 回傳 `undefined`；整數值不帶小數，其他值保留兩位小數；此函式不主動拋錯。
    """
    if value is None:
        return "undefined"
    numeric_value = float(value)
    if numeric_value.is_integer():
        return f"{numeric_value:.0f}"
    return f"{numeric_value:.2f}"


def _format_bool(value: bool) -> str:
    """
    用途與流程：將布林設定轉成 Markdown 報表可讀文字，避免 True/False 與策略欄位混淆。
    參數：value 是布林值。
    回傳與錯誤：True 回傳 `on`，False 回傳 `off`；此函式不主動拋錯。
    """
    return "on" if value else "off"


if __name__ == "__main__":
    raise SystemExit(main())
