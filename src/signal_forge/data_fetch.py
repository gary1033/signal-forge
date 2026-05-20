from pathlib import Path

from signal_forge.data import fetch as _fetch
from signal_forge.data.fetch import (
    FetchDataResult,
    NormalizedBar,
    fetch_stooq_daily_stock,
    fetch_twse_daily_stock,
    format_signal_forge_csv,
    parse_stooq_csv,
    parse_twse_row,
)

_fetch_url_text = _fetch._fetch_url_text


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
    用途與流程：保留舊 `signal_forge.data_fetch.fetch_market_data` 入口，並將實作委派給 data.fetch。
    參數：market、symbol、start、end、output_root、stooq_api_key 與新模組相同；測試可 patch 本模組 `_fetch_url_text`。
    回傳與錯誤：回傳 FetchDataResult；底層下載、日期或資料驗證錯誤會照原本例外傳出。
    """
    original_fetch = _fetch._fetch_url_text
    _fetch._fetch_url_text = _fetch_url_text
    try:
        return _fetch.fetch_market_data(
            market=market,
            symbol=symbol,
            start=start,
            end=end,
            output_root=output_root,
            stooq_api_key=stooq_api_key,
        )
    finally:
        _fetch._fetch_url_text = original_fetch

__all__ = [
    "FetchDataResult",
    "NormalizedBar",
    "_fetch_url_text",
    "fetch_market_data",
    "fetch_stooq_daily_stock",
    "fetch_twse_daily_stock",
    "format_signal_forge_csv",
    "parse_stooq_csv",
    "parse_twse_row",
]
