from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from tools.build_twse_adjusted_ohlcv import (
    ADJUSTMENT_METHOD,
    ADJUSTMENT_SOURCE,
    AdjustedOhlcvResult,
    build_adjusted_ohlcv,
)


@dataclass(frozen=True)
class AdjustedOhlcvBatchResult:
    """批次 adjusted OHLCV 建立結果，保留每檔輸出與彙總 manifest 位置。"""

    symbols: tuple[str, ...]
    start: str
    end: str
    row_count_total: int
    missing_adjustment_count_total: int
    skipped_row_count_total: int
    output_dir: Path
    batch_manifest_json: Path
    results: list[AdjustedOhlcvResult]


def build_parser() -> argparse.ArgumentParser:
    """
    用途與流程：建立批次 adjusted OHLCV 工具的 CLI parser，讓同一批股票可用一致日期窗與目錄規則重建。
    參數：無。
    回傳與錯誤：回傳 argparse.ArgumentParser；parser 不做 I/O，格式與檔案存在性由後續流程驗證。
    """
    parser = argparse.ArgumentParser(
        description=(
            "Build adjusted SignalForge TWSE OHLCV CSVs for a comma-separated "
            "symbol list and write a deterministic batch manifest."
        )
    )
    parser.add_argument(
        "--symbols-list",
        required=True,
        help="Comma-separated TWSE symbols, for example 2330,2317,2454.",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("data/processed"),
        help="Directory containing TWSE_<symbol>_1D.csv source files.",
    )
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/generated/adjusted-data"),
        help="Directory for TWSEADJ_<symbol>_1D.csv and per-symbol manifests.",
    )
    parser.add_argument(
        "--batch-manifest-json",
        required=True,
        type=Path,
        help="Output JSON manifest summarizing the batch.",
    )
    return parser


def parse_symbols_list(value: str) -> tuple[str, ...]:
    """
    用途與流程：解析逗號分隔股票代號，標準化空白與大小寫，並拒絕空清單或重複代號。
    參數：value 是外部 CLI 傳入的字串，例如 `2330, 2317`。
    回傳與錯誤：回傳 tuple[str, ...]；沒有有效代號或出現重複代號時拋出 ValueError。
    """
    symbols = tuple(symbol.strip().upper() for symbol in value.split(",") if symbol.strip())
    if not symbols:
        raise ValueError("symbols-list must contain at least one symbol")
    seen: set[str] = set()
    duplicates: list[str] = []
    for symbol in symbols:
        if symbol in seen:
            duplicates.append(symbol)
        seen.add(symbol)
    if duplicates:
        raise ValueError("symbols-list contains duplicate symbols: " + ", ".join(duplicates))
    return symbols


def build_adjusted_ohlcv_batch(
    *,
    symbols: tuple[str, ...],
    source_dir: Path,
    start: str,
    end: str,
    output_dir: Path,
    batch_manifest_json: Path,
    fetch_chart_json: Callable[[str, date, date], dict[str, Any]] | None = None,
) -> AdjustedOhlcvBatchResult:
    """
    用途與流程：依固定檔名規則批次建立 adjusted OHLCV，並把每檔結果彙總成 batch manifest。
    參數：symbols 是已解析股票代號；source_dir 是 `TWSE_<symbol>_1D.csv` 所在目錄；start/end 是日期窗；output_dir 是 adjusted CSV 與 per-symbol manifest 輸出目錄；batch_manifest_json 是批次 manifest 路徑；fetch_chart_json 可由測試注入固定 Yahoo payload。
    回傳與錯誤：回傳 AdjustedOhlcvBatchResult；任一 source CSV 缺失、Yahoo payload 無效或調整後資料驗證失敗時由單檔工具拋出例外並停止批次。
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[AdjustedOhlcvResult] = []
    for symbol in symbols:
        result = build_adjusted_ohlcv(
            symbol=symbol,
            source_csv=source_dir / f"TWSE_{symbol}_1D.csv",
            start=start,
            end=end,
            output_csv=output_dir / f"TWSEADJ_{symbol}_1D.csv",
            manifest_json=output_dir / f"TWSEADJ_{symbol}_1D_manifest.json",
            fetch_chart_json=fetch_chart_json,
        )
        results.append(result)

    batch = AdjustedOhlcvBatchResult(
        symbols=symbols,
        start=start,
        end=end,
        row_count_total=sum(result.row_count for result in results),
        missing_adjustment_count_total=sum(
            result.missing_adjustment_count for result in results
        ),
        skipped_row_count_total=sum(result.skipped_row_count for result in results),
        output_dir=output_dir,
        batch_manifest_json=batch_manifest_json,
        results=results,
    )
    write_batch_manifest(batch)
    return batch


def write_batch_manifest(batch: AdjustedOhlcvBatchResult) -> None:
    """
    用途與流程：將批次 adjusted OHLCV 結果寫成 deterministic JSON，提供後續報表與筆記引用。
    參數：batch 是 build_adjusted_ohlcv_batch 產生的彙總結果。
    回傳與錯誤：回傳 None；寫檔失敗時由 Path.write_text 或 mkdir 拋出例外。
    """
    manifest = {
        "adjusted": True,
        "adjustment_method": ADJUSTMENT_METHOD,
        "adjustment_source": ADJUSTMENT_SOURCE,
        "batch_manifest_json": batch.batch_manifest_json.as_posix(),
        "end": batch.end,
        "missing_adjustment_count_total": batch.missing_adjustment_count_total,
        "notes": (
            "Batch manifest for adjusted TWSE OHLCV. Each symbol preserves "
            "source CSV volume and scales OHLC by Yahoo adjclose/close ratio."
        ),
        "output_dir": batch.output_dir.as_posix(),
        "result_count": len(batch.results),
        "results": [
            {
                **asdict(result),
                "source_csv": result.source_csv.as_posix(),
                "output_csv": result.output_csv.as_posix(),
                "manifest_json": result.manifest_json.as_posix(),
            }
            for result in batch.results
        ],
        "row_count_total": batch.row_count_total,
        "skipped_row_count_total": batch.skipped_row_count_total,
        "start": batch.start,
        "symbols": list(batch.symbols),
        "timeframe": "1D",
        "timezone": "Asia/Taipei",
        "volume_source": "source CSV volume preserved",
    }
    batch.batch_manifest_json.parent.mkdir(parents=True, exist_ok=True)
    batch.batch_manifest_json.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="",
    )


def main(argv: list[str] | None = None) -> int:
    """
    用途與流程：命令列入口，解析 symbols-list 與目錄參數後執行批次 adjusted OHLCV 建立。
    參數：argv 是可選命令列參數；None 時使用系統命令列。
    回傳與錯誤：成功回傳 0；輸入錯誤、下載錯誤或資料驗證錯誤會往外拋出並讓 CLI 失敗。
    """
    args = build_parser().parse_args(argv)
    batch = build_adjusted_ohlcv_batch(
        symbols=parse_symbols_list(args.symbols_list),
        source_dir=args.source_dir,
        start=args.start,
        end=args.end,
        output_dir=args.output_dir,
        batch_manifest_json=args.batch_manifest_json,
    )
    print(
        "built adjusted OHLCV batch "
        f"symbols={len(batch.symbols)} rows={batch.row_count_total} "
        f"manifest={batch.batch_manifest_json}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
