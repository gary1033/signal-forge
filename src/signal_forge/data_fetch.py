from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
import io
import json
import os
from pathlib import Path
from typing import Callable
from urllib.parse import urlencode
from urllib.request import urlopen

from signal_forge.market_data import Bar, MarketDataValidationError, validate_bars


@dataclass(frozen=True)
class FetchDataResult:
    market: str
    symbol: str
    start: str
    end: str
    row_count: int
    raw_csv: Path
    processed_csv: Path
    manifest_json: Path


@dataclass(frozen=True)
class NormalizedBar:
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float

    def to_bar(self) -> Bar:
        """
        用途與流程：將資料下載層的 NormalizedBar 轉成回測層共用的 Bar 物件。
        參數：self 表示目前物件實例
        回傳與錯誤：回傳 Bar；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
        """
        return Bar(self.timestamp, self.open, self.high, self.low, self.close, self.volume)


def fetch_market_data(
    *,
    market: str,
    symbol: str,
    start: str,
    end: str,
    output_root: str | Path = ".",
    stooq_api_key: str | None = None,
) -> FetchDataResult:
    """
    用途與流程：依市場代碼下載日線資料，驗證後寫出 raw CSV、processed CSV 與 manifest。
    參數：market（str）由呼叫端傳入，需符合函式 contract；symbol（str）由呼叫端傳入，需符合函式 contract；start（str）由呼叫端傳入，需符合函式 contract；end（str）由呼叫端傳入，需符合函式 contract；output_root（str | Path）由呼叫端傳入，需符合函式 contract；stooq_api_key（str | None）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 FetchDataResult；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    normalized_market = market.strip().lower()
    normalized_symbol = symbol.strip().upper()
    start_date = _parse_iso_date(start)
    end_date = _parse_iso_date(end)
    if end_date < start_date:
        raise ValueError("end date must be on or after start date")

    if normalized_market == "twse":
        raw_csv, bars, source = fetch_twse_daily_stock(normalized_symbol, start_date, end_date)
        timezone = "Asia/Taipei"
    elif normalized_market == "us":
        raw_csv, bars, source = fetch_stooq_daily_stock(
            normalized_symbol, start_date, end_date, api_key=stooq_api_key
        )
        timezone = "America/New_York"
    else:
        raise ValueError("market must be either 'twse' or 'us'")

    if not bars:
        raise MarketDataValidationError(
            f"no daily OHLCV rows returned for {normalized_market}:{normalized_symbol}"
        )
    _validate_normalized_bars(bars)

    output_root_path = Path(output_root)
    stem = f"{normalized_market.upper()}_{normalized_symbol}_1D"
    raw_path = output_root_path / "data" / "raw" / f"{stem}_raw.csv"
    processed_path = output_root_path / "data" / "processed" / f"{stem}.csv"
    manifest_path = output_root_path / "data" / "processed" / f"{stem}_manifest.json"

    _write_text(raw_path, raw_csv)
    _write_text(processed_path, format_signal_forge_csv(bars))
    _write_text(
        manifest_path,
        json.dumps(
            {
                "adjusted": False,
                "csv_path": processed_path.as_posix(),
                "data_source": source,
                "end": end_date.isoformat(),
                "market": normalized_market,
                "notes": "Daily OHLCV only; prices are not dividend/split adjusted.",
                "raw_csv_path": raw_path.as_posix(),
                "row_count": len(bars),
                "session": "regular",
                "start": start_date.isoformat(),
                "symbol": normalized_symbol,
                "timeframe": "1D",
                "timezone": timezone,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )

    return FetchDataResult(
        market=normalized_market,
        symbol=normalized_symbol,
        start=start_date.isoformat(),
        end=end_date.isoformat(),
        row_count=len(bars),
        raw_csv=raw_path,
        processed_csv=processed_path,
        manifest_json=manifest_path,
    )


def fetch_twse_daily_stock(
    symbol: str,
    start: date,
    end: date,
    *,
    fetch_text: Callable[[str], str] | None = None,
) -> tuple[str, list[NormalizedBar], str]:
    """
    用途與流程：從 TWSE 月資料端點抓取指定區間日線，轉成 SignalForge 正規化 K 線。
    參數：symbol（str）由呼叫端傳入，需符合函式 contract；start（date）由呼叫端傳入，需符合函式 contract；end（date）由呼叫端傳入，需符合函式 contract；fetch_text（Callable[[str], str] | None）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 tuple[str, list[NormalizedBar], str]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    fetch = fetch_text or _fetch_url_text
    raw_rows: list[dict[str, str]] = []
    bars: list[NormalizedBar] = []

    for month_start in _iter_month_starts(start, end):
        payload = json.loads(fetch(_twse_stock_day_url(symbol, month_start)))
        fields = payload.get("fields") or []
        for values in payload.get("data") or []:
            row = dict(zip(fields, values))
            raw_rows.append(row)
            bar = parse_twse_row(row)
            if bar is None:
                continue
            bar_date = _parse_iso_date(bar.timestamp)
            if start <= bar_date <= end:
                bars.append(bar)

    return _format_dict_csv(raw_rows), _sort_unique_bars(bars), "TWSE STOCK_DAY"


def fetch_stooq_daily_stock(
    symbol: str,
    start: date,
    end: date,
    *,
    api_key: str | None = None,
    fetch_text: Callable[[str], str] | None = None,
) -> tuple[str, list[NormalizedBar], str]:
    """
    用途與流程：從 Stooq daily CSV 端點抓取美股日線，處理 API key 要求並轉成正規化 K 線。
    參數：symbol（str）由呼叫端傳入，需符合函式 contract；start（date）由呼叫端傳入，需符合函式 contract；end（date）由呼叫端傳入，需符合函式 contract；api_key（str | None）由呼叫端傳入，需符合函式 contract；fetch_text（Callable[[str], str] | None）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 tuple[str, list[NormalizedBar], str]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    key = api_key or os.environ.get("STOOQ_API_KEY")
    fetch = fetch_text or _fetch_url_text
    raw_csv = fetch(_stooq_daily_url(symbol, start, end, api_key=key))
    if "Get your apikey" in raw_csv:
        raise MarketDataValidationError(
            "Stooq CSV download currently requires a free apikey; pass "
            "--stooq-api-key or set STOOQ_API_KEY."
        )
    return raw_csv, _sort_unique_bars(parse_stooq_csv(raw_csv)), "Stooq daily CSV"


def parse_twse_row(row: dict[str, str]) -> NormalizedBar | None:
    """
    用途與流程：解析單筆 TWSE 原始列，將民國日期與含逗號數字轉成 NormalizedBar。
    參數：row（dict[str, str]）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 NormalizedBar | None；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    values = (
        row.get("日期", ""),
        row.get("開盤價", ""),
        row.get("最高價", ""),
        row.get("最低價", ""),
        row.get("收盤價", ""),
        row.get("成交股數", ""),
    )
    if any(_is_empty_market_value(value) for value in values):
        return None
    return NormalizedBar(
        timestamp=_roc_date_to_iso(row["日期"]),
        open=_parse_market_float(row["開盤價"]),
        high=_parse_market_float(row["最高價"]),
        low=_parse_market_float(row["最低價"]),
        close=_parse_market_float(row["收盤價"]),
        volume=_parse_market_float(row["成交股數"]),
    )


def parse_stooq_csv(raw_csv: str) -> list[NormalizedBar]:
    """
    用途與流程：解析 Stooq CSV 文字，檢查必要欄位並轉成 NormalizedBar 清單。
    參數：raw_csv（str）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 list[NormalizedBar]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    reader = csv.DictReader(io.StringIO(raw_csv))
    required = {"Date", "Open", "High", "Low", "Close", "Volume"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise MarketDataValidationError("Stooq CSV missing Date/Open/High/Low/Close/Volume")

    bars: list[NormalizedBar] = []
    for row in reader:
        if any(_is_empty_market_value(row.get(field, "")) for field in required):
            continue
        bars.append(
            NormalizedBar(
                timestamp=_parse_iso_date(row["Date"]).isoformat(),
                open=_parse_market_float(row["Open"]),
                high=_parse_market_float(row["High"]),
                low=_parse_market_float(row["Low"]),
                close=_parse_market_float(row["Close"]),
                volume=_parse_market_float(row["Volume"]),
            )
        )
    return bars


def format_signal_forge_csv(bars: list[NormalizedBar]) -> str:
    """
    用途與流程：把正規化 K 線輸出為 SignalForge 固定 OHLCV CSV schema。
    參數：bars（list[NormalizedBar]）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("timestamp", "open", "high", "low", "close", "volume"))
    for bar in bars:
        writer.writerow(
            (
                bar.timestamp,
                _format_number(bar.open),
                _format_number(bar.high),
                _format_number(bar.low),
                _format_number(bar.close),
                _format_number(bar.volume),
            )
        )
    return output.getvalue()


def _twse_stock_day_url(symbol: str, month_start: date) -> str:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：symbol（str）由呼叫端傳入，需符合函式 contract；month_start（date）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    return (
        "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?"
        + urlencode(
            {
                "date": month_start.strftime("%Y%m%d"),
                "stockNo": symbol,
                "response": "json",
            }
        )
    )


def _stooq_daily_url(
    symbol: str, start: date, end: date, *, api_key: str | None = None
) -> str:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：symbol（str）由呼叫端傳入，需符合函式 contract；start（date）由呼叫端傳入，需符合函式 contract；end（date）由呼叫端傳入，需符合函式 contract；api_key（str | None）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    query = {
        "s": f"{symbol.lower()}.us",
        "i": "d",
        "d1": start.strftime("%Y%m%d"),
        "d2": end.strftime("%Y%m%d"),
    }
    if api_key:
        query["apikey"] = api_key
    return "https://stooq.com/q/d/l/?" + urlencode(query)


def _fetch_url_text(url: str) -> str:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：url（str）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    with urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8-sig")


def _iter_month_starts(start: date, end: date) -> list[date]:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：start（date）由呼叫端傳入，需符合函式 contract；end（date）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 list[date]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    current = date(start.year, start.month, 1)
    last = date(end.year, end.month, 1)
    months: list[date] = []
    while current <= last:
        months.append(current)
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return months


def _roc_date_to_iso(value: str) -> str:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：value（str）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    parts = value.strip().split("/")
    if len(parts) != 3:
        raise MarketDataValidationError(f"invalid TWSE date: {value}")
    return date(int(parts[0]) + 1911, int(parts[1]), int(parts[2])).isoformat()


def _parse_iso_date(value: str) -> date:
    """
    用途與流程：解析外部輸入文字或 CSV 欄位，轉成程式內部可驗證的型別與格式。
    參數：value（str）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 date；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    return datetime.strptime(value, "%Y-%m-%d").date()


def _parse_market_float(value: str) -> float:
    """
    用途與流程：解析外部輸入文字或 CSV 欄位，轉成程式內部可驗證的型別與格式。
    參數：value（str）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 float；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    return float(value.strip().replace(",", ""))


def _is_empty_market_value(value: str | None) -> bool:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：value（str | None）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 bool；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    if value is None:
        return True
    return value.strip() in {"", "--", "N/A", "null"}


def _sort_unique_bars(bars: list[NormalizedBar]) -> list[NormalizedBar]:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：bars（list[NormalizedBar]）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 list[NormalizedBar]；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    by_timestamp = {bar.timestamp: bar for bar in bars}
    return [by_timestamp[timestamp] for timestamp in sorted(by_timestamp)]


def _validate_normalized_bars(bars: list[NormalizedBar]) -> None:
    """
    用途與流程：執行內部 contract 驗證，將格式錯誤、語意不一致或安全邊界破壞轉成明確例外。
    參數：bars（list[NormalizedBar]）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
    """
    result = validate_bars([bar.to_bar() for bar in bars])
    if not result.is_valid:
        raise MarketDataValidationError("; ".join(result.errors))


def _format_number(value: float) -> str:
    """
    用途與流程：將內部資料格式化為 artifact 或 CLI 需要的 deterministic 文字表示。
    參數：value（float）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    if value.is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _format_dict_csv(rows: list[dict[str, str]]) -> str:
    """
    用途與流程：將內部資料格式化為 artifact 或 CLI 需要的 deterministic 文字表示。
    參數：rows（list[dict[str, str]]）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 str；若輸入不合法，會依原實作拋出 ValueError 或專用驗證例外。
    """
    if not rows:
        return ""
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _write_text(path: Path, text: str) -> None:
    """
    用途與流程：提供模組內部輔助流程，將主要函式中的重複規則集中到單一位置。
    參數：path（Path）由呼叫端傳入，需符合函式 contract；text（str）由呼叫端傳入，需符合函式 contract
    回傳與錯誤：回傳 None；若輸入不合法或 assertion 失敗，會依原實作拋出例外。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
