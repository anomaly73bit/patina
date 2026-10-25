"""Regression tests for Patina scanner and market calibration (stdlib only)."""
import datetime as dt
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scanner"))
import scan
import market


class ScannerTests(unittest.TestCase):
    def test_missing_timestamp_is_not_assumed_fresh(self):
        old = {"url": "https://example.org/1", "via": "source"}
        t = dt.datetime(2026, 10, 25, tzinfo=dt.timezone.utc)
        self.assertIsNone(scan.parse(old.get("seen")))
        self.assertLess(dt.datetime.min.replace(tzinfo=dt.timezone.utc), t - scan.MAX_STALE)

    def test_closed_auction_is_filtered(self):
        t = dt.datetime(2026, 10, 25, tzinfo=dt.timezone.utc)
        self.assertFalse(scan.still_open({"endDate": "2026-10-24T00:00:00Z"}, t))
        self.assertFalse(scan.still_open({"sold": True}, t))


class MarketTests(unittest.TestCase):
    def test_extreme_and_auction_prices_do_not_shift_estimate(self):
        model = {"id": "watch", "lo": 1000, "hi": 2000, "t": 0}
        items = [
            {"m": "watch", "total": p, "title": "Watch", "auction": False}
            for p in [1200, 1300, 1400, 1500, 1600]
        ] + [
            {"m": "watch", "total": 100000, "title": "Watch", "auction": False},
            {"m": "watch", "total": 50, "title": "Watch", "auction": True},
        ]
        with patch.object(market, "load", return_value={}), patch.object(market, "save"):
            adjusted = market.calibrate([model], items, today=dt.date(2026, 10, 25))
        self.assertEqual(adjusted[0]["p25"], 1250)
        self.assertLess(adjusted[0]["hi"], 2100)


if __name__ == "__main__":
    unittest.main()
