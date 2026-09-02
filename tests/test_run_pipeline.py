import unittest
import os
import json
import shutil
import tempfile

from core.run_pipeline import execute_pipeline, MANIFEST_DIR

class TestRunPipeline(unittest.TestCase):
    def test_pipeline_execution_and_manifest_generation(self):
        # Run pipeline with skip_forecast=True
        manifest = execute_pipeline(skip_forecast=True)

        self.assertEqual(manifest["status"], "success")
        self.assertTrue(manifest["skip_forecast"])
        self.assertIn("ingest", manifest["stages"])
        self.assertIn("quality_scoring", manifest["stages"])
        self.assertIn("anomaly_detection", manifest["stages"])
        self.assertIn("fare_index", manifest["stages"])

        latest_path = os.path.join(MANIFEST_DIR, "latest_manifest.json")
        self.assertTrue(os.path.exists(latest_path))

        with open(latest_path, encoding="utf-8") as f:
            saved_manifest = json.load(f)

        self.assertEqual(saved_manifest["status"], "success")

if __name__ == "__main__":
    unittest.main()
