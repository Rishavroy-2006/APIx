import unittest
import os
import json
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
import pandas as pd

from core.quality_scoring import (
    compute_quality_scores,
    _build_cross_source_keys,
    _build_stale_site_set,
    STALE_DAYS,
    IST,
)

class TestQualityScoring(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.patch_sdir = unittest.mock.patch("core.quality_scoring.SELECTORS_DIR", self.tmp_dir)
        self.patch_sdir.start()

        # Create selector files in temp dir
        now = datetime.now(IST)
        recent_ts = now.isoformat()
        old_ts = (now - timedelta(days=STALE_DAYS + 5)).isoformat()

        # Fresh site
        with open(os.path.join(self.tmp_dir, "indigo.json"), "w") as f:
            json.dump({"selectors": {"total_fare": {"last_verified_at": recent_ts}}}, f)

        # Stale site
        with open(os.path.join(self.tmp_dir, "spicejet.json"), "w") as f:
            json.dump({"selectors": {"total_fare": {"last_verified_at": old_ts}}}, f)

    def tearDown(self):
        self.patch_sdir.stop()
        shutil.rmtree(self.tmp_dir)

    def test_default_perfect_score(self):
        df = pd.DataFrame([{
            "origin": "DEL", "destination": "BOM", "carrier_code": "6E", "carrier_name": "IndiGo",
            "flight_num": "6E-101", "travel_date": "2026-09-10", "advance_purchase_days": 7,
            "fare_class": "economy", "base_fare": 4000.0, "taxes_and_fees": 1000.0, "total_fare": 5000.0,
            "fare_split_estimated": False, "departure_time": "08:00", "status": "ok",
            "scraped_at": "2026-09-02T10:00:00+05:30", "capture_run": "20260902_1000",
            "source_scraper": "indigo", "source_file": "indigo.csv", "data_source_method": "regex_parser"
        }])

        scored = compute_quality_scores(df)
        self.assertEqual(scored["confidence_score"].iloc[0], 1.0)
        self.assertEqual(scored["quality_flags"].iloc[0], [])

    def test_llm_sourced_flag(self):
        df = pd.DataFrame([{
            "origin": "DEL", "destination": "BOM", "carrier_code": "6E", "carrier_name": "IndiGo",
            "flight_num": "6E-101", "travel_date": "2026-09-10", "advance_purchase_days": 7,
            "fare_class": "economy", "base_fare": 4000.0, "taxes_and_fees": 1000.0, "total_fare": 5000.0,
            "fare_split_estimated": False, "departure_time": "08:00", "status": "ok",
            "scraped_at": "2026-09-02T10:00:00+05:30", "capture_run": "20260902_1000",
            "source_scraper": "indigo", "source_file": "indigo.csv", "data_source_method": "llm_fallback"
        }])

        scored = compute_quality_scores(df)
        self.assertEqual(scored["confidence_score"].iloc[0], 0.70)
        self.assertIn("llm_sourced", scored["quality_flags"].iloc[0])

    def test_fare_estimated_flag(self):
        df = pd.DataFrame([{
            "origin": "DEL", "destination": "BOM", "carrier_code": "6E", "carrier_name": "IndiGo",
            "flight_num": "6E-101", "travel_date": "2026-09-10", "advance_purchase_days": 7,
            "fare_class": "economy", "base_fare": 4000.0, "taxes_and_fees": 1000.0, "total_fare": 5000.0,
            "fare_split_estimated": True, "departure_time": "08:00", "status": "ok",
            "scraped_at": "2026-09-02T10:00:00+05:30", "capture_run": "20260902_1000",
            "source_scraper": "indigo", "source_file": "indigo.csv", "data_source_method": "regex_parser"
        }])

        scored = compute_quality_scores(df)
        self.assertEqual(scored["confidence_score"].iloc[0], 0.85)
        self.assertIn("fare_estimated", scored["quality_flags"].iloc[0])

    def test_missing_price_flag(self):
        df = pd.DataFrame([{
            "origin": "DEL", "destination": "BOM", "carrier_code": "6E", "carrier_name": "IndiGo",
            "flight_num": "6E-101", "travel_date": "2026-09-10", "advance_purchase_days": 7,
            "fare_class": "economy", "base_fare": None, "taxes_and_fees": None, "total_fare": None,
            "fare_split_estimated": False, "departure_time": "08:00", "status": "ok",
            "scraped_at": "2026-09-02T10:00:00+05:30", "capture_run": "20260902_1000",
            "source_scraper": "indigo", "source_file": "indigo.csv", "data_source_method": "regex_parser"
        }])

        scored = compute_quality_scores(df)
        self.assertEqual(scored["confidence_score"].iloc[0], 0.50)
        self.assertIn("missing_price", scored["quality_flags"].iloc[0])

    def test_stale_selector_flag(self):
        df = pd.DataFrame([{
            "origin": "DEL", "destination": "BOM", "carrier_code": "SG", "carrier_name": "SpiceJet",
            "flight_num": "SG-202", "travel_date": "2026-09-10", "advance_purchase_days": 7,
            "fare_class": "economy", "base_fare": 4000.0, "taxes_and_fees": 1000.0, "total_fare": 5000.0,
            "fare_split_estimated": False, "departure_time": "08:00", "status": "ok",
            "scraped_at": "2026-09-02T10:00:00+05:30", "capture_run": "20260902_1000",
            "source_scraper": "spicejet", "source_file": "spicejet.csv", "data_source_method": "regex_parser"
        }])

        scored = compute_quality_scores(df)
        self.assertEqual(scored["confidence_score"].iloc[0], 0.80)
        self.assertIn("stale_selector", scored["quality_flags"].iloc[0])

    def test_cross_source_confirmed_boost(self):
        # Two scrapers (indigo and makemytrip) reporting same flight & date with price within 2%
        df = pd.DataFrame([
            {
                "origin": "DEL", "destination": "BOM", "carrier_code": "6E", "carrier_name": "IndiGo",
                "flight_num": "6E-101", "travel_date": "2026-09-10", "advance_purchase_days": 7,
                "fare_class": "economy", "base_fare": 4000.0, "taxes_and_fees": 1000.0, "total_fare": 5000.0,
                "fare_split_estimated": True, "departure_time": "08:00", "status": "ok",
                "scraped_at": "2026-09-02T10:00:00+05:30", "capture_run": "20260902_1000",
                "source_scraper": "indigo", "source_file": "indigo.csv", "data_source_method": "regex_parser"
            },
            {
                "origin": "DEL", "destination": "BOM", "carrier_code": "6E", "carrier_name": "IndiGo",
                "flight_num": "6E-101", "travel_date": "2026-09-10", "advance_purchase_days": 7,
                "fare_class": "economy", "base_fare": 4000.0, "taxes_and_fees": 1050.0, "total_fare": 5050.0, # 1% difference
                "fare_split_estimated": False, "departure_time": "08:00", "status": "ok",
                "scraped_at": "2026-09-02T11:00:00+05:30", "capture_run": "20260902_1100",
                "source_scraper": "makemytrip", "source_file": "mmt.csv", "data_source_method": "regex_parser"
            }
        ])

        scored = compute_quality_scores(df)
        
        # Row 0: 1.0 - 0.15 (estimated) + 0.10 (cross source) = 0.95
        self.assertEqual(scored["confidence_score"].iloc[0], 0.95)
        self.assertIn("cross_source_confirmed", scored["quality_flags"].iloc[0])

        # Row 1: 1.0 - 0.20 (stale selector for makemytrip since missing in temp dir) + 0.10 = 0.90
        self.assertEqual(scored["confidence_score"].iloc[1], 0.90)
        self.assertIn("cross_source_confirmed", scored["quality_flags"].iloc[1])

if __name__ == "__main__":
    unittest.main()
