import unittest
from fastapi.testclient import TestClient

from api.main import app

class TestAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_get_root(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "operational")
        self.assertIn("endpoints", data)

    def test_get_latest_index(self):
        response = self.client.get("/index/latest")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("composite_fare_index", data)
        self.assertIn("latest_date", data)

    def test_get_index_history(self):
        response = self.client.get("/index/history?days=5")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertLessEqual(data["count"], 5)
        self.assertTrue(isinstance(data["records"], list))

    def test_get_index_history_with_route_filter(self):
        response = self.client.get("/index/history?route=DEL-BOM&days=5")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["route_filter"], "DEL-BOM")

    def test_get_forecast(self):
        response = self.client.get("/forecast")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn(data["status"], ["success", "insufficient_history"])

    def test_get_quality_flags(self):
        response = self.client.get("/quality/flags?limit=10")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(isinstance(data["records"], list))

    def test_get_selectors_health(self):
        response = self.client.get("/selectors/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("sites", data)
        self.assertIn("recent_healing_events", data)

if __name__ == "__main__":
    unittest.main()
