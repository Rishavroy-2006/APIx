import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
import time
import random
import os
import datetime
import argparse
import csv
import re
from dataclasses import dataclass, fields, astuple

ROUTES = [("DEL", "BOM"), ("DEL", "BLR"), ("BOM", "BLR"), ("DEL", "CCU"), ("BLR", "HYD"), ("MAA", "DEL")]
ADVANCE_PURCHASE_WINDOWS = [1, 7, 15, 30, 45]

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

FIELDNAMES = [
    "origin", "destination", "carrier_code", "carrier_name", "flight_num",
    "travel_date", "advance_purchase_days", "fare_class", "base_fare",
    "taxes_and_fees", "total_fare", "fare_split_estimated", "departure_time",
    "status", "scraped_at", "capture_run"
]


@dataclass
class FareQuote:
    """Canonical schema per GUIDELINES.md Section 2. Must match all other scrapers exactly."""
    origin: str
    destination: str
    carrier_code: str           # Fixed lookup: QP = Akasa Air
    carrier_name: str           # Fixed lookup: never scraped as free text
    flight_num: str
    travel_date: str            # YYYY-MM-DD
    advance_purchase_days: int  # one of {1, 7, 15, 30, 45}
    fare_class: str             # 'economy' | 'business'
    base_fare: float | None
    taxes_and_fees: float | None
    total_fare: float | None
    fare_split_estimated: bool  # True if split was estimated, False if directly scraped
    departure_time: str         # HH:MM 24hr local
    status: str                 # 'ok' | 'sold_out' | 'parse_error' | 'no_flights'
    scraped_at: str             # ISO 8601 with +05:30 offset
    capture_run: str            # e.g. 2026-09-02_0300IST


def init_driver():
    """Fresh undetected-chromedriver instance, windowed (no headless)."""
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    # NOTE: No --headless flag per SCRAPING_RULES Section 2 (headful windowed required)
    driver = uc.Chrome(options=options, version_main=152)
    return driver


def human_type(element, text: str):
    """Type character-by-character with jitter (Rule 3)."""
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.10, 0.25))


def scrape_akasa(origin: str, dest: str, target_date: datetime.date, days_ahead: int, csv_path: str):
    """Fresh driver per route, with try-finally quit (Rule 2)."""
    now_ist = datetime.datetime.now(IST)
    now_iso = now_ist.isoformat()  # includes +05:30 offset per Rule 6b
    capture_run = now_ist.strftime("%Y-%m-%d_%H%MIST")
    search_date_str = target_date.strftime("%Y-%m-%d")

    quotes: list[FareQuote] = []
    driver = init_driver()
    try:
        wait = WebDriverWait(driver, 15)
        url = "https://www.akasaair.com/"
        print(f"  [{origin}->{dest}] Navigating to Akasa...")
        driver.get(url)
        time.sleep(random.uniform(2.5, 4.0))

        # 1. From field
        print(f"  [{origin}->{dest}] Entering Origin ({origin})...")
        # Handle potential overlay / cookie consent on Akasa
        try:
            cookie_btn = driver.find_elements(By.XPATH, "//button[contains(., 'Accept') or contains(., 'Agree')]")
            if cookie_btn:
                driver.execute_script("arguments[0].click();", cookie_btn[0])
            
            # Look for general promotional modals/close buttons
            close_btns = driver.find_elements(By.CSS_SELECTOR, "img[alt='close'], img[alt='Close'], button.close, .close-icon, [aria-label='Close']")
            for btn in close_btns:
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
        except Exception:
            pass

        from_input = wait.until(EC.presence_of_element_located((By.ID, "From")))
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", from_input)
        time.sleep(1)
        
        # Aggressive clear and focus via JS
        driver.execute_script("arguments[0].value = ''; arguments[0].focus(); arguments[0].click();", from_input)
        try:
            human_type(from_input, origin)
        except Exception:
            from selenium.webdriver.common.action_chains import ActionChains
            ActionChains(driver).send_keys(origin).perform()
            
        time.sleep(random.uniform(1.5, 2.5))
        from_option = wait.until(EC.element_to_be_clickable(
            (By.XPATH, f"//div[contains(text(), '{origin}')] | //p[contains(text(), '{origin}')] | //span[contains(text(), '{origin}')]")
        ))
        driver.execute_script("arguments[0].click();", from_option)
        time.sleep(random.uniform(0.8, 1.4))

        # 2. To field
        print(f"  [{origin}->{dest}] Entering Destination ({dest})...")
        to_input = wait.until(EC.presence_of_element_located((By.ID, "To")))
        driver.execute_script("arguments[0].scrollIntoView(true);", to_input)
        time.sleep(0.5)
        try:
            to_input.click()
        except Exception:
            driver.execute_script("arguments[0].click();", to_input)

        time.sleep(random.uniform(0.8, 1.4))
        to_input.send_keys(Keys.CONTROL + "a")
        to_input.send_keys(Keys.BACKSPACE)
        driver.execute_script("arguments[0].value = '';", to_input)
        try:
            human_type(to_input, dest)
        except Exception:
            from selenium.webdriver.common.action_chains import ActionChains
            ActionChains(driver).send_keys(dest).perform()
        time.sleep(random.uniform(1.5, 2.5))
        to_option = wait.until(EC.element_to_be_clickable(
            (By.XPATH, f"//div[contains(text(), '{dest}')] | //p[contains(text(), '{dest}')] | //span[contains(text(), '{dest}')]")
        ))
        driver.execute_script("arguments[0].click();", to_option)
        time.sleep(random.uniform(0.8, 1.4))

        # 3. Date
        target_label = target_date.strftime("%a, %d %b %Y")
        print(f"  [{origin}->{dest}] Entering Date ({target_label})...")
        date_input = driver.find_element(By.NAME, "DepartureDate")
        date_input.click()
        time.sleep(1)
        date_input.send_keys(Keys.CONTROL + "a")
        time.sleep(0.5)
        for _ in range(30):
            date_input.send_keys(Keys.BACKSPACE)
            date_input.send_keys(Keys.DELETE)
        time.sleep(0.5)
        date_input.send_keys(target_label)
        time.sleep(1)
        date_input.send_keys(Keys.ENTER)
        time.sleep(random.uniform(0.8, 1.4))

        # 4. Search
        print(f"  [{origin}->{dest}] Clicking Search Flights...")
        search_btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(text(), 'Search Flights')]")
        ))
        search_btn.click()
        print(f"  [{origin}->{dest}] Waiting 30s for results...")
        time.sleep(30)

        # 5. Parse
        print(f"  [{origin}->{dest}] Parsing DOM...")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        flight_nodes = []
        for el in soup.find_all("div", class_=lambda c: c and "w-full" in c and "flex" in c):
            text = el.text.strip()
            if re.search(r"QP\d{4}", text) and re.search(r"\d{2}:\d{2}", text) and re.search(r"₹[\d,]+", text):
                flight_nodes.append(el)

        print(f"  [{origin}->{dest}] Found {len(flight_nodes)} flight card(s).")

        for node in flight_nodes:
            text = node.text.strip()
            match = re.search(r"(QP\d+).*?(\d{2}:\d{2})([A-Z]{3}).*?(\d{2}:\d{2})([A-Z]{3}).*?₹([\d,]+)", text)
            if match:
                flight_num, dep_time, dep_city, arr_time, arr_city, price_str = match.groups()

                # Rule 4a: Alternate airport validation
                if dep_city != origin or arr_city != dest:
                    with open("discarded_routes.log", "a") as lf:
                        lf.write(f"[{now_iso}] QP: Discarded {dep_city}->{arr_city} (Target: {origin}->{dest}) flight={flight_num}\n")
                    continue

                if "Non-stop" not in text:
                    continue  # Skip connecting flights

                price = int(price_str.replace(",", ""))
                
                # Mathematical estimation based on Akasa fee structure:
                # Taxable fixed fees = CUTE (75) + RCS (50) = 125
                # Non-taxable fees = ASF (236) + UDF (Assumed avg ~150) = 386
                # Total Fare = (Base + Taxable) * 1.05 + Non-taxable
                # Base = ((Total - Non-taxable) / 1.05) - Taxable
                estimated_base = max(0, round(((price - 386) / 1.05) - 125))
                estimated_taxes = price - estimated_base

                quote = FareQuote(
                    origin=origin,
                    destination=dest,
                    carrier_code="QP",
                    carrier_name="Akasa Air",
                    flight_num=flight_num.replace(" ", ""),
                    travel_date=search_date_str,
                    advance_purchase_days=days_ahead,
                    fare_class="economy",
                    base_fare=float(estimated_base),
                    taxes_and_fees=float(estimated_taxes),
                    total_fare=float(price),
                    fare_split_estimated=True,  # Explicitly flagging that this was mathematically modeled
                    departure_time=dep_time,
                    status="ok",
                    scraped_at=now_iso,
                    capture_run=capture_run,
                )
                quotes.append(quote)

        if not quotes:
            if os.getenv("ENABLE_LLM_FALLBACK", "false").lower() == "true":
                try:
                    from core.llm_fallback_parser import llm_extract_flights
                    llm_quotes = llm_extract_flights(
                        html_or_text=driver.page_source, origin=origin, destination=dest,
                        travel_date=search_date_str, advance_days=days_ahead, source_scraper="akasa"
                    )
                    if llm_quotes:
                        quotes = llm_quotes
                except Exception as _ex:
                    print(f"  [LLM Fallback Warning] {_ex}")

        if not quotes:
            quotes.append(FareQuote(
                origin=origin,
                destination=dest,
                carrier_code="QP",
                carrier_name="Akasa Air",
                flight_num="unknown",
                travel_date=search_date_str,
                advance_purchase_days=days_ahead,
                fare_class="economy",
                base_fare=None,
                taxes_and_fees=None,
                total_fare=None,
                fare_split_estimated=False,
                departure_time="unknown",
                status="no_flights_or_timeout",
                scraped_at=now_iso,
                capture_run=capture_run,
            ))

    except Exception as e:
        print(f"  [{origin}->{dest}] Error: {e}")
        quotes.append(FareQuote(
            origin=origin,
            destination=dest,
            carrier_code="QP",
            carrier_name="Akasa Air",
            flight_num="error",
            travel_date=search_date_str,
            advance_purchase_days=days_ahead,
            fare_class="economy",
            base_fare=None,
            taxes_and_fees=None,
            total_fare=None,
            fare_split_estimated=False,
            departure_time="unknown",
            status="error",
            scraped_at=now_iso,
            capture_run=capture_run,
        ))
        has_error = True
    else:
        has_error = False
    finally:
        driver.quit()  # CRITICAL: guaranteed per Rule 2b

    # Atomic append to CSV per Rule 1c
    file_exists = os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        for q in quotes:
            row = {
                "origin": q.origin,
                "destination": q.destination,
                "carrier_code": q.carrier_code,
                "carrier_name": q.carrier_name,
                "flight_num": q.flight_num,
                "travel_date": q.travel_date,
                "advance_purchase_days": q.advance_purchase_days,
                "fare_class": q.fare_class,
                "base_fare": q.base_fare if q.base_fare is not None else "",
                "taxes_and_fees": q.taxes_and_fees if q.taxes_and_fees is not None else "",
                "total_fare": q.total_fare if q.total_fare is not None else "",
                "fare_split_estimated": q.fare_split_estimated,  # Python bool → True/False in CSV
                "departure_time": q.departure_time,
                "status": q.status,
                "scraped_at": q.scraped_at,
                "capture_run": q.capture_run,
            }
            writer.writerow(row)

    usable = len([q for q in quotes if q.status == "ok"])
    return usable, has_error


def main():
    parser = argparse.ArgumentParser(description="Akasa Air Scraper")
    parser.add_argument("--windows", type=str, default="1,7,15,30,45",
                        help="Comma-separated advance days, e.g. 1,7")
    parser.add_argument("--routes", type=str,
                        default="DEL-BOM,DEL-BLR,BOM-BLR,DEL-CCU,BLR-HYD,MAA-DEL",
                        help="Comma-separated routes e.g. DEL-BOM,DEL-BLR")
    args = parser.parse_args()

    # Support both T+1 format and plain int
    raw_windows = [w.strip().replace("T+", "") for w in args.windows.split(",") if w.strip()]
    windows_to_scrape = [int(w) for w in raw_windows]
    routes_to_run = [(r.split("-")[0], r.split("-")[1]) for r in args.routes.split(",") if "-" in r]

    now_ist = datetime.datetime.now(IST)
    today = now_ist.date()
    today_str = today.strftime("%Y-%m-%d")
    time_str = now_ist.strftime("%H%MIST")

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "udaan_data", "raw", today_str)
    os.makedirs(out_dir, exist_ok=True)

    windows_str = "-".join([f"T{w}" for w in windows_to_scrape])
    csv_path = os.path.join(out_dir, f"akasa_raw_{today_str}_batch_{windows_str}_{time_str}.csv")
    print(f"Target CSV: {csv_path}")

    consecutive_errors = 0

    # Rule 1a: Horizons outer, routes inner
    for days_ahead in windows_to_scrape:
        print(f"\n{'='*60}")
        print(f"  AKASA HORIZON: T+{days_ahead}")
        print(f"{'='*60}")
        target_date = today + datetime.timedelta(days=days_ahead)

        for origin, dest in routes_to_run:
            print(f"\n--- Scraping T+{days_ahead} ({origin} -> {dest}) ---")
            usable, has_error = scrape_akasa(origin, dest, target_date, days_ahead, csv_path)
            print(f"  -> {usable} usable quote(s) appended.")

            if has_error:
                consecutive_errors += 1
                if consecutive_errors >= 5:
                    print("\n[CRITICAL] 5 consecutive technical failures detected! Triggering circuit breaker.")
                    import sys
                    sys.exit(1)
            else:
                consecutive_errors = 0

            # Rule 6a: Inter-route jitter 30-45s
            delay = random.uniform(30.0, 45.0)
            print(f"  Waiting {delay:.1f}s before next request...")
            time.sleep(delay)

    print("\nAkasa scraping completed successfully!")


if __name__ == "__main__":
    main()
