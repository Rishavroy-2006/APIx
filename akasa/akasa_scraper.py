import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
import time
import os
import datetime
import argparse
import csv
import re

ROUTES = ["DEL-BOM", "BOM-BLR", "BLR-DEL", "DEL-BLR", "DEL-CCU", "CCU-DEL"]

def init_driver():
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    options.add_argument('--headless')
    driver = uc.Chrome(options=options)
    return driver

def scrape_akasa(driver, origin, dest, target_date, days_ahead, writer):
    wait = WebDriverWait(driver, 15)
    url = "https://www.akasaair.com/"
    print(f"Navigating to {url} for {origin}-{dest} (T+{days_ahead})")
    
    try:
        driver.get(url)
        time.sleep(3)
        
        # 1. Click From
        print(f"Selecting {origin}...")
        from_input = wait.until(EC.element_to_be_clickable((By.ID, "From")))
        from_input.click()
        time.sleep(2)
        from_input.send_keys(Keys.COMMAND + "a")
        from_input.send_keys(Keys.BACKSPACE)
        from_input.send_keys(origin)
        time.sleep(3)
        from_option = wait.until(EC.element_to_be_clickable((By.XPATH, f"//div[contains(text(), '{origin}')] | //p[contains(text(), '{origin}')] | //span[contains(text(), '{origin}')]")))
        from_option.click()
        time.sleep(2)
        
        # 2. Click To
        print(f"Selecting {dest}...")
        to_input = wait.until(EC.element_to_be_clickable((By.ID, "To")))
        to_input.click()
        time.sleep(2)
        to_input.send_keys(Keys.COMMAND + "a")
        to_input.send_keys(Keys.BACKSPACE)
        to_input.send_keys(dest)
        time.sleep(3)
        to_option = wait.until(EC.element_to_be_clickable((By.XPATH, f"//div[contains(text(), '{dest}')] | //p[contains(text(), '{dest}')] | //span[contains(text(), '{dest}')]")))
        to_option.click()
        time.sleep(2)
        
        # 3. Handle Date via Formatting and Typing
        target_label = target_date.strftime("%a, %d %b %Y")
        print(f"Typing date: {target_label}...")
        
        date_input = driver.find_element(By.NAME, "DepartureDate")
        date_input.click()
        time.sleep(1)
        
        date_input.send_keys(Keys.COMMAND + "a")
        time.sleep(0.5)
        date_input.send_keys(Keys.BACKSPACE)
        for _ in range(30):
            date_input.send_keys(Keys.BACKSPACE)
            date_input.send_keys(Keys.DELETE)
        time.sleep(1)
        
        date_input.send_keys(target_label)
        time.sleep(1)
        date_input.send_keys(Keys.ENTER)
        time.sleep(1)
        
        # 4. Click Search Flights
        print("Waiting for Search Flights to be enabled...")
        search_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Search Flights')]")))
        search_btn.click()
        
        print("Waiting 30s for flight results to load...")
        time.sleep(30)
        
        # 5. Parse Results
        print("Parsing DOM...")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        flight_nodes = []
        for el in soup.find_all("div", class_=lambda c: c and "w-full" in c and "flex" in c):
            text = el.text.strip()
            if re.search(r"QP\d{4}", text) and re.search(r"\d{2}:\d{2}", text) and re.search(r"₹[\d,]+", text):
                flight_nodes.append(el)
        
        print(f"Found {len(flight_nodes)} flight cards")
        
        for node in flight_nodes:
            text = node.text.strip()
            match = re.search(r"(QP\d+).*?(\d{2}:\d{2})([A-Z]{3}).*?(\d{2}:\d{2})([A-Z]{3}).*?₹([\d,]+)", text)
            if match:
                flight_num, dep_time, dep_city, arr_time, arr_city, price_str = match.groups()
                price = int(price_str.replace(",", ""))
                
                # Check if it's Non-stop
                if "Non-stop" not in text:
                    continue # Skip connecting flights
                
                now_ist = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
                scraped_at = now_ist.strftime("%Y-%m-%dT%H:%M:%S")
                search_date_str = target_date.strftime("%Y-%m-%d")
                
                writer.writerow({
                    "origin": origin,
                    "destination": dest,
                    "carrier_code": "QP",
                    "carrier_name": "Akasa Air",
                    "flight_num": flight_num.replace(" ", ""),
                    "travel_date": search_date_str,
                    "advance_purchase_days": days_ahead,
                    "fare_class": "economy",
                    "base_fare": "",
                    "taxes_and_fees": "",
                    "total_fare": price,
                    "fare_split_estimated": "false",
                    "departure_time": dep_time,
                    "status": "ok",
                    "scraped_at": scraped_at,
                    "capture_run": f"{now_ist.strftime('%Y-%m-%d_%H%MIST')}"
                })
        print("Saved flights for route.")

    except Exception as e:
        print(f"Error scraping {origin}-{dest}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Scrape Akasa Air prices.")
    parser.add_argument("--windows", type=str, default="T+1,T+7,T+15,T+30,T+45", help="Comma-separated list of windows, e.g., T+1,T+7")
    parser.add_argument("--routes", type=str, default="DEL-BOM,BOM-BLR,BLR-DEL,DEL-BLR,DEL-CCU,CCU-DEL", help="Comma-separated list of routes")
    args = parser.parse_args()
    
    windows = [w.strip() for w in args.windows.split(",") if w.strip()]
    routes_to_run = [r.strip() for r in args.routes.split(",") if r.strip()]
    
    now_ist = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
    today = now_ist.date()
    today_str = today.strftime("%Y-%m-%d")
    time_str = now_ist.strftime("%H%MIST")
    
    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "apix_data", "raw", today_str)
    os.makedirs(out_dir, exist_ok=True)
    
    windows_str = "-".join([f"T{w.replace('T+', '')}" for w in windows])
    out_file = os.path.join(out_dir, f"akasa_raw_{today_str}_batch_{windows_str}_{time_str}.csv")
    file_exists = os.path.exists(out_file)
    
    with open(out_file, "a", newline="", encoding="utf-8") as f:
        fieldnames = [
            "origin", "destination", "carrier_code", "carrier_name", "flight_num",
            "travel_date", "advance_purchase_days", "fare_class", "base_fare",
            "taxes_and_fees", "total_fare", "fare_split_estimated", "departure_time",
            "status", "scraped_at", "capture_run"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
            
        driver = init_driver()
        try:
            for window in windows:
                days_ahead = int(window.replace("T+", ""))
                target_date = today + datetime.timedelta(days=days_ahead)
                
                for route in routes_to_run:
                    try:
                        origin, dest = route.split("-")
                    except:
                        continue
                    
                    scrape_akasa(driver, origin, dest, target_date, days_ahead, writer)
                    f.flush()
                    print(f"Waiting before next request...")
                    time.sleep(5)
        finally:
            driver.quit()

if __name__ == "__main__":
    main()
