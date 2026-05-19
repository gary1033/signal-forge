from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from signal_forge.entry_edge import EntryEdgeResult
from signal_forge.market_data import BarValidationResult


@dataclass(frozen=True)
class EntryEdgeReportPaths:
    markdown: Path
    summary_json: Path
    trade_log_csv: Path


def write_entry_edge_outputs(
    result: EntryEdgeResult,
    output_dir: str | Path,
    *,
    run_name: str | None = None,
    data_validation: BarValidationResult | None = None,
    strategy_spec: dict[str, str] | None = None,
) -> EntryEdgeReportPaths:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    stem = _safe_stem(run_name or result.strategy_name)
    markdown_path = output_path / f"{stem}.md"
    summary_path = output_path / f"{stem}.json"
    trade_log_path = output_path / f"{stem}_trades.csv"

    summary = _summary_dict(result, data_validation, strategy_spec)
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    trade_log_path.write_text(_trade_log_csv(result), encoding="utf-8", newline="")
    markdown_path.write_text(
        _markdown_report(result, data_validation, strategy_spec),
        encoding="utf-8",
    )

    return EntryEdgeReportPaths(
        markdown=markdown_path,
        summary_json=summary_path,
        trade_log_csv=trade_log_path,
    )


def _summary_dict(
    result: EntryEdgeResult,
    data_validation: BarValidationResult | None,
    strategy_spec: dict[str, str] | None,
) -> dict[str, object]:
    return {
        "strategy_name": result.strategy_name,
        "decision": result.decision,
        "failure_reason": result.failure_reason,
        "profit_factor": result.profit_factor,
        "profit_factor_status": result.profit_factor_status,
        "sample_risk": result.sample_risk,
        "metrics": {
            "gross_profit": result.gross_profit,
            "gross_loss": result.gross_loss,
            "trade_count": result.trade_count,
            "ignored_short_count": result.ignored_short_count,
            "unclosed_signal_count": result.unclosed_signal_count,
            "overlapping_signal_count": result.overlapping_signal_count,
            "win_rate": result.win_rate,
            "average_net_pnl": result.average_net_pnl,
            "max_drawdown": result.max_drawdown,
            "start_equity": result.start_equity,
            "end_equity": result.end_equity,
        },
        "config": asdict(result.config),
        "data_validation": asdict(data_validation) if data_validation else None,
        "strategy_spec": strategy_spec or {},
    }


def _trade_log_csv(result: EntryEdgeResult) -> str:
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "signal_index",
            "signal_timestamp",
            "entry_index",
            "entry_timestamp",
            "exit_index",
            "exit_timestamp",
            "entry_price",
            "exit_price",
            "gross_pnl",
            "cost",
            "net_pnl",
            "return_pct",
            "signal_reason",
            "signal_score",
        ],
    )
    writer.writeheader()
    for trade in result.trades:
        writer.writerow(asdict(trade))
    return buffer.getvalue()


def _markdown_report(
    result: EntryEdgeResult,
    data_validation: BarValidationResult | None,
    strategy_spec: dict[str, str] | None,
) -> str:
    pf = _format_profit_factor(result)
    lines = [
        f"# Entry Edge Report - {result.strategy_name}",
        "",
        "## 結論",
        "",
        f"- 判定：{result.decision.upper()}",
        f"- Profit Factor：{pf}",
        f"- 交易數：{result.trade_count}",
        f"- 勝率：{result.win_rate:.2%}",
        f"- 平均淨損益：{result.average_net_pnl:.2f}",
        f"- 最大回撤：{result.max_drawdown:.2%}",
    ]
    if result.failure_reason:
        lines.append(f"- 未通過原因：{result.failure_reason}")
    if result.sample_risk:
        lines.append(f"- 樣本風險：{result.sample_risk}")

    lines.extend(
        [
            "",
            "## 回測設定",
            "",
            f"- 初始權益：{result.config.initial_equity:.2f}",
            f"- 手續費 bps：{result.config.commission_bps:.2f}",
            f"- 滑價 bps：{result.config.slippage_bps:.2f}",
            f"- 固定持有 bars：{result.config.hold_bars_per_day}",
            f"- PF 門檻：>{result.config.pass_profit_factor:.2f}",
            "- 成交規則：訊號於 bar close 後成立，下一根 bar open 進場，固定持有後以 exit bar close 出場。",
            "- 第一階段規則：純多優先；short 訊號忽略；不套用停損、停利、濾網或參數最佳化。",
            "",
            "## 資料檢查",
            "",
        ]
    )

    if data_validation:
        lines.extend(
            [
                f"- bar 數：{data_validation.bar_count}",
                f"- 起始時間：{data_validation.start_timestamp}",
                f"- 結束時間：{data_validation.end_timestamp}",
                f"- 錯誤數：{len(data_validation.errors)}",
                f"- 警告數：{len(data_validation.warnings)}",
            ]
        )
        for warning in data_validation.warnings:
            lines.append(f"- 警告：{warning}")
    else:
        lines.append("- 未提供資料檢查結果。")

    lines.extend(["", "## 蒸餾後進場規格", ""])
    if strategy_spec:
        for key, value in strategy_spec.items():
            lines.append(f"- {key}：{value}")
    else:
        lines.append("- 未提供策略蒸餾規格。")

    lines.extend(
        [
            "",
            "## 交易統計",
            "",
            f"- 總獲利：{result.gross_profit:.2f}",
            f"- 總虧損：{result.gross_loss:.2f}",
            f"- 忽略 short 訊號數：{result.ignored_short_count}",
            f"- 無法關閉訊號數：{result.unclosed_signal_count}",
            f"- 重疊略過訊號數：{result.overlapping_signal_count}",
            f"- 期末權益：{result.end_equity:.2f}",
            "",
        ]
    )
    return "\n".join(lines)


def _format_profit_factor(result: EntryEdgeResult) -> str:
    if result.profit_factor_status == "infinite":
        return "Infinity"
    if result.profit_factor is None:
        return "undefined"
    return f"{result.profit_factor:.3f}"


def _safe_stem(value: str) -> str:
    allowed = []
    for char in value.lower():
        if char.isalnum() or char in {"-", "_"}:
            allowed.append(char)
        elif char.isspace():
            allowed.append("-")
    stem = "".join(allowed).strip("-_")
    return stem or "entry-edge-report"
