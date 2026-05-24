from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class UniverseSelectionRow:
    """單一股票在 high-quality universe selector 中的選取結果。"""

    symbol: str
    group: str
    source_decision: str
    average_traded_value: float | None
    row_count: int
    selected: bool
    rank_in_group: int | None
    selection_reasons: list[str]
    source_failure_reasons: list[str]


@dataclass(frozen=True)
class UniverseSelectionGroupRow:
    """單一群組在 high-quality universe selector 中的候選與入選摘要。"""

    group: str
    eligible_candidate_count: int
    selected_count: int
    selected_symbols: list[str]
    excluded_symbols: list[str]


@dataclass(frozen=True)
class PortfolioRotationUniverseSelection:
    """portfolio rotation high-quality universe selection 的完整 JSON payload。"""

    schema_version: str
    source_audit_json: str | None
    source_schema_version: str | None
    min_average_traded_value: float | None
    min_eligible_members_per_group: int
    max_symbols_per_group: int
    selected_symbol_count: int
    selected_symbols: list[str]
    selected_symbols_by_group: dict[str, list[str]]
    rows: list[UniverseSelectionRow]
    groups: list[UniverseSelectionGroupRow]


def build_parser() -> argparse.ArgumentParser:
    """
    用途與流程：建立 high-quality universe selector 的 CLI parser，將 universe audit JSON 轉成可重跑的股票池選取結果。
    參數：無。
    回傳與錯誤：回傳 argparse.ArgumentParser；命令列格式錯誤由 argparse 處理，語意驗證由 run_universe_selection 處理。
    """
    parser = argparse.ArgumentParser(
        description=(
            "Select a deterministic high-quality portfolio rotation universe from "
            "a portfolio_rotation_universe_audit.v1 JSON artifact."
        )
    )
    parser.add_argument("--audit-json", type=Path, required=True)
    parser.add_argument("--min-average-traded-value", type=float)
    parser.add_argument("--min-eligible-members-per-group", type=int, default=2)
    parser.add_argument("--max-symbols-per-group", type=int, default=4)
    parser.add_argument("--summary-json", type=Path)
    parser.add_argument("--summary-md", type=Path)
    return parser


def load_audit_json(audit_json: Path) -> dict[str, Any]:
    """
    用途與流程：讀取 universe audit JSON artifact，並驗證它至少包含 selector 需要的 schema 與 rows。
    參數：audit_json 是 `portfolio_rotation_universe_audit.py` 輸出的 JSON 路徑。
    回傳與錯誤：回傳 dict payload；檔案不存在、JSON 格式錯誤或缺少 rows 時由 pathlib/json 或 ValueError 回報。
    """
    payload = json.loads(audit_json.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("audit JSON must contain an object")
    if not isinstance(payload.get("rows"), list):
        raise ValueError("audit JSON must contain rows")
    return payload


def run_universe_selection(
    audit: dict[str, Any],
    *,
    source_audit_json: str | None,
    min_average_traded_value: float | None,
    min_eligible_members_per_group: int,
    max_symbols_per_group: int,
) -> PortfolioRotationUniverseSelection:
    """
    用途與流程：從 universe audit 的 eligible rows 建立 deterministic high-quality 股票池；先套用可選成交金額門檻，再排除 eligible 成員不足的 group，最後在每個 group 內依平均成交金額、資料筆數與 symbol 排序，取前 N 檔。
    參數：audit 是 universe audit JSON payload；source_audit_json 是來源路徑字串；min_average_traded_value 是 selector 額外成交金額門檻，None 表示沿用 audit 的 eligible 判斷；min_eligible_members_per_group 是 selector 層級要求的 group 可用成員數下限；max_symbols_per_group 是每個 group 最多入選檔數。
    回傳與錯誤：回傳 PortfolioRotationUniverseSelection；門檻不合法或 audit rows 缺少必要欄位時拋出 ValueError。
    """
    if min_average_traded_value is not None and min_average_traded_value < 0:
        raise ValueError("min-average-traded-value cannot be negative")
    if min_eligible_members_per_group <= 0:
        raise ValueError("min-eligible-members-per-group must be positive")
    if max_symbols_per_group <= 0:
        raise ValueError("max-symbols-per-group must be positive")

    raw_rows = audit.get("rows")
    if not isinstance(raw_rows, list):
        raise ValueError("audit rows must be a list")
    candidate_rows = [_coerce_audit_row(row) for row in raw_rows]
    ranked_by_group = _rank_candidates_by_group(
        candidate_rows,
        min_average_traded_value=min_average_traded_value,
    )
    selected_symbols = _select_symbols_by_group(
        ranked_by_group,
        min_eligible_members_per_group=min_eligible_members_per_group,
        max_symbols_per_group=max_symbols_per_group,
    )
    rows = [
        _build_selection_row(
            row,
            ranked_by_group=ranked_by_group,
            selected_symbols=selected_symbols,
            min_average_traded_value=min_average_traded_value,
            min_eligible_members_per_group=min_eligible_members_per_group,
            max_symbols_per_group=max_symbols_per_group,
        )
        for row in candidate_rows
    ]
    groups = _build_group_rows(rows, ranked_by_group)
    selected_by_group = {
        group.group: group.selected_symbols
        for group in groups
        if group.selected_symbols
    }
    selected = sorted(selected_symbols)
    return PortfolioRotationUniverseSelection(
        schema_version="portfolio_rotation_universe_selection.v1",
        source_audit_json=source_audit_json,
        source_schema_version=audit.get("schema_version"),
        min_average_traded_value=min_average_traded_value,
        min_eligible_members_per_group=min_eligible_members_per_group,
        max_symbols_per_group=max_symbols_per_group,
        selected_symbol_count=len(selected),
        selected_symbols=selected,
        selected_symbols_by_group=selected_by_group,
        rows=rows,
        groups=groups,
    )


def write_universe_selection_json(
    selection: PortfolioRotationUniverseSelection,
    output_json: Path,
) -> None:
    """
    用途與流程：將 high-quality universe selection 寫成 deterministic JSON，供後續回測命令與實驗紀錄引用。
    參數：selection 是 run_universe_selection 產生的結果；output_json 是輸出路徑。
    回傳與錯誤：回傳 None；寫檔失敗時由 pathlib 拋出例外。
    """
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(asdict(selection), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="",
    )


def format_universe_selection_markdown(
    selection: PortfolioRotationUniverseSelection,
) -> str:
    """
    用途與流程：把 high-quality universe selection 轉成 Markdown，摘要 selector 參數、入選股票、逐股原因與分組結果。
    參數：selection 是 run_universe_selection 產生的結果。
    回傳與錯誤：回傳 Markdown 字串；此函式不做 I/O。
    """
    lines = [
        "# Portfolio Rotation Universe Selection",
        "",
        f"- Schema: `{selection.schema_version}`",
        f"- Source audit: `{selection.source_audit_json or 'n/a'}`",
        f"- Selected symbols: `{selection.selected_symbol_count}`",
        f"- Min average traded value: `{_format_optional_float(selection.min_average_traded_value)}`",
        f"- Min eligible members per group: `{selection.min_eligible_members_per_group}`",
        f"- Max symbols per group: `{selection.max_symbols_per_group}`",
        f"- Selected list: `{', '.join(selection.selected_symbols) or 'none'}`",
        "",
        "## Groups",
        "",
        "| Group | Eligible candidates | Selected | Selected symbols | Excluded symbols |",
        "|---|---:|---:|---|---|",
    ]
    for group in selection.groups:
        lines.append(
            "| "
            f"{group.group} | {group.eligible_candidate_count} | {group.selected_count} | "
            f"{', '.join(group.selected_symbols) or 'none'} | "
            f"{', '.join(group.excluded_symbols) or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Symbols",
            "",
            "| Symbol | Selected | Group | Rank | Avg traded value | Rows | Reasons |",
            "|---|---|---|---:|---:|---:|---|",
        ]
    )
    for row in selection.rows:
        lines.append(
            "| "
            f"{row.symbol} | {_format_bool(row.selected)} | {row.group} | "
            f"{row.rank_in_group if row.rank_in_group is not None else 'n/a'} | "
            f"{_format_optional_float(row.average_traded_value)} | {row.row_count} | "
            f"{'; '.join(row.selection_reasons) or 'selected'} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_universe_selection_markdown(
    selection: PortfolioRotationUniverseSelection,
    output_md: Path,
) -> None:
    """
    用途與流程：將 high-quality universe selection 寫成 Markdown artifact，方便人工檢查股票池建構規則。
    參數：selection 是 run_universe_selection 的結果；output_md 是輸出 Markdown 路徑。
    回傳與錯誤：回傳 None；寫檔失敗時由 pathlib 拋出例外。
    """
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(
        format_universe_selection_markdown(selection),
        encoding="utf-8",
        newline="",
    )


def main(argv: list[str] | None = None) -> int:
    """
    用途與流程：CLI 入口，讀取 universe audit JSON、執行 high-quality selector，輸出 Markdown 並依需求寫 JSON/Markdown artifact。
    參數：argv 是可選命令列參數清單；None 時使用系統命令列。
    回傳與錯誤：成功回傳 0；輸入檔或 selector 門檻不合法時拋出 ValueError。
    """
    args = build_parser().parse_args(argv)
    audit = load_audit_json(args.audit_json)
    selection = run_universe_selection(
        audit,
        source_audit_json=args.audit_json.as_posix(),
        min_average_traded_value=args.min_average_traded_value,
        min_eligible_members_per_group=args.min_eligible_members_per_group,
        max_symbols_per_group=args.max_symbols_per_group,
    )
    markdown = format_universe_selection_markdown(selection)
    if args.summary_json is not None:
        write_universe_selection_json(selection, args.summary_json)
    if args.summary_md is not None:
        write_universe_selection_markdown(selection, args.summary_md)
    print(markdown, end="")
    return 0


def _coerce_audit_row(row: Any) -> dict[str, Any]:
    """
    用途與流程：驗證並標準化單筆 audit row，避免 selector 對缺欄位或型別錯誤產生隱性結果。
    參數：row 是 audit JSON 的單筆 rows 元素。
    回傳與錯誤：回傳 dict；缺少 symbol/group/decision/row_count 或 failure_reasons 型別不符時拋出 ValueError。
    """
    if not isinstance(row, dict):
        raise ValueError("audit row must be an object")
    for key in ("symbol", "group", "decision", "row_count"):
        if key not in row:
            raise ValueError(f"audit row missing {key}")
    failure_reasons = row.get("failure_reasons", [])
    if not isinstance(failure_reasons, list):
        raise ValueError("audit row failure_reasons must be a list")
    return row


def _rank_candidates_by_group(
    rows: list[dict[str, Any]],
    *,
    min_average_traded_value: float | None,
) -> dict[str, list[dict[str, Any]]]:
    """
    用途與流程：依 group 收集 selector eligible candidates，並用平均成交金額、資料筆數與 symbol 做 deterministic 排名。
    參數：rows 是標準化 audit rows；min_average_traded_value 是 selector 額外流動性門檻，None 表示不加門檻。
    回傳與錯誤：回傳 group 到排序後 row list 的 dict；此函式不做 I/O。
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("decision") != "eligible":
            continue
        average_traded_value = row.get("average_traded_value")
        if min_average_traded_value is not None:
            if average_traded_value is None or average_traded_value < min_average_traded_value:
                continue
        grouped.setdefault(str(row["group"]), []).append(row)
    for group_rows in grouped.values():
        group_rows.sort(
            key=lambda row: (
                -float(row.get("average_traded_value") or 0.0),
                -int(row.get("row_count") or 0),
                str(row.get("symbol")),
            )
        )
    return dict(sorted(grouped.items()))


def _select_symbols_by_group(
    ranked_by_group: dict[str, list[dict[str, Any]]],
    *,
    min_eligible_members_per_group: int,
    max_symbols_per_group: int,
) -> set[str]:
    """
    用途與流程：對每個 group 套用最低候選成員數與每組最多入選數，產生最終股票代號集合。
    參數：ranked_by_group 是已排序的 group 候選；min_eligible_members_per_group 是 group 進入股票池的最低候選數；max_symbols_per_group 是每組最多入選檔數。
    回傳與錯誤：回傳 selected symbol set；此函式不主動拋錯。
    """
    selected: set[str] = set()
    for group_rows in ranked_by_group.values():
        if len(group_rows) < min_eligible_members_per_group:
            continue
        for row in group_rows[:max_symbols_per_group]:
            selected.add(str(row["symbol"]))
    return selected


def _build_selection_row(
    row: dict[str, Any],
    *,
    ranked_by_group: dict[str, list[dict[str, Any]]],
    selected_symbols: set[str],
    min_average_traded_value: float | None,
    min_eligible_members_per_group: int,
    max_symbols_per_group: int,
) -> UniverseSelectionRow:
    """
    用途與流程：將單筆 audit row 加上 selector rank、selected flag 與排除原因，供 JSON/Markdown 檢查。
    參數：row 是 audit row；ranked_by_group 是 group 內候選排名；selected_symbols 是最終入選集合；其餘參數是 selector 門檻，用於產生原因。
    回傳與錯誤：回傳 UniverseSelectionRow；輸入 row 已由 _coerce_audit_row 驗證。
    """
    symbol = str(row["symbol"])
    group = str(row["group"])
    ranked_rows = ranked_by_group.get(group, [])
    ranked_symbols = [str(candidate["symbol"]) for candidate in ranked_rows]
    rank = ranked_symbols.index(symbol) + 1 if symbol in ranked_symbols else None
    source_failure_reasons = [str(reason) for reason in row.get("failure_reasons", [])]
    reasons = _selection_reasons(
        row,
        rank=rank,
        candidate_count=len(ranked_rows),
        selected=symbol in selected_symbols,
        min_average_traded_value=min_average_traded_value,
        min_eligible_members_per_group=min_eligible_members_per_group,
        max_symbols_per_group=max_symbols_per_group,
    )
    return UniverseSelectionRow(
        symbol=symbol,
        group=group,
        source_decision=str(row["decision"]),
        average_traded_value=row.get("average_traded_value"),
        row_count=int(row["row_count"]),
        selected=symbol in selected_symbols,
        rank_in_group=rank,
        selection_reasons=reasons,
        source_failure_reasons=source_failure_reasons,
    )


def _selection_reasons(
    row: dict[str, Any],
    *,
    rank: int | None,
    candidate_count: int,
    selected: bool,
    min_average_traded_value: float | None,
    min_eligible_members_per_group: int,
    max_symbols_per_group: int,
) -> list[str]:
    """
    用途與流程：依來源 eligibility、selector 流動性門檻、group 候選數與 group cap 產生 deterministic selection reason。
    參數：row 是 audit row；rank/candidate_count 是 group ranking 結果；selected 表示是否入選；其餘參數是 selector 門檻。
    回傳與錯誤：回傳原因清單；入選股票回傳空清單。
    """
    if selected:
        return []
    reasons: list[str] = []
    if row.get("decision") != "eligible":
        reasons.append("source_not_eligible")
    average_traded_value = row.get("average_traded_value")
    if (
        min_average_traded_value is not None
        and row.get("decision") == "eligible"
        and (average_traded_value is None or average_traded_value < min_average_traded_value)
    ):
        reasons.append("selector_liquidity_below_threshold")
    if rank is not None and candidate_count < min_eligible_members_per_group:
        reasons.append("eligible_group_members_below_threshold")
    if rank is not None and candidate_count >= min_eligible_members_per_group:
        if rank > max_symbols_per_group:
            reasons.append("group_cap_excluded")
    if not reasons:
        reasons.append("not_selected")
    return reasons


def _build_group_rows(
    rows: list[UniverseSelectionRow],
    ranked_by_group: dict[str, list[dict[str, Any]]],
) -> list[UniverseSelectionGroupRow]:
    """
    用途與流程：彙總 selector 的 group-level 候選數、入選數與排除股票，方便檢查股票池是否仍被單一群組壟斷。
    參數：rows 是逐股 selection rows；ranked_by_group 是 group 候選排序。
    回傳與錯誤：回傳依 group 名稱排序的 UniverseSelectionGroupRow 清單；此函式不做 I/O。
    """
    group_names = sorted({row.group for row in rows} | set(ranked_by_group))
    output: list[UniverseSelectionGroupRow] = []
    for group in group_names:
        group_rows = [row for row in rows if row.group == group]
        ranked_symbols = [str(row["symbol"]) for row in ranked_by_group.get(group, [])]
        selected_set = {row.symbol for row in group_rows if row.selected}
        selected_symbols = [
            symbol for symbol in ranked_symbols if symbol in selected_set
        ]
        excluded_symbols = sorted(row.symbol for row in group_rows if not row.selected)
        output.append(
            UniverseSelectionGroupRow(
                group=group,
                eligible_candidate_count=len(ranked_by_group.get(group, [])),
                selected_count=len(selected_symbols),
                selected_symbols=selected_symbols,
                excluded_symbols=excluded_symbols,
            )
        )
    return output


def _format_optional_float(value: float | None) -> str:
    """
    用途與流程：格式化可選浮點數，讓 Markdown 對缺值顯示 n/a，對整數顯示無小數。
    參數：value 是 float 或 None。
    回傳與錯誤：回傳字串；此函式不主動拋錯。
    """
    if value is None:
        return "n/a"
    numeric_value = float(value)
    if numeric_value.is_integer():
        return str(int(numeric_value))
    return f"{numeric_value:.2f}"


def _format_bool(value: bool) -> str:
    """
    用途與流程：把布林值轉成 Markdown 中較容易讀的 yes/no。
    參數：value 是布林值。
    回傳與錯誤：True 回傳 yes，False 回傳 no；此函式不主動拋錯。
    """
    return "yes" if value else "no"


if __name__ == "__main__":
    raise SystemExit(main())
