from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.multi_stock_target_state_sweep import infer_symbol_from_path, load_filtered_bars
from tools.portfolio_rotation_sweep import parse_symbol_group_assignments


@dataclass(frozen=True)
class UniverseAuditRow:
    """單一股票在 portfolio rotation universe audit 中的資料品質摘要。"""

    symbol: str
    csv_path: str
    group: str
    row_count: int
    first_timestamp: str | None
    last_timestamp: str | None
    average_traded_value: float | None
    group_member_count: int
    has_adjusted_csv: bool | None
    passes_history: bool
    passes_liquidity: bool
    passes_group_members: bool
    passes_adjusted_requirement: bool
    decision: str
    failure_reasons: list[str]


@dataclass(frozen=True)
class UniverseGroupAuditRow:
    """單一股票群組在 universe audit 中的成員數與通過數摘要。"""

    group: str
    member_count: int
    eligible_member_count: int
    symbols: list[str]
    eligible_symbols: list[str]


@dataclass(frozen=True)
class PortfolioRotationUniverseAudit:
    """portfolio rotation 股票池 audit 的完整 JSON payload。"""

    schema_version: str
    start: str | None
    end: str | None
    min_row_count: int
    min_average_traded_value: float | None
    min_group_members: int
    adjusted_csv_dir: str | None
    require_adjusted_csv: bool
    symbol_count: int
    eligible_symbol_count: int
    adjusted_available_count: int | None
    group_count: int
    singleton_group_count: int
    rows: list[UniverseAuditRow]
    groups: list[UniverseGroupAuditRow]


def build_parser() -> argparse.ArgumentParser:
    """
    用途與流程：建立股票池品質 audit CLI parser，集中管理 CSV 清單、日期窗、流動性、分組與 adjusted CSV 條件。
    參數：無。
    回傳與錯誤：回傳 argparse.ArgumentParser；命令列格式錯誤由 argparse 處理，語意驗證由 run_universe_audit 處理。
    """
    parser = argparse.ArgumentParser(
        description=(
            "Audit a portfolio rotation universe before running strategy sweeps. "
            "The report highlights history length, traded value, group coverage, "
            "and adjusted CSV availability."
        )
    )
    parser.add_argument("--csv", action="append", required=True, help="OHLCV CSV path")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--min-row-count", type=int, default=1000)
    parser.add_argument("--min-average-traded-value", type=float, default=500_000_000.0)
    parser.add_argument("--min-group-members", type=int, default=1)
    parser.add_argument("--adjusted-csv-dir", type=Path)
    parser.add_argument("--require-adjusted-csv", action="store_true")
    parser.add_argument("--symbol-group", action="append")
    parser.add_argument("--summary-json", type=Path)
    parser.add_argument("--summary-md", type=Path)
    return parser


def run_universe_audit(
    *,
    csv_paths: list[Path],
    start: str | None,
    end: str | None,
    min_row_count: int,
    min_average_traded_value: float | None,
    min_group_members: int,
    adjusted_csv_dir: Path | None,
    require_adjusted_csv: bool,
    symbol_groups: dict[str, str] | None,
) -> PortfolioRotationUniverseAudit:
    """
    用途與流程：讀取多檔 OHLCV CSV 並建立股票池品質 audit，讓 portfolio rotation 擴大股票池前先檢查歷史長度、成交金額、群組覆蓋與 adjusted data availability。
    參數：csv_paths 是待檢查的 OHLCV 檔案；start/end 是可選日期窗；min_row_count 是最低資料筆數；min_average_traded_value 是最低平均成交金額，None 表示不檢查；min_group_members 是群組最低成員數；adjusted_csv_dir 是可選 adjusted CSV 目錄；require_adjusted_csv 決定缺 adjusted 是否列為失敗；symbol_groups 是 symbol 到 group 的對照表。
    回傳與錯誤：回傳 PortfolioRotationUniverseAudit；空 CSV 清單、門檻不合法、缺資料或 require adjusted 但未提供 adjusted_csv_dir 時拋出 ValueError。
    """
    if not csv_paths:
        raise ValueError("universe audit requires at least one CSV")
    if min_row_count <= 0:
        raise ValueError("min-row-count must be positive")
    if min_average_traded_value is not None and min_average_traded_value < 0:
        raise ValueError("min-average-traded-value cannot be negative")
    if min_group_members <= 0:
        raise ValueError("min-group-members must be positive")
    if require_adjusted_csv and adjusted_csv_dir is None:
        raise ValueError("require-adjusted-csv needs adjusted-csv-dir")

    groups_by_symbol = symbol_groups or {}
    symbols = [infer_symbol_from_path(path) for path in csv_paths]
    group_member_counts = _count_group_members(symbols, groups_by_symbol)
    rows = [
        _build_audit_row(
            csv_path=path,
            start=start,
            end=end,
            min_row_count=min_row_count,
            min_average_traded_value=min_average_traded_value,
            min_group_members=min_group_members,
            adjusted_csv_dir=adjusted_csv_dir,
            require_adjusted_csv=require_adjusted_csv,
            symbol_groups=groups_by_symbol,
            group_member_counts=group_member_counts,
        )
        for path in csv_paths
    ]
    groups = _build_group_rows(rows)
    adjusted_available = (
        sum(1 for row in rows if row.has_adjusted_csv) if adjusted_csv_dir is not None else None
    )
    return PortfolioRotationUniverseAudit(
        schema_version="portfolio_rotation_universe_audit.v1",
        start=start,
        end=end,
        min_row_count=min_row_count,
        min_average_traded_value=min_average_traded_value,
        min_group_members=min_group_members,
        adjusted_csv_dir=adjusted_csv_dir.as_posix() if adjusted_csv_dir is not None else None,
        require_adjusted_csv=require_adjusted_csv,
        symbol_count=len(rows),
        eligible_symbol_count=sum(row.decision == "eligible" for row in rows),
        adjusted_available_count=adjusted_available,
        group_count=len(groups),
        singleton_group_count=sum(group.member_count == 1 for group in groups),
        rows=rows,
        groups=groups,
    )


def write_universe_audit_json(
    audit: PortfolioRotationUniverseAudit,
    output_json: Path,
) -> None:
    """
    用途與流程：將股票池 audit 寫成 deterministic JSON，供實驗紀錄與後續自動化引用。
    參數：audit 是 run_universe_audit 產生的結果；output_json 是輸出路徑。
    回傳與錯誤：回傳 None；寫檔失敗時由 pathlib 拋出例外。
    """
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(asdict(audit), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="",
    )


def format_universe_audit_markdown(audit: PortfolioRotationUniverseAudit) -> str:
    """
    用途與流程：把股票池 audit 轉成 Markdown，優先呈現 eligible count、adjusted coverage、分組覆蓋與逐股失敗原因。
    參數：audit 是 run_universe_audit 產生的結果。
    回傳與錯誤：回傳 Markdown 字串；此函式不做 I/O。
    """
    lines = [
        "# Portfolio Rotation Universe Audit",
        "",
        f"- Schema: `{audit.schema_version}`",
        f"- Symbols: `{audit.symbol_count}`",
        f"- Eligible symbols: `{audit.eligible_symbol_count}`",
        f"- Groups: `{audit.group_count}`",
        f"- Singleton groups: `{audit.singleton_group_count}`",
        f"- Min row count: `{audit.min_row_count}`",
        f"- Min average traded value: `{_format_optional_float(audit.min_average_traded_value)}`",
        f"- Min group members: `{audit.min_group_members}`",
    ]
    if audit.adjusted_available_count is not None:
        lines.append(f"- Adjusted available: `{audit.adjusted_available_count}`")
    lines.extend(
        [
            "",
            "## Symbols",
            "",
            "| Symbol | Decision | Group | Rows | Avg traded value | Adjusted | Group members | Failure reasons |",
            "|---|---|---|---:|---:|---|---:|---|",
        ]
    )
    for row in audit.rows:
        lines.append(
            "| "
            f"{row.symbol} | {row.decision} | {row.group} | {row.row_count} | "
            f"{_format_optional_float(row.average_traded_value)} | "
            f"{_format_optional_bool(row.has_adjusted_csv)} | "
            f"{row.group_member_count} | "
            f"{'; '.join(row.failure_reasons) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Groups",
            "",
            "| Group | Members | Eligible | Symbols | Eligible symbols |",
            "|---|---:|---:|---|---|",
        ]
    )
    for group in audit.groups:
        lines.append(
            "| "
            f"{group.group} | {group.member_count} | {group.eligible_member_count} | "
            f"{', '.join(group.symbols)} | {', '.join(group.eligible_symbols) or 'none'} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_universe_audit_markdown(
    audit: PortfolioRotationUniverseAudit,
    output_md: Path,
) -> None:
    """
    用途與流程：將股票池 audit 寫成 Markdown artifact，方便人工檢查下一輪股票池擴充方向。
    參數：audit 是 run_universe_audit 的結果；output_md 是輸出 Markdown 路徑。
    回傳與錯誤：回傳 None；寫檔失敗時由 pathlib 拋出例外。
    """
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(
        format_universe_audit_markdown(audit),
        encoding="utf-8",
        newline="",
    )


def main(argv: list[str] | None = None) -> int:
    """
    用途與流程：CLI 入口，解析股票池 audit 參數後輸出 Markdown，並依需求寫 JSON/Markdown 檔。
    參數：argv 是可選命令列參數清單；None 時使用系統命令列。
    回傳與錯誤：成功回傳 0；輸入資料、門檻或 adjusted 條件不合法時拋出 ValueError。
    """
    args = build_parser().parse_args(argv)
    audit = run_universe_audit(
        csv_paths=[Path(path) for path in args.csv],
        start=args.start,
        end=args.end,
        min_row_count=args.min_row_count,
        min_average_traded_value=args.min_average_traded_value,
        min_group_members=args.min_group_members,
        adjusted_csv_dir=args.adjusted_csv_dir,
        require_adjusted_csv=args.require_adjusted_csv,
        symbol_groups=parse_symbol_group_assignments(args.symbol_group),
    )
    markdown = format_universe_audit_markdown(audit)
    if args.summary_json is not None:
        write_universe_audit_json(audit, args.summary_json)
    if args.summary_md is not None:
        write_universe_audit_markdown(audit, args.summary_md)
    print(markdown, end="")
    return 0


def _build_audit_row(
    *,
    csv_path: Path,
    start: str | None,
    end: str | None,
    min_row_count: int,
    min_average_traded_value: float | None,
    min_group_members: int,
    adjusted_csv_dir: Path | None,
    require_adjusted_csv: bool,
    symbol_groups: dict[str, str],
    group_member_counts: dict[str, int],
) -> UniverseAuditRow:
    """
    用途與流程：載入單檔 OHLCV 並計算其股票池品質欄位，包含資料筆數、平均成交金額、群組成員數與 adjusted CSV 狀態。
    參數：csv_path/start/end 定義資料；min_row_count/min_average_traded_value/min_group_members 是 gate 門檻；adjusted_csv_dir/require_adjusted_csv 定義 adjusted data 條件；symbol_groups/group_member_counts 提供分組資訊。
    回傳與錯誤：回傳 UniverseAuditRow；資料讀取或日期過濾無有效 bar 時由 load_filtered_bars 拋出 ValueError。
    """
    symbol = infer_symbol_from_path(csv_path)
    bars = load_filtered_bars(csv_path, start=start, end=end)
    row_count = len(bars)
    group = symbol_groups.get(symbol, "ungrouped")
    group_member_count = group_member_counts.get(group, 1)
    average_traded_value = (
        sum(bar.close * bar.volume for bar in bars) / row_count if row_count else None
    )
    has_adjusted_csv = (
        (adjusted_csv_dir / f"TWSEADJ_{symbol}_1D.csv").exists()
        if adjusted_csv_dir is not None
        else None
    )
    passes_history = row_count >= min_row_count
    passes_liquidity = (
        True
        if min_average_traded_value is None
        else average_traded_value is not None
        and average_traded_value >= min_average_traded_value
    )
    passes_group_members = group_member_count >= min_group_members
    passes_adjusted_requirement = (
        True if not require_adjusted_csv else bool(has_adjusted_csv)
    )
    failure_reasons = _build_failure_reasons(
        passes_history=passes_history,
        passes_liquidity=passes_liquidity,
        passes_group_members=passes_group_members,
        passes_adjusted_requirement=passes_adjusted_requirement,
    )
    return UniverseAuditRow(
        symbol=symbol,
        csv_path=csv_path.as_posix(),
        group=group,
        row_count=row_count,
        first_timestamp=bars[0].timestamp if bars else None,
        last_timestamp=bars[-1].timestamp if bars else None,
        average_traded_value=average_traded_value,
        group_member_count=group_member_count,
        has_adjusted_csv=has_adjusted_csv,
        passes_history=passes_history,
        passes_liquidity=passes_liquidity,
        passes_group_members=passes_group_members,
        passes_adjusted_requirement=passes_adjusted_requirement,
        decision="eligible" if not failure_reasons else "diagnostic-only",
        failure_reasons=failure_reasons,
    )


def _count_group_members(
    symbols: list[str],
    symbol_groups: dict[str, str],
) -> dict[str, int]:
    """
    用途與流程：計算每個 group 在輸入股票池中的成員數，讓單成員群組可以在事前 audit 中被標記。
    參數：symbols 是待檢查股票代號；symbol_groups 是 symbol 到 group 的 mapping，缺值會歸為 ungrouped。
    回傳與錯誤：回傳 group 到成員數的 dict；此函式不做 I/O。
    """
    counts: dict[str, int] = {}
    for symbol in symbols:
        group = symbol_groups.get(symbol, "ungrouped")
        counts[group] = counts.get(group, 0) + 1
    return counts


def _build_group_rows(rows: list[UniverseAuditRow]) -> list[UniverseGroupAuditRow]:
    """
    用途與流程：由逐股 audit rows 彙總群組成員數與 eligible member count，方便檢查股票池是否仍有單一群組過薄問題。
    參數：rows 是逐股 UniverseAuditRow 清單。
    回傳與錯誤：回傳依 group 名稱排序的 UniverseGroupAuditRow 清單；此函式不做 I/O。
    """
    groups: dict[str, list[UniverseAuditRow]] = {}
    for row in rows:
        groups.setdefault(row.group, []).append(row)
    return [
        UniverseGroupAuditRow(
            group=group,
            member_count=len(group_rows),
            eligible_member_count=sum(row.decision == "eligible" for row in group_rows),
            symbols=sorted(row.symbol for row in group_rows),
            eligible_symbols=sorted(
                row.symbol for row in group_rows if row.decision == "eligible"
            ),
        )
        for group, group_rows in sorted(groups.items())
    ]


def _build_failure_reasons(
    *,
    passes_history: bool,
    passes_liquidity: bool,
    passes_group_members: bool,
    passes_adjusted_requirement: bool,
) -> list[str]:
    """
    用途與流程：將各 gate 的布林結果轉成 deterministic failure reason list，讓 Markdown / JSON 能清楚說明股票為何不能進主股票池。
    參數：四個布林值分別代表歷史長度、流動性、群組成員數與 adjusted CSV 條件是否通過。
    回傳與錯誤：回傳 failure reason list；此函式不主動拋錯。
    """
    reasons: list[str] = []
    if not passes_history:
        reasons.append("history_below_threshold")
    if not passes_liquidity:
        reasons.append("liquidity_below_threshold")
    if not passes_group_members:
        reasons.append("group_members_below_threshold")
    if not passes_adjusted_requirement:
        reasons.append("adjusted_csv_missing")
    return reasons


def _format_optional_float(value: float | None) -> str:
    """
    用途與流程：格式化可選浮點數，讓 Markdown 對缺值顯示 n/a，對整數顯示無小數。
    參數：value 是 float 或 None。
    回傳與錯誤：回傳字串；此函式不主動拋錯。
    """
    if value is None:
        return "n/a"
    if value.is_integer():
        return str(int(value))
    return f"{value:.2f}"


def _format_optional_bool(value: bool | None) -> str:
    """
    用途與流程：格式化可選布林值，讓 adjusted CSV 未檢查時顯示 n/a。
    參數：value 是 bool 或 None。
    回傳與錯誤：True 回傳 yes，False 回傳 no，None 回傳 n/a。
    """
    if value is None:
        return "n/a"
    return "yes" if value else "no"


if __name__ == "__main__":
    raise SystemExit(main())
