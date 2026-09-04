#!/usr/bin/env python3
"""
Goibibo Flight Fare Scraper
===========================
Production-grade scraper for Goibibo flight fares matching the FareQuote canonical schema.
Powered by SeleniumBase UC mode for anti-bot resilience and automated REFRESH handling.
"""

import os
import sys
import time
import random
import re
import csv
import logging
import argparse
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from seleniumbase import SB

# Configure logging with IST timestamp
IST = timezone(timedelta(hours=5, minutes=30))

class ISTFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=IST)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.isoformat()

logger = logging.getLogger("GoibiboScraper")
logger.setLevel(logging.INFO)
if not logger.handlers:
    console_handler = logging.StreamHandler(sys.stdout)
    formatter = ISTFormatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S IST")
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# --------------------------------------------------------------------------
# CANONICAL SCHEMA & DATA STRUCTURE
# --------------------------------------------------------------------------

CANONICAL_COLUMNS = [
    "origin",
    "destination",
    "carrier_code",
    "carrier_name",
    "flight_num",
    "travel_date",
    "advance_purchase_days",
    "fare_class",
    "base_fare",
    "taxes_and_fees",
    "total_fare",
    "fare_split_estimated",
    "departure_time",
    "status",
    "scraped_at",
    "capture_run",
]

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


DEFAULT_ROUTES = [
    ("DEL", "BOM"),
    ("DEL", "BLR"),
    ("BOM", "BLR"),
    ("DEL", "CCU"),
    ("BLR", "HYD"),
    ("MAA", "DEL")
]

DEFAULT_ADVANCE_WINDOWS = [1, 7, 15, 30, 45]

CARRIER_TABLE = {
    "6E": ("6E", "IndiGo"),
    "AI": ("AI", "Air India"),
    "IX": ("IX", "Air India Express"),
    "SG": ("SG", "SpiceJet"),
    "QP": ("QP", "Akasa Air"),
    "UK": ("UK", "Vistara"),
}

NAME_TO_CARRIER = {
    "indigo": ("6E", "IndiGo"),
    "air india express": ("IX", "Air India Express"),
    "air india": ("AI", "Air India"),
    "spicejet": ("SG", "SpiceJet"),
    "akasa air": ("QP", "Akasa Air"),
    "akasa": ("QP", "Akasa Air"),
    "vistara": ("UK", "Vistara"),
}


def resolve_carrier(carrier_text: str, flight_num: str) -> tuple[str, str]:
    """Resolves carrier_code and carrier_name from flight number or carrier text."""
    if flight_num:
        clean_num = flight_num.strip().upper()
        match = re.match(r"^([A-Z0-9]{2})[\s-]*\d+", clean_num)
        if match:
            code = match.group(1)
            if code in CARRIER_TABLE:
                return CARRIER_TABLE[code]

    if carrier_text:
        c_lower = carrier_text.strip().lower()
        for key, val in NAME_TO_CARRIER.items():
            if key in c_lower:
                return val

    return ("UNKNOWN", carrier_text if carrier_text else "Unknown Airline")


def dismiss_overlays(sb):
    """Dismisses Goibibo and partner popup overlays."""
    close_selectors = [
        "span.log-close",
        "span.commonModal__close",
        "span.modalClose",
        "[data-cy='closeModal']",
        "[class*='closeBtn']",
        "[class*='modalClose']",
        "[class*='overlayClose']",
        "span[class*='ic-close']",
        "button[aria-label='Close']",
        ".login__close",
        "[data-testid='modal-close']",
        ".common-overlay .close",
        "div.close",
        "i.wtr__close"
    ]
    for sel in close_selectors:
        try:
            if sb.is_element_visible(sel):
                sb.execute_script("arguments[0].click();", sb.find_element(sel))
                sb.sleep(random.uniform(0.3, 0.6))
        except Exception:
            pass


def handle_refresh_prompt(sb):
    """Handles 'NETWORK PROBLEM' / 'REFRESH' prompts with robust multi-attempt UC clicking and fallback reload."""
    refresh_selectors = [
        "//button[contains(translate(., 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'REFRESH')]",
        "//a[contains(translate(., 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'REFRESH')]",
        "//span[contains(translate(., 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'REFRESH')]",
        "button.refreshBtn",
        ".refresh-btn",
        ".button-refresh"
    ]
    
    for attempt in range(1, 4):
        # Check if error/refresh screen is present
        page_source_sample = ""
        try:
            page_source_sample = sb.get_page_source().lower()
        except Exception:
            pass

        is_waf_block = len(page_source_sample) < 1000 or "200-ok" in page_source_sample
        has_network_problem = "network problem" in page_source_sample or "unable to connect" in page_source_sample or is_waf_block
        
        btn_found = None
        for sel in refresh_selectors:
            try:
                if sb.is_element_visible(sel):
                    btn_found = sel
                    break
            except Exception:
                pass

        if not btn_found and not has_network_problem:
            return True  # Results are loading cleanly

        logger.info(f"  [Notice] Detected NETWORK PROBLEM / REFRESH prompt (Attempt {attempt}/3)...")
        sb.sleep(random.uniform(2.0, 3.0))

        if btn_found:
            try:
                sb.uc_click(btn_found)
                sb.sleep(random.uniform(5.0, 7.0))
                dismiss_overlays(sb)
            except Exception:
                try:
                    sb.execute_script("arguments[0].click();", sb.find_element(btn_found))
                    sb.sleep(random.uniform(5.0, 7.0))
                    dismiss_overlays(sb)
                except Exception:
                    pass
        else:
            # Fallback browser reload if button element wasn't caught directly
            logger.info("  [Notice] Reloading page via browser refresh...")
            if is_waf_block:
                logger.info("  [Notice] WAF block detected (200-OK). Clearing cookies and bouncing session...")
                sb.delete_all_cookies()
                sb.refresh()
            else:
                sb.refresh()
            sb.sleep(random.uniform(5.0, 7.0))
            dismiss_overlays(sb)

    return False


def parse_flight_cards(page_source: str, origin_code: str, dest_code: str, travel_date: str, advance_days: int, now_iso: str, capture_run: str) -> list[FareQuote]:
    """Parses Goibibo flight cards from the page DOM."""
    soup = BeautifulSoup(page_source, "html.parser")
    
    # Modern Goibibo flight card container selectors
    cards = soup.find_all("div", class_=lambda c: c and any(k in c for k in ["listingCard", "clusterCard", "singleFlightGroup", "tupleCard", "flt-card", "flight-card"]))
    if not cards:
        cards = soup.find_all("div", id=re.compile(r"^listing-card"))

    quotes_dict = {}
    discarded = 0

    for card in cards:
        card_text = card.get_text(" ", strip=True)

        # 1. Flight Number & Airline Name
        airline_el = card.find(class_=re.compile(r"airlineName|flightName|boldFont|airline-name"))
        airline_text = airline_el.get_text(strip=True) if airline_el else ""

        flight_num_el = card.find(class_=re.compile(r"flightCode|flightNumber|code|flight-no"))
        flight_num_raw = flight_num_el.get_text(strip=True) if flight_num_el else ""

        if not flight_num_raw:
            fn_match = re.search(r"\b(6E|AI|IX|SG|QP|UK)[\s-]*\d{3,4}\b", card_text, re.IGNORECASE)
            if fn_match:
                flight_num_raw = fn_match.group(0)

        carrier_code, carrier_name = resolve_carrier(airline_text, flight_num_raw)
        flight_num = flight_num_raw.upper() if flight_num_raw else f"{carrier_code} UNK"

        # 2. Airport validation
        dep_code_el = card.find(class_=re.compile(r"dept-city|deptCity|fromCity|departureCity"))
        arr_code_el = card.find(class_=re.compile(r"arr-city|arrCity|toCity|arrivalCity"))

        act_origin = origin_code
        act_dest = dest_code

        if dep_code_el:
            dep_m = re.search(r"\b([A-Z]{3})\b", dep_code_el.get_text(strip=True))
            if dep_m:
                act_origin = dep_m.group(1)

        if arr_code_el:
            arr_m = re.search(r"\b([A-Z]{3})\b", arr_code_el.get_text(strip=True))
            if arr_m:
                act_dest = arr_m.group(1)

        if act_origin and act_dest and (act_origin != origin_code or act_dest != dest_code):
            discarded += 1
            continue

        # 3. Departure Time
        dep_time = "unknown"
        dep_time_el = card.find(class_=re.compile(r"dept-time|depart-time|deptTime"))
        if dep_time_el:
            dep_time = dep_time_el.get_text(strip=True)
        else:
            time_m = re.search(r"\b([0-2]?\d:[0-5]\d)\b", card_text)
            if time_m:
                dep_time = time_m.group(1)

        # 4. Total Fare / Price
        total_fare = None
        
        # Strategy 1: Look for explicit currency symbol first (safest)
        price_m = re.search(r"₹\s*([\d,]+)", card_text)
        if price_m:
            try:
                total_fare = float(price_m.group(1).replace(",", ""))
            except ValueError:
                pass
                
        # Strategy 2: Look for specific price classes, avoiding generic text classes
        if total_fare is None:
            price_el = card.find(class_=re.compile(r"actual-price|clusterViewPrice|flt-price|price(?!-)|fare", re.IGNORECASE))
            if price_el:
                price_clean = re.sub(r"[^\d]", "", price_el.get_text(strip=True))
                if price_clean and len(price_clean) >= 3:
                    try:
                        total_fare = float(price_clean)
                    except ValueError:
                        pass

        status = "ok" if (total_fare is not None and total_fare > 1000 and flight_num) else "parse_error"

        quote = FareQuote(origin=origin_code,
            destination=dest_code,
            carrier_code=carrier_code,
            carrier_name=carrier_name,
            flight_num=flight_num,
            travel_date=travel_date,
            advance_purchase_days=advance_days,
            fare_class="economy",
            base_fare=None,
            taxes_and_fees=None,
            total_fare=total_fare,
            fare_split_estimated=False,
            departure_time=dep_time,
            status=status,
            scraped_at=now_iso,
            capture_run=capture_run, source="ota", source_name="Goibibo")
            
        key = (flight_num, dep_time)
        if key not in quotes_dict or quotes_dict[key].status == 'parse_error':
            quotes_dict[key] = quote

    if discarded:
        logger.info(f"  [Airport Filter] Discarded {discarded} card(s) with alternate airports.")
    return list(quotes_dict.values())


def scrape_one_window(sb, origin_code: str, dest_code: str, advance_days: int) -> list[FareQuote]:
    target_date = datetime.now() + timedelta(days=advance_days)
    travel_date = target_date.strftime("%Y-%m-%d")
    date_str_url = target_date.strftime("%d/%m/%Y")
    
    quotes = []
    now = datetime.now(IST)
    now_iso = now.isoformat()
    capture_run = f"GOIBIBO_RUN_{now.strftime('%Y%m%d_%H%M%S')}"

    # Unified Goibibo Flight Search URL
    search_url = f"https://www.goibibo.com/flight/search?itinerary={origin_code}-{dest_code}-{date_str_url}&tripType=O&paxType=A-1_C-0_I-0&intl=false&cabinClass=E&lang=eng"

    try:
        logger.info(f"[{origin_code}->{dest_code}] Loading Goibibo Search URL (T+{advance_days}, Date: {travel_date})...")
        sb.open(search_url)
        sb.sleep(random.uniform(4.0, 6.0))
        
        dismiss_overlays(sb)
        handle_refresh_prompt(sb)

        # Scroll page to load dynamic flight cards
        logger.info(f"[{origin_code}->{dest_code}] Scrolling page to load flight listings...")
        for _ in range(3):
            sb.execute_script("window.scrollBy(0, 600);")
            sb.sleep(random.uniform(1.0, 1.8))
        
        sb.sleep(random.uniform(2.0, 3.0))

        page_source = sb.get_page_source()
        if "no flights found" in page_source.lower() or "sold out" in page_source.lower():
            logger.info(f"[{origin_code}->{dest_code}] Route indicated as sold out or no flights.")
            quotes.append(FareQuote(origin=origin_code, destination=dest_code,
                carrier_code="GOI", carrier_name="Goibibo",
                flight_num="none", travel_date=travel_date, advance_purchase_days=advance_days,
                fare_class="Economy", base_fare=None, taxes_and_fees=None, total_fare=None, fare_split_estimated=False,
                departure_time="unknown", status="sold_out", scraped_at=now_iso, capture_run=capture_run, source="ota", source_name="Goibibo"))
            return quotes

        quotes = parse_flight_cards(page_source, origin_code, dest_code, travel_date, advance_days, now_iso, capture_run)

        if not quotes:
            logger.warning(f"[{origin_code}->{dest_code}] No flight cards parsed from DOM.")
            quotes.append(FareQuote(origin=origin_code, destination=dest_code,
                carrier_code="GOI", carrier_name="Goibibo",
                flight_num="none", travel_date=travel_date, advance_purchase_days=advance_days,
                fare_class="Economy", base_fare=None, taxes_and_fees=None, total_fare=None, fare_split_estimated=False,
                departure_time="unknown", status="parse_error", scraped_at=now_iso, capture_run=capture_run, source="ota", source_name="Goibibo"))

    except Exception as e:
        logger.error(f"[ERROR] T+{advance_days} ({origin_code}->{dest_code}): {e}")
        quotes.append(FareQuote(origin=origin_code, destination=dest_code,
            carrier_code="GOI", carrier_name="Goibibo",
            flight_num="error", travel_date=travel_date, advance_purchase_days=advance_days,
            fare_class="Economy", base_fare=None, taxes_and_fees=None, total_fare=None, fare_split_estimated=False,
            departure_time="unknown", status="error", scraped_at=now_iso, capture_run=capture_run, source="ota", source_name="Goibibo"))

    return quotes


def append_csv(quotes: list[FareQuote], path: str):
    """Atomically appends scraped quotes to target CSV file."""
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


def run(target_windows=None, target_routes=None, delay_min=30, delay_max=45, output_dir="apix_data/raw"):
    now = datetime.now(IST)
    today_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H%MIST")
    
    windows_to_scrape = target_windows if target_windows else DEFAULT_ADVANCE_WINDOWS
    routes_to_scrape = target_routes if target_routes else DEFAULT_ROUTES
    windows_str = "-".join([f"T{w}" for w in windows_to_scrape])
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, output_dir, today_str)
    os.makedirs(data_dir, exist_ok=True)
    
    csv_filename = f"goibibo_raw_{today_str}_batch_{windows_str}_{time_str}.csv"
    csv_path = os.path.join(data_dir, csv_filename)
    
    logger.info("=" * 70)
    logger.info("Starting SeleniumBase UC session for Goibibo scraping...")
    logger.info(f"Target CSV: {csv_path}")
    logger.info(f"Horizons  : {windows_to_scrape}")
    logger.info(f"Routes    : {routes_to_scrape}")
    logger.info("=" * 70)
    
    with SB(uc=True) as sb:
        consecutive_errors = 0
        
        # Warm-up session on Goibibo homepage
        logger.info("[Warmup] Initializing session on Goibibo homepage...")
        try:
            sb.open("https://www.goibibo.com/flights/")
            sb.sleep(random.uniform(3.0, 5.0))
            dismiss_overlays(sb)
            logger.info("[Warmup] Session tokens and cookies initialized successfully.\n")
        except Exception as e:
            logger.warning(f"[Warmup Notice] {e}")

        for advance_days in windows_to_scrape:
            logger.info(f"\n{'='*60}")
            logger.info(f"  GOIBIBO HORIZON: T+{advance_days}")
            logger.info(f"{'='*60}")

            for idx, (origin, dest) in enumerate(routes_to_scrape):
                logger.info(f"\n--- Scraping T+{advance_days} ({origin} -> {dest}) ---")
                
                try:
                    quotes = scrape_one_window(sb, origin, dest, advance_days)
                    has_error = any(q.status in ['error', 'parse_error'] for q in quotes)
                    
                    if has_error:
                        logger.info("  [Notice] Block/Error detected. IP ban suspected. Initiating 3-minute cooldown...")
                        sb.sleep(180)  # 3 minute cooldown for IP unban
                        sb.delete_all_cookies()
                        sb.open("https://www.goibibo.com/flights/")
                        sb.sleep(random.uniform(4.0, 6.0))
                        dismiss_overlays(sb)
                        quotes = scrape_one_window(sb, origin, dest, advance_days)
                        has_error = any(q.status in ['error', 'parse_error'] for q in quotes)

                    usable = sum(1 for q in quotes if q.status == 'ok')
                    logger.info(f"  -> {len(quotes)} quote(s) captured ({usable} usable)")
                    append_csv(quotes, csv_path)
                    logger.info(f"  -> Appended to {csv_path}")
                    
                    if has_error:
                        consecutive_errors += 1
                        if consecutive_errors >= 5:
                            logger.critical("[CRITICAL] 5 consecutive technical failures detected! Triggering circuit breaker.")
                            sys.exit(1)
                    else:
                        consecutive_errors = 0
                        
                except Exception as e:
                    logger.error(f"Critical error on {origin}->{dest}: {e}")
                    consecutive_errors += 1
                    if consecutive_errors >= 5:
                        logger.critical("[CRITICAL] 5 consecutive technical failures detected! Triggering circuit breaker.")
                        sys.exit(1)
                    
                # Rate Limiting & Jitter delay between routes
                delay = random.uniform(delay_min, delay_max)
                logger.info(f"  Waiting {delay:.1f}s before next route request...")
                sb.sleep(delay)

    logger.info("\nGoibibo scraping completed successfully across all horizons and routes!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Goibibo Flight Scraper")
    parser.add_argument("--windows", type=str, help="Comma separated list of horizons, e.g. 1,7")
    parser.add_argument("--routes", type=str, help="Comma separated routes, e.g. DEL-BOM,DEL-BLR")
    parser.add_argument("--delay-min", type=int, default=30, help="Min delay between routes (default: 30)")
    parser.add_argument("--delay-max", type=int, default=45, help="Max delay between routes (default: 45)")
    args = parser.parse_args()
    
    target_windows = None
    if args.windows:
        target_windows = [int(w.strip()) for w in args.windows.split(",")]

    target_routes = None
    if args.routes:
        target_routes = [tuple(r.strip().split("-")) for r in args.routes.split(",")]
        
    run(
        target_windows=target_windows,
        target_routes=target_routes,
        delay_min=args.delay_min,
        delay_max=args.delay_max
    )