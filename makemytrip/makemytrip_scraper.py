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

BASE_URL = "https://www.makemytrip.com/"
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
    "login_modal_close": "span.commonModal__close, span.modalClose, [data-cy='closeModal'], i.wtr__close, div.close",
    "one_way_radio": "//li[@data-cy='oneWayTrip'] | //span[normalize-space(text())='One Way']",
    "from_city": "#fromCity",
    "to_city": "#toCity",
    "search_input": "input[placeholder*='From'], input[placeholder*='To'], input.react-autosuggest__input",
    "search_button": "//a[contains(@class, 'widgetSearchBtn')] | //button[contains(., 'Search')] | //a[text()='Search']",
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
    source: str
    source_name: str


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
    "6E": ("6E", "IndiGo"),
    "AI": ("AI", "Air India"),
    "IX": ("IX", "Air India Express"),
    "SG": ("SG", "SpiceJet"),
    "QP": ("QP", "Akasa Air"),
}

_NAME_TO_CARRIER = {
    "indigo": ("6E", "IndiGo"),
    "air india express": ("IX", "Air India Express"),
    "air india": ("AI", "Air India"),
    "spicejet": ("SG", "SpiceJet"),
    "akasa air": ("QP", "Akasa Air"),
    "akasa": ("QP", "Akasa Air"),
}


def resolve_carrier(carrier_text: str, flight_num: str) -> tuple[str, str]:
    """Resolves carrier_code and carrier_name from flight number or carrier text."""
    # 1. Try resolving via flight number prefix (e.g. "6E 5314", "AI 803", "IX 2714", "SG 8169", "QP 1101")
    if flight_num:
        clean_num = flight_num.strip().upper()
        match = re.match(r"^([A-Z0-9]{2})[\s-]*\d+", clean_num)
        if match:
            code = match.group(1)
            if code in _CARRIER_TABLE:
                return _CARRIER_TABLE[code]

    # 2. Try resolving via carrier text name
    if carrier_text:
        c_lower = carrier_text.strip().lower()
        for key, val in _NAME_TO_CARRIER.items():
            if key in c_lower:
                return val

    # Fallback default if unrecognized
    return ("UNKNOWN", carrier_text if carrier_text else "Unknown Airline")


def parse_flight_cards(page_source: str, origin_code: str, dest_code: str, travel_date: str, advance_days: int, now_iso: str, capture_run: str) -> list[FareQuote]:
    """Parses MakeMyTrip flight cards from the page DOM."""
    soup = BeautifulSoup(page_source, "html.parser")
    
    # MakeMyTrip cards are usually in div containers with classes containing listingCard, clusterCard, etc.
    cards = soup.find_all("div", class_=lambda c: c and any(k in c for k in ["listingCard", "clusterCard", "singleFlightGroup", "tupleCard"]))
    if not cards:
        # Fallback: search for cards with id starting with listing-card or data-test-id
        cards = soup.find_all("div", id=re.compile(r"^listing-card"))

    quotes_dict = {}
    discarded = 0

    for card in cards:
        # 1. Flight Number & Airline Name
        airline_el = card.find(class_=re.compile(r"airlineName|flightName|boldFont"))
        airline_text = airline_el.get_text(strip=True) if airline_el else ""

        flight_num_el = card.find(class_=re.compile(r"flightCode|flightNumber|code"))
        flight_num_raw = flight_num_el.get_text(strip=True) if flight_num_el else ""

        # Extract flight number using regex if not explicitly found
        card_text = card.get_text(" ", strip=True)
        if not flight_num_raw:
            fn_match = re.search(r"\b(6E|AI|IX|SG|QP)[\s-]*\d{3,4}\b", card_text, re.IGNORECASE)
            if fn_match:
                flight_num_raw = fn_match.group(0)

        carrier_code, carrier_name = resolve_carrier(airline_text, flight_num_raw)
        flight_num = flight_num_raw.upper() if flight_num_raw else f"{carrier_code} UNK"

        # --- Alternate Airport Validation (Rule 7) ---
        # Extract IATA codes or city names from card
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

        # Check for alternate airport mismatch
        if act_origin and act_dest and (act_origin != origin_code or act_dest != dest_code):
            with open("discarded_routes.log", "a", encoding="utf-8") as lf:
                lf.write(f"[{now_iso}] MMT: Discarded {act_origin}->{act_dest} (Target: {origin_code}->{dest_code}) flight={flight_num}\n")
            discarded += 1
            continue

        # 2. Departure Time
        dep_time = "unknown"
        dep_time_el = card.find(class_=re.compile(r"dept-time|depart-time|deptTime"))
        if dep_time_el:
            dep_time = dep_time_el.get_text(strip=True)
        else:
            time_m = re.search(r"\b([0-2]?\d:[0-5]\d)\b", card_text)
            if time_m:
                dep_time = time_m.group(1)

        # 3. Total Fare / Price
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
            price_el = card.find(class_=re.compile(r"actual-price|clusterViewPrice|price(?!-)|fare", re.IGNORECASE))
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
            capture_run=capture_run, source="ota", source_name="MakeMyTrip")
            
        key = (flight_num, dep_time)
        if key not in quotes_dict or quotes_dict[key].status == 'parse_error':
            quotes_dict[key] = quote

    if discarded:
        print(f"  [Airport Filter] Discarded {discarded} card(s) with alternate airports.")
    return list(quotes_dict.values())


def handle_popups(sb):
    """Closes any login modals or promo popups on MakeMyTrip."""
    popups = [
        "span.commonModal__close",
        "span.modalClose",
        "[data-cy='closeModal']",
        "i.wtr__close",
        "div.close"
    ]
    for selector in popups:
        try:
            if sb.is_element_visible(selector):
                sb.execute_script("arguments[0].click();", sb.find_element(selector))
                sb.sleep(random.uniform(0.5, 1.0))
        except Exception:
            pass


def scrape_one_window(sb, origin_code: str, dest_code: str, advance_days: int) -> list[FareQuote]:
    target_date = datetime.now() + timedelta(days=advance_days)
    travel_date = target_date.strftime("%Y-%m-%d")
    date_str_url = target_date.strftime("%d/%m/%Y")
    
    quotes = []
    
    now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    now_iso = now.isoformat()
    capture_run = now.strftime("%Y-%m-%d_%H%MIST")

    # Direct search URL construction for maximum resilience & speed
    search_url = f"https://www.makemytrip.com/flight/search?itinerary={origin_code}-{dest_code}-{date_str_url}&tripType=O&paxType=A-1_C-0_I-0&intl=false&cabinClass=E&lang=eng"

    try:
        print(f"[{origin_code}->{dest_code}] Loading MakeMyTrip Search URL (T+{advance_days}, Date: {travel_date})...")
        sb.open(search_url)
        sb.sleep(random.uniform(4.0, 6.0))
        
        # Handle login modals/popups
        handle_popups(sb)

        # Check for and handle "Refresh" prompt / button if MakeMyTrip requests it
        refresh_selectors = [
            "//button[contains(translate(., 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'REFRESH')]",
            ".fullpage-error-cta-wrapper button",
            "button.buttonPrimary"
        ]
        
        for attempt in range(1, 4):
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
                break  # Clean, no network error
                
            print(f"  [Notice] Detected NETWORK PROBLEM / REFRESH prompt (Attempt {attempt}/3)...")
            sb.sleep(random.uniform(2.0, 3.0))

            if btn_found:
                try:
                    sb.uc_click(btn_found)
                    sb.sleep(random.uniform(5.0, 7.0))
                    handle_popups(sb)
                except Exception:
                    try:
                        sb.execute_script("arguments[0].click();", sb.find_element(btn_found))
                        sb.sleep(random.uniform(5.0, 7.0))
                        handle_popups(sb)
                    except Exception:
                        pass
            else:
                print("  [Notice] Reloading page via browser refresh...")
                if is_waf_block:
                    print("  [Notice] WAF block detected (200-OK). Clearing cookies and bouncing session...")
                    sb.delete_all_cookies()
                    sb.open(BASE_URL)
                    sb.sleep(random.uniform(3.0, 5.0))
                    sb.open(search_url)
                else:
                    sb.refresh()
                sb.sleep(random.uniform(5.0, 7.0))
                handle_popups(sb)

        # Sometimes MMT doesn't auto-submit the search from the URL. Click the search button if visible.
        try:
            if sb.is_element_visible("a.widgetSearchBtn"):
                print(f"[{origin_code}->{dest_code}] Clicking Search button to initiate search...")
                sb.click("a.widgetSearchBtn")
                sb.sleep(random.uniform(6.0, 8.0))
                handle_popups(sb)
        except Exception:
            pass

        # Wait for dynamic flight card listings
        try:
            sb.wait_for_element_visible("div[class*='listingCard'], div[class*='clusterCard'], div[id^='listing-card']", timeout=12)
        except Exception:
            pass

        # Scroll to load dynamic flight card listings
        print(f"[{origin_code}->{dest_code}] Scrolling page to load flight listings...")
        for _ in range(3):
            sb.execute_script("window.scrollBy(0, 600);")
            sb.sleep(random.uniform(1.0, 1.8))
        
        sb.sleep(random.uniform(2.0, 3.0))

        # Check for 'No Flights' or 'Sold Out' indicators
        page_source = sb.get_page_source()
        if "no flights found" in page_source.lower() or "sold out" in page_source.lower():
            print(f"[{origin_code}->{dest_code}] Route indicated as sold out or no flights.")
            quotes.append(FareQuote(origin=origin_code, destination=dest_code,
                carrier_code="MMT", carrier_name="MakeMyTrip",
                flight_num="none", travel_date=travel_date, advance_purchase_days=advance_days,
                fare_class="economy", base_fare=None, taxes_and_fees=None, total_fare=None, fare_split_estimated=False,
                departure_time="unknown", status="sold_out", scraped_at=now_iso, capture_run=capture_run, source="ota", source_name="MakeMyTrip"))
            return quotes

        # Parse flight cards DOM
        quotes = parse_flight_cards(page_source, origin_code, dest_code, travel_date, advance_days, now_iso, capture_run)

        # Fallback if 0 cards parsed
        if not quotes:
            print(f"[{origin_code}->{dest_code}] No flight cards parsed from DOM.")
            
            if os.getenv("ENABLE_LLM_FALLBACK", "false").lower() == "true":
                try:
                    from core.llm_fallback_parser import llm_extract_flights
                    llm_qs = llm_extract_flights(
                        html_or_text=page_source, origin=origin_code, destination=dest_code,
                        travel_date=travel_date, advance_days=advance_days, source_scraper="makemytrip"
                    )
                    for lq in llm_qs:
                        quotes.append(FareQuote(
                            origin=lq.origin, destination=lq.destination, carrier_code=lq.carrier_code,
                            carrier_name=lq.carrier_name, flight_num=lq.flight_num, travel_date=lq.travel_date,
                            advance_purchase_days=lq.advance_purchase_days, fare_class=lq.fare_class,
                            base_fare=lq.base_fare, taxes_and_fees=lq.taxes_and_fees, total_fare=lq.total_fare,
                            fare_split_estimated=lq.fare_split_estimated, departure_time=lq.departure_time,
                            status=lq.status, scraped_at=lq.scraped_at, capture_run=lq.capture_run,
                            source="ota", source_name="MakeMyTrip"
                        ))
                except Exception as ex:
                    print(f"  [LLM Fallback Warning] {ex}")

            if not quotes:
                quotes.append(FareQuote(origin=origin_code, destination=dest_code,
                    carrier_code="MMT", carrier_name="MakeMyTrip",
                    flight_num="none", travel_date=travel_date, advance_purchase_days=advance_days,
                    fare_class="economy", base_fare=None, taxes_and_fees=None, total_fare=None, fare_split_estimated=False,
                    departure_time="unknown", status="parse_error", scraped_at=now_iso, capture_run=capture_run, source="ota", source_name="MakeMyTrip"))

    except Exception as e:
        print(f"[ERROR] T+{advance_days} ({origin_code}->{dest_code}):", e)
        quotes.append(FareQuote(origin=origin_code, destination=dest_code,
            carrier_code="MMT", carrier_name="MakeMyTrip",
            flight_num="error", travel_date=travel_date, advance_purchase_days=advance_days,
            fare_class="economy", base_fare=None, taxes_and_fees=None, total_fare=None, fare_split_estimated=False,
            departure_time="unknown", status="error", scraped_at=now_iso, capture_run=capture_run, source="ota", source_name="MakeMyTrip"))

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


def run(target_windows=None, target_routes=None, delay_min=30, delay_max=45):
    now = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    today_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H%MIST")
    
    windows_to_scrape = target_windows if target_windows else ADVANCE_PURCHASE_WINDOWS
    routes_to_scrape = target_routes if target_routes else ROUTES
    windows_str = "-".join([f"T{w}" for w in windows_to_scrape])
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "udaan_data", "raw", today_str)
    os.makedirs(data_dir, exist_ok=True)
    
    csv_filename = f"makemytrip_raw_{today_str}_batch_{windows_str}_{time_str}.csv"
    csv_path = os.path.join(data_dir, csv_filename)
    
    print(f"Starting SeleniumBase UC session for MakeMyTrip scraping...")
    print(f"Target CSV: {csv_path}")
    
    with SB(uc=True, uc_cdp=True) as sb:
        consecutive_errors = 0
        
        # Warm-up session on homepage to establish essential tokens/cookies
        print("\n[Warmup] Initializing session on MakeMyTrip homepage...")
        try:
            sb.open(BASE_URL)
            sb.sleep(random.uniform(3.0, 5.0))
            handle_popups(sb)
            print("[Warmup] Session tokens and cookies successfully initialized.\n")
        except Exception as e:
            print(f"[Warmup Notice] {e}")

        # Outer loop: Advance Purchase Horizons
        for advance_days in windows_to_scrape:
            print(f"\n{'='*60}")
            print(f"  MAKEMYTRIP HORIZON: T+{advance_days}")
            print(f"{'='*60}")

            # Inner loop: Core Routes
            for idx, (origin, dest) in enumerate(routes_to_scrape):
                print(f"\n--- Scraping T+{advance_days} ({origin} -> {dest}) ---")
                
                try:
                    quotes = scrape_one_window(sb, origin, dest, advance_days)
                    has_error = any(q.status in ['error', 'parse_error'] for q in quotes)
                    
                    if has_error:
                        print("  [Notice] Block/Error detected. IP ban suspected. Initiating 3-minute cooldown...")
                        sb.sleep(180)  # 3 minute cooldown for IP unban
                        sb.delete_all_cookies()
                        sb.open(BASE_URL)
                        sb.sleep(random.uniform(4.0, 6.0))
                        handle_popups(sb)
                        quotes = scrape_one_window(sb, origin, dest, advance_days)
                        has_error = any(q.status in ['error', 'parse_error'] for q in quotes)

                    usable = sum(1 for q in quotes if q.status == 'ok')
                    print(f"  -> {len(quotes)} quote(s) captured ({usable} usable)")
                    append_csv(quotes, csv_path)
                    print(f"  -> Appended to {csv_path}")
                    
                    if has_error:
                        consecutive_errors += 1
                        if consecutive_errors >= 5:
                            print("\n[CRITICAL] 5 consecutive technical failures detected! Triggering circuit breaker.")
                            sys.exit(1)
                    else:
                        consecutive_errors = 0
                        
                except Exception as e:
                    print(f"Critical error on {origin}->{dest}: {e}")
                    consecutive_errors += 1
                    if consecutive_errors >= 5:
                        print("\n[CRITICAL] 5 consecutive technical failures detected! Triggering circuit breaker.")
                        sys.exit(1)
                    
                # Rate Limiting & Jitter delay between routes
                delay = random.uniform(delay_min, delay_max)
                print(f"  Waiting {delay:.1f}s before next route request...")
                sb.sleep(delay)

    print("\nMakeMyTrip scraping completed successfully across all horizons and routes!")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="MakeMyTrip Flight Scraper")
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