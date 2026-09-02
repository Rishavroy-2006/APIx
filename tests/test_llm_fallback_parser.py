import unittest
from unittest.mock import MagicMock, patch
import os

from core.llm_fallback_parser import llm_extract_flights, reset_call_counter, clean_and_trim_html
from core.fare_schema import FareQuote


class TestLLMFallbackParser(unittest.TestCase):

    def setUp(self):
        reset_call_counter()

    def test_well_formed_html(self):
        html_content = """
        <html>
            <body>
                <script>var x = 1;</script>
                <div class="flight-card">
                    <span>6E 2034</span>
                    <span>08:55</span>
                    <span>₹6,733</span>
                </div>
            </body>
        </html>
        """
        mock_client = MagicMock()
        mock_client.extract_json.return_value = {
            "quotes": [
                {
                    "flight_num": "6E 2034",
                    "carrier_code": "6E",
                    "carrier_name": "IndiGo",
                    "departure_time": "08:55",
                    "total_fare": 6733.0,
                    "fare_class": "economy"
                }
            ]
        }

        quotes = llm_extract_flights(
            html_or_text=html_content,
            origin="DEL",
            destination="BOM",
            travel_date="2026-09-10",
            advance_days=7,
            source_scraper="indigo",
            llm_client=mock_client
        )

        self.assertEqual(len(quotes), 1)
        q = quotes[0]
        self.assertIsInstance(q, FareQuote)
        self.assertEqual(q.origin, "DEL")
        self.assertEqual(q.destination, "BOM")
        self.assertEqual(q.flight_num, "6E 2034")
        self.assertEqual(q.total_fare, 6733.0)
        self.assertEqual(q.status, "ok")
        self.assertEqual(q.data_source_method, "llm_fallback")
        self.assertTrue(q.raw_html_sample_path.endswith(".html"))

    def test_no_fares_html(self):
        html_content = "<html><body><p>No flights available today.</p></body></html>"
        mock_client = MagicMock()
        mock_client.extract_json.return_value = {"quotes": []}

        quotes = llm_extract_flights(
            html_or_text=html_content,
            origin="DEL",
            destination="CCU",
            travel_date="2026-09-15",
            advance_days=15,
            source_scraper="spicejet",
            llm_client=mock_client
        )

        self.assertEqual(quotes, [])

    def test_schema_validation_failure(self):
        html_content = "<html><body><div>Some content</div></body></html>"
        mock_client = MagicMock()
        # One valid quote, one with unparseable total_fare ('invalid_price')
        mock_client.extract_json.return_value = {
            "quotes": [
                {
                    "flight_num": "AI 865",
                    "carrier_code": "AI",
                    "carrier_name": "Air India",
                    "departure_time": "14:20",
                    "total_fare": 5400.0,
                    "fare_class": "economy"
                },
                {
                    "flight_num": "AI 999",
                    "carrier_code": "AI",
                    "carrier_name": "Air India",
                    "departure_time": "18:00",
                    "total_fare": "invalid_price",
                    "fare_class": "economy"
                }
            ]
        }

        quotes = llm_extract_flights(
            html_or_text=html_content,
            origin="DEL",
            destination="BLR",
            travel_date="2026-09-03",
            advance_days=1,
            source_scraper="air_india",
            llm_client=mock_client
        )

        # The invalid quote should be dropped and logged, keeping only the 1 valid quote
        self.assertEqual(len(quotes), 1)
        self.assertEqual(quotes[0].flight_num, "AI 865")
        self.assertEqual(quotes[0].total_fare, 5400.0)

    @patch.dict(os.environ, {"LLM_FALLBACK_MAX_CALLS_PER_RUN": "2"})
    def test_budget_cap(self):
        html_content = "<html><body>Flight Data</body></html>"
        mock_client = MagicMock()
        mock_client.extract_json.return_value = {"quotes": []}

        # First call (counter = 1)
        llm_extract_flights("html1", "DEL", "BOM", "2026-09-02", 1, "indigo", llm_client=mock_client)
        # Second call (counter = 2)
        llm_extract_flights("html2", "DEL", "BOM", "2026-09-02", 1, "indigo", llm_client=mock_client)
        self.assertEqual(mock_client.extract_json.call_count, 2)

        # Third call should hit budget cap and return [] without calling LLM
        res = llm_extract_flights("html3", "DEL", "BOM", "2026-09-02", 1, "indigo", llm_client=mock_client)
        self.assertEqual(res, [])
        self.assertEqual(mock_client.extract_json.call_count, 2)


if __name__ == "__main__":
    unittest.main()
