import os
import csv
import time
import random
import datetime
from dataclasses import dataclass, asdict
from typing import List

from core.fare_schema import FareQuote

ROUTES = [("DEL", "BOM"), ("DEL", "BLR"), ("BOM", "BLR"), ("DEL", "CCU"), ("BLR", "HYD"), ("MAA", "DEL")]
ADVANCE_PURCHASE_WINDOWS = [1, 7, 15, 30, 45]


def parse_mmt_page(page_text: str, origin: str, dest: str, date_str: str, advance_days: int, now_iso: str, capture_run: str) -> List[FareQuote]:
    """Parse MakeMyTrip HTML / page source for flight quotes."""
    quotes = []

    # LLM Fallback Hook (gated behind ENABLE_LLM_FALLBACK=true)
    if os.getenv("ENABLE_LLM_FALLBACK", "false").lower() == "true" and page_text:
        try:
            from core.llm_fallback_parser import llm_extract_flights
            llm_quotes = llm_extract_flights(
                html_or_text=page_text, origin=origin, destination=dest,
                travel_date=date_str, advance_days=advance_days, source_scraper="makemytrip"
            )
            if llm_quotes:
                return llm_quotes
        except Exception as _ex:
            print(f"  [LLM Fallback Warning] {_ex}")

    if not quotes:
        quotes.append(FareQuote(
            origin=origin, destination=dest, carrier_code="MMT", carrier_name="MakeMyTrip",
            flight_num="unknown", travel_date=date_str, advance_purchase_days=advance_days,
            fare_class="economy", base_fare=None, taxes_and_fees=None, total_fare=None,
            fare_split_estimated=False, departure_time="unknown", status="parse_error",
            scraped_at=now_iso, capture_run=capture_run
        ))

    return quotes
