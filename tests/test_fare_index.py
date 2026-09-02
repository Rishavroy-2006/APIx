import unittest
import os
import shutil
import tempfile
import pandas as pd

from core.fare_index import (
    build_fare_index,
    run,
    KNOWN_ROUTES,
    KNOWN_HORIZONS,
    TOTAL_EXPECTED_COMBOS,
)

class TestFareIndex(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

        # Build mock dataset over 2 scraped dates
        records = []
        dates = ["2026-09-01", "2026-09-02"]
        routes = ["DEL-BOM", "DEL-BLR"]

        for d in dates:
            for r in routes:
                orig, dest = r.split("-")
                for h in [1, 7, 15]:
                    base_price = 5000.0 if d == "2026-09-01" else 6000.0
                    records.append({
                        "origin": orig,
                        "destination": dest,
                        "route": r,
                        "carrier_code": "6E",
                        "carrier_name": "IndiGo",
                        "flight_num": "6E-101",
                        "travel_date": "2026-09-10",
                        "advance_purchase_days": h,
                        "fare_class": "economy",
                        "base_fare": base_price * 0.8,
                        "taxes_and_fees": base_price * 0.2,
                        "total_fare": base_price,
                        "fare_split_estimated": False,
                        "departure_time": "08:00",
                        "status": "ok",
                        "scraped_at": f"{d}T10:00:00+05:30",
                        "capture_run": f"{d}_1000",
                        "source_scraper": "indigo",
                        "source_file": "indigo.csv",
                        "data_source_method": "regex_parser",
                        "confidence_score": 1.0,
                        "quality_flags": [],
                    })

        # Add 1 excluded row (status not ok)
        records.append({
            "origin": "DEL",
            "destination": "BOM",
            "route": "DEL-BOM",
            "carrier_code": "6E",
            "carrier_name": "IndiGo",
            "flight_num": "6E-102",
            "travel_date": "2026-09-10",
            "advance_purchase_days": 1,
            "fare_class": "economy",
            "base_fare": None,
            "taxes_and_fees": None,
            "total_fare": None,
            "fare_split_estimated": False,
            "departure_time": "08:00",
            "status": "no_flights",
            "scraped_at": "2026-09-01T10:00:00+05:30",
            "capture_run": "20260901_1000",
            "source_scraper": "indigo",
            "source_file": "indigo.csv",
            "data_source_method": "regex_parser",
            "confidence_score": 0.0,
            "quality_flags": [],
        })

        # Add 1 statistical anomaly row
        records.append({
            "origin": "DEL",
            "destination": "BOM",
            "route": "DEL-BOM",
            "carrier_code": "6E",
            "carrier_name": "IndiGo",
            "flight_num": "6E-103",
            "travel_date": "2026-09-10",
            "advance_purchase_days": 1,
            "fare_class": "economy",
            "base_fare": 40000.0,
            "taxes_and_fees": 10000.0,
            "total_fare": 50000.0,
            "fare_split_estimated": False,
            "departure_time": "08:00",
            "status": "ok",
            "scraped_at": "2026-09-01T10:00:00+05:30",
            "capture_run": "20260901_1000",
            "source_scraper": "indigo",
            "source_file": "indigo.csv",
            "data_source_method": "regex_parser",
            "confidence_score": 0.75,
            "quality_flags": ["price_anomaly_statistical"],
        })

        self.df = pd.DataFrame(records)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_build_fare_index(self):
        index_df, excluded_df = build_fare_index(self.df)

        # Check excluded count
        self.assertEqual(len(excluded_df), 2)
        self.assertTrue("exclusion_reason" in excluded_df.columns)

        # Check dates present
        self.assertEqual(list(index_df["date"]), ["2026-09-01", "2026-09-02"])

        # Check composite index base 100.0 on Day 0
        self.assertEqual(index_df.loc[0, "composite_fare_index"], 100.0)
        self.assertEqual(index_df.loc[0, "composite_daily_fare"], 5000.0)

        # Day 1: base fare increased from 5000 to 6000 (+20%) -> index should be 120.0
        self.assertEqual(index_df.loc[1, "composite_fare_index"], 120.0)
        self.assertEqual(index_df.loc[1, "composite_daily_fare"], 6000.0)

        # Completeness: 2 routes * 3 horizons = 6 combinations present out of 30 expected -> 6 / 30 = 0.20
        self.assertAlmostEqual(index_df.loc[0, "data_completeness"], 0.20)

    def test_traffic_weighted_index(self):
        weights = {"DEL-BOM": 0.8, "DEL-BLR": 0.2}
        index_df, _ = build_fare_index(self.df, route_weights=weights)
        self.assertEqual(index_df.loc[0, "composite_fare_index"], 100.0)

    def test_run_saves_output_files(self):
        input_p = os.path.join(self.tmp_dir, "quality_flagged.parquet")
        output_idx = os.path.join(self.tmp_dir, "fare_index_daily.parquet")
        excluded_p = os.path.join(self.tmp_dir, "excluded_fare_audit.parquet")

        self.df.to_parquet(input_p, index=False)

        res = run(input_p, output_idx, excluded_p)

        self.assertTrue(os.path.exists(output_idx))
        self.assertTrue(os.path.exists(excluded_p))
        self.assertEqual(len(res), 2)

if __name__ == "__main__":
    unittest.main()
