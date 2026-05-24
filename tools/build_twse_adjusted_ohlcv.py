from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from signal_forge.core.market_data import Bar, load_bars_from_csv, validate_bars
from signal_forge.data.fetch import NormalizedBar, format_signal_forge_csv


TAIPEI_TZ = timezone(timedelta(hours=8), "Asia/Taipei")
ADJUSTMENT_METHOD = "source_ohlcv_scaled_by_yahoo_adjclose_ratio"
ADJUSTMENT_SOURCE = "Yahoo chart adjclose/close ratio"


@dataclass(frozen=True)
class AdjustedOhlcvBuild:
    """調整價資料建立結果，包含輸出 K 線與資料品質計數。"""

    bars: list[NormalizedBar]
    source_row_count: int
    row_count: int
    missing_adjustment_count: int
    skipped_row_count: int


@dataclass(frozen=True)
class AdjustedOhlcvResult:
    """命令列工具的輸出摘要，方便測試與批次流程確認寫檔位置。"""

    market: str
    symbol: str
    yahoo_symbol: str
    start: str
    end: str
    row_count: int
    missing_adjustment_count: int
    skipped_row_count: int
    source_csv: Path
    output_csv: Path
    manifest_json: Path


def build_parser() -> argparse.ArgumentParser:
    """
    用途與流程：建立 TWSE 調整價 OHLCV 工具的命令列 parser，集中定義必要輸入與輸出檔案。
    參數：無。
    回傳與錯誤：回傳 argparse.ArgumentParser；parser 本身不做 I/O，實際驗證在 parse_args 與後續流程中發生。
    """
    parser = argparse.ArgumentParser(
        description=(
            "Build SignalForge adjusted TWSE OHLCV by scaling source OHLC "
            "with Yahoo adjclose/close ratios while preserving source volume."
        )
    )
    parser.add_argument("--symbol", required=True, help="TWSE symbol, for example 2330")
    parser.add_argument(
        "--yahoo-symbol",
        default=None,
        help="Yahoo chart symbol. Defaults to <symbol>.TW.",
    )
    parser.add_argument(
        "--source-csv",
        required=True,
        type=Path,
        help="Existing SignalForge TWSE OHLCV CSV.",
    )
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument(
        "--output-csv",
        required=True,
        type=Path,
        help="Output adjusted SignalForge OHLCV CSV.",
    )
    parser.add_argument(
        "--manifest-json",
        required=True,
        type=Path,
        help="Output manifest JSON documenting adjustment method and source.",
    )
    return parser


def build_adjusted_ohlcv(
    *,
    symbol: str,
    source_csv: Path,
    start: str,
    end: str,
    output_csv: Path,
    manifest_json: Path,
    yahoo_symbol: str | None = None,
    fetch_chart_json: Callable[[str, date, date], dict[str, Any]] | None = None,
) -> AdjustedOhlcvResult:
    """
    用途與流程：讀取既有 TWSE OHLCV CSV，抓取或接收 Yahoo chart JSON，將 `adjclose / close` 比例套到 source OHLC，最後寫出調整後 CSV 與 deterministic manifest。
    參數：symbol 是台股代號；source_csv 是原始 SignalForge CSV；start/end 是 `YYYY-MM-DD` 日期窗；output_csv 與 manifest_json 是輸出路徑；yahoo_symbol 可覆寫 Yahoo 代號；fetch_chart_json 是測試或批次可注入的下載函式。
    回傳與錯誤：回傳 AdjustedOhlcvResult；日期範圍錯誤、source CSV 無效、Yahoo ratio 不足或調整後資料無效時拋出 ValueError 或 market data 驗證例外。
    """
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("symbol must not be empty")
    normalized_yahoo_symbol = yahoo_symbol or f"{normalized_symbol}.TW"
    start_date = _parse_iso_date(start)
    end_date = _parse_iso_date(end)
    if end_date < start_date:
        raise ValueError("end date must be on or after start date")

    source_bars = load_bars_from_csv(source_csv)
    fetch = fetch_chart_json or fetch_yahoo_chart_json
    yahoo_payload = fetch(normalized_yahoo_symbol, start_date, end_date)
    ratios = parse_yahoo_adjustment_ratios(yahoo_payload)
    build = apply_adjustment_ratios(
        source_bars,
        ratios,
        start=start_date,
        end=end_date,
    )
    if not build.bars:
        raise ValueError("no adjusted rows were produced")

    validation = validate_bars([bar.to_bar() for bar in build.bars])
    if not validation.is_valid:
        raise ValueError("; ".join(validation.errors))

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_csv.write_text(format_signal_forge_csv(build.bars), encoding="utf-8", newline="")

    manifest = build_manifest(
        symbol=normalized_symbol,
        yahoo_symbol=normalized_yahoo_symbol,
        source_csv=source_csv,
        output_csv=output_csv,
        start=start_date,
        end=end_date,
        build=build,
    )
    manifest_json.parent.mkdir(parents=True, exist_ok=True)
    manifest_json.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="",
    )

    return AdjustedOhlcvResult(
        market="twse",
        symbol=normalized_symbol,
        yahoo_symbol=normalized_yahoo_symbol,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
        row_count=build.row_count,
        missing_adjustment_count=build.missing_adjustment_count,
        skipped_row_count=build.skipped_row_count,
        source_csv=source_csv,
        output_csv=output_csv,
        manifest_json=manifest_json,
    )


def fetch_yahoo_chart_json(
    yahoo_symbol: str,
    start: date,
    end: date,
) -> dict[str, Any]:
    """
    用途與流程：從 Yahoo chart endpoint 下載日線 JSON，僅作公開研究資料的調整係數來源，不讀 API key 或 credential。
    參數：yahoo_symbol 是 Yahoo 代號，例如 `2330.TW`；start/end 是查詢日期窗，end 會轉成 Yahoo period2 的隔日邊界。
    回傳與錯誤：成功時回傳解析後 JSON dict；HTTP、JSON 或網路錯誤會由標準函式原樣拋出。
    """
    request = Request(
        _yahoo_chart_url(yahoo_symbol, start, end),
        headers={
            "Accept": "application/json,text/plain,*/*",
            "User-Agent": "Mozilla/5.0 SignalForge/1.0 adjusted price research",
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def parse_yahoo_adjustment_ratios(payload: dict[str, Any]) -> dict[str, float]:
    """
    用途與流程：解析 Yahoo chart JSON，把每個 timestamp 轉成 Asia/Taipei 日期，並計算 `adjclose / close` 調整比例。
    參數：payload 是 Yahoo chart endpoint 的 JSON dict，需包含 timestamp、quote.close 與 adjclose.adjclose。
    回傳與錯誤：回傳日期字串到正數比例的 dict；payload 結構缺漏、沒有有效比例或價格非正時拋出 ValueError。
    """
    try:
        result = (payload.get("chart", {}).get("result") or [])[0]
        timestamps = result.get("timestamp") or []
        indicators = result.get("indicators") or {}
        closes = (indicators.get("quote") or [{}])[0].get("close") or []
        adjcloses = (indicators.get("adjclose") or [{}])[0].get("adjclose") or []
    except (AttributeError, IndexError) as exc:
        raise ValueError("Yahoo chart payload is missing result indicators") from exc

    ratios: dict[str, float] = {}
    for raw_timestamp, close, adjclose in zip(timestamps, closes, adjcloses):
        if raw_timestamp is None or close is None or adjclose is None:
            continue
        close_value = float(close)
        adjclose_value = float(adjclose)
        if close_value <= 0 or adjclose_value <= 0:
            continue
        local_date = datetime.fromtimestamp(
            int(raw_timestamp),
            tz=timezone.utc,
        ).astimezone(TAIPEI_TZ).date().isoformat()
        ratios[local_date] = adjclose_value / close_value

    if not ratios:
        raise ValueError("Yahoo chart payload contains no valid adjustment ratios")
    return ratios


def apply_adjustment_ratios(
    source_bars: list[Bar],
    ratios_by_date: dict[str, float],
    *,
    start: date,
    end: date,
) -> AdjustedOhlcvBuild:
    """
    用途與流程：將 Yahoo 調整比例套用到 source OHLC，保留 source volume，並統計日期窗外與缺少調整比例而略過的列。
    參數：source_bars 是既有 SignalForge Bar 清單；ratios_by_date 是 `YYYY-MM-DD -> ratio`；start/end 是輸出日期窗。
    回傳與錯誤：回傳 AdjustedOhlcvBuild；ratio 非正數時拋出 ValueError，日期解析錯誤會由 datetime 拋出。
    """
    adjusted: list[NormalizedBar] = []
    missing_adjustment_count = 0
    skipped_row_count = 0

    for bar in source_bars:
        bar_date = _parse_iso_date(bar.timestamp)
        if bar_date < start or bar_date > end:
            skipped_row_count += 1
            continue
        ratio = ratios_by_date.get(bar.timestamp)
        if ratio is None:
            missing_adjustment_count += 1
            skipped_row_count += 1
            continue
        if ratio <= 0:
            raise ValueError(f"adjustment ratio must be positive for {bar.timestamp}")
        adjusted.append(
            NormalizedBar(
                timestamp=bar.timestamp,
                open=bar.open * ratio,
                high=bar.high * ratio,
                low=bar.low * ratio,
                close=bar.close * ratio,
                volume=bar.volume,
            )
        )

    return AdjustedOhlcvBuild(
        bars=adjusted,
        source_row_count=len(source_bars),
        row_count=len(adjusted),
        missing_adjustment_count=missing_adjustment_count,
        skipped_row_count=skipped_row_count,
    )


def build_manifest(
    *,
    symbol: str,
    yahoo_symbol: str,
    source_csv: Path,
    output_csv: Path,
    start: date,
    end: date,
    build: AdjustedOhlcvBuild,
) -> dict[str, Any]:
    """
    用途與流程：建立 deterministic manifest，記錄調整價資料如何由 TWSE source CSV 與 Yahoo ratio 組成。
    參數：symbol/yahoo_symbol 是資料代號；source_csv/output_csv 是來源與輸出檔；start/end 是日期窗；build 是調整結果計數。
    回傳與錯誤：回傳可 JSON 序列化的 dict；此函式不做 I/O，也不主動讀檔。
    """
    return {
        "adjusted": True,
        "adjustment_method": ADJUSTMENT_METHOD,
        "adjustment_source": ADJUSTMENT_SOURCE,
        "csv_path": output_csv.as_posix(),
        "end": end.isoformat(),
        "market": "twse",
        "missing_adjustment_count": build.missing_adjustment_count,
        "notes": (
            "OHLC are source TWSE prices scaled by Yahoo adjclose/close ratio; "
            "volume is preserved from source CSV and is not adjusted."
        ),
        "output_csv": output_csv.as_posix(),
        "price_source_csv": source_csv.as_posix(),
        "row_count": build.row_count,
        "session": "regular",
        "skipped_row_count": build.skipped_row_count,
        "source_row_count": build.source_row_count,
        "start": start.isoformat(),
        "symbol": symbol,
        "timeframe": "1D",
        "timezone": "Asia/Taipei",
        "volume_source": "source CSV volume preserved",
        "yahoo_symbol": yahoo_symbol,
    }


def main(argv: list[str] | None = None) -> int:
    """
    用途與流程：命令列入口，解析參數後建立調整價 CSV 與 manifest，並把輸出路徑摘要印到 stdout。
    參數：argv 是可選參數清單；None 時使用系統命令列參數。
    回傳與錯誤：成功回傳 0；輸入錯誤、下載錯誤或資料驗證失敗時讓例外往外傳給 CLI。
    """
    args = build_parser().parse_args(argv)
    result = build_adjusted_ohlcv(
        symbol=args.symbol,
        yahoo_symbol=args.yahoo_symbol,
        source_csv=args.source_csv,
        start=args.start,
        end=args.end,
        output_csv=args.output_csv,
        manifest_json=args.manifest_json,
    )
    print(
        "built adjusted OHLCV "
        f"symbol={result.symbol} rows={result.row_count} "
        f"csv={result.output_csv} manifest={result.manifest_json}"
    )
    return 0


def _yahoo_chart_url(yahoo_symbol: str, start: date, end: date) -> str:
    """
    用途與流程：組出 Yahoo chart 日線 URL，將日期窗轉成 epoch seconds 並要求 adjusted close。
    參數：yahoo_symbol 是 Yahoo 代號；start/end 是查詢日期窗。
    回傳與錯誤：回傳 URL 字串；若 end 早於 start 不在此函式檢查，由上層負責。
    """
    period1 = int(datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).timestamp())
    period2 = int(
        datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        .timestamp()
    )
    query = urlencode(
        {
            "period1": period1,
            "period2": period2,
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        }
    )
    return f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}?{query}"


def _parse_iso_date(value: str) -> date:
    """
    用途與流程：解析 `YYYY-MM-DD` 日期字串，讓 CLI、CSV timestamp 與 manifest 日期共用同一格式。
    參數：value 是日期字串。
    回傳與錯誤：回傳 date；格式不符時由 datetime.strptime 拋出 ValueError。
    """
    return datetime.strptime(value, "%Y-%m-%d").date()


if __name__ == "__main__":
    raise SystemExit(main())
