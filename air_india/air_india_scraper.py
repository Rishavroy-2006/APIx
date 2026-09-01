import time
import csv
import random
import sys
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

from seleniumbase import SB

# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------

BASE_URL = "https://www.airindia.com/"
ROUTES = [
    ("DEL", "BOM"),
    ("DEL", "BLR"),
    ("BOM", "BLR"),
    ("DEL", "CCU"),
    ("BLR", "HYD"),
    ("MAA", "DEL")
]
ADVANCE_PURCHASE_WINDOWS = [1, 7, 15, 30, 45]

SELECTORS = {
    "origin_input": "div[aria-label='Select origin airport'] input",
    "destination_input": "div[aria-label='Select destination airport'] input",
    "search_button": "//button[@aria-label='Search'] | //button[contains(@class, 'ai-booking-widget__search-btn')] | //button[contains(., 'Search')]",
}

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


def human_type(sb, selector: str, text: str):
    """Types characters one by one with human-like jitter delays."""
    try:
        sb.clear(selector)
    except Exception:
        pass
    time.sleep(random.uniform(0.2, 0.4))
    for char in text:
        sb.add_text(selector, char)
        time.sleep(random.uniform(0.12, 0.28))


# Fixed carrier lookup table per GUIDELINES Section 2
_CARRIER_TABLE = {
    "Air India Express": ("IX", "Air India Express"),
    "Air India": ("AI", "Air India"),
}


def parse_flight_cards(page_source: str, origin_code: str, dest_code: str, travel_date: str, advance_days: int, now_iso: str, capture_run: str) -> list[FareQuote]:
    """Parses Air India flight cards from the page DOM."""
    soup = BeautifulSoup(page_source, "html.parser")
    cards = soup.find_all("ai-pb-flight-card")
    quotes = []
    discarded = 0

    for card in cards:
        flight_id_el = card.find(class_="ai-pb-flight-id")
        if not flight_id_el:
            continue
        flight_num = flight_id_el.get_text(strip=True)

        # --- Alternate Airport Validation (Rule 4a) ---
        # Extract IATA codes from departure/arrival city elements
        dep_city_el = card.find(class_="ai-pb-departure-city-code")
        arr_city_el = card.find(class_="ai-pb-arrival-city-code")
        act_origin = dep_city_el.get_text(strip=True) if dep_city_el else origin_code
        act_dest = arr_city_el.get_text(strip=True) if arr_city_el else dest_code
        if act_origin and act_dest and (act_origin != origin_code or act_dest != dest_code):
            with open("discarded_routes.log", "a") as lf:
                lf.write(f"[{now_iso}] AI: Discarded {act_origin}->{act_dest} (Target: {origin_code}->{dest_code}) flight={flight_num}\n")
            discarded += 1
            continue

        # --- Carrier lookup from fixed table (GUIDELINES Section 2) ---
        operated_by_el = card.find(class_="ai-pb-operated-by-info")
        operated_by = operated_by_el.get_text(strip=True) if operated_by_el else ""
        if "Express" in operated_by:
            carrier_code, carrier_name = _CARRIER_TABLE["Air India Express"]
        else:
            carrier_code, carrier_name = _CARRIER_TABLE["Air India"]

        dep_time_el = card.find(class_="ai-pb-departure-time")
        dep_time = dep_time_el.get_text(strip=True) if dep_time_el else "unknown"

        price_el = card.find(class_="ai-pb-price")
        total_fare = None
        if price_el:
            price_clean = re.sub(r"[^\d.]", "", price_el.get_text(strip=True))
            if price_clean:
                try:
                    total_fare = float(price_clean)
                except ValueError:
                    pass

        status = "ok" if (total_fare is not None and flight_num) else "parse_error"

        quotes.append(FareQuote(
            origin=origin_code,
            destination=dest_code,
            carrier_code=carrier_code,
            carrier_name=carrier_name,
            flight_num=flight_num,
            travel_date=travel_date,
            advance_purchase_days=advance_days,
            fare_class="economy",  # lowercase per GUIDELINES Section 2
            base_fare=None,
            taxes_and_fees=None,
            total_fare=total_fare,
            fare_split_estimated=False,
            departure_time=dep_time,
            status=status,
            scraped_at=now_iso,
            capture_run=capture_run
        ))

    if discarded:
        print(f"  [Airport Filter] Discarded {discarded} card(s) with alternate airports.")
    return quotes


def scrape_one_window(sb, origin_code: str, dest_code: str, advance_days: int) -> list[FareQuote]:
    travel_date = (datetime.now() + timedelta(days=advance_days)).strftime("%Y-%m-%d")
    quotes = []
    
    now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    now_iso = now.isoformat()
    capture_run = now.strftime("%Y-%m-%d_%H%MIST")

    try:
        print(f"[{origin_code}->{dest_code}] Loading Air India...")
        sb.open(BASE_URL)
        sb.sleep(random.uniform(3.0, 4.5))
        
        # 1. Cookie banner
        if sb.is_element_visible("#onetrust-accept-btn-handler"):
            sb.click("#onetrust-accept-btn-handler")
            sb.sleep(random.uniform(0.8, 1.5))

        # 2. Select One Way
        print(f"[{origin_code}->{dest_code}] Selecting One Way...")
        sb.click("//span[normalize-space(text())='One Way']")
        sb.sleep(random.uniform(0.8, 1.4))

        # 3. Enter Origin
        print(f"[{origin_code}->{dest_code}] Entering Origin ({origin_code})...")
        sb.click("div[aria-label='Select origin airport']")
        sb.sleep(random.uniform(0.5, 1.0))
        human_type(sb, SELECTORS["origin_input"], origin_code)
        sb.sleep(random.uniform(0.8, 1.2))
        
        # 4. Enter Destination
        print(f"[{origin_code}->{dest_code}] Entering Destination ({dest_code})...")
        sb.click("div[aria-label='Select destination airport']")
        sb.sleep(random.uniform(0.5, 1.0))
        human_type(sb, SELECTORS["destination_input"], dest_code)
        sb.sleep(random.uniform(1.0, 1.5))
        sb.add_text(SELECTORS["destination_input"], "\n")
        sb.sleep(2.5)

        # 5. Select Travel Date from Calendar
        target_date = datetime.now() + timedelta(days=advance_days)
        # Angular Material format: "M/D/YYYY" (e.g. "9/2/2026")
        date_aria_label = f"{target_date.month}/{target_date.day}/{target_date.year}"
        print(f"[{origin_code}->{dest_code}] Selecting Date: {travel_date} (aria-label='{date_aria_label}')...")
        
        date_clicked = False
        for _ in range(4):
            date_xpath = f"//button[@aria-label='{date_aria_label}']"
            if sb.is_element_visible(date_xpath):
                sb.click(date_xpath)
                sb.sleep(random.uniform(1.0, 1.8))
                date_clicked = True
                print(f"[{origin_code}->{dest_code}] Successfully selected date {date_aria_label}!")
                break
            else:
                print(f"[{origin_code}->{dest_code}] Date not in current view, clicking Next Month...")
                if sb.is_element_visible("button.ai-date-picker__arrow--right"):
                    sb.click("button.ai-date-picker__arrow--right")
                    sb.sleep(1)
                elif sb.is_element_visible("button[aria-label='Next month']"):
                    sb.click("button[aria-label='Next month']")
                    sb.sleep(1)

        if not date_clicked:
            print(f"[{origin_code}->{dest_code}] Warning: Could not find date cell for {date_aria_label}")

        sb.sleep(1)

        # 6. Click Search
        print(f"[{origin_code}->{dest_code}] Clicking Search Button...")
        sb.click(SELECTORS["search_button"])

        # 7. Wait for results
        print(f"[{origin_code}->{dest_code}] Waiting for flight results to load...")
        sb.sleep(15)

        # 8. Parse DOM
        page_source = sb.get_page_source()
        quotes = parse_flight_cards(page_source, origin_code, dest_code, travel_date, advance_days, now_iso, capture_run)

        # Fallback if 0 cards found
        if not quotes:
            print(f"[{origin_code}->{dest_code}] No flight cards found in DOM.")
            quotes.append(FareQuote(
                origin=origin_code, destination=dest_code,
                carrier_code="AI", carrier_name="Air India",
                flight_num="none", travel_date=travel_date, advance_purchase_days=advance_days,
                fare_class="economy", base_fare=None, taxes_and_fees=None, total_fare=None, fare_split_estimated=False,
                departure_time="unknown", status="parse_error", scraped_at=now_iso, capture_run=capture_run
            ))

    except Exception as e:
        print(f"[ERROR] T+{advance_days} ({origin_code}->{dest_code}):", e)
        quotes.append(FareQuote(
            origin=origin_code, destination=dest_code,
            carrier_code="AI", carrier_name="Air India",
            flight_num="error", travel_date=travel_date, advance_purchase_days=advance_days,
            fare_class="economy", base_fare=None, taxes_and_fees=None, total_fare=None, fare_split_estimated=False,
            departure_time="unknown", status="error", scraped_at=now_iso, capture_run=capture_run
        ))

    return quotes


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
    now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    today_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H%MIST")
    
    windows_to_scrape = target_windows if target_windows else ADVANCE_PURCHASE_WINDOWS
    windows_str = "-".join([f"T{w}" for w in windows_to_scrape])
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "apix_data", "raw", today_str)
    os.makedirs(data_dir, exist_ok=True)
    
    csv_filename = f"air_india_raw_{today_str}_batch_{windows_str}_{time_str}.csv"
    csv_path = os.path.join(data_dir, csv_filename)
    
    print(f"Starting SeleniumBase UC session for Air India scraping...")
    print(f"Target CSV: {csv_path}")
    
    consecutive_errors = 0
    # Outer loop: Advance Purchase Horizons (Resilience Rule: T+1 first, T+7, etc.)
    for advance_days in windows_to_scrape:
        print(f"\n{'='*60}")
        print(f"  AIR INDIA HORIZON: T+{advance_days}")
        print(f"{'='*60}")

        # Instantiate fresh browser for each horizon to prevent session degradation/blocking
        with SB(uc=True) as sb:
            # Inner loop: Routes
            for idx, (origin, dest) in enumerate(ROUTES):
                print(f"\n--- Scraping T+{advance_days} ({origin} -> {dest}) ---")
                
                try:
                    quotes = scrape_one_window(sb, origin, dest, advance_days)
                    has_error = any(q.status == 'error' for q in quotes)
                    usable = sum(1 for q in quotes if q.status == 'ok')
                    print(f"  -> {len(quotes)} quote(s) captured ({usable} usable)")
                    append_csv(quotes, csv_path)
                    print(f"  -> Appended to {csv_path}")
                    
                    if has_error:
                        consecutive_errors += 1
                        if consecutive_errors >= 5:
                            print("\n[CRITICAL] 5 consecutive technical failures detected! Triggering circuit breaker.")
                            import sys
                            sys.exit(1)
                    else:
                        consecutive_errors = 0
                        
                except Exception as e:
                    print(f"Critical error on {origin}->{dest}: {e}")
                    consecutive_errors += 1
                    if consecutive_errors >= 5:
                        print("\n[CRITICAL] 5 consecutive technical failures detected! Triggering circuit breaker.")
                        import sys
                        sys.exit(1)
                    
                # Rate Limiting & Jitter delay between routes
                delay = random.uniform(20.0, 40.0)
                print(f"  Waiting {delay:.1f}s before next route request...")
                sb.sleep(delay)

    print("\nAir India scraping completed successfully across all horizons and routes!")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Air India Scraper")
    parser.add_argument("--windows", type=str, help="Comma separated list of horizons, e.g. 1,7")
    args = parser.parse_args()
    
    if args.windows:
        target_windows = [int(w.strip()) for w in args.windows.split(",")]
        run(target_windows=target_windows)
    else:
        run()
