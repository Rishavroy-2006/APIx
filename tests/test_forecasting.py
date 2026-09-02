import unittest
import os
import shutil
import tempfile
import pandas as pd

from core.forecasting import (
    generate_forecasts,
    run,
    PROPHET_AVAILABLE,
    MIN_HISTORICAL_DAYS,
)

class TestForecasting(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_insufficient_history_guard(self):
        # Create dataset with only 3 days of index data (< 14 days)
        df_short = pd.DataFrame({
            "date": ["2026-09-01", "2026-09-02", "2026-09-03"],
            "composite_fare_index": [100.0, 105.0, 98.0],
            "data_completeness": [1.0, 1.0, 0.96],
        })

        res = generate_forecasts(df_short, min_historical_days=14)

        # Should return empty forecast dataframe due to 14-day guard
        self.assertEqual(len(res), 0)
        self.assertIn("ds", res.columns)
        self.assertIn("forecast_confidence", res.columns)

    @unittest.skipUnless(PROPHET_AVAILABLE, "Prophet not installed")
    def test_sufficient_history_prophet_forecast(self):
        # Create synthetic dataset with 15 days of index data (>= 14 days)
        dates = pd.date_range("2026-08-15", periods=15, freq="D").strftime("%Y-%m-%d")
        df_long = pd.DataFrame({
            "date": dates,
            "composite_fare_index": [100.0 + (i % 7) * 2.0 for i in range(15)],
            "index_DEL-BOM": [100.0 + (i % 5) * 1.5 for i in range(15)],
            "data_completeness": [0.95] * 15,
        })

        res = generate_forecasts(df_long, forecast_horizon_days=3, min_historical_days=14)

        # 15 historical days + 3 forecast days = 18 days per target
        # 2 targets (composite_fare_index and index_DEL-BOM) -> 36 total rows
        self.assertEqual(len(res), 36)

        # Check columns
        expected_cols = {"ds", "target", "yhat", "yhat_lower", "yhat_upper", "forecast_confidence", "is_forecast"}
        self.assertTrue(expected_cols.issubset(set(res.columns)))

        # Check is_forecast flag (last 3 rows per target should be True)
        forecast_rows = res[res["is_forecast"] == True]
        self.assertEqual(len(forecast_rows), 6) # 3 days * 2 targets

        # Confidence scores should be between 0.0 and 1.0
        self.assertTrue((res["forecast_confidence"] >= 0.0).all())
        self.assertTrue((res["forecast_confidence"] <= 1.0).all())

    def test_run_command_file_persistence(self):
        input_p = os.path.join(self.tmp_dir, "fare_index_daily.parquet")
        output_p = os.path.join(self.tmp_dir, "forecast.parquet")

        df = pd.DataFrame({
            "date": ["2026-09-01", "2026-09-02"],
            "composite_fare_index": [100.0, 105.0],
            "data_completeness": [1.0, 1.0],
        })
        df.to_parquet(input_p, index=False)

        res = run(input_p, output_p)
        self.assertTrue(os.path.exists(output_p))
        self.assertEqual(len(res), 0)

if __name__ == "__main__":
    unittest.main()
