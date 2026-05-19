from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from signal_forge import Bar, MarketDataValidationError, load_bars_from_csv, validate_bars


class MarketDataTests(unittest.TestCase):
    def test_validate_bars_rejects_duplicate_and_unsorted_timestamps(self) -> None:
        bars = [
            Bar("2026-01-02", 10, 11, 9, 10, 100),
            Bar("2026-01-02", 10, 11, 9, 10, 100),
            Bar("2026-01-01", 10, 11, 9, 10, 100),
        ]
        result = validate_bars(bars)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("duplicates timestamp" in error for error in result.errors))
        self.assertTrue(any("is not after" in error for error in result.errors))

    def test_validate_bars_rejects_invalid_ohlcv(self) -> None:
        bars = [Bar("2026-01-01", 10, 9, 11, 10, -1)]
        result = validate_bars(bars)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("high is below" in error for error in result.errors))
        self.assertTrue(any("low is above" in error for error in result.errors))
        self.assertTrue(any("volume is negative" in error for error in result.errors))

    def test_load_bars_from_csv_requires_ohlcv_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.csv"
            path.write_text("timestamp,open,high,low,close\n2026-01-01,1,1,1,1\n")
            with self.assertRaises(MarketDataValidationError):
                load_bars_from_csv(path)


if __name__ == "__main__":
    unittest.main()
