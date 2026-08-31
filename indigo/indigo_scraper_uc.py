import time
import csv
import random
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------

BASE_URL = "https://www.goindigo.in/"
ROUTES = [
    ("DEL", "BOM"),
    ("DEL", "BLR"),
    ("BOM", "BLR"),
    ("DEL", "CCU"),
    ("BLR", "HYD"),
    ("MAA", "DEL")
]
ADVANCE_PURCHASE_WINDOWS = [1, 7, 15, 30, 45]
REQUEST_DELAY_SECONDS = (4, 8)

SELECTORS = {
    "origin_input": ".search-widget-form-body__from .booking-widget-field input",
    "destination_input": ".search-widget-form-body__to .booking-widget-field input",
    "date_input": ".search-widget-form-body__departure .booking-widget-field input",
    "search_button": ".search-widget-form-bottom .search-btn button",
    "fare_card": "div.srp__search-result-list__item[data-journey-key]",
    "fare_card_price": "div.selected-fare__fare-price",
    "fare_card_fareclass": "span.fare-category-chip",
    "fare_card_departure_time": "div.details-wrapper__flight-departure > div.time",
    "sold_out_marker": ".sold-out, .unavailable",
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


def scrape_one_window(driver, origin_code: str, dest_code: str, advance_days: int) -> list[FareQuote]:
    """Scrapes a single advance purchase window for the given route."""
    travel_date = (datetime.now() + timedelta(days=advance_days)).strftime("%Y-%m-%d")
    display_date = (datetime.now() + timedelta(days=advance_days)).strftime("%d %b %Y")
    quotes = []
    
    # Python 3.12+ safe UTC time
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    now_iso = now.isoformat()
    capture_run = now.strftime("%Y-%m-%d_%H%MIST") # using IST as a convention for run tag

    try:
        driver.get(BASE_URL)
        
        wait = WebDriverWait(driver, 20)
        
        from selenium.webdriver.common.action_chains import ActionChains

        # Origin
        origin_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SELECTORS["origin_input"])))
        driver.execute_script("arguments[0].click();", origin_input)
        time.sleep(1)
        ActionChains(driver).send_keys(origin_code).perform()
        time.sleep(1.5)
        try:
            opt = wait.until(EC.presence_of_element_located((By.XPATH, f"//*[text()='{origin_code}']")))
            driver.execute_script("arguments[0].click();", opt)
        except Exception as e:
            print("Could not click origin dropdown:", e)
        time.sleep(1)
        
        # Destination
        dest_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SELECTORS["destination_input"])))
        driver.execute_script("arguments[0].click();", dest_input)
        time.sleep(1)
        ActionChains(driver).send_keys(dest_code).perform()
        time.sleep(1.5)
        try:
            opt = wait.until(EC.presence_of_element_located((By.XPATH, f"//*[text()='{dest_code}']")))
            driver.execute_script("arguments[0].click();", opt)
        except Exception as e:
            print("Could not click dest dropdown:", e)
        time.sleep(1)

        # Date
        date_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SELECTORS["date_input"])))
        driver.execute_script("arguments[0].click();", date_input)
        time.sleep(1)
        
        target_date_selector = f"div[data-date='{travel_date}']"
        for _ in range(6): # Try up to 6 months
            elements = driver.find_elements(By.CSS_SELECTOR, target_date_selector)
            if elements:
                # Use React-compatible event dispatch (JS .click() doesn't trigger React)
                driver.execute_script("""
                    var el = arguments[0];
                    ['mousedown', 'mouseup', 'click'].forEach(function(evtName) {
                        el.dispatchEvent(new MouseEvent(evtName, {bubbles:true, cancelable:true, view:window}));
                    });
                """, elements[0])
                break
            else:
                next_btn = driver.find_element(By.CSS_SELECTOR, "button.rdrNextButton")
                driver.execute_script("arguments[0].click();", next_btn)
                time.sleep(0.5)
        
        time.sleep(1)

        # Search
        search_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTORS["search_button"])))
        search_btn.click()

        # Wait for results
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, SELECTORS["fare_card"])))
        except:
            print(f"Timeout waiting for results on T+{advance_days}")
            quotes.append(FareQuote(
                origin_code, dest_code, "6E", "IndiGo", "unknown", travel_date, advance_days,
                "unknown", None, None, None, False, "unknown", "no_flights_or_timeout", now_iso, capture_run
            ))
            return quotes

        time.sleep(2) # Give it a second to render
        cards = driver.find_elements(By.CSS_SELECTOR, SELECTORS["fare_card"])
        
        for card in cards:
            # Check for sold out
            import re
            try:
                card_text = card.text
                card_html = card.get_attribute("outerHTML").lower()
                
                act_origin = origin_code
                act_dest = dest_code
                dep_time = ""
                
                # 1. Extract Details
                dep_wrappers = card.find_elements(By.CSS_SELECTOR, "div.details-wrapper__flight-departure")
                arr_wrappers = card.find_elements(By.CSS_SELECTOR, "div.details-wrapper__flight-arrival")
                
                if dep_wrappers:
                    dep_text = dep_wrappers[0].text
                    times = re.findall(r'\b\d{2}:\d{2}\b', dep_text)
                    if times: dep_time = times[0]
                    iatas = re.findall(r'\b[A-Z]{3}\b', dep_text)
                    if iatas: act_origin = iatas[0]
                
                if arr_wrappers:
                    arr_text = arr_wrappers[0].text
                    iatas = re.findall(r'\b[A-Z]{3}\b', arr_text)
                    if iatas: act_dest = iatas[0]
                
                # 2. Check if this is an alternate airport route (drop it)
                if act_origin != origin_code or act_dest != dest_code:
                    with open("discarded_routes.log", "a") as lf:
                        lf.write(f"[{now_iso}] Discarded {act_origin}->{act_dest} (Target: {origin_code}->{dest_code})\n")
                    continue
                
                # Fallback for time if missing
                if not dep_time:
                    times = re.findall(r'\b\d{2}:\d{2}\b', card_text)
                    if times: dep_time = times[0]
                    
                # Extract Flight Number
                flight_num = "IndiGo"
                fn_matches = re.findall(r'6E\s*[-]?\s*\d{2,4}', card_text)
                if fn_matches:
                    flight_num = fn_matches[0]
                
                carrier_code = flight_num[:2] if len(flight_num) >= 2 else "6E"
                carrier_name = "IndiGo"
                    
                # 2. Check Sold Out
                sold_out_els = card.find_elements(By.CSS_SELECTOR, SELECTORS["sold_out_marker"])
                if sold_out_els or "sold out" in card_html or "unavailable" in card_html:
                    quotes.append(FareQuote(
                        origin=act_origin, destination=act_dest,
                        carrier_code=carrier_code, carrier_name=carrier_name,
                        flight_num=flight_num, travel_date=travel_date, advance_purchase_days=advance_days,
                        fare_class="", base_fare=None, taxes_and_fees=None, total_fare=None, fare_split_estimated=False,
                        departure_time=dep_time, status="sold_out", scraped_at=now_iso, capture_run=capture_run
                    ))
                    continue

                # 3. Extract Fares
                chips = card.find_elements(By.CSS_SELECTOR, SELECTORS["fare_card_fareclass"])
                fares_found = False
                for chip in chips:
                    fc_text = chip.text.strip().lower()
                    price_val = None
                    
                    # Climb up to 5 levels of divs to find the isolated container with exactly 1 price
                    for i in range(1, 6):
                        try:
                            parent = chip.find_element(By.XPATH, f"./ancestor::div[{i}]")
                            prices = parent.find_elements(By.CSS_SELECTOR, SELECTORS["fare_card_price"])
                            if len(prices) == 1:
                                p_text = prices[0].text.strip()
                                num_str = "".join(ch for ch in p_text if ch.isdigit() or ch == ".")
                                if num_str:
                                    price_val = float(num_str)
                                    break
                        except:
                            continue
                    
                    if price_val:
                        fares_found = True
                        fare_class = "economy"
                        if "business" in fc_text or "stretch" in fc_text:
                            fare_class = "business"
                        
                        quotes.append(FareQuote(
                            origin=act_origin, destination=act_dest,
                            carrier_code=carrier_code, carrier_name=carrier_name,
                            flight_num=flight_num, travel_date=travel_date, advance_purchase_days=advance_days,
                            fare_class=fare_class, base_fare=None, taxes_and_fees=None, total_fare=price_val, fare_split_estimated=False,
                            departure_time=dep_time, status="ok", scraped_at=now_iso, capture_run=capture_run
                        ))
                
                if not fares_found:
                    quotes.append(FareQuote(
                        origin=act_origin, destination=act_dest,
                        carrier_code=carrier_code, carrier_name=carrier_name,
                        flight_num=flight_num, travel_date=travel_date, advance_purchase_days=advance_days,
                        fare_class="", base_fare=None, taxes_and_fees=None, total_fare=None, fare_split_estimated=False,
                        departure_time=dep_time, status="parse_error", scraped_at=now_iso, capture_run=capture_run
                    ))
            except Exception as e:
                print("[parse_error] card parse failed:", e)
                quotes.append(FareQuote(
                    origin=origin_code, destination=dest_code,
                    carrier_code="6E", carrier_name="IndiGo",
                    flight_num="unknown", travel_date=travel_date,
                    advance_purchase_days=advance_days,
                    fare_class="unknown", base_fare=None, taxes_and_fees=None,
                    total_fare=None, fare_split_estimated=False,
                    departure_time="unknown", status="scrape_error",
                    scraped_at=now_iso, capture_run=capture_run
                ))

    except Exception as e:
        print(f"[ERROR] T+{advance_days}:", e)

    return quotes

def append_csv(quotes: list[FareQuote], path: str):
    if not quotes:
        return
    import os
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
    
    now = dt.datetime.now(dt.timezone.utc)
    today_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H%MIST")
    
    windows_to_scrape = target_windows if target_windows else ADVANCE_PURCHASE_WINDOWS
    windows_str = "-".join([f"T{w}" for w in windows_to_scrape])
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "apix_data", "raw", today_str)
    os.makedirs(data_dir, exist_ok=True)
    
    csv_filename = f"indigo_raw_{today_str}_batch_{windows_str}_{time_str}.csv"
    csv_path = os.path.join(data_dir, csv_filename)
    
    for advance_days in windows_to_scrape:
        print(f"\n{'='*60}")
        print(f"  HORIZON: T+{advance_days}")
        print(f"{'='*60}")
        
        for idx, (origin, dest) in enumerate(ROUTES):
            print(f"\n--- Scraping T+{advance_days} ({origin} -> {dest}) ---")
            
            print("Starting fresh undetected-chromedriver session...")
            options = uc.ChromeOptions()
            options.add_argument(f'--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{random.randint(110, 120)}.0.0.0 Safari/537.36')
            driver = uc.Chrome(options=options, version_main=151)
            
            try:
                quotes = scrape_one_window(driver, origin, dest, advance_days)
                usable = sum(1 for q in quotes if q.status == 'ok')
                print(f"  -> {len(quotes)} quote(s) captured ({usable} usable)")
                
                append_csv(quotes, csv_path)
                print(f"  -> Appended to {csv_path}")
                
            finally:
                driver.quit()
                
            delay = random.uniform(30, 45)  
            print(f"  Waiting {delay:.1f}s before next request...")
            time.sleep(delay)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="IndiGo Scraper")
    parser.add_argument("--windows", type=str, help="Comma separated list of horizons, e.g. 1,7")
    args = parser.parse_args()
    
    if args.windows:
        target_windows = [int(w.strip()) for w in args.windows.split(",")]
        run(target_windows=target_windows)
    else:
        run()
