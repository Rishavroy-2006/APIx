import os
import re
import csv
import time
import random
import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Tuple

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import undetected_chromedriver as uc

ROUTES = [
    ("DEL", "BOM"),
    ("DEL", "BLR"),
    ("BOM", "BLR"),
    ("DEL", "CCU"),
    ("BLR", "HYD"),
    ("MAA", "DEL")
]

ADVANCE_PURCHASE_WINDOWS = [1, 7, 15, 30, 45]

_FLIGHT_RE = re.compile(r'\bSG\s*[-]?\s*(\d{2,4})\b')
_TIME_RE   = re.compile(r'^\d{2}:\d{2}$')

@dataclass
class FareQuote:
    origin: str
    destination: str
    carrier_code: str
    carrier_name: str
    flight_num: str
    travel_date: str
    advance_purchase_days: int
    fare_class: str
    base_fare: float | None
    taxes_and_fees: float | None
    total_fare: float | None
    fare_split_estimated: bool
    departure_time: str
    status: str
    scraped_at: str
    capture_run: str
    source: str
    source_name: str

def init_driver(headless: bool = False):
    options = uc.ChromeOptions()
    options.add_argument(f'--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(110, 120)}.0.0.0 Safari/537.36')
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    driver = uc.Chrome(options=options, version_main=151)
    return driver

def parse_page_flights(page_text: str, origin: str, dest: str, date_str: str, advance_days: int, now_iso: str, capture_run: str) -> Tuple[str, List[FareQuote]]:
    if "no flights available" in page_text.lower() or "unfortunately" in page_text.lower():
        return "no_flights", []

    lines = [l.strip() for l in page_text.split('\n') if l.strip()]
    quotes = []
    
    for i, line in enumerate(lines):
        f_match = _FLIGHT_RE.search(line)
        if f_match and len(line) < 15:
            flight_num = f"SG {f_match.group(1)}"
            
            dep_time = None
            for j in range(max(0, i - 12), i):
                txt = lines[j]
                if re.match(r'^\d{2}:\d{2}$', txt):
                    if dep_time is None:
                        dep_time = txt
            
            fares_found = []
            for j in range(i + 1, min(len(lines), i + 25)):
                txt = lines[j]
                if _FLIGHT_RE.search(txt) and len(txt) < 15:
                    break
                if lines[j - 1] == '₹' or '₹' in txt:
                    fare_val = txt.replace('₹', '').replace(',', '').strip()
                    if fare_val.isdigit() and 500 <= int(fare_val) <= 100000:
                        f_float = float(fare_val)
                        if f_float not in fares_found:
                            fares_found.append(f_float)
            
            if fares_found:
                tier_labels = ["economy", "economy", "economy"]  # SpiceJet search page only shows economy fares; label all as economy
                for t_idx, fare_amt in enumerate(fares_found[:3]):
                    quotes.append(FareQuote(
                        origin=origin,
                        destination=dest,
                        carrier_code="SG",
                        carrier_name="SpiceJet",
                        flight_num=flight_num,
                        travel_date=date_str,
                        advance_purchase_days=advance_days,
                        fare_class=tier_labels[t_idx] if t_idx < len(tier_labels) else "economy",
                        base_fare=None,
                        taxes_and_fees=None,
                        total_fare=fare_amt,
                        fare_split_estimated=False,
                        departure_time=dep_time or "N/A",
                        status="ok",
                        scraped_at=now_iso,
                        capture_run=capture_run, source="airline_direct", source_name="SpiceJet"
                    ))
                    
    if not quotes:
        sg_any = re.findall(r'\bSG\s*[-]?\s*\d{2,4}\b', page_text)
        if sg_any:
            return "parse_error", []
        else:
            return "no_flights", []
            
    return "ok", quotes

def append_csv(quotes: list[FareQuote], path: str):
    if not quotes:
        return
    file_exists = os.path.isfile(path)
    fieldnames = list(asdict(quotes[0]).keys())
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for q in quotes:
            writer.writerow(asdict(q))

def run(target_windows=None):
    import datetime as dt
    import os
    
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30)))
    capture_run = now.strftime("%Y-%m-%d_%H%MIST")
    today = now.date()
    today_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H%MIST")

    windows_to_scrape = target_windows if target_windows else ADVANCE_PURCHASE_WINDOWS
    windows_str = "-".join([f"T{w}" for w in windows_to_scrape])
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "udaan_data", "raw", today_str)
    os.makedirs(data_dir, exist_ok=True)
    
    csv_filename = f"spicejet_raw_{today_str}_batch_{windows_str}_{time_str}.csv"
    csv_path = os.path.join(data_dir, csv_filename)
    
    consecutive_errors = 0
    for advance_days in windows_to_scrape:
        print(f"\n{'='*60}")
        print(f"  HORIZON: T+{advance_days}")
        print(f"{'='*60}")
        
        for idx, (origin, dest) in enumerate(ROUTES):
            travel_date = today + dt.timedelta(days=advance_days)
            date_str = travel_date.strftime("%Y-%m-%d")
            
            print(f"\n--- Scraping T+{advance_days} ({origin} -> {dest} for {date_str}) ---")
            
            print("Starting fresh undetected-chromedriver session...")
            driver = init_driver(headless=False)
            # Rule 6b: IST-aware timestamp with +05:30 offset
            now_ist = dt.datetime.now(dt.timezone(dt.timedelta(hours=5, minutes=30)))
            now_iso = now_ist.isoformat()  # e.g. 2026-09-01T05:30:00+05:30
            
            url = f"https://www.spicejet.com/search?from={origin}&to={dest}&tripType=1&departure={date_str}&adult=1&child=0&srCitizen=0&infant=0&currency=INR&redirectTo=/&airline=SG"
            
            try:
                driver.get(url)
                time.sleep(10)
                
                page_text = driver.find_element(By.TAG_NAME, "body").text
                status, quotes = parse_page_flights(page_text, origin, dest, date_str, advance_days, now_iso, capture_run)
                
                usable = sum(1 for q in quotes if q.status == 'ok')
                print(f"  -> {len(quotes)} quote(s) captured ({usable} usable) | Status: {status}")
                
                if usable == 0 and os.getenv("ENABLE_LLM_FALLBACK", "false").lower() == "true":
                    try:
                        from core.llm_fallback_parser import llm_extract_flights
                        llm_quotes = llm_extract_flights(
                            html_or_text=page_text, origin=origin, destination=dest,
                            travel_date=date_str, advance_days=advance_days, source_scraper="spicejet"
                        )
                        if llm_quotes:
                            quotes = llm_quotes
                            status = "ok"
                            usable = len(quotes)
                    except Exception as _ex:
                        print(f"  [LLM Fallback Warning] {_ex}")

                if usable == 0:
                    quotes.append(FareQuote(
                        origin=origin, destination=dest, carrier_code="SG", carrier_name="SpiceJet",
                        flight_num="unknown", travel_date=date_str, advance_purchase_days=advance_days,
                        fare_class="unknown", base_fare=None, taxes_and_fees=None, total_fare=None,
                        fare_split_estimated=False, departure_time="unknown", status=status,
                        scraped_at=now_iso, capture_run=capture_run, source="airline_direct", source_name="SpiceJet"
                    ))
                
                append_csv(quotes, csv_path)
                print(f"  -> Appended to {csv_path}")
                consecutive_errors = 0
                
            except Exception as e:
                print(f"  -> Error: {e}")
                consecutive_errors += 1
                if consecutive_errors >= 5:
                    print("\n[CRITICAL] 5 consecutive technical failures detected! Triggering circuit breaker.")
                    import sys
                    sys.exit(1)
            finally:
                driver.quit()
                
            delay = random.uniform(30, 45)  
            print(f"  Waiting {delay:.1f}s before next request...")
            time.sleep(delay)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="SpiceJet Scraper")
    parser.add_argument("--windows", type=str, help="Comma separated list of horizons, e.g. 1,7")
    args = parser.parse_args()
    
    if args.windows:
        target_windows = [int(w.strip()) for w in args.windows.split(",")]
        run(target_windows=target_windows)
    else:
        run()
