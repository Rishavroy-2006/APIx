import unittest
import os
import shutil
import tempfile
import numpy as np
import pandas as pd

from core.anomaly_detection import (
    detect_anomalies,
    _compute_mad,
    run,
    MIN_ML_SAMPLES,
)

class TestAnomalyDetection(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

        # Build mock dataset with 60 normal rows and 2 extreme outlier rows
        np.random.seed(42)
        n = 60
        data = {
            "origin": ["DEL"] * n,
            "destination": ["BOM"] * n,
            "route": ["DEL-BOM"] * n,
            "carrier_code": ["6E"] * n,
            "carrier_name": ["IndiGo"] * n,
            "flight_num": [f"6E-{100+i%5}" for i in range(n)],
            "travel_date": ["2026-09-10"] * n,
            "advance_purchase_days": [7] * n,
            "fare_class": ["economy"] * n,
            "base_fare": [4000.0] * n,
            "taxes_and_fees": [1000.0] * n,
            "total_fare": [5000.0 + float(np.random.normal(0, 50)) for _ in range(n)],
            "fare_split_estimated": [False] * n,
            "departure_time": ["08:00"] * n,
            "status": ["ok"] * n,
            "scraped_at": ["2026-09-02T10:00:00+05:30"] * n,
            "capture_run": ["20260902_1000"] * n,
            "source_scraper": ["indigo"] * n,
            "source_file": ["indigo.csv"] * n,
            "data_source_method": ["regex_parser"] * n,
            "confidence_score": [1.0] * n,
            "quality_flags": [[] for _ in range(n)],
        }

        # Inject extreme outlier at index 0
        data["total_fare"][0] = 50000.0

        self.df = pd.DataFrame(data)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_compute_mad(self):
        s = pd.Series([10.0, 12.0, 11.0, 13.0, 100.0])
        mad = _compute_mad(s)
        self.assertAlmostEqual(mad, 1.0) # Median = 12. Absolute diffs: [2, 0, 1, 1, 88]. Sorted diffs: [0, 1, 1, 2, 88]. Median diff = 1.0

    def test_statistical_pass_flagging(self):
        processed = detect_anomalies(self.df, min_ml_samples=100) # Disable ML pass via min samples requirement

        # Outlier at index 0 should be flagged
        flags_0 = processed.at[0, "quality_flags"]
        self.assertIn("price_anomaly_statistical", flags_0)
        self.assertEqual(processed.at[0, "confidence_score"], 0.75) # 1.0 - 0.25

        # Normal row (index 1) should NOT be flagged as statistical anomaly
        flags_1 = processed.at[1, "quality_flags"]
        self.assertNotIn("price_anomaly_statistical", flags_1)
        self.assertEqual(processed.at[1, "confidence_score"], 1.0)

    def test_ml_pass_skipped_when_samples_insufficient(self):
        # min_ml_samples set to 100, but dataframe only has 60 rows
        processed = detect_anomalies(self.df, min_ml_samples=100)

        # No row should have price_anomaly_ml
        ml_flags = [f for flags in processed["quality_flags"] for f in flags if f == "price_anomaly_ml"]
        self.assertEqual(len(ml_flags), 0)

    def test_ml_pass_runs_when_samples_sufficient(self):
        # min_ml_samples set to 50, dataframe has 60 rows
        processed = detect_anomalies(self.df, min_ml_samples=50)

        # Extreme outlier at index 0 should be caught by ML pass or statistical pass
        self.assertTrue("anomaly_score" in processed.columns)
        self.assertTrue("price_anomaly_ml" in processed.at[0, "quality_flags"] or "price_anomaly_statistical" in processed.at[0, "quality_flags"])

    def test_run_saves_files(self):
        input_p = os.path.join(self.tmp_dir, "input.parquet")
        output_p = os.path.join(self.tmp_dir, "output.parquet")
        anomalies_p = os.path.join(self.tmp_dir, "anomalies.parquet")

        self.df.to_parquet(input_p, index=False)

        res = run(input_p, output_p, anomalies_p)

        self.assertTrue(os.path.exists(output_p))
        self.assertTrue(os.path.exists(anomalies_p))
        self.assertEqual(len(res), len(self.df))

        flagged_df = pd.read_parquet(anomalies_p)
        self.assertGreater(len(flagged_df), 0)

if __name__ == "__main__":
    unittest.main()
